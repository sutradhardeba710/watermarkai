# AWS EC2 Deployment Guide

This guide deploys the project as follows:

```text
Vercel frontend -> Backend EC2 -> PostgreSQL EC2
                         |       -> ElastiCache Redis
                         |       -> S3
                         +-- Worker EC2
```

Use Ubuntu 24.04 LTS and the same AWS Region for every resource. Start with staging.

## 1. Create AWS resources

Create these resources in AWS Console:

1. Private S3 bucket, for example `vwa-media-UNIQUE-NAME`.
2. VPC with public and private subnets.
3. Backend EC2: `t3.small` or `t3.medium`, Ubuntu 24.04.
4. Worker EC2: `t3.medium` minimum, Ubuntu 24.04.
5. PostgreSQL EC2: `t3.small`, encrypted EBS volume.
6. ElastiCache Redis in the same VPC.
7. IAM role for EC2 with limited access to the S3 bucket.
8. CloudWatch log groups and alarms.
9. Vercel project using the `frontend` directory.

Do not expose PostgreSQL or Redis publicly.

## 2. Security groups

Create these security groups:

### `vwa-backend-sg`

Inbound:

- TCP 22 from your IP only.
- TCP 8000 from your IP temporarily, then from the ALB only.

### `vwa-worker-sg`

Inbound:

- TCP 22 from your IP only.

### `vwa-postgres-sg`

Inbound:

- TCP 5432 from `vwa-backend-sg`.
- TCP 5432 from `vwa-worker-sg`.
- TCP 22 from your IP temporarily.

### `vwa-redis-sg`

Inbound:

- TCP 6379 from `vwa-backend-sg`.
- TCP 6379 from `vwa-worker-sg`.

Never allow ports 5432 or 6379 from `0.0.0.0/0`.

## 3. S3 and IAM

Create the bucket with:

- Block all public access enabled.
- Versioning enabled.
- Default encryption enabled.
- Object ownership set to bucket owner enforced.

Create an IAM role named `vwa-ec2-s3-role` and attach a policy limited to your bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
    "Resource": [
      "arn:aws:s3:::vwa-media-UNIQUE-NAME",
      "arn:aws:s3:::vwa-media-UNIQUE-NAME/*"
    ]
  }]
}
```

Attach this role to backend and worker EC2. Do not put AWS keys in `.env`.

## 4. PostgreSQL EC2

SSH into the PostgreSQL instance:

```bash
ssh -i /path/to/vwa-key.pem ubuntu@POSTGRES_PUBLIC_IP
sudo apt update && sudo apt upgrade -y
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

Create the database:

```bash
sudo -u postgres psql
```

```sql
CREATE USER vwa_admin WITH ENCRYPTED PASSWORD 'STRONG_PRIVATE_PASSWORD';
CREATE DATABASE vwa OWNER vwa_admin;
\q
```

Edit PostgreSQL configuration:

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
```

Set:

```text
listen_addresses = '*'
```

Edit `pg_hba.conf` to permit only your VPC/backend/worker security groups or private CIDR, then:

```bash
sudo systemctl restart postgresql
```

Create regular `pg_dump` backups and upload them to S3. Test restoring one backup before launch.

## 5. ElastiCache Redis

Create Redis OSS in the same VPC and attach `vwa-redis-sg`.

Record the primary endpoint. It will be used as:

```text
rediss://REDIS_ENDPOINT:6379/0
```

Use database `/1` for Celery broker and `/2` for Celery result backend.

## 6. Backend EC2

SSH and install dependencies:

```bash
ssh -i /path/to/vwa-key.pem ubuntu@BACKEND_PUBLIC_IP
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3.11 python3.11-venv python3-pip ffmpeg nginx curl
cd /opt
sudo git clone https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git video-watermark-ai
sudo chown -R ubuntu:ubuntu /opt/video-watermark-ai
cd /opt/video-watermark-ai/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Create `/opt/video-watermark-ai/backend/.env`:

```dotenv
VWA_ENVIRONMENT=prod
VWA_SECRET_KEY=RANDOM_LONG_SECRET
VWA_DATABASE_URL=postgresql+psycopg://vwa_admin:DB_PASSWORD@POSTGRES_PRIVATE_IP:5432/vwa
VWA_REDIS_URL=rediss://REDIS_ENDPOINT:6379/0
VWA_CELERY_BROKER_URL=rediss://REDIS_ENDPOINT:6379/1
VWA_CELERY_RESULT_BACKEND=rediss://REDIS_ENDPOINT:6379/2
VWA_STORAGE_BACKEND=minio
VWA_MINIO_ENDPOINT=s3.amazonaws.com
VWA_MINIO_SECURE=true
VWA_MINIO_BUCKET_PREFIX=vwa-media-UNIQUE-NAME
VWA_CORS_ORIGINS=["https://YOUR_VERCEL_DOMAIN"]
VWA_APP_BASE_URL=https://YOUR_VERCEL_DOMAIN
VWA_SMTP_CONSOLE=false
VWA_FFMPEG_BIN=ffmpeg
VWA_FFPROBE_BIN=ffprobe
```

Verify the repository's S3/MinIO adapter with a test upload before production. The project currently uses a pluggable storage interface.

Run migrations:

```bash
cd /opt/video-watermark-ai
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Test from your computer:

```bash
curl http://BACKEND_PUBLIC_IP:8000/health
```

## 7. Backend systemd service

Create `/etc/systemd/system/vwa-backend.service`:

```ini
[Unit]
Description=VWA FastAPI backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/video-watermark-ai
EnvironmentFile=/opt/video-watermark-ai/backend/.env
ExecStart=/opt/video-watermark-ai/backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vwa-backend
sudo journalctl -u vwa-backend -f
```

## 8. Worker EC2

Install the worker:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3.11 python3.11-venv python3-pip ffmpeg libgl1 libglib2.0-0
cd /opt
sudo git clone https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git video-watermark-ai
sudo chown -R ubuntu:ubuntu /opt/video-watermark-ai
cd /opt/video-watermark-ai/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Copy the same `.env` file to the worker. Test:

```bash
cd /opt/video-watermark-ai
backend/.venv/bin/celery -A workers.celery_app worker -Q detection,processing,encoding --pool=solo -l info
```

Create `/etc/systemd/system/vwa-worker.service`:

```ini
[Unit]
Description=VWA Celery worker
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/video-watermark-ai
EnvironmentFile=/opt/video-watermark-ai/backend/.env
ExecStart=/opt/video-watermark-ai/backend/.venv/bin/celery -A workers.celery_app worker -Q detection,processing,encoding --pool=solo -l info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vwa-worker
sudo journalctl -u vwa-worker -f
```

## 9. Vercel frontend

1. Import the Git repository into Vercel.
2. Set Root Directory to `frontend`.
3. Build command: `npm run build`.
4. Install command: `npm ci`.
5. Set the frontend API environment variable used in `frontend/services/api.ts` to the backend URL.

For temporary testing:

```text
http://BACKEND_PUBLIC_IP:8000
```

After HTTPS is configured, use:

```text
https://api.example.com
```

## 10. HTTPS, Route 53, and ALB

After the direct backend test succeeds:

1. Create an ACM certificate for `api.example.com`.
2. Validate it through Route 53.
3. Create an internet-facing Application Load Balancer.
4. Create a target group for backend EC2 port 8000.
5. Health check path: `/health`.
6. Add HTTPS listener on port 443.
7. Redirect port 80 to 443.
8. Create a Route 53 alias record pointing `api.example.com` to the ALB.
9. Update Vercel and `VWA_CORS_ORIGINS` to use the HTTPS API URL.

## 11. Monitoring and backups

Configure CloudWatch for:

- Backend logs
- Worker logs
- PostgreSQL logs
- CPU and memory
- Root/data disk usage
- Instance status checks
- HTTP 5xx errors
- Worker service failures

Create alarms for disk above 80%, CPU above 85%, stopped services, and repeated API errors.

Back up PostgreSQL nightly with `pg_dump` and upload encrypted backups to S3. Test restoration regularly.

## 12. Verification checklist

- [ ] S3 is private and encrypted.
- [ ] PostgreSQL allows only backend/worker traffic.
- [ ] Redis is private.
- [ ] `/health` returns success.
- [ ] Frontend register/login works.
- [ ] Upload reaches S3.
- [ ] Detection job reaches Celery.
- [ ] Processing completes successfully.
- [ ] SSE progress updates work.
- [ ] Signed output download works.
- [ ] Users cannot access another user's project.
- [ ] PostgreSQL backup restores successfully.
- [ ] HTTPS works through the ALB.

Run the existing tests:

```bash
cd /opt/video-watermark-ai/backend
.venv/bin/python -m pytest tests --ignore=tests/test_security.py -q
VWA_INTEGRATION=1 .venv/bin/python -m pytest tests/test_integration_phase9.py -q
VWA_E2E=1 VWA_SAMPLE_CLIP=/path/to/sample.mp4 .venv/bin/python -m pytest tests/test_e2e_phase9.py -q
```

## 13. Launch blockers

Before commercial launch:

1. Replace the console email stub with a real provider.
2. Remove seeded demo/admin accounts.
3. Move secrets to AWS Systems Manager Parameter Store or Secrets Manager.
4. Confirm the AGPL licensing decision for Ultralytics/YOLO; see `LICENSE-NOTE.md`.
5. Add user quotas and abuse protection.
6. Test database recovery and S3 recovery.
7. Use HTTPS everywhere.

Never share passwords, private keys, JWT secrets, or AWS access keys in chat. When asking for deployment help, share only the step number and sanitized command/error output.

# AWS Deployment Plan (12-Step Architecture)

Target Architecture:
Vercel frontend -> EC2 backend API -> PostgreSQL EC2, ElastiCache Redis, EC2 Celery worker, S3 video storage.

## Verification of Current State

- **[DONE] Step 1 — Create AWS account access**
  - Account is ready.
  - Region: us-east-1 (assumed based on previous `.env` configuration, but needs exact confirmation).

- **[PENDING] Step 2 — Create S3 storage**
  - Needs creation of bucket: `vwa-production-media-<unique-name>`

- **[IN PROGRESS] Step 3 — Create networking**
  - [DONE] VPC and Subnets (`public-subnet-a`) created.
  - [DONE] Security groups for backend (`vwa-backend-sg`) and PostgreSQL created.
  - [PENDING] Worker security group.
  - [PENDING] ElastiCache Redis security group and network configuration.

- **[DONE] Step 4 — Create PostgreSQL EC2**
  - Instance is running (`vwa-postgres` / `prosgredsql`).
  - Private IP: `10.0.1.92`.

- **[DONE] Step 5 — Create backend EC2**
  - Instance is running (`vwa-backend`).
  - Private IP: `10.0.1.86`, Public IP: `44.198.56.145`.
  - SSH access is verified.

- **[PENDING] Step 6 — Create worker EC2**
  - EC2 instance for Celery/YOLO needs to be created.

- **[PENDING] Step 7 — Configure Redis**
  - ElastiCache Redis instance needs to be created.

- **[PENDING] Step 8 — Configure the project**
  - User will update project for production (S3, CORS, DB URLs, etc.).

- **[PENDING] Step 9 — Deploy backend and worker**
  - User will deploy, migrate, start API and Celery, then verify.

- **[PENDING] Step 10 — Deploy frontend to Vercel**
  - User will connect frontend repository to Vercel.

- **[PENDING] Step 11 — Add domain and HTTPS**
  - Route 53, ALB, ACM certificates to be configured after API works.

- **[PENDING] Step 12 — Add monitoring and backups**
  - CloudWatch, Alarms, DB backups, etc., to be configured.

## Next Action Required
We need to finalize the Step 1 response and proceed to Step 2 (S3 Storage Creation).

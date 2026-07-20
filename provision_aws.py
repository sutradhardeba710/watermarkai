"""
VWA — AWS EC2 Provisioner
=========================
Provisions a single Ubuntu 22.04 EC2 instance (t3.large) with:
  • Docker + Docker Compose installed via cloud-init UserData
  • Security group: SSH (22), HTTP (80), HTTPS (443) open to the world
  • ElastiCache Redis cluster (cache.t3.micro) — optional, see USE_ELASTICACHE
  • RDS PostgreSQL — NOT used by default (postgres runs in Docker on EC2)

Usage:
    pip install boto3
    aws configure                  # set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
    python provision_aws.py        # provision
    python provision_aws.py --dry-run   # print plan only

Requirements:
    • An EC2 key pair in us-east-1 (set KEY_PAIR_NAME below or pass --key-name)
    • boto3 installed in your Python env

After provisioning:
    1. SSH into the instance:
         ssh -i ~/.ssh/<KEY_PAIR_NAME>.pem ubuntu@<PUBLIC_IP>
    2. Tail the bootstrap log:
         tail -f /var/log/vwa-bootstrap.log
    3. Once bootstrap completes, visit http://<PUBLIC_IP>
"""
import argparse
import base64
import pathlib
import sys
import time
import urllib.request

import boto3

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
REGION = "us-east-1"

# Instance type — t3.large recommended (4 GB RAM for YOLO + uvicorn workers)
# For very tight budgets: t3.medium (4 GB) or t3.small (2 GB, no YOLO)
INSTANCE_TYPE = "t3.micro"  # matches existing vwa-backend instance type

# Set to True to use AWS ElastiCache for Redis instead of the Docker redis container.
# Adds ~$12/mo but gives managed Redis with persistence/failover.
USE_ELASTICACHE = False

# Root EBS volume size in GB (video files stored here inside Docker volume)
ROOT_VOLUME_GB = 50

# ── FILL IN BEFORE RUNNING ────────────────────────────────────────────────────
# Your EC2 key pair name in us-east-1 (create in AWS Console → EC2 → Key Pairs)
DEFAULT_KEY_PAIR = "watermark-ai"  # existing key pair in account

# Your GitHub repo (used in bootstrap UserData to git clone the project)
GITHUB_REPO = "https://github.com/REPLACE_ME_GITHUB_USER/REPLACE_ME_REPO_NAME.git"
# ─────────────────────────────────────────────────────────────────────────────


def get_my_ip() -> str:
    return urllib.request.urlopen("http://checkip.amazonaws.com").read().decode().strip()


def get_ubuntu_ami(ssm_client) -> str:
    """Resolve latest Ubuntu 22.04 LTS AMI via SSM Parameter Store."""
    param = ssm_client.get_parameter(
        Name="/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id"
    )
    return param["Parameter"]["Value"]


def get_or_create_sg(ec2_client, name: str, desc: str, vpc_id: str) -> str:
    sgs = ec2_client.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [name]}, {"Name": "vpc-id", "Values": [vpc_id]}]
    )["SecurityGroups"]
    if sgs:
        print(f"  SG '{name}' already exists: {sgs[0]['GroupId']}")
        return sgs[0]["GroupId"]
    print(f"  Creating SG '{name}'…")
    resp = ec2_client.create_security_group(GroupName=name, Description=desc, VpcId=vpc_id)
    return resp["GroupId"]


def authorize_ingress(ec2_client, group_id: str, permissions: list) -> None:
    try:
        ec2_client.authorize_security_group_ingress(GroupId=group_id, IpPermissions=permissions)
    except Exception as exc:
        if "InvalidPermission.Duplicate" not in str(exc):
            print(f"  ⚠  SG rule error ({group_id}): {exc}")


def build_userdata(public_host_placeholder: str = "REPLACE_AFTER_LAUNCH") -> str:
    """Read ec2-bootstrap.sh and wrap it as cloud-init UserData."""
    bootstrap_path = pathlib.Path(__file__).parent / "scripts" / "ec2-bootstrap.sh"
    if not bootstrap_path.exists():
        raise FileNotFoundError(f"scripts/ec2-bootstrap.sh not found at {bootstrap_path}")
    script = bootstrap_path.read_text()
    # Patch the repo URL into the bootstrap script
    script = script.replace(
        "https://github.com/REPLACE_ME_GITHUB_USER/REPLACE_ME_REPO_NAME.git",
        GITHUB_REPO,
    )
    # public host will be patched after launch (we don't know the IP yet)
    # The instance can use EC2 metadata to discover its own IP at runtime
    script = script.replace(
        "REPLACE_ME_EC2_PUBLIC_IP_OR_DOMAIN",
        '$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)',
    )
    # Wrap with #!/bin/bash shebang if not already present
    if not script.startswith("#!"):
        script = "#!/bin/bash\n" + script
    return "#!/bin/bash\n" + script


def provision(key_name: str, dry_run: bool = False) -> None:
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║          VWA — AWS EC2 Provisioner                  ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    ec2_client = boto3.client("ec2", region_name=REGION)
    ec2_resource = boto3.resource("ec2", region_name=REGION)
    ssm_client = boto3.client("ssm", region_name=REGION)

    # ── My IP (for SSH whitelist) ─────────────────────────────────────────────
    my_ip = get_my_ip()
    print(f"Your public IP (for SSH allow): {my_ip}")

    # ── Default VPC + subnet ──────────────────────────────────────────────────
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        print("✗ No default VPC found. Create one in the AWS Console.")
        sys.exit(1)
    vpc_id = vpcs[0]["VpcId"]
    print(f"VPC: {vpc_id}")

    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    primary_subnet = subnets[0]["SubnetId"]
    subnet_ids = [s["SubnetId"] for s in subnets]
    print(f"Subnets: {subnet_ids}  (using {primary_subnet})")

    # ── AMI ───────────────────────────────────────────────────────────────────
    ami_id = get_ubuntu_ami(ssm_client)
    print(f"AMI: {ami_id}  (Ubuntu 22.04 LTS)")

    # ── Security group ────────────────────────────────────────────────────────
    print("\n→ Security groups…")
    app_sg = get_or_create_sg(ec2_client, "vwa-app-sg", "VWA App SG (SSH+HTTP+HTTPS)", vpc_id)

    open_world = [{"CidrIp": "0.0.0.0/0"}]
    ipv6_world = [{"CidrIpv6": "::/0"}]

    authorize_ingress(ec2_client, app_sg, [
        # SSH — restricted to your IP only
        {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
         "IpRanges": [{"CidrIp": f"{my_ip}/32", "Description": "SSH from provisioner"}]},
        # HTTP
        {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
         "IpRanges": open_world, "Ipv6Ranges": ipv6_world},
        # HTTPS
        {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
         "IpRanges": open_world, "Ipv6Ranges": ipv6_world},
        # HTTPS/UDP (HTTP/3 — Caddy)
        {"IpProtocol": "udp", "FromPort": 443, "ToPort": 443,
         "IpRanges": open_world, "Ipv6Ranges": ipv6_world},
    ])

    # ── ElastiCache Redis (optional) ──────────────────────────────────────────
    redis_endpoint = None
    if USE_ELASTICACHE and not dry_run:
        print("\n→ ElastiCache Redis…")
        ec_client = boto3.client("elasticache", region_name=REGION)
        redis_sg = get_or_create_sg(ec2_client, "vwa-redis-sg", "VWA Redis SG", vpc_id)
        authorize_ingress(ec2_client, redis_sg, [
            {"IpProtocol": "tcp", "FromPort": 6379, "ToPort": 6379,
             "UserIdGroupPairs": [{"GroupId": app_sg}]},
        ])
        subnet_group = "vwa-redis-subnet"
        try:
            ec_client.create_cache_subnet_group(
                CacheSubnetGroupName=subnet_group,
                CacheSubnetGroupDescription="VWA Redis",
                SubnetIds=subnet_ids,
            )
        except Exception as e:
            if "AlreadyExists" not in str(e):
                raise
        try:
            ec_client.create_cache_cluster(
                CacheClusterId="vwa-redis",
                Engine="redis",
                CacheNodeType="cache.t3.micro",
                NumCacheNodes=1,
                CacheSubnetGroupName=subnet_group,
                SecurityGroupIds=[redis_sg],
            )
        except Exception as e:
            if "AlreadyExists" not in str(e):
                raise
        print("  Waiting for Redis (this takes ~5 min)…")
        while True:
            info = ec_client.describe_cache_clusters(CacheClusterId="vwa-redis")["CacheClusters"][0]
            if info["CacheClusterStatus"] == "available":
                redis_endpoint = info["CacheNodes"][0]["Endpoint"]["Address"]
                break
            print(f"  Redis status: {info['CacheClusterStatus']} — waiting 20s…")
            time.sleep(20)
        print(f"  Redis endpoint: {redis_endpoint}:6379")

    # ── UserData cloud-init ───────────────────────────────────────────────────
    userdata = build_userdata()

    # ── EC2 instance ──────────────────────────────────────────────────────────
    print(f"\n→ Launching EC2 {INSTANCE_TYPE} (Ubuntu 22.04)…")
    block_devices = [
        {
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": ROOT_VOLUME_GB,
                "VolumeType": "gp3",
                "Encrypted": True,
                "DeleteOnTermination": True,
            },
        }
    ]

    launch_kwargs = dict(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        KeyName=key_name,
        SecurityGroupIds=[app_sg],
        SubnetId=primary_subnet,
        BlockDeviceMappings=block_devices,
        UserData=userdata,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "vwa-app"}],
            }
        ],
    )

    if dry_run:
        print("\n[DRY RUN] Would launch with:")
        for k, v in launch_kwargs.items():
            if k != "UserData":
                print(f"  {k}: {v}")
        print("  UserData: <ec2-bootstrap.sh>")
        return

    instances = ec2_resource.create_instances(**launch_kwargs)
    instance = instances[0]
    print(f"  Instance ID: {instance.id} — waiting until running…")
    instance.wait_until_running()
    instance.reload()

    public_ip = instance.public_ip_address
    private_ip = instance.private_ip_address

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("✓ Provisioning complete!")
    print("─" * 60)
    print(f"  Instance ID  : {instance.id}")
    print(f"  Public IP    : {public_ip}")
    print(f"  Private IP   : {private_ip}")
    print(f"  Instance type: {INSTANCE_TYPE}")
    if redis_endpoint:
        print(f"  Redis        : {redis_endpoint}:6379")
    print()
    print("NEXT STEPS:")
    print(f"  1. Wait ~5 min for cloud-init to finish:")
    print(f"       ssh -i ~/.ssh/{key_name}.pem ubuntu@{public_ip} 'tail -f /var/log/vwa-bootstrap.log'")
    print(f"  2. Visit:  http://{public_ip}")
    print(f"  3. To deploy updates later:")
    print(f"       ssh -i ~/.ssh/{key_name}.pem ubuntu@{public_ip} 'cd /opt/vwa && bash scripts/deploy.sh'")
    print()
    print("Admin login: admin@vwa.local  (password in backend/app/seed.py)")
    print("─" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision VWA on AWS EC2")
    parser.add_argument("--key-name", default=DEFAULT_KEY_PAIR,
                        help=f"EC2 key pair name (default: {DEFAULT_KEY_PAIR})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan without creating resources")
    args = parser.parse_args()
    provision(key_name=args.key_name, dry_run=args.dry_run)

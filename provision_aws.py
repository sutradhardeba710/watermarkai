import boto3
import urllib.request
import json
import time

def main():
    print("Initializing AWS provisioning script...")
    ec2_client = boto3.client('ec2', region_name='us-east-1')
    ec2_resource = boto3.resource('ec2', region_name='us-east-1')
    ssm_client = boto3.client('ssm', region_name='us-east-1')
    elasticache_client = boto3.client('elasticache', region_name='us-east-1')

    # Get my IP
    my_ip = urllib.request.urlopen('http://checkip.amazonaws.com').read().decode('utf-8').strip()
    print(f"My IP: {my_ip}")

    # Get Default VPC
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs']
    if not vpcs:
        print("No default VPC found.")
        return
    vpc_id = vpcs[0]['VpcId']
    print(f"Using VPC: {vpc_id}")

    # Get Subnets
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
    subnet_ids = [s['SubnetId'] for s in subnets]
    primary_subnet = subnet_ids[0]
    print(f"Found {len(subnet_ids)} subnets. Primary: {primary_subnet}")

    # Helper to get or create SG
    def get_or_create_sg(name, desc):
        sgs = ec2_client.describe_security_groups(Filters=[
            {'Name': 'group-name', 'Values': [name]},
            {'Name': 'vpc-id', 'Values': [vpc_id]}
        ])['SecurityGroups']
        if sgs:
            return sgs[0]['GroupId']
        print(f"Creating SG: {name}")
        response = ec2_client.create_security_group(GroupName=name, Description=desc, VpcId=vpc_id)
        return response['GroupId']

    backend_sg = get_or_create_sg('vwa-backend-sg', 'VWA Backend Security Group')
    worker_sg = get_or_create_sg('vwa-worker-sg', 'VWA Worker Security Group')
    postgres_sg = get_or_create_sg('PostgreSQL SG', 'VWA PostgreSQL Security Group')
    redis_sg = get_or_create_sg('vwa-redis-sg', 'VWA Redis Security Group')

    # Authorize rules (ignore errors if they exist)
    def authorize_ingress(group_id, ip_permissions):
        try:
            ec2_client.authorize_security_group_ingress(GroupId=group_id, IpPermissions=ip_permissions)
        except Exception as e:
            if 'InvalidPermission.Duplicate' not in str(e):
                print(f"Error authorizing rule for {group_id}: {e}")

    # Backend: SSH from my IP, HTTP 8000 internal
    authorize_ingress(backend_sg, [
        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': f'{my_ip}/32'}]},
        {'IpProtocol': 'tcp', 'FromPort': 8000, 'ToPort': 8000, 'UserIdGroupPairs': [{'GroupId': backend_sg}]} # allow itself for now, or whole VPC later
    ])
    
    # Worker: SSH from my IP
    authorize_ingress(worker_sg, [
        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': f'{my_ip}/32'}]}
    ])

    # Postgres: 5432 from backend and worker
    authorize_ingress(postgres_sg, [
        {'IpProtocol': 'tcp', 'FromPort': 5432, 'ToPort': 5432, 'UserIdGroupPairs': [{'GroupId': backend_sg}, {'GroupId': worker_sg}]}
    ])

    # Redis: 6379 from backend and worker
    authorize_ingress(redis_sg, [
        {'IpProtocol': 'tcp', 'FromPort': 6379, 'ToPort': 6379, 'UserIdGroupPairs': [{'GroupId': backend_sg}, {'GroupId': worker_sg}]}
    ])

    # Get Ubuntu 22.04 AMI
    response = ssm_client.get_parameter(Name='/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id')
    ami_id = response['Parameter']['Value']
    print(f"Using AMI: {ami_id}")

    # Helper to create instances
    def create_instance(name, instance_type, sg_id, block_devices=None):
        print(f"Creating instance {name}...")
        kwargs = {
            'ImageId': ami_id,
            'InstanceType': instance_type,
            'MaxCount': 1,
            'MinCount': 1,
            'SecurityGroupIds': [sg_id],
            'SubnetId': primary_subnet,
            'TagSpecifications': [{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': name}]}]
        }
        if block_devices:
            kwargs['BlockDeviceMappings'] = block_devices
            
        instances = ec2_resource.create_instances(**kwargs)
        instances[0].wait_until_running()
        instances[0].reload()
        print(f"Instance {name} created with IP: {instances[0].public_ip_address} and Private IP: {instances[0].private_ip_address}")
        return instances[0]

    # Create EC2 instances
    postgres_bd = [
        {'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 8, 'VolumeType': 'gp3', 'Encrypted': True}},
        {'DeviceName': '/dev/sdf', 'Ebs': {'VolumeSize': 20, 'VolumeType': 'gp3', 'Encrypted': True}}
    ]
    pg_inst = create_instance('vwa-postgresql', 't3.small', postgres_sg, postgres_bd)
    backend_inst = create_instance('vwa-backend', 't3.small', backend_sg)
    worker_inst = create_instance('vwa-worker', 't3.medium', worker_sg)

    # Create Redis
    subnet_group_name = 'vwa-redis-subnet-group'
    try:
        elasticache_client.create_cache_subnet_group(
            CacheSubnetGroupName=subnet_group_name,
            CacheSubnetGroupDescription='VWA Redis Subnet Group',
            SubnetIds=subnet_ids
        )
    except Exception as e:
        if 'CacheSubnetGroupAlreadyExists' not in str(e):
            print(f"Error creating Subnet Group: {e}")

    try:
        print("Creating Redis cluster...")
        elasticache_client.create_cache_cluster(
            CacheClusterId='vwa-redis',
            Engine='redis',
            CacheNodeType='cache.t3.micro',
            NumCacheNodes=1,
            CacheSubnetGroupName=subnet_group_name,
            SecurityGroupIds=[redis_sg]
        )
    except Exception as e:
        if 'CacheClusterAlreadyExists' not in str(e):
            print(f"Error creating Redis cluster: {e}")

    print("Waiting for Redis to be available... (this might take a few minutes)")
    while True:
        info = elasticache_client.describe_cache_clusters(CacheClusterId='vwa-redis')['CacheClusters'][0]
        status = info['CacheClusterStatus']
        if status == 'available':
            redis_endpoint = info['CacheNodes'][0]['Endpoint']['Address']
            redis_port = info['CacheNodes'][0]['Endpoint']['Port']
            break
        print(f"Redis status: {status} - Waiting 20 seconds...")
        time.sleep(20)

    # Summarize
    print("\n--- INFRASTRUCTURE SUMMARY ---")
    print(f"PostgreSQL Private IP: {pg_inst.private_ip_address}")
    print(f"Backend Public IP: {backend_inst.public_ip_address}")
    print(f"Worker Public IP: {worker_inst.public_ip_address}")
    print(f"Redis Endpoint: {redis_endpoint}:{redis_port}")
    print("------------------------------")

if __name__ == '__main__':
    main()

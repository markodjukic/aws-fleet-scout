"""
Quota checking utilities for AWS Fleet Scout.

Validates instance requests against AWS Service Quotas to provide
early warnings and suggestions before attempting deployments.
"""

from typing import Dict, Optional, Tuple

from .cache import get_cached_data


def _fetch_all_quota_codes(region: str = "us-east-1") -> Dict[str, str]:
    """
    Fetch all EC2 spot quota codes from AWS.

    Args:
        region: AWS region

    Returns:
        Dict mapping family name to quota code
    """
    try:
        import boto3

        client = boto3.client("service-quotas", region_name=region)

        # Get all EC2 quotas
        paginator = client.get_paginator("list_service_quotas")
        quota_map = {}

        for page in paginator.paginate(ServiceCode="ec2"):
            for quota in page.get("Quotas", []):
                quota_name = quota["QuotaName"]
                quota_code = quota["QuotaCode"]

                # Only cache spot instance quotas
                if "Spot Instance Requests" in quota_name:
                    # Extract family from quota name
                    # e.g., "All P5 Spot Instance Requests" -> "p5"
                    if "P5" in quota_name:
                        quota_map["p5"] = quota_code
                    elif "P4, P3 and P2" in quota_name:
                        quota_map["p4"] = quota_code
                        quota_map["p3"] = quota_code
                        quota_map["p2"] = quota_code
                    elif "G and VT" in quota_name:
                        quota_map["g5"] = quota_code
                        quota_map["g4"] = quota_code
                        quota_map["g3"] = quota_code
                    elif "Inf" in quota_name:
                        quota_map["inf1"] = quota_code
                        quota_map["inf2"] = quota_code
                    elif "Trn" in quota_name:
                        quota_map["trn1"] = quota_code
                    elif "DL" in quota_name:
                        quota_map["dl1"] = quota_code
                    elif "All F" in quota_name:
                        quota_map["f1"] = quota_code
                    elif "All X" in quota_name:
                        quota_map["x2"] = quota_code
                    elif "Standard" in quota_name:
                        quota_map["standard"] = quota_code

        return quota_map
    except Exception:
        return {}


def get_quota_code_for_family(family: str, region: str = "us-east-1") -> Optional[str]:
    """
    Get quota code for an instance family.

    Uses 2-tier lookup: cache → AWS API

    Args:
        family: Instance family (e.g., 'p5', 'g5', 'standard')
        region: AWS region

    Returns:
        Quota code or None if not found
    """

    def fetch_quotas():
        return _fetch_all_quota_codes(region)

    quota_map = get_cached_data("quota_codes", fetch_quotas, region=region)

    if quota_map and family in quota_map:
        return quota_map[family]

    return None


def get_instance_family(instance_type: str) -> str:
    """
    Extract instance family from instance type.

    Args:
        instance_type: EC2 instance type (e.g., 'p5.48xlarge')

    Returns:
        Instance family (e.g., 'p5') or 'standard' for common types
    """
    family = instance_type.split(".")[0].lower()

    # Map to quota family
    if family.startswith(("p5", "p4", "p3", "p2")):
        return family[:2]
    elif family.startswith(("g5", "g4", "g3")):
        return family[:2]
    elif family.startswith(("inf", "trn", "dl", "f", "x")):
        return family[:3] if len(family) >= 3 else family
    else:
        # Standard instance families (m, c, r, t, etc.)
        return "standard"


def get_vcpu_count(instance_type: str, region: str = "us-east-1") -> Optional[int]:
    """
    Get vCPU count for an instance type.

    Uses 2-tier lookup: cache → AWS API

    Args:
        instance_type: EC2 instance type
        region: AWS region to query

    Returns:
        vCPU count or None if unable to fetch
    """

    def fetch_vcpu_counts():
        """Fetch vCPU counts for all instance types in the region."""
        try:
            import boto3

            ec2 = boto3.client("ec2", region_name=region)

            # Fetch all instance types (paginated)
            paginator = ec2.get_paginator("describe_instance_types")
            vcpu_map = {}

            for page in paginator.paginate():
                for instance_info in page["InstanceTypes"]:
                    itype = instance_info["InstanceType"]
                    vcpus = instance_info["VCpuInfo"]["DefaultVCpus"]
                    vcpu_map[itype] = vcpus

            return vcpu_map
        except Exception:
            return {}

    # Use cached data or fetch fresh
    vcpu_map = get_cached_data("vcpu_counts", fetch_vcpu_counts, region=region)

    if vcpu_map and instance_type in vcpu_map:
        return vcpu_map[instance_type]

    # Fallback: try single instance lookup if not in cache
    try:
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_instance_types(InstanceTypes=[instance_type])

        if response["InstanceTypes"]:
            return response["InstanceTypes"][0]["VCpuInfo"]["DefaultVCpus"]
    except Exception:
        pass

    return None


def get_quota_for_instance(instance_type: str, region: str = "us-east-1") -> Optional[Dict]:
    """
    Get quota information for an instance type.

    Uses caching with 1-hour TTL (quotas can change when increases are approved).

    Args:
        instance_type: EC2 instance type
        region: AWS region (quotas can vary by region)

    Returns:
        Dict with quota info or None if unable to fetch
    """
    family = get_instance_family(instance_type)
    quota_code = get_quota_code_for_family(family, region)

    if not quota_code:
        return None

    # Cache key includes quota code to cache per family
    cache_key = f"quota_value_{quota_code}"

    def fetch_quota():
        try:
            import boto3

            client = boto3.client("service-quotas", region_name=region)
            response = client.get_service_quota(ServiceCode="ec2", QuotaCode=quota_code)

            return {
                "quota_name": response["Quota"]["QuotaName"],
                "quota_code": quota_code,
                "value": response["Quota"]["Value"],
                "unit": "vCPUs",
                "adjustable": response["Quota"].get("Adjustable", False),
            }
        except Exception:
            return None

    # Use 1-hour TTL for quota values (they can change when increases are approved)
    return get_cached_data(cache_key, fetch_quota, ttl=3600, region=region)


def validate_instance_request(
    instance_type: str, count: int, region: str = "us-east-1", skip_check: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate if an instance request is within quota limits.

    Args:
        instance_type: EC2 instance type
        count: Number of instances requested
        region: AWS region
        skip_check: Skip quota validation

    Returns:
        Tuple of (is_valid, warning_message)
    """
    if skip_check:
        return True, None

    vcpu_count = get_vcpu_count(instance_type)
    if not vcpu_count:
        # Unknown instance type, can't validate
        return True, None

    quota_info = get_quota_for_instance(instance_type, region)
    if not quota_info:
        # Can't fetch quota, skip validation
        return True, None

    requested_vcpus = vcpu_count * count
    quota_vcpus = quota_info["value"]

    if requested_vcpus > quota_vcpus:
        max_instances = int(quota_vcpus // vcpu_count)
        family = get_instance_family(instance_type)

        warning = f"""
⚠️  Warning: Requesting {count}x {instance_type} ({requested_vcpus:,} vCPUs) exceeds your quota
    Quota: {quota_info['quota_name']} = {quota_vcpus:,.0f} vCPUs
    Maximum you can request: {max_instances} instances

    Suggestion: Request quota increase or reduce instance count
    
    To request quota increase:
    aws service-quotas request-service-quota-increase \\
      --service-code ec2 \\
      --quota-code {quota_info['quota_code']} \\
      --desired-value {requested_vcpus * 2}
    
    Or use --skip-quota-check to bypass this validation
"""
        return False, warning

    return True, None


def check_discovered_instances_quotas(
    instance_types: list, target_capacity: int, region: str = "us-east-1", skip_check: bool = False
) -> Dict[str, Dict]:
    """
    Check quotas for multiple discovered instance types.

    Args:
        instance_types: List of instance type strings
        target_capacity: Target number of instances
        region: AWS region
        skip_check: Skip quota validation

    Returns:
        Dict mapping instance_type to quota status
    """
    if skip_check:
        return {}

    results = {}

    for instance_type in instance_types:
        vcpu_count = get_vcpu_count(instance_type)
        if not vcpu_count:
            results[instance_type] = {"status": "unknown", "message": "vCPU count unknown"}
            continue

        quota_info = get_quota_for_instance(instance_type, region)
        if not quota_info:
            results[instance_type] = {"status": "unknown", "message": "Quota info unavailable"}
            continue

        requested_vcpus = vcpu_count * target_capacity
        quota_vcpus = quota_info["value"]
        max_instances = int(quota_vcpus // vcpu_count)

        if requested_vcpus <= quota_vcpus:
            results[instance_type] = {
                "status": "ok",
                "max_instances": max_instances,
                "quota_vcpus": quota_vcpus,
                "vcpu_per_instance": vcpu_count,
            }
        else:
            results[instance_type] = {
                "status": "insufficient",
                "max_instances": max_instances,
                "quota_vcpus": quota_vcpus,
                "vcpu_per_instance": vcpu_count,
                "requested_vcpus": requested_vcpus,
            }

    return results


def print_quota_summary(quota_results: Dict[str, Dict], target_capacity: int):
    """
    Print a summary of quota validation results.

    Args:
        quota_results: Results from check_discovered_instances_quotas
        target_capacity: Target number of instances
    """
    if not quota_results:
        return

    print("\nQuota Validation:")
    print("-" * 80)

    for instance_type, result in sorted(quota_results.items()):
        status = result["status"]

        if status == "ok":
            print(
                f"✓ {instance_type}: Can request up to {result['max_instances']} instances "
                f"({result['quota_vcpus']:.0f} vCPU quota)"
            )
        elif status == "insufficient":
            print(
                f"✗ {instance_type}: Can only request {result['max_instances']} instances "
                f"({result['quota_vcpus']:.0f} vCPU quota) - insufficient for target of {target_capacity}"
            )
        else:
            print(f"? {instance_type}: {result['message']}")

    print()

"""
Shared AWS client management for AWS Fleet Scout.

Provides centralized boto3 client creation with caching to avoid
redundant client initialization across commands.
"""

from typing import Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .cache import get_cached_data


class AWSClientManager:
    """
    Manages boto3 client instances with caching.

    Ensures that clients for the same service and region are reused
    rather than recreated, improving performance and reducing overhead.
    """

    def __init__(self):
        self._clients: Dict[tuple, boto3.client] = {}

    def get_client(self, service: str, region: str = "us-east-1") -> boto3.client:
        """
        Get or create a boto3 client for the specified service and region.

        Args:
            service: AWS service name (e.g., 'ec2', 'pricing')
            region: AWS region name (default: 'us-east-1')

        Returns:
            boto3 client instance
        """
        key = (service, region)

        if key not in self._clients:
            self._clients[key] = boto3.client(service, region_name=region)

        return self._clients[key]

    def clear_cache(self):
        """Clear all cached clients."""
        self._clients.clear()


# Global client manager instance
_client_manager = AWSClientManager()


def get_ec2_client(region: str = "us-east-1") -> boto3.client:
    """
    Get an EC2 client for the specified region.

    Args:
        region: AWS region name (default: 'us-east-1')

    Returns:
        boto3 EC2 client
    """
    return _client_manager.get_client("ec2", region)


def get_pricing_client(region: str = "us-east-1") -> boto3.client:
    """
    Get a Pricing client for the specified region.

    Note: AWS Pricing API is only available in us-east-1 and ap-south-1.

    Args:
        region: AWS region name (default: 'us-east-1')

    Returns:
        boto3 Pricing client
    """
    return _client_manager.get_client("pricing", region)


def clear_client_cache():
    """Clear all cached AWS clients."""
    _client_manager.clear_cache()


def check_on_demand_availability(instance_type: str, regions: List[str]) -> Dict[str, bool]:
    """
    Check if an instance type is available for on-demand in specified regions.

    Uses describe_instance_type_offerings to dynamically query AWS for availability.

    Args:
        instance_type: EC2 instance type (e.g., 'p5.48xlarge')
        regions: List of AWS regions to check

    Returns:
        Dict mapping region to availability (True if available on-demand)
    """
    availability = {}

    for region in regions:
        try:
            client = get_ec2_client(region)
            response = client.describe_instance_type_offerings(
                LocationType="region",
                Filters=[
                    {"Name": "instance-type", "Values": [instance_type]},
                    {"Name": "location", "Values": [region]},
                ],
            )

            # Check if any offerings exist for this instance type in this region
            # If offerings exist, the instance type is available (could be spot or on-demand)
            # We assume if it's offered in the region, on-demand is available
            # (spot-only instances are rare and usually documented separately)
            availability[region] = len(response.get("InstanceTypeOfferings", [])) > 0

        except ClientError as e:
            # Region might not be enabled or other access issues
            availability[region] = False
        except Exception as e:
            # Any other error, assume not available
            availability[region] = False

    return availability


def get_available_regions_for_instance(
    instance_type: str, regions: Optional[List[str]] = None
) -> List[str]:
    """
    Get list of regions where an instance type is available.

    Args:
        instance_type: EC2 instance type (e.g., 'p5.48xlarge')
        regions: List of regions to check (if None, checks DEFAULT_REGIONS)

    Returns:
        List of regions where the instance type is available
    """
    from ..config import DEFAULT_REGIONS

    if regions is None:
        regions = DEFAULT_REGIONS

    availability = check_on_demand_availability(instance_type, regions)
    return [region for region, available in availability.items() if available]


def discover_p_series_instances(regions: List[str]) -> List[str]:
    """
    Auto-discover all P-series (P4/P5/P6) GPU instances available in specified regions.

    Queries AWS to find all P4, P5, and P6 instance types available across the given regions.
    Returns a deduplicated, sorted list of instance types.

    Args:
        regions: List of AWS regions to search

    Returns:
        Sorted list of P-series instance types (e.g., ['p4d.24xlarge', 'p5.48xlarge', ...])
    """
    return discover_instances_by_prefix(regions, ["p4", "p5", "p6"])


def discover_instances_by_prefix(regions: List[str], prefixes: List[str]) -> List[str]:
    """
    Auto-discover instance types matching specified prefixes in given regions.

    Queries AWS to find all instance types that start with any of the given prefixes.
    Returns a deduplicated, sorted list of instance types.
    Uses caching to avoid repeated API calls.

    Args:
        regions: List of AWS regions to search
        prefixes: List of instance family prefixes (e.g., ['p5', 'g5'], ['m7i', 'c7i'])

    Returns:
        Sorted list of matching instance types

    Examples:
        # Find all P-series GPU instances
        discover_instances_by_prefix(['us-east-1'], ['p4', 'p5', 'p6'])

        # Find all G-series GPU instances
        discover_instances_by_prefix(['us-east-1'], ['g5', 'g6'])

        # Find all 7th gen compute instances
        discover_instances_by_prefix(['us-east-1'], ['m7i', 'c7i', 'r7i'])
    """
    all_instances = set()

    for region in regions:
        # Get cached instance offerings for this region
        def fetch_offerings():
            try:
                client = get_ec2_client(region)
                response = client.describe_instance_type_offerings(
                    LocationType="region", Filters=[{"Name": "location", "Values": [region]}]
                )
                # Return list of instance types
                return [
                    offering["InstanceType"]
                    for offering in response.get("InstanceTypeOfferings", [])
                ]
            except Exception:
                return []

        # Use a closure to capture the current region value correctly
        def make_fetch_offerings(r):
            def fetch_offerings():
                try:
                    client = get_ec2_client(r)
                    all_types = []
                    paginator = client.get_paginator("describe_instance_type_offerings")
                    for page in paginator.paginate(
                        LocationType="region", Filters=[{"Name": "location", "Values": [r]}]
                    ):
                        all_types.extend(
                            offering["InstanceType"]
                            for offering in page.get("InstanceTypeOfferings", [])
                        )
                    return all_types
                except Exception:
                    return []

            return fetch_offerings

        instance_types = get_cached_data(
            "instance_offerings", make_fetch_offerings(region), region=region
        )

        if instance_types:
            # Filter by prefixes
            for itype in instance_types:
                if any(itype.startswith(prefix) for prefix in prefixes):
                    all_instances.add(itype)

    return sorted(list(all_instances))

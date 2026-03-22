"""
Configuration constants for AWS Fleet Scout.
"""

import json
from pathlib import Path

from .utils.cache import get_cached_data

# Default AWS regions to check when none specified
DEFAULT_REGIONS = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]


def _load_pricing_region_map():
    """
    Dynamically load AWS Pricing API region name mapping from botocore endpoints.

    AWS Pricing API uses descriptive names (e.g., "US East (N. Virginia)")
    while EC2 API uses region codes (e.g., "us-east-1").

    This function extracts the mapping from botocore's endpoints.json file.
    Uses caching to avoid repeated file reads.

    Raises:
        RuntimeError: If unable to load region mapping from botocore
    """

    def fetch_region_map():
        try:
            # Find botocore's endpoints.json
            import botocore

            botocore_path = Path(botocore.__file__).parent
            endpoints_file = botocore_path / "data" / "endpoints.json"

            if not endpoints_file.exists():
                raise RuntimeError(f"Botocore endpoints file not found at {endpoints_file}")

            with open(endpoints_file, "r") as f:
                endpoints = json.load(f)

            # Extract region descriptions from first partition (usually 'aws')
            partitions = endpoints.get("partitions", [])
            if not partitions:
                raise RuntimeError("No partitions found in botocore endpoints.json")

            regions = next(iter(partitions), {}).get("regions", {})
            if not regions:
                raise RuntimeError("No regions found in botocore endpoints.json")

            region_map = {k: v["description"] for k, v in regions.items()}

            # AWS Pricing API uses slightly different names for some EU regions
            # These overrides match what the Pricing API actually expects
            region_map["eu-west-1"] = "EU (Ireland)"
            region_map["eu-central-1"] = "EU (Frankfurt)"
            region_map["eu-north-1"] = "EU (Stockholm)"
            region_map["eu-west-2"] = "EU (London)"
            region_map["eu-west-3"] = "EU (Paris)"

            return region_map
        except ImportError as e:
            raise RuntimeError(f"Failed to import botocore: {e}. Ensure boto3 is installed.")
        except Exception as e:
            raise RuntimeError(f"Failed to load AWS region mapping from botocore: {e}")

    # Cache region map for 30 days (regions rarely change)
    # Use a dummy region parameter since this is global data
    cached_map = get_cached_data(
        "pricing_region_map", fetch_region_map, ttl=86400 * 30, region="global"  # 30 days
    )

    if cached_map is None:
        # Fallback if caching fails - fetch directly
        cached_map = fetch_region_map()

    return cached_map


# AWS Pricing API region name mapping (loaded dynamically with caching)
PRICING_REGION_MAP = _load_pricing_region_map()

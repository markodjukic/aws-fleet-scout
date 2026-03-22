import hashlib
import json
import sys

from rich.console import Console
from rich.table import Table

from ...config import DEFAULT_REGIONS
from ...utils.aws_client import discover_instances_by_prefix, get_ec2_client
from ...utils.cache import CACHE_DIR, get_cached_data
from ...utils.output import print_error_output, print_json_output
from ...utils.quotas import (
    check_discovered_instances_quotas,
    print_quota_summary,
    validate_instance_request,
)


def main(
    instance_type: str = "",
    output: str = "json",
    regions=None,
    target_capacity: int = 15,
    discover: str = "",
    discover_p_series: bool = False,
    skip_quota_check: bool = False,
    force_refresh: bool = False,
):
    """
    Query EC2 spot placement scores for instance type(s).

    Spot placement scores (0-10) indicate the likelihood of successfully launching
    and maintaining spot instances in a region. Higher scores mean better availability.

    Args:
        instance_type: EC2 instance type to check (e.g., 'p5.48xlarge')
        output: Output format (json or table)
        regions: List of AWS regions to check (default: all US regions)
        target_capacity: Number of instances to check for (default: 15)
        discover: Auto-discover instances by prefix (e.g., 'p5', 'g5', 'm7i,c7i')
        discover_p_series: Auto-discover all P4/P5/P6 instances (shortcut for --discover p)
        skip_quota_check: Skip quota validation (default: False)
        force_refresh: Force refresh from AWS API, bypass cache (default: False)

    Returns:
        Dict of instance types to placement scores, or list for single instance
    """
    if not regions:
        regions = DEFAULT_REGIONS

    # Parse input - discovery or single instance
    if discover or discover_p_series:
        # Determine prefixes to search for
        if discover:
            prefixes = [p.strip() for p in discover.split(",") if p.strip()]
            prefix_display = ", ".join(prefixes)
        else:
            prefixes = ["p4", "p5", "p6"]
            prefix_display = "P-series (P4/P5/P6)"

        if output != "json":
            print(f"Discovering {prefix_display} instances in: {', '.join(regions)}")
            print()

        discovered_instances = discover_instances_by_prefix(regions, prefixes)

        if not discovered_instances:
            if output != "json":
                print(f"No instances matching prefixes {prefixes} found in the specified regions.")
            return {}

        if output != "json":
            print(f"Found {len(discovered_instances)} instance types:")
            for itype in discovered_instances:
                print(f"  - {itype}")
            print()

            # Check quotas for discovered instances
            quota_results = check_discovered_instances_quotas(
                discovered_instances,
                target_capacity,
                region=regions[0],
                skip_check=skip_quota_check,
            )
            if quota_results:
                print_quota_summary(quota_results, target_capacity)

            if len(discovered_instances) > 10:
                print("⚠️  Warning: Discovering many instances may hit AWS API rate limits.")
                print("   If you see MaxConfigLimitExceeded errors, use more specific prefixes")
                print("   or use cached results (scores are cached for 10 minutes).")
                print()

                # Interactive confirmation for large discoveries
                try:
                    response = input(
                        f"Proceed with querying {len(discovered_instances)} instance types? [y/N]: "
                    )
                    if response.lower() not in ["y", "yes"]:
                        print("Cancelled.")
                        return {}
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return {}
                print()

        instance_types = discovered_instances
    elif instance_type:
        # Validate single instance request against quotas
        is_valid, warning = validate_instance_request(
            instance_type, target_capacity, region=regions[0], skip_check=skip_quota_check
        )

        if not is_valid and warning and output != "json":
            print(warning)
            # Continue anyway - user might have pending quota increase

        instance_types = [instance_type]
    else:
        if output != "json":
            print("Error: Either --instance-type, --discover, or --discover-p-series is required")
        return {}

    # Query scores for all instance types
    results = {}
    cache_hits = 0

    for itype in instance_types:
        if output != "json" and len(instance_types) > 1:
            print(f"Querying spot scores for {itype}...")

        # Try cache first (unless force_refresh is set)
        if not force_refresh:
            cached_scores = _get_cached_spot_scores(itype, target_capacity, regions)
            if cached_scores is not None:
                results[itype] = cached_scores
                cache_hits += 1
                if output != "json" and len(instance_types) > 1:
                    print(f"  ✓ Using cached scores (less than 1 hour old)")
                continue

        # Cache miss or force refresh - fetch from AWS
        client = get_ec2_client(regions[0])
        try:
            response = client.get_spot_placement_scores(
                InstanceTypes=[itype],
                TargetCapacity=target_capacity,
                TargetCapacityUnitType="units",
                RegionNames=regions,
                SingleAvailabilityZone=True,
            )
            scores = response["SpotPlacementScores"]
            # Sort scores by Score descending
            scores_sorted = sorted(scores, key=lambda s: s["Score"], reverse=True)
            results[itype] = scores_sorted

            # Cache the results
            _cache_spot_scores(itype, target_capacity, regions, scores_sorted)

        except Exception as e:
            if output != "json":
                print(f"  Warning: Could not fetch spot scores for {itype}: {e}")
            results[itype] = []

    # Show cache info for multi-instance queries
    if output != "json" and len(instance_types) > 1 and cache_hits > 0:
        print()
        print(
            f"ℹ️  {cache_hits}/{len(instance_types)} results from cache (10 min TTL, use --force-refresh to bypass)"
        )

    # Format output
    if output == "json":
        if len(instance_types) == 1:
            # Single instance - return list for backward compatibility
            print_json_output(
                data=results[instance_types[0]],
                command="spot.score",
                regions_checked=regions,
                metadata={
                    "instance_type": instance_types[0],
                    "target_capacity": target_capacity,
                    "cache_hits": cache_hits,
                    "total_queries": len(instance_types),
                },
            )
            return results[instance_types[0]]
        else:
            # Multiple instances - return dict
            print_json_output(
                data=results,
                command="spot.score",
                regions_checked=regions,
                metadata={
                    "instance_types": instance_types,
                    "target_capacity": target_capacity,
                    "cache_hits": cache_hits,
                    "total_queries": len(instance_types),
                },
            )
            return results
    else:
        console = Console()

        for itype, scores in results.items():
            if len(instance_types) > 1:
                print()

            table = Table(title=f"Spot Placement Scores: {itype}")
            table.add_column("Region", style="cyan")
            table.add_column("AZ ID", style="magenta")
            table.add_column("Score", style="green", justify="right")

            for s in scores:
                table.add_row(s["Region"], s["AvailabilityZoneId"], str(s["Score"]))

            console.print(table)

        return results


def _get_cache_key(instance_type: str, target_capacity: int, regions: list) -> str:
    """
    Generate a unique cache key for spot placement scores.

    Args:
        instance_type: EC2 instance type
        target_capacity: Number of instances
        regions: List of regions (will be sorted for consistency)

    Returns:
        Cache key string
    """
    # Sort regions for consistent cache keys
    regions_sorted = sorted(regions)
    regions_str = ",".join(regions_sorted)

    # Create a hash of regions to keep key short
    regions_hash = hashlib.md5(regions_str.encode()).hexdigest()[:8]

    return f"spot_score_{instance_type}_{target_capacity}_{regions_hash}"


def _get_cached_spot_scores(instance_type: str, target_capacity: int, regions: list):
    """
    Get cached spot placement scores if available and fresh.

    Args:
        instance_type: EC2 instance type
        target_capacity: Number of instances
        regions: List of regions

    Returns:
        Cached scores or None if not available/stale
    """
    cache_key = _get_cache_key(instance_type, target_capacity, regions)

    # Use a fetch function that returns None (cache will return None on miss)
    def fetch_none():
        return None

    # Try to get from cache with 10 minute TTL
    cached_data = get_cached_data(
        cache_key=cache_key,
        fetch_func=fetch_none,
        ttl=600,  # 10 minutes
        region="global",  # Not region-specific, use 'global'
    )

    return cached_data


def _cache_spot_scores(instance_type: str, target_capacity: int, regions: list, scores: list):
    """
    Cache spot placement scores.

    Args:
        instance_type: EC2 instance type
        target_capacity: Number of instances
        regions: List of regions
        scores: Spot placement scores to cache
    """
    cache_key = _get_cache_key(instance_type, target_capacity, regions)

    # Use get_cached_data with a function that returns the scores
    # This will cache them for future use
    def fetch_scores():
        return scores

    get_cached_data(
        cache_key=cache_key, fetch_func=fetch_scores, ttl=600, region="global"  # 10 minutes
    )

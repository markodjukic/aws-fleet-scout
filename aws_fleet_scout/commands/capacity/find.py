import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ...config import DEFAULT_REGIONS
from ...utils.aws_client import discover_instances_by_prefix, get_ec2_client
from ...utils.output import print_json_output


def _is_valid_duration(days: int) -> bool:
    """
    Check if duration is valid for capacity blocks.

    Valid durations:
    - 1-14 days (daily increments)
    - 21, 28, 35... up to 182 days (7-day increments)
    """
    if 1 <= days <= 14:
        return True
    elif 21 <= days <= 182:
        return days % 7 == 0
    return False


def _days_to_hours(days: int) -> int:
    """Convert days to hours for AWS API."""
    return days * 24


def main(
    instance_type: str = "",
    job_spec: str = "",
    duration: int = 1,
    max_days: int = 7,
    output: str = "json",
    regions: Optional[List[str]] = None,
    discover: str = "",
    discover_p_series: bool = False,
    ctx: Optional[typer.Context] = None,
):
    """
    Find available capacity block offerings for GPU instances.

    Capacity blocks provide reserved capacity for a fixed duration with upfront pricing.
    Ideal for scheduled training jobs that need guaranteed GPU availability.

    Valid durations: 1-14 days (daily), or 21-182 days (7-day increments)

    Args:
        instance_type: Single instance type (e.g., 'p5.48xlarge')
        job_spec: JSON string with instance requirements (e.g., '{"p5.48xlarge": 2}')
        duration: Desired duration in days (default: 1). Must be 1-14 daily, or 21-182 in 7-day steps
        max_days: Search window in days ahead (default: 7)
        output: Output format (json or table)
        regions: List of AWS regions to check
        discover: Auto-discover instances by prefix (e.g., 'p5', 'g5', 'm7i,c7i')
        discover_p_series: Auto-discover all P4/P5/P6 instances (shortcut for --discover p)
        ctx: Typer context for CLI help display
    """

    # Validate duration
    if not _is_valid_duration(duration):
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(
                f"\nError: Invalid duration {duration} days. Must be 1-14 daily, or 21-182 in 7-day increments.",
                err=True,
            )
            raise typer.Exit(1)
        raise typer.BadParameter(f"Invalid duration {duration} days")

    # Convert days to hours for AWS API
    duration_hours = _days_to_hours(duration)

    if not regions:
        regions = DEFAULT_REGIONS

    # Parse input - discovery or explicit specification
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

            if len(discovered_instances) > 10:
                print("⚠️  Warning: Discovering many instances may hit AWS API rate limits.")
                print("   If you see errors, use more specific prefixes.")
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

        instance_requirements = {itype: 1 for itype in discovered_instances}
    elif instance_type:
        instance_requirements = {instance_type: 1}
    elif job_spec:
        try:
            instance_requirements = json.loads(job_spec)
        except json.JSONDecodeError as e:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo(
                    f"\nError: Invalid job_spec JSON: {e}. Expected format: '{{\"instance_type\": quantity, ...}}'",
                    err=True,
                )
                raise typer.Exit(1)
            raise typer.BadParameter(
                f"Invalid job_spec JSON: {e}. Expected format: '{{\"instance_type\": quantity, ...}}'"
            )
    else:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(
                "\nError: Either --instance-type, --job-spec, --discover, or --discover-p-series is required",
                err=True,
            )
            raise typer.Exit(1)
        raise typer.BadParameter(
            "Either --instance-type, --job-spec, --discover, or --discover-p-series is required"
        )

    if output != "json":
        print(f"Capacity Block Analysis for: {instance_requirements}")
        print(f"Duration: {duration} days ({duration_hours} hours), Search window: {max_days} days")
        print(f"Checking regions: {', '.join(regions)}")
        print()

    # Query capacity blocks for each instance type
    all_offerings = {}

    for instance_type, count in instance_requirements.items():
        if output != "json":
            print(f"Querying capacity blocks for {count}x {instance_type}...")
        offerings_by_region = _query_capacity_blocks(
            instance_type=instance_type,
            instance_count=count,
            duration_hours=duration_hours,
            max_days=max_days,
            regions=regions,
            output=output,
        )
        all_offerings[instance_type] = offerings_by_region

    # Find best offerings
    best_offerings = _find_best_offerings(all_offerings, instance_requirements)

    # Format output
    if output == "json":
        result_data = {
            "offerings": best_offerings,
            "best_region": best_offerings[0]["region"] if best_offerings else None,
            "best_offering": best_offerings[0] if best_offerings else None,
        }
        print_json_output(
            data=result_data,
            command="capacity.find",
            regions_checked=regions,
            metadata={
                "instance_requirements": instance_requirements,
                "duration_days": duration,
                "duration_hours": duration_hours,
                "search_window_days": max_days,
            },
        )
        return result_data
    else:
        # Table format
        _print_table(best_offerings, instance_requirements, duration, duration_hours, max_days)
        return best_offerings


def _query_capacity_blocks(
    instance_type: str,
    instance_count: int,
    duration_hours: int,
    max_days: int,
    regions: List[str],
    output: str = "json",
) -> Dict[str, List[Dict]]:
    """
    Query capacity block offerings across regions.

    Returns:
        Dict mapping region to list of capacity block offerings
    """

    offerings_by_region = {}
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=max_days)

    for region in regions:
        try:
            client = get_ec2_client(region)
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=instance_count,
                CapacityDurationHours=duration_hours,
                StartDateRange=start_date,
                EndDateRange=end_date,
                MaxResults=50,
            )
            offerings = response.get("CapacityBlockOfferings", [])
            offerings_by_region[region] = offerings

            if output != "json":
                if offerings:
                    print(f"  ✓ Found {len(offerings)} offerings in {region}")
                else:
                    print(f"  - No offerings in {region}")

        except Exception as e:
            if output != "json":
                print(f"  ✗ Error querying {region}: {e}")
            offerings_by_region[region] = []

    return offerings_by_region


def _find_best_offerings(
    all_offerings: Dict[str, Dict[str, List[Dict]]], instance_requirements: Dict[str, int]
) -> List[Dict]:
    """
    Find best capacity block offerings across all instance types and regions.

    Selection criteria (in order):
    1. Earliest start date
    2. Shortest duration
    3. Lowest upfront fee

    Returns:
        List of best offerings sorted by start date
    """
    results = []

    for instance_type, offerings_by_region in all_offerings.items():
        all_region_offerings = []

        for region, offerings in offerings_by_region.items():
            for offering in offerings:
                all_region_offerings.append(
                    {
                        "instance_type": instance_type,
                        "region": region,
                        "availability_zone": offering.get("AvailabilityZone", "N/A"),
                        "start_date": offering["StartDate"],
                        "duration_hours": offering["CapacityBlockDurationHours"],
                        "upfront_fee": float(offering["UpfrontFee"]),
                        "offering_id": offering.get("CapacityBlockOfferingId", "N/A"),
                        "instance_count": offering.get("InstanceCount", 1),
                    }
                )

        if all_region_offerings:
            # Sort by: earliest start, shortest duration, lowest price
            best = min(
                all_region_offerings,
                key=lambda x: (x["start_date"], x["duration_hours"], x["upfront_fee"]),
            )
            results.append(best)
        else:
            # No offerings available
            results.append(
                {
                    "instance_type": instance_type,
                    "region": "No availability",
                    "availability_zone": "N/A",
                    "start_date": None,
                    "duration_hours": None,
                    "upfront_fee": None,
                    "offering_id": None,
                    "instance_count": instance_requirements[instance_type],
                }
            )

    # Sort results by start date (available first)
    results.sort(
        key=lambda x: (
            x["start_date"] is None,
            x["start_date"] or datetime.max.replace(tzinfo=timezone.utc),
        )
    )

    return results


def _print_table(
    offerings: List[Dict],
    requirements: Dict[str, int],
    duration_days: int,
    duration_hours: int,
    max_days: int,
):  # pragma: no cover
    """Print capacity block offerings in table format."""

    console = Console()

    if not any(o["start_date"] for o in offerings):
        console.print("\n⚠️  [yellow]No capacity blocks available in the selected regions[/yellow]")
        console.print(
            "   Try expanding your search to additional regions or adjusting the time window.\n"
        )
        return

    table = Table(
        title=f"Capacity Block Offerings (Duration: {duration_days}d/{duration_hours}hrs, Window: {max_days} days)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Instance Type", style="cyan", width=18)
    table.add_column("Count", justify="right", width=6)
    table.add_column("Region", style="yellow", width=15)
    table.add_column("AZ", width=15)
    table.add_column("Start Date", style="green", width=20)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Upfront Fee", justify="right", style="green", width=12)
    table.add_column("Offering ID", width=20)

    for offering in offerings:
        if offering["start_date"]:
            # Format start date
            now = datetime.now(timezone.utc)
            time_diff = (offering["start_date"] - now).total_seconds() / 3600

            if time_diff <= 1:
                start_str = "Immediate"
            else:
                start_str = offering["start_date"].strftime("%Y-%m-%d %H:%M UTC")

            duration_str = f"{offering['duration_hours']}hrs"
            fee_str = f"${offering['upfront_fee']:.2f}"
            offering_id = (
                offering["offering_id"][:18]
                if len(offering["offering_id"]) > 18
                else offering["offering_id"]
            )

            table.add_row(
                offering["instance_type"],
                str(offering["instance_count"]),
                offering["region"],
                offering["availability_zone"],
                start_str,
                duration_str,
                fee_str,
                offering_id,
            )
        else:
            table.add_row(
                offering["instance_type"],
                str(offering["instance_count"]),
                "No availability",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
                "N/A",
            )

    console.print(table)
    console.print()

    # Show best recommendation
    available = [o for o in offerings if o["start_date"]]
    if available:
        best = available[0]
        print(f"\n✓ RECOMMENDED: {best['instance_type']} in {best['region']}")
        print(f"  Start: {best['start_date'].strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  Cost: ${best['upfront_fee']:.2f} for {best['duration_hours']} hours")
        print(f"  Offering ID: {best['offering_id']}")
        print()

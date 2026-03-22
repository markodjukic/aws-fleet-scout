import typer
from dotenv import load_dotenv

from . import __version__
from .commands.capacity.calendar import main as capacity_calendar_main
from .commands.capacity.find import main as capacityblocks_main
from .commands.compare import main as compare_main
from .commands.fleet.pack import main as fleetpacking_main
from .commands.fleet.recommend import main as placement_main
from .commands.fleet.utility import main as utility_main
from .commands.spot.score import main as spotscore_main
from .utils.regions import parse_region_input

load_dotenv()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        typer.echo(f"aws-fleet-scout version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    help="AWS Fleet Scout: Scout the best AWS regions for spot or capacity block deployments"
)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    )
):
    """AWS Fleet Scout CLI"""
    pass


# Command groups
capacity_app = typer.Typer(help="Capacity block commands")
fleet_app = typer.Typer(help="Fleet optimization commands")
spot_app = typer.Typer(help="Spot instance commands")

app.add_typer(capacity_app, name="capacity")
app.add_typer(fleet_app, name="fleet")
app.add_typer(spot_app, name="spot")


# ============================================================================
# SPOT COMMANDS
# ============================================================================


@spot_app.command("score")
def spot_score(
    instance_type: str = typer.Option("", help="EC2 instance type to check"),
    output: str = typer.Option("json", help="Output format (json or table)"),
    regions: str = typer.Option(
        "",
        help="Comma-separated AWS regions or wildcards (e.g. us-east-1,us-west-2 or us-* or eu-west-*). If not set, defaults to all us-east-* and us-west-* regions.",
    ),
    target_capacity: int = typer.Option(
        15, help="Target capacity (number of instances) to check for spot placement score."
    ),
    discover_p_series: bool = typer.Option(
        False,
        "--discover-p-series",
        help="Auto-discover P4/P5/P6 GPU instances (shortcut for --discover p)",
    ),
    discover: str = typer.Option(
        "",
        "--discover",
        help="Auto-discover instances by prefix (e.g., 'p5' for P5-series, 'g5' for G5-series, 'm7i,c7i' for multiple)",
    ),
    skip_quota_check: bool = typer.Option(
        False,
        "--skip-quota-check",
        help="Skip quota validation (useful if you have pending quota increases)",
    ),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Force refresh from AWS API, bypass cache (scores cached for 10 minutes)",
    ),
):
    """
    Query EC2 spot placement scores for instance type(s).

    Examples:
        # Single instance type
        aws-fleet-scout spot score --instance-type p5.48xlarge

        # Auto-discover all P-series
        aws-fleet-scout spot score --discover-p-series --regions us-east-1

        # Auto-discover G5 instances
        aws-fleet-scout spot score --discover g5 --regions us-east-1

        # Use wildcards for regions
        aws-fleet-scout spot score --instance-type p5.48xlarge --regions "us-*"
        aws-fleet-scout spot score --instance-type p5.48xlarge --regions "eu-west-*"
    """
    region_list = parse_region_input(regions)
    spotscore_main(
        instance_type=instance_type,
        output=output,
        regions=region_list,
        target_capacity=target_capacity,
        discover=discover,
        discover_p_series=discover_p_series,
        skip_quota_check=skip_quota_check,
        force_refresh=force_refresh,
    )


# ============================================================================
# CAPACITY COMMANDS
# ============================================================================


@capacity_app.command("find")
def capacity_find(
    ctx: typer.Context,
    instance_type: str = typer.Option("", help="Single instance type (e.g., 'p5.48xlarge')"),
    job_spec: str = typer.Option(
        "", help="JSON string with instance requirements, e.g. '{\"p5.48xlarge\": 2}'"
    ),
    duration: int = typer.Option(1, help="Duration in days: 1-14 daily, or 21-182 in 7-day steps"),
    max_days: int = typer.Option(7, help="Search window in days ahead (default: 7)"),
    regions: str = typer.Option(
        "", help="Comma-separated AWS regions or wildcards (e.g. us-east-1,us-west-2 or us-*)"
    ),
    discover_p_series: bool = typer.Option(
        False,
        "--discover-p-series",
        help="Auto-discover P4/P5/P6 GPU instances (shortcut for --discover p)",
    ),
    discover: str = typer.Option(
        "",
        "--discover",
        help="Auto-discover instances by prefix (e.g., 'p5' for P5-series, 'g5' for G5-series, 'm7i,c7i' for multiple)",
    ),
    output: str = typer.Option("table", help="Output format (json or table)"),
):
    """
    Find available capacity block offerings for GPU instances.

    Capacity blocks provide reserved capacity for a fixed duration with upfront pricing.
    Ideal for scheduled training jobs that need guaranteed GPU availability.

    Valid durations: 1-14 days (daily), or 21-182 days (7-day increments)

    Examples:
        aws-fleet-scout capacity find --instance-type p5.48xlarge --duration 1
        aws-fleet-scout capacity find --instance-type p5.48xlarge --duration 7
        aws-fleet-scout capacity find --job-spec '{"p5.48xlarge": 2}' --max-days 7
        aws-fleet-scout capacity find --discover-p-series --regions us-east-1
    """
    region_list = parse_region_input(regions)
    capacityblocks_main(
        instance_type=instance_type,
        job_spec=job_spec,
        duration=duration,
        max_days=max_days,
        output=output,
        regions=region_list,
        discover=discover,
        discover_p_series=discover_p_series,
        ctx=ctx,
    )


@capacity_app.command("calendar")
def capacity_calendar(
    ctx: typer.Context,
    instance_type: str = typer.Option("", help="Single instance type (e.g., 'p5.48xlarge')"),
    job_spec: str = typer.Option(
        "", help="JSON string with instance requirements, e.g. '{\"p5.48xlarge\": 2}'"
    ),
    duration: int = typer.Option(1, help="Duration in days: 1-14 daily, or 21-182 in 7-day steps"),
    window: int = typer.Option(7, help="Number of days ahead to search (default: 7)"),
    regions: str = typer.Option(
        "", help="Comma-separated AWS regions or wildcards (e.g. us-east-1,us-west-2 or us-*)"
    ),
    discover_p_series: bool = typer.Option(
        False,
        "--discover-p-series",
        help="Auto-discover P4/P5/P6 GPU instances (requires single region)",
    ),
    discover: str = typer.Option(
        "",
        "--discover",
        help="Auto-discover instances by prefix (e.g., 'p5', 'g5') - requires single region",
    ),
    output: str = typer.Option("table", help="Output format (json or table)"),
):
    """
    Show capacity block availability in a calendar matrix view.

    Displays availability across dates and regions in a flight-booking style
    calendar, making it easy to spot patterns and compare options at a glance.

    Valid durations: 1-14 days (daily), or 21-182 days (7-day increments)

    Examples:
        # Single instance across regions
        aws-fleet-scout capacity calendar --instance-type p5.48xlarge

        # Discovery mode (single region, instances as rows)
        aws-fleet-scout capacity calendar --discover-p-series --regions us-east-1
        aws-fleet-scout capacity calendar --discover p5 --regions us-east-1

        # Multiple instances
        aws-fleet-scout capacity calendar --job-spec '{"p5.48xlarge": 2}' --regions us-east-1,us-west-2
    """
    region_list = parse_region_input(regions)
    capacity_calendar_main(
        instance_type=instance_type,
        job_spec=job_spec,
        duration=duration,
        window=window,
        regions=region_list,
        output=output,
        discover=discover,
        discover_p_series=discover_p_series,
        ctx=ctx,
    )


# ============================================================================
# FLEET COMMANDS
# ============================================================================


@fleet_app.command("pack")
def fleet_pack(
    ctx: typer.Context,
    job_spec: str = typer.Option(
        "",
        help='JSON string with instance requirements, e.g. \'{"m7i.4xlarge": 20, "p5.48xlarge": 2}\'',
    ),
    output: str = typer.Option("json", help="Output format (json or table)"),
    regions: str = typer.Option(
        "",
        help="Comma-separated AWS regions or wildcards (e.g. us-east-1,us-west-2 or us-*). If not set, defaults to all us-east-* and us-west-* regions.",
    ),
):
    """Find the best region for multi-instance fleet packing (Ray/Slurm/HPC jobs)."""
    region_list = parse_region_input(regions)
    fleetpacking_main(job_spec=job_spec, output=output, regions=region_list, ctx=ctx)


@fleet_app.command("recommend")
def fleet_recommend(
    ctx: typer.Context,
    instance: str = typer.Option("", help="Single instance type (e.g., 'm7i.4xlarge')"),
    count: int = typer.Option(1, help="Instance count for single instance type"),
    job_spec: str = typer.Option(
        "",
        help='JSON string with instance requirements, e.g. \'{"m7i.4xlarge": 20, "p5.48xlarge": 2}\'',
    ),
    min_score: float = typer.Option(5.0, help="Minimum acceptable spot placement score (0-10)"),
    regions: str = typer.Option("", help="Comma-separated AWS regions to check"),
    region_allowlist: str = typer.Option("", help="Comma-separated allowed regions"),
    region_denylist: str = typer.Option("", help="Comma-separated denied regions"),
    required_families: str = typer.Option(
        "", help="Comma-separated required instance families (e.g., 'm7i,p5')"
    ),
    gpu_families: str = typer.Option(
        "", help="Comma-separated required GPU families (e.g., 'p5,p4d')"
    ),
    network_adjacency: str = typer.Option(
        "", help="Preferred region for network adjacency (e.g., 'us-east-1')"
    ),
    output: str = typer.Option("table", help="Output format (json or table)"),
):
    """
    Recommend optimal placement with constraints (Spot-Aware Placement Engine).

    Returns ranked list of viable placement options based on constraints like
    min score threshold, instance families, region filters, network adjacency,
    and GPU availability.
    """
    placement_main(
        instance=instance,
        count=count,
        job_spec=job_spec,
        min_score=min_score,
        regions=regions,
        region_allowlist=region_allowlist,
        region_denylist=region_denylist,
        required_families=required_families,
        gpu_families=gpu_families,
        network_adjacency=network_adjacency,
        output=output,
        ctx=ctx,
    )


@fleet_app.command("utility")
def fleet_utility(
    ctx: typer.Context,
    job_spec: str = typer.Option(
        "",
        help='JSON string with instance requirements, e.g. \'{"m7i.4xlarge": 20, "p5.48xlarge": 2}\'',
    ),
    regions: str = typer.Option("", help="Comma-separated AWS regions to check"),
    spot_weight: float = typer.Option(0.5, help="Weight for spot stability score (0.0-1.0)"),
    price_weight: float = typer.Option(0.3, help="Weight for price consideration (0.0-1.0)"),
    latency_weight: float = typer.Option(0.2, help="Weight for latency penalty (0.0-1.0)"),
    base_region: str = typer.Option("", help="Reference region for latency calculations"),
    latency_penalty: float = typer.Option(0.3, help="Penalty for inter-region latency (0.0-1.0)"),
    output: str = typer.Option("table", help="Output format (json or table)"),
):
    """
    Calculate composite utility scores (Spot Score + Price + Latency).

    Combines spot stability scores, on-demand pricing, and latency penalties
    into a composite utility value for optimal region selection.
    """
    utility_main(
        job_spec=job_spec,
        regions=regions,
        spot_weight=spot_weight,
        price_weight=price_weight,
        latency_weight=latency_weight,
        base_region=base_region,
        latency_penalty=latency_penalty,
        output=output,
        ctx=ctx,
    )


# ============================================================================
# TOP-LEVEL COMMANDS
# ============================================================================


@app.command()
def interactive():
    """
    Launch interactive mode with guided menus.

    Provides a step-by-step interface to build and execute commands
    without needing to remember all the flags and options.
    """
    from .interactive import main as interactive_main

    interactive_main()


@app.command()
def compare(
    ctx: typer.Context,
    instance_type: str = typer.Option("", help="Single instance type (e.g., 'p5.48xlarge')"),
    job_spec: str = typer.Option(
        "", help="JSON string with instance requirements, e.g. '{\"p5.48xlarge\": 2}'"
    ),
    count: int = typer.Option(1, help="Instance count for single instance type"),
    duration: int = typer.Option(24, help="Capacity block duration in hours (default: 24)"),
    max_days: int = typer.Option(7, help="Capacity block search window in days (default: 7)"),
    regions: str = typer.Option(
        "", help="Comma-separated AWS regions or wildcards (e.g. us-east-1,us-west-2 or us-*)"
    ),
    discover_p_series: bool = typer.Option(
        False,
        "--discover-p-series",
        help="Auto-discover P4/P5/P6 GPU instances (shortcut for --discover p)",
    ),
    discover: str = typer.Option(
        "",
        "--discover",
        help="Auto-discover instances by prefix (e.g., 'p' for P-series, 'g' for G-series, 'm7i,c7i' for multiple)",
    ),
    output: str = typer.Option("table", help="Output format (json or table)"),
):
    """
    Compare all procurement methods: Spot, Capacity Blocks, and On-Demand.

    Shows side-by-side comparison of pricing, availability, and recommendations
    for all three ways to acquire EC2 instances.

    Examples:
        # Single instance type
        aws-fleet-scout compare --instance-type p5.48xlarge

        # Multiple instances
        aws-fleet-scout compare --instance-type p4d.24xlarge --count 4

        # Custom job spec
        aws-fleet-scout compare --job-spec '{"p5.48xlarge": 2}' --regions us-east-1,us-west-2

        # Auto-discover P-series (P4/P5/P6)
        aws-fleet-scout compare --discover-p-series --regions us-east-1,us-west-2

        # Auto-discover G-series GPU instances
        aws-fleet-scout compare --discover g --regions us-east-1

        # Auto-discover multiple families
        aws-fleet-scout compare --discover m7i,c7i,r7i --regions us-east-1
    """
    region_list = parse_region_input(regions)
    compare_main(
        instance_type=instance_type,
        job_spec=job_spec,
        count=count,
        duration=duration,
        max_days=max_days,
        output=output,
        regions=region_list,
        discover_p_series=discover_p_series,
        discover=discover,
        ctx=ctx,
    )


if __name__ == "__main__":
    app()

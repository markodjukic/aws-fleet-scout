import sys
import json
import typer
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from ...utils.aws_client import get_ec2_client, discover_instances_by_prefix
from ...utils.output import print_json_output
from ...config import DEFAULT_REGIONS


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
    window: int = 7,
    regions: List[str] = None,
    output: str = "table",
    discover: str = "",
    discover_p_series: bool = False,
    ctx: typer.Context = None
):
    """
    Show capacity block availability in a calendar matrix view.
    
    Displays availability across dates and regions in a flight-booking style
    calendar, making it easy to spot patterns and compare options at a glance.
    
    Valid durations: 1-14 days (daily), or 21-182 days (7-day increments)
    
    Args:
        instance_type: Single instance type (e.g., 'p5.48xlarge')
        job_spec: JSON string with instance requirements (e.g., '{"p5.48xlarge": 2}')
        duration: Desired duration in days (default: 1). Must be 1-14 daily, or 21-182 in 7-day steps
        window: Number of days ahead to search (default: 7)
        regions: List of AWS regions to check
        output: Output format (json or table)
        discover: Auto-discover instances by prefix (e.g., 'p5', 'g5') - requires single region
        discover_p_series: Auto-discover all P4/P5/P6 instances - requires single region
        ctx: Typer context for error handling
    """
    
    # Validate duration
    if not _is_valid_duration(duration):
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(f"\nError: Invalid duration {duration} days. Must be 1-14 daily, or 21-182 in 7-day increments.", err=True)
            raise typer.Exit(1)
        raise typer.BadParameter(f"Invalid duration {duration} days")
    
    # Convert days to hours for AWS API
    duration_hours = _days_to_hours(duration)
    
    if not regions:
        regions = DEFAULT_REGIONS
    
    # Parse input - discovery or explicit specification
    if discover or discover_p_series:
        # Discovery mode requires single region
        if len(regions) != 1:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo(f"\nError: Discovery mode requires exactly one region. Got {len(regions)}: {regions}", err=True)
                typer.echo("Hint: Use --regions us-east-1 (single region only)", err=True)
                raise typer.Exit(1)
            raise typer.BadParameter(f"Discovery mode requires exactly one region. Got {len(regions)}")
        
        # Determine prefixes to search for
        if discover:
            prefixes = [p.strip() for p in discover.split(',') if p.strip()]
            prefix_display = ', '.join(prefixes)
        else:
            prefixes = ['p4', 'p5', 'p6']
            prefix_display = 'P-series (P4/P5/P6)'
        
        if output != 'json':
            print(f"Discovering {prefix_display} instances in: {regions[0]}")
            print()
        
        discovered_instances = discover_instances_by_prefix(regions, prefixes)
        
        if not discovered_instances:
            if output != 'json':
                print(f"No instances matching prefixes {prefixes} found in {regions[0]}.")
            return {}
        
        if output != 'json':
            print(f"Found {len(discovered_instances)} instance types:")
            for itype in discovered_instances:
                print(f"  - {itype}")
            print()
        
        instance_requirements = {itype: 1 for itype in discovered_instances}
        discovery_mode = True
    elif instance_type:
        instance_requirements = {instance_type: 1}
        discovery_mode = False
    elif job_spec:
        try:
            instance_requirements = json.loads(job_spec)
        except json.JSONDecodeError as e:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo(f"\nError: Invalid job_spec JSON: {e}", err=True)
                raise typer.Exit(1)
            raise typer.BadParameter(f"Invalid job_spec JSON: {e}")
        discovery_mode = False
    else:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo("\nError: Either --instance-type, --job-spec, --discover, or --discover-p-series is required", err=True)
            raise typer.Exit(1)
        raise typer.BadParameter("Either --instance-type, --job-spec, --discover, or --discover-p-series is required")
    
    if output != 'json':
        print(f"Fetching capacity block calendar for: {instance_requirements}")
        print(f"Duration: {duration} days ({duration_hours} hours), Window: {window} days")
        print()
    
    # Query capacity blocks for each instance type
    calendar_data = {}
    
    for itype, count in instance_requirements.items():
        if output != 'json':
            print(f"Querying {count}x {itype}...")
        
        offerings = _query_capacity_blocks_by_date(
            instance_type=itype,
            instance_count=count,
            duration_hours=duration_hours,
            days=window,
            regions=regions,
            output=output
        )
        calendar_data[itype] = offerings
    
    # Format output
    if output == 'json':
        result_data = {
            "calendar": calendar_data,
            "duration_days": duration,
            "duration_hours": duration_hours,
            "window_days": window,
            "discovery_mode": discovery_mode
        }
        print_json_output(
            data=result_data,
            command="capacity.calendar",
            regions_checked=regions,
            metadata={
                "instance_requirements": instance_requirements,
                "duration_days": duration,
                "duration_hours": duration_hours,
                "window_days": window,
                "discovery_mode": discovery_mode
            }
        )
        return result_data
    else:
        # Calendar table format
        if discovery_mode:
            # Discovery mode: instances as rows, dates as columns (single region)
            _print_discovery_calendar_view(calendar_data, instance_requirements, duration, duration_hours, window, regions[0])
        else:
            # Normal mode: regions as rows, dates as columns
            _print_calendar_view(calendar_data, instance_requirements, duration, duration_hours, window, regions)
        return calendar_data


def _query_capacity_blocks_by_date(
    instance_type: str,
    instance_count: int,
    duration_hours: int,
    days: int,
    regions: List[str],
    output: str = 'table'
) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Query capacity blocks and organize by date and region.
    
    Returns:
        Dict mapping date_str -> region -> list of offerings
    """
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=days)
    
    # Structure: {date_str: {region: [offerings]}}
    offerings_by_date = defaultdict(lambda: defaultdict(list))
    
    for region in regions:
        try:
            client = get_ec2_client(region)
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=instance_count,
                CapacityDurationHours=duration_hours,
                StartDateRange=start_date,
                EndDateRange=end_date,
                MaxResults=100
            )
            
            offerings = response.get('CapacityBlockOfferings', [])
            
            for offering in offerings:
                # Group by date (ignore time for calendar view)
                offering_date = offering['StartDate'].date()
                date_str = offering_date.strftime('%Y-%m-%d')
                
                offerings_by_date[date_str][region].append({
                    'start_date': offering['StartDate'],
                    'duration_hours': offering['CapacityBlockDurationHours'],
                    'upfront_fee': float(offering['UpfrontFee']),
                    'offering_id': offering.get('CapacityBlockOfferingId', 'N/A'),
                    'availability_zone': offering.get('AvailabilityZone', 'N/A')
                })
            
            if output != 'json' and offerings:
                print(f"  ✓ Found {len(offerings)} offerings in {region}")
                
        except Exception as e:
            if output != 'json':
                print(f"  ✗ Error querying {region}: {e}")
    
    return dict(offerings_by_date)


def _print_calendar_view(  # pragma: no cover
    calendar_data: Dict[str, Dict[str, Dict[str, List[Dict]]]],
    instance_requirements: Dict[str, int],
    duration_days: int,
    duration_hours: int,
    days: int,
    regions: List[str]
):
    """Print calendar matrix view of capacity block availability."""
    
    console = Console()
    
    # Generate date range for columns
    today = datetime.now(timezone.utc).date()
    date_range = [today + timedelta(days=i) for i in range(days)]
    
    for instance_type, offerings_by_date in calendar_data.items():
        count = instance_requirements[instance_type]
        
        # Create calendar table
        table = Table(
            title=f"Capacity Block Calendar: {instance_type} (Qty: {count}, Duration: {duration_days}d/{duration_hours}hrs)",
            show_header=True,
            header_style="bold magenta"
        )
        
        # Add columns: Region + each date
        table.add_column("Region", style="cyan", width=15)
        for date in date_range:
            # Format: "Jan 23" or "Jan 23*" for today
            date_str = date.strftime("%b %d")
            if date == today:
                date_str += "*"
            table.add_column(date_str, justify="center", width=12)
        
        # Add rows for each region
        for region in regions:
            row = [region]
            
            for date in date_range:
                date_str = date.strftime('%Y-%m-%d')
                offerings = offerings_by_date.get(date_str, {}).get(region, [])
                
                if offerings:
                    # Find cheapest offering for this date/region
                    cheapest = min(offerings, key=lambda x: x['upfront_fee'])
                    price = cheapest['upfront_fee']
                    
                    # Format price compactly
                    if price >= 10000:
                        cell = f"${price/1000:.1f}K"
                    elif price >= 1000:
                        cell = f"${price/1000:.2f}K"
                    else:
                        cell = f"${price:.0f}"
                    
                    row.append(cell)
                else:
                    row.append("-")
            
            table.add_row(*row)
        
        console.print(table)
        console.print()
        
        # Summary statistics
        total_offerings = sum(
            len(offerings)
            for date_offerings in offerings_by_date.values()
            for offerings in date_offerings.values()
        )
        
        if total_offerings > 0:
            # Find best deal
            all_offerings = [
                (date_str, region, offering)
                for date_str, regions_dict in offerings_by_date.items()
                for region, offerings in regions_dict.items()
                for offering in offerings
            ]
            
            if all_offerings:
                best_date, best_region, best_offering = min(
                    all_offerings,
                    key=lambda x: (x[2]['start_date'], x[2]['upfront_fee'])
                )
                
                console.print(f"[bold green]✓ BEST DEAL:[/bold green] {best_region} on {best_date}")
                console.print(f"  Price: ${best_offering['upfront_fee']:.2f}")
                console.print(f"  Start: {best_offering['start_date'].strftime('%Y-%m-%d %H:%M UTC')}")
                console.print(f"  Offering ID: {best_offering['offering_id']}")
                console.print()
        else:
            console.print(f"[yellow]No capacity blocks available for {instance_type}[/yellow]")
            console.print()
    
    # Legend
    console.print("[dim]Legend: Price shown for cheapest offering, - = Not available, * = Today[/dim]")



def _print_discovery_calendar_view(  # pragma: no cover
    calendar_data: Dict[str, Dict[str, Dict[str, List[Dict]]]],
    instance_requirements: Dict[str, int],
    duration_days: int,
    duration_hours: int,
    days: int,
    region: str
):
    """Print calendar matrix view with instances as rows (discovery mode)."""
    
    console = Console()
    
    # Generate date range for columns
    today = datetime.now(timezone.utc).date()
    date_range = [today + timedelta(days=i) for i in range(days)]
    
    # Create calendar table with instances as rows
    table = Table(
        title=f"Capacity Block Calendar: {region} (Duration: {duration_days}d/{duration_hours}hrs)",
        show_header=True,
        header_style="bold magenta"
    )
    
    # Add columns: Instance Type + each date
    table.add_column("Instance Type", style="cyan", width=20)
    for date in date_range:
        # Format: "Jan 23" or "Jan 23*" for today
        date_str = date.strftime("%b %d")
        if date == today:
            date_str += "*"
        table.add_column(date_str, justify="center", width=12)
    
    # Add rows for each instance type
    for instance_type in sorted(instance_requirements.keys()):
        offerings_by_date = calendar_data.get(instance_type, {})
        row = [instance_type]
        
        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')
            offerings = offerings_by_date.get(date_str, {}).get(region, [])
            
            if offerings:
                # Find cheapest offering for this date
                cheapest = min(offerings, key=lambda x: x['upfront_fee'])
                price = cheapest['upfront_fee']
                
                # Format price compactly
                if price >= 10000:
                    cell = f"${price/1000:.1f}K"
                elif price >= 1000:
                    cell = f"${price/1000:.2f}K"
                else:
                    cell = f"${price:.0f}"
                
                row.append(cell)
            else:
                row.append("-")
        
        table.add_row(*row)
    
    console.print(table)
    console.print()
    
    # Summary statistics
    total_offerings = sum(
        len(offerings)
        for instance_type, offerings_by_date in calendar_data.items()
        for date_offerings in offerings_by_date.values()
        for offerings in date_offerings.values()
    )
    
    if total_offerings > 0:
        # Find best deal across all instance types
        all_offerings = [
            (instance_type, date_str, offering)
            for instance_type, offerings_by_date in calendar_data.items()
            for date_str, regions_dict in offerings_by_date.items()
            for offerings in regions_dict.values()
            for offering in offerings
        ]
        
        if all_offerings:
            best_instance, best_date, best_offering = min(
                all_offerings,
                key=lambda x: (x[2]['start_date'], x[2]['upfront_fee'])
            )
            
            console.print(f"[bold green]✓ BEST DEAL:[/bold green] {best_instance} on {best_date}")
            console.print(f"  Price: ${best_offering['upfront_fee']:.2f}")
            console.print(f"  Start: {best_offering['start_date'].strftime('%Y-%m-%d %H:%M UTC')}")
            console.print(f"  Offering ID: {best_offering['offering_id']}")
            console.print()
    else:
        console.print(f"[yellow]No capacity blocks available for any discovered instances[/yellow]")
        console.print()
    
    # Legend
    console.print("[dim]Legend: Price shown for cheapest offering, - = Not available, * = Today[/dim]")

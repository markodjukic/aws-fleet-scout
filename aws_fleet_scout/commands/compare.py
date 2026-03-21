
import sys
import json
import typer
from typing import List, Dict, Optional
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from ..utils.aws_client import get_ec2_client, get_pricing_client, check_on_demand_availability
from ..utils.output import print_json_output, print_error_output
from ..config import DEFAULT_REGIONS, PRICING_REGION_MAP

def main(
    instance_type: str = "",
    job_spec: str = "",
    count: int = 1,
    duration: int = 24,
    max_days: int = 7,
    output: str = "table",
    regions: List[str] = None,
    discover_p_series: bool = False,
    discover: str = "",
    ctx: typer.Context = None
):
    """
    Compare all procurement methods: Spot, Capacity Blocks, and On-Demand.
    
    Shows side-by-side comparison of:
    - Spot instances: dynamic pricing with placement scores
    - Capacity blocks: reserved capacity with upfront fees
    - On-demand: fixed hourly pricing (if available)
    
    Args:
        instance_type: Single instance type (e.g., 'p5.48xlarge')
        job_spec: JSON string with instance requirements
        count: Instance count for single instance type
        duration: Desired duration for capacity blocks (days: 1-14 daily, or 21-182 in 7-day increments)
        max_days: Search window for capacity blocks (days)
        output: Output format (json or table)
        regions: List of AWS regions to check
        discover_p_series: Auto-discover all P4/P5/P6 instances in regions (deprecated, use --discover p)
        discover: Auto-discover instances by prefix (e.g., 'p' for P-series, 'g' for G-series, 'm7i,c7i' for multiple)
        ctx: Typer context for CLI help display
    """
    
    # Parse input
    if discover or discover_p_series:
        if not regions:
            regions = DEFAULT_REGIONS
        
        # Determine prefixes to search for
        if discover:
            # Parse comma-separated prefixes
            prefixes = [p.strip() for p in discover.split(',') if p.strip()]
            prefix_display = ', '.join(prefixes)
        else:
            # Legacy --discover-p-series flag
            prefixes = ['p4', 'p5', 'p6']
            prefix_display = 'P-series (P4/P5/P6)'
        
        if output != 'json':
            print(f"Discovering {prefix_display} GPU instances in: {', '.join(regions)}")
            print()
        
        from ..utils.aws_client import discover_instances_by_prefix
        discovered_instances = discover_instances_by_prefix(regions, prefixes)
        
        if not discovered_instances:
            if output != 'json':
                print(f"No instances matching prefixes {prefixes} found in the specified regions.")
            return {}
        
        if output != 'json':
            print(f"Found {len(discovered_instances)} instance types:")
            for itype in discovered_instances:
                print(f"  - {itype}")
            print()
            if len(discovered_instances) > 10:
                print("⚠️  Warning: Discovering many instances may hit AWS API rate limits.")
                print("   If you see MaxConfigLimitExceeded errors, use more specific prefixes.")
                print()
                
                # Interactive confirmation for large discoveries
                import sys
                try:
                    response = input(f"Proceed with comparing {len(discovered_instances)} instance types? [y/N]: ")
                    if response.lower() not in ['y', 'yes']:
                        print("Cancelled.")
                        return {}
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return {}
                print()
        
        instance_requirements = {itype: 1 for itype in discovered_instances}
    elif instance_type:
        instance_requirements = {instance_type: count}
    elif job_spec:
        try:
            instance_requirements = json.loads(job_spec)
        except json.JSONDecodeError as e:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo(f"\nError: Invalid job_spec JSON: {e}", err=True)
                raise typer.Exit(1)
            raise typer.BadParameter(f"Invalid job_spec JSON: {e}")
    else:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo("\nError: Either --instance-type, --job-spec, --discover, or --discover-p-series is required", err=True)
            raise typer.Exit(1)
        raise typer.BadParameter("Either --instance-type, --job-spec, --discover, or --discover-p-series is required")
    
    if not regions:
        regions = DEFAULT_REGIONS
    
    # Only show progress messages for table output (keep stdout clean for JSON)
    if output != 'json':
        print(f"Comparing procurement methods for: {instance_requirements}")
        print(f"Regions: {', '.join(regions)}")
        print()
    
    # Collect data for all procurement methods
    results = {}
    
    for itype, qty in instance_requirements.items():
        if output != 'json':
            print(f"Analyzing {qty}x {itype}...")
        
        spot_data = _get_spot_data(itype, qty, regions)
        cb_data = _get_capacity_block_data(itype, qty, duration, max_days, regions)
        od_data = _get_on_demand_data(itype, regions)
        
        results[itype] = {
            'spot': spot_data,
            'capacity_blocks': cb_data,
            'on_demand': od_data,
            'quantity': qty
        }
    
    # Format output
    if output == 'json':
        print_json_output(
            data=results,
            command="compare",
            regions_checked=regions,
            metadata={
                "instance_requirements": instance_requirements,
                "duration_hours": duration,
                "max_days_ahead": max_days
            }
        )
        return results
    else:
        _print_comparison_table(results, instance_requirements, regions)
        return results


def _get_spot_data(instance_type: str, quantity: int, regions: List[str]) -> Dict:
    """Get spot pricing and placement scores."""
    
    best_spot = None
    
    try:
        client = get_ec2_client(regions[0])
        
        # Get spot placement scores across regions
        response = client.get_spot_placement_scores(
            InstanceTypes=[instance_type],
            TargetCapacity=quantity,
            TargetCapacityUnitType="units",
            RegionNames=regions,
            SingleAvailabilityZone=True
        )
        
        scores = response.get("SpotPlacementScores", [])
        
        if scores:
            # Find best score
            best_score_entry = max(scores, key=lambda x: x['Score'])
            region = best_score_entry['Region']
            
            # Get spot price for that region
            regional_client = get_ec2_client(region)
            price_response = regional_client.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=["Linux/UNIX"],
                MaxResults=10
            )
            
            prices = price_response.get("SpotPriceHistory", [])
            if prices:
                avg_price = sum(float(p['SpotPrice']) for p in prices[:5]) / min(5, len(prices))
                
                best_spot = {
                    'available': True,
                    'region': region,
                    'score': best_score_entry['Score'],
                    'price_per_hour': avg_price,
                    'total_hourly_cost': avg_price * quantity,
                    'availability_zone': best_score_entry.get('AvailabilityZoneId', 'N/A')
                }
    except Exception as e:
        print(f"  Warning: Could not fetch spot data: {e}")
    
    if not best_spot:
        best_spot = {
            'available': False,
            'region': 'N/A',
            'score': 0,
            'price_per_hour': None,
            'total_hourly_cost': None,
            'availability_zone': 'N/A'
        }
    
    return best_spot


def _get_capacity_block_data(
    instance_type: str,
    quantity: int,
    duration: int,
    max_days: int,
    regions: List[str]
) -> Dict:
    """Get capacity block offerings."""
    from datetime import timedelta
    
    best_cb = None
    all_offerings = []
    
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=max_days)
    
    for region in regions:
        try:
            client = get_ec2_client(region)
            response = client.describe_capacity_block_offerings(
                InstanceType=instance_type,
                InstanceCount=quantity,
                CapacityDurationHours=duration,
                StartDateRange=start_date,
                EndDateRange=end_date,
                MaxResults=50
            )
            
            offerings = response.get('CapacityBlockOfferings', [])
            for offering in offerings:
                all_offerings.append({
                    'region': region,
                    'start_date': offering['StartDate'],
                    'duration_hours': offering['CapacityBlockDurationHours'],
                    'upfront_fee': float(offering['UpfrontFee']),
                    'offering_id': offering.get('CapacityBlockOfferingId', 'N/A'),
                    'availability_zone': offering.get('AvailabilityZone', 'N/A')
                })
        except Exception:
            pass
    
    if all_offerings:
        # Find earliest/cheapest
        best_cb = min(all_offerings, key=lambda x: (x['start_date'], x['upfront_fee']))
        best_cb['available'] = True
        best_cb['hourly_equivalent'] = best_cb['upfront_fee'] / best_cb['duration_hours']
    else:
        best_cb = {
            'available': False,
            'region': 'N/A',
            'start_date': None,
            'duration_hours': None,
            'upfront_fee': None,
            'hourly_equivalent': None,
            'offering_id': None,
            'availability_zone': 'N/A'
        }
    
    return best_cb


def _get_on_demand_data(instance_type: str, regions: List[str]) -> Dict:
    """Get on-demand pricing and availability."""
    
    # Dynamically check if on-demand is available for this instance type
    availability = check_on_demand_availability(instance_type, regions)
    available_regions = [region for region, available in availability.items() if available]
    
    if not available_regions:
        return {
            'available': False,
            'region': 'Not Available',
            'price_per_hour': None,
            'note': 'This instance type is not available in the specified regions'
        }
    
    # Try to get pricing for first available region
    best_price = None
    best_region = available_regions[0]
    
    try:
        client = get_pricing_client('us-east-1')
        
        for region in available_regions:
            if region not in PRICING_REGION_MAP:
                continue
            
            location = PRICING_REGION_MAP[region]
            
            response = client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'}
                ],
                MaxResults=5
            )
            
            for price_item_str in response.get('PriceList', []):
                price_item = json.loads(price_item_str)
                attrs = price_item.get('product', {}).get('attributes', {})
                
                if (attrs.get('preInstalledSw', '').lower() in ['na', 'n/a', ''] and
                    attrs.get('capacitystatus', '').lower() == 'used'):
                    
                    terms = price_item.get('terms', {}).get('OnDemand', {})
                    if terms:
                        term_key = list(terms.keys())[0]
                        dims = terms[term_key].get('priceDimensions', {})
                        if dims:
                            dim_key = list(dims.keys())[0]
                            usd = dims[dim_key].get('pricePerUnit', {}).get('USD', '0')
                            price = float(usd)
                            if price > 0:
                                if best_price is None or price < best_price:
                                    best_price = price
                                    best_region = region
                                break
    except Exception as e:
        print(f"  Warning: Could not fetch on-demand pricing: {e}")
    
    if best_price:
        return {
            'available': True,
            'region': best_region,
            'price_per_hour': best_price,
            'note': 'Fixed pricing, guaranteed availability'
        }
    else:
        return {
            'available': True,
            'region': best_region,
            'price_per_hour': None,
            'note': 'Available but pricing data unavailable'
        }


def _print_comparison_table(results: Dict, requirements: Dict, regions: List[str]):  # pragma: no cover
    """Print comparison in table format."""
    
    console = Console()
    
    for instance_type, data in results.items():
        qty = data['quantity']
        spot = data['spot']
        cb = data['capacity_blocks']
        od = data['on_demand']
        
        table = Table(title=f"{instance_type} (Quantity: {qty})", show_header=True, header_style="bold magenta")
        table.add_column("Method", style="cyan", width=20)
        table.add_column("Available", justify="center", width=10)
        table.add_column("Region", style="yellow", width=15)
        table.add_column("Cost", style="green", width=35)
        table.add_column("Details", width=50)
        
        # Spot
        if spot['available']:
            cost_str = f"${spot['price_per_hour']:.4f}/hr (${spot['total_hourly_cost']:.2f}/hr total)"
            details = f"Score: {spot['score']}/10, AZ: {spot['availability_zone']}"
            available = "✓"
        else:
            cost_str = "N/A"
            details = "No availability"
            available = "✗"
        table.add_row("Spot Instances", available, spot['region'], cost_str, details)
        
        # Capacity Blocks
        if cb['available']:
            now = datetime.now(timezone.utc)
            time_until = (cb['start_date'] - now).total_seconds() / 3600
            start_str = "Immediate" if time_until <= 1 else cb['start_date'].strftime('%Y-%m-%d %H:%M UTC')
            cost_str = f"${cb['upfront_fee']:.2f} upfront (${cb['hourly_equivalent']:.2f}/hr)"
            details = f"Start: {start_str}, Duration: {cb['duration_hours']}hrs"
            available = "✓"
        else:
            cost_str = "N/A"
            details = "No offerings available"
            available = "✗"
        table.add_row("Capacity Blocks", available, cb['region'], cost_str, details)
        
        # On-Demand
        if od['available'] and od['price_per_hour']:
            cost_str = f"${od['price_per_hour']:.4f}/hr (${od['price_per_hour'] * qty:.2f}/hr total)"
            details = od['note']
            available = "✓"
        elif od['available']:
            cost_str = "Pricing unavailable"
            details = od['note']
            available = "✓"
        else:
            cost_str = "N/A"
            details = od['note']
            available = "✗"
        table.add_row("On-Demand", available, od['region'], cost_str, details)
        
        console.print(table)
        console.print()
    
    
    # Recommendations
    print("\nRECOMMENDATIONS:")
    for instance_type, data in results.items():
        spot = data['spot']
        cb = data['capacity_blocks']
        od = data['on_demand']
        
        print(f"\n{instance_type}:")
        
        if spot['available'] and spot['score'] >= 7:
            print(f"  ✓ BEST: Spot instances (Score: {spot['score']}/10, ${spot['total_hourly_cost']:.2f}/hr)")
            print(f"    - Lowest cost with high availability")
            print(f"    - Use capacity-optimized allocation strategy")
        elif cb['available']:
            print(f"  ✓ BEST: Capacity blocks (${cb['upfront_fee']:.2f} for {cb['duration_hours']}hrs)")
            print(f"    - Guaranteed capacity for scheduled workloads")
            print(f"    - Offering ID: {cb['offering_id']}")
        elif od['available'] and od['price_per_hour']:
            print(f"  ✓ BEST: On-demand (${od['price_per_hour']:.4f}/hr)")
            print(f"    - Guaranteed availability, no interruptions")
        else:
            print(f"  ✗ Limited availability - consider alternative regions or instance types")
    
    print()

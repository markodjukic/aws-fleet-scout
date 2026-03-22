import json
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from ...config import DEFAULT_REGIONS
from ...utils.aws_client import get_ec2_client
from ...utils.output import print_json_output


def main(
    job_spec: str = "",
    output: str = "json",
    regions: Optional[List[str]] = None,
    ctx: Optional[typer.Context] = None,
):
    """
    Multi-instance matchmaking (fleet packing) for mixed instance fleets.

    Finds the best single region that can satisfy multiple instance type requirements
    with acceptable spot placement scores.

    Args:
        job_spec: JSON string specifying instance requirements, e.g.:
                  '{"m7i.4xlarge": 20, "p5.48xlarge": 2}'
        output: Output format (json or table)
        regions: List of AWS regions to check
    """

    if not job_spec:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(
                '\nError: job_spec is required. Example: \'{"m7i.4xlarge": 20, "p5.48xlarge": 2}\'',
                err=True,
            )
            raise typer.Exit(1)
        raise typer.BadParameter(
            'job_spec is required. Example: \'{"m7i.4xlarge": 20, "p5.48xlarge": 2}\''
        )

    # Parse job specification
    try:
        job_requirements = json.loads(job_spec)
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

    if not regions:
        regions = DEFAULT_REGIONS

    if output != "json":
        print(f"Fleet Packing Analysis for job: {job_requirements}")
        print(f"Checking regions: {', '.join(regions)}")
        print()

    # Collect spot placement scores for each instance type
    client = get_ec2_client(regions[0])
    instance_scores = {}

    for instance_type, capacity in job_requirements.items():
        if output != "json":
            print(f"Querying spot placement scores for {capacity}x {instance_type}...")
        try:
            response = client.get_spot_placement_scores(
                InstanceTypes=[instance_type],
                TargetCapacity=capacity,
                TargetCapacityUnitType="units",
                RegionNames=regions,
                SingleAvailabilityZone=True,
            )
            instance_scores[instance_type] = response["SpotPlacementScores"]
        except Exception as e:
            print(f"Error fetching spot placement scores for {instance_type}: {e}")
            instance_scores[instance_type] = []

    # Compute aggregate scores per region
    region_scores = _compute_region_scores(instance_scores, job_requirements)

    # Sort by aggregate score descending
    sorted_regions = sorted(
        region_scores.items(), key=lambda x: x[1]["aggregate_score"], reverse=True
    )

    # Format output
    if output == "json":
        result_data = {
            "region_scores": [
                {
                    "region": region,
                    "aggregate_score": data["aggregate_score"],
                    "availability_zone_id": data["az_id"],
                    "instance_scores": data["instance_scores"],
                }
                for region, data in sorted_regions
            ],
            "best_region": sorted_regions[0][0] if sorted_regions else None,
            "best_score": sorted_regions[0][1]["aggregate_score"] if sorted_regions else None,
        }
        print_json_output(
            data=result_data,
            command="fleet.pack",
            regions_checked=regions,
            metadata={"job_requirements": job_requirements},
        )
        return result_data
    else:
        # Table format
        console = Console()
        table = Table(title="Fleet Packing Scores", show_header=True, header_style="bold magenta")
        table.add_column("Region", style="cyan", width=15)
        table.add_column("AZ ID", style="yellow", width=15)
        table.add_column("Aggregate Score", justify="right", style="green", width=15)
        table.add_column("Instance Scores", width=50)

        for region, data in sorted_regions:
            scores_str = ", ".join(
                [f"{itype}: {score}" for itype, score in data["instance_scores"].items()]
            )
            table.add_row(region, data["az_id"], f"{data['aggregate_score']:.2f}", scores_str)

        console.print(table)

        if sorted_regions:
            console.print(
                f"\n[bold green]Best region:[/bold green] {sorted_regions[0][0]} (aggregate score: {sorted_regions[0][1]['aggregate_score']:.2f})"
            )
        return sorted_regions


def _compute_region_scores(
    instance_scores: Dict[str, List[Dict]], job_requirements: Dict[str, int]
) -> Dict[str, Dict]:
    """
    Compute aggregate scores for each region based on all instance type requirements.

    Strategy: For each region, find the best AZ that can accommodate all instance types,
    and compute a weighted average score.

    Args:
        instance_scores: Dict mapping instance_type to list of spot placement scores
        job_requirements: Dict mapping instance_type to required quantity

    Returns:
        Dict mapping region to {aggregate_score, az_id, instance_scores}
    """
    region_data: Dict[Tuple[str, str], Dict[str, float]] = {}

    # Group scores by region and AZ
    for instance_type, scores in instance_scores.items():
        for score_entry in scores:
            region = score_entry["Region"]
            az_id = score_entry["AvailabilityZoneId"]
            score = score_entry["Score"]

            key = (region, az_id)
            if key not in region_data:
                region_data[key] = {}
            region_data[key][instance_type] = score

    # Compute aggregate scores for each region
    result: Dict[str, Dict] = {}
    for (region, az_id), scores_dict in region_data.items():
        # Check if this region/AZ has scores for all required instance types
        missing_types = set(job_requirements.keys()) - set(scores_dict.keys())
        if missing_types:
            # Skip this region/AZ if it doesn't have all instance types
            continue

        # Compute weighted average score (weighted by capacity)
        total_capacity = sum(job_requirements.values())
        weighted_sum = sum(
            scores_dict[itype] * job_requirements[itype] for itype in job_requirements
        )
        aggregate_score = weighted_sum / total_capacity if total_capacity > 0 else 0

        # Keep the best AZ per region
        if region not in result or aggregate_score > result[region]["aggregate_score"]:
            result[region] = {
                "aggregate_score": aggregate_score,
                "az_id": az_id,
                "instance_scores": scores_dict,
            }

    return result

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from ...config import DEFAULT_REGIONS
from ...utils.output import print_json_output

# Constants
NETWORK_ADJACENCY_BOOST = 0.5  # Score boost for network adjacency preference


class GPUFamily(Enum):
    """GPU instance families supported by the placement engine."""

    P4D = "p4d"
    P5 = "p5"
    P5E = "p5e"
    I4 = "i4"
    G5 = "g5"
    G6 = "g6"


@dataclass
class PlacementConstraints:
    """
    Constraints for placement recommendation.

    Attributes:
        min_score_threshold: Minimum acceptable spot placement score (0-10)
        required_instance_families: List of instance families that must be available (e.g., ['m7i', 'p5'])
        region_allowlist: List of regions to consider (None = all regions)
        region_denylist: List of regions to exclude
        network_adjacency: Region preference for network adjacency (e.g., same region for EFS/FSx)
        max_price_deviation: Maximum acceptable price deviation from cheapest option (as percentage, e.g., 20.0 for 20%)
        gpu_families: List of GPU families required (if any)
        network_boost: Score boost for preferred network adjacency region (default: 0.5)
    """

    min_score_threshold: float = 5.0
    required_instance_families: Optional[List[str]] = None
    region_allowlist: Optional[List[str]] = None
    region_denylist: Optional[List[str]] = None
    network_adjacency: Optional[str] = None  # Preferred region for network adjacency
    max_price_deviation: Optional[float] = None  # Percentage (e.g., 20.0 for 20%)
    gpu_families: Optional[List[str]] = None
    network_boost: float = NETWORK_ADJACENCY_BOOST


@dataclass
class PlacementOption:
    """
    A viable placement option with all relevant details.

    Attributes:
        region: AWS region name
        availability_zone_id: Availability zone ID
        aggregate_score: Weighted average spot placement score
        instance_scores: Dict mapping instance type to individual scores
        predicted_stability: Stability prediction based on score (High/Medium/Low)
        price_estimate: Optional price estimate if pricing data available
    """

    region: str
    availability_zone_id: str
    aggregate_score: float
    instance_scores: Dict[str, float]
    predicted_stability: str
    price_estimate: Optional[float] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def _classify_stability(score: float) -> str:
    """
    Classify predicted stability based on spot placement score.

    Args:
        score: Spot placement score (0-10)

    Returns:
        Stability classification: High, Medium, or Low
    """
    if score >= 8.0:
        return "High"
    elif score >= 6.0:
        return "Medium"
    else:
        return "Low"


def _extract_instance_family(instance_type: str) -> str:
    """
    Extract instance family from instance type.

    Args:
        instance_type: EC2 instance type (e.g., 'm7i.4xlarge')

    Returns:
        Instance family (e.g., 'm7i')
    """
    # Instance type format: family.size (e.g., m7i.4xlarge)
    return instance_type.split(".")[0] if "." in instance_type else instance_type


def _has_gpu_family(instance_type: str, gpu_families: List[str]) -> bool:
    """
    Check if instance type belongs to any of the specified GPU families.

    Args:
        instance_type: EC2 instance type
        gpu_families: List of GPU family strings

    Returns:
        True if instance belongs to one of the GPU families
    """
    family = _extract_instance_family(instance_type).lower()
    return any(family.startswith(gpu.lower()) for gpu in gpu_families)


def _apply_constraints(
    region_scores: List[Dict], job_requirements: Dict[str, int], constraints: PlacementConstraints
) -> List[PlacementOption]:
    """
    Filter and transform region scores based on constraints.

    This function applies all placement constraints to filter out regions that don't
    meet the specified criteria, and creates PlacementOption objects for viable regions.

    Constraints applied:
    - Minimum spot placement score threshold
    - Region allowlist/denylist filtering
    - Required instance family validation
    - GPU family requirements
    - Network adjacency preference (adds score boost)

    Args:
        region_scores: List of region score dicts from FleetPacking
        job_requirements: Dict mapping instance type to quantity
        constraints: PlacementConstraints object with filtering criteria

    Returns:
        List of viable PlacementOption objects, sorted by aggregate score descending
    """
    viable_options = []

    for region_data in region_scores:
        region = region_data["region"]
        score = region_data["aggregate_score"]

        # Apply min score threshold
        if score < constraints.min_score_threshold:
            continue

        # Apply region allowlist
        if constraints.region_allowlist and region not in constraints.region_allowlist:
            continue

        # Apply region denylist
        if constraints.region_denylist and region in constraints.region_denylist:
            continue

        # Check required instance families
        if constraints.required_instance_families:
            instance_families = set(_extract_instance_family(it) for it in job_requirements.keys())
            required_families = set(constraints.required_instance_families)
            if not required_families.issubset(instance_families):
                continue

        # Check GPU families if specified
        if constraints.gpu_families:
            has_required_gpu = any(
                _has_gpu_family(instance_type, constraints.gpu_families)
                for instance_type in job_requirements.keys()
            )
            if not has_required_gpu:
                continue

        # Create placement option
        option = PlacementOption(
            region=region,
            availability_zone_id=region_data["availability_zone_id"],
            aggregate_score=score,
            instance_scores=region_data["instance_scores"],
            predicted_stability=_classify_stability(score),
        )

        viable_options.append(option)

    # Apply network adjacency preference (boost score for preferred region)
    if constraints.network_adjacency:
        for option in viable_options:
            if option.region == constraints.network_adjacency:
                # Boost score for network adjacency using configurable boost factor
                option.aggregate_score += constraints.network_boost

    # Sort by aggregate score descending
    viable_options.sort(key=lambda x: x.aggregate_score, reverse=True)

    return viable_options


def recommend_placement(
    instance: str = None,
    count: int = 1,
    job_spec: Dict[str, int] = None,
    constraints: PlacementConstraints = None,
    regions: List[str] = None,
    output: str = "json",
    ctx: typer.Context = None,
) -> Optional[List[PlacementOption]]:
    """
    Recommend optimal placement options based on constraints.

    This function serves as a drop-in decision helper for orchestration systems,
    providing ranked placement recommendations based on spot stability scores
    and configurable constraints.

    Args:
        instance: Single instance type (alternative to job_spec)
        count: Instance count for single instance type
        job_spec: Dict mapping instance types to quantities (alternative to instance/count)
        constraints: PlacementConstraints object with filtering criteria
        regions: List of AWS regions to check
        output: Output format (json or table)

    Returns:
        List of PlacementOption objects sorted by predicted stability, or None on error

    Example:
        # Simple usage
        options = recommend_placement(instance="m7i.4xlarge", count=40)

        # With constraints
        constraints = PlacementConstraints(
            min_score_threshold=7.0,
            region_allowlist=["us-east-1", "us-west-2"],
            gpu_families=["p5"]
        )
        options = recommend_placement(
            job_spec={"m7i.4xlarge": 20, "p5.48xlarge": 2},
            constraints=constraints
        )
    """
    from .pack import main as fleet_packing

    # Determine job specification
    if job_spec is None:
        if instance is None:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo("\nError: Either 'instance' or 'job_spec' must be provided", err=True)
                raise typer.Exit(1)
            raise typer.BadParameter("Either 'instance' or 'job_spec' must be provided")
        job_spec = {instance: count}

    # Use default constraints if none provided
    if constraints is None:
        constraints = PlacementConstraints()

    # Default regions
    if not regions:
        regions = DEFAULT_REGIONS

    if output != "json":
        print(f"Analyzing placement options for: {job_spec}")
        print(f"Constraints: min_score={constraints.min_score_threshold}")
        if constraints.region_allowlist:
            print(f"  Allowed regions: {', '.join(constraints.region_allowlist)}")
        if constraints.region_denylist:
            print(f"  Denied regions: {', '.join(constraints.region_denylist)}")
        if constraints.network_adjacency:
            print(f"  Network adjacency preference: {constraints.network_adjacency}")
        print()

    # Get fleet packing results
    job_spec_str = json.dumps(job_spec)
    result = fleet_packing(job_spec=job_spec_str, output="json", regions=regions)

    if not result or not result.get("region_scores"):
        typer.echo("Error: No placement options found", err=True)
        raise typer.Exit(1)

    # Apply constraints and get viable options
    viable_options = _apply_constraints(result["region_scores"], job_spec, constraints)

    if not viable_options:
        if output != "json":
            typer.echo(
                f"Error: No viable options found with constraints (min_score >= {constraints.min_score_threshold})",
                err=True,
            )
        raise typer.Exit(1)

    # Format output
    if output == "json":
        result_data = {
            "viable_options": [opt.to_dict() for opt in viable_options],
            "recommended": viable_options[0].to_dict() if viable_options else None,
        }
        print_json_output(
            data=result_data,
            command="fleet.recommend",
            regions_checked=regions,
            metadata={"job_spec": job_spec, "constraints": asdict(constraints)},
        )
    else:
        # Table format
        console = Console()
        table = Table(title="Placement Options", show_header=True, header_style="bold magenta")
        table.add_column("Rank", justify="right", width=6)
        table.add_column("Region", style="cyan", width=15)
        table.add_column("AZ ID", style="yellow", width=15)
        table.add_column("Score", justify="right", style="green", width=8)
        table.add_column("Stability", width=12)
        table.add_column("Instance Scores", width=50)

        for idx, option in enumerate(viable_options, 1):
            scores_str = ", ".join(
                [f"{itype}: {score}" for itype, score in option.instance_scores.items()]
            )
            table.add_row(
                str(idx),
                option.region,
                option.availability_zone_id,
                f"{option.aggregate_score:.2f}",
                option.predicted_stability,
                scores_str,
            )

        console.print(table)

        if viable_options:
            best = viable_options[0]
            console.print(
                f"\n[bold green]✓ RECOMMENDED:[/bold green] {best.region} (score: {best.aggregate_score:.2f}, stability: {best.predicted_stability})"
            )

    return viable_options


def main(
    instance: str = "",
    count: int = 1,
    job_spec: str = "",
    min_score: float = 5.0,
    regions: str = "",
    region_allowlist: str = "",
    region_denylist: str = "",
    required_families: str = "",
    gpu_families: str = "",
    network_adjacency: str = "",
    output: str = "json",
    ctx: typer.Context = None,
):
    """
    CLI entry point for placement recommendation.

    Args:
        instance: Single instance type
        count: Instance count for single instance type
        job_spec: JSON string with instance requirements
        min_score: Minimum acceptable spot score
        regions: Comma-separated regions to check
        region_allowlist: Comma-separated allowed regions
        region_denylist: Comma-separated denied regions
        required_families: Comma-separated required instance families
        gpu_families: Comma-separated required GPU families
        network_adjacency: Preferred region for network adjacency
        output: Output format (json or table)
        ctx: Typer context for CLI help display
    """
    # Parse job spec
    job_spec_dict = None
    if job_spec:
        try:
            job_spec_dict = json.loads(job_spec)
        except json.JSONDecodeError as e:
            if ctx:
                typer.echo(ctx.get_help())
                typer.echo(f"\nError: Invalid job_spec JSON: {e}", err=True)
                raise typer.Exit(1)
            raise typer.BadParameter(f"Invalid job_spec JSON: {e}")

    # Parse regions
    region_list = [r.strip() for r in regions.split(",") if r.strip()] if regions else None

    # Build constraints
    constraints = PlacementConstraints(
        min_score_threshold=min_score,
        required_instance_families=(
            [f.strip() for f in required_families.split(",") if f.strip()]
            if required_families
            else None
        ),
        region_allowlist=(
            [r.strip() for r in region_allowlist.split(",") if r.strip()]
            if region_allowlist
            else None
        ),
        region_denylist=(
            [r.strip() for r in region_denylist.split(",") if r.strip()]
            if region_denylist
            else None
        ),
        network_adjacency=network_adjacency if network_adjacency else None,
        gpu_families=(
            [g.strip() for g in gpu_families.split(",") if g.strip()] if gpu_families else None
        ),
    )

    return recommend_placement(
        instance=instance if instance else None,
        count=count,
        job_spec=job_spec_dict,
        constraints=constraints,
        regions=region_list,
        output=output,
        ctx=ctx,
    )

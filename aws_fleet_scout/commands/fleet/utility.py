import json
import logging
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from ...config import DEFAULT_REGIONS
from ...utils.output import print_json_output

# Constants
WEIGHT_SUM_TOLERANCE = 0.01  # Tolerance for weight sum validation
DEFAULT_INTER_REGION_PENALTY = 0.3  # 30% penalty for different regions
DEFAULT_EGRESS_COST_PER_GB = 0.02  # $0.02/GB default

# AWS region name mapping for Pricing API
AWS_REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-central-1": "EU (Frankfurt)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "sa-east-1": "South America (Sao Paulo)",
    "ca-central-1": "Canada (Central)",
}

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class UtilityWeights:
    """
    Weights for composite utility calculation.

    Attributes:
        spot_stability_weight: Weight for spot stability score (0.0 - 1.0)
        price_weight: Weight for price consideration (0.0 - 1.0)
        latency_weight: Weight for latency/egress penalty (0.0 - 1.0)

    Note: Weights should sum to 1.0 for normalized utility scores
    """

    spot_stability_weight: float = 0.5
    price_weight: float = 0.3
    latency_weight: float = 0.2

    def __post_init__(self):
        """Validate that weights sum to approximately 1.0."""
        total = self.spot_stability_weight + self.price_weight + self.latency_weight
        if not (1.0 - WEIGHT_SUM_TOLERANCE <= total <= 1.0 + WEIGHT_SUM_TOLERANCE):
            raise ValueError(f"Weights must sum to 1.0 (±{WEIGHT_SUM_TOLERANCE}), got {total}")


@dataclass
class LatencyConfig:
    """
    Configuration for latency/egress penalties.

    Attributes:
        base_region: Reference region for latency calculations
        inter_region_penalty: Penalty for different regions (0.0 - 1.0), default 0.3
        egress_cost_per_gb: Estimated egress cost per GB for inter-region transfers, default $0.02
    """

    base_region: Optional[str] = None
    inter_region_penalty: float = DEFAULT_INTER_REGION_PENALTY
    egress_cost_per_gb: float = DEFAULT_EGRESS_COST_PER_GB


@dataclass
class CompositeUtility:
    """
    Composite utility value combining multiple factors.

    Attributes:
        region: AWS region
        availability_zone_id: Availability zone ID
        spot_score: Spot placement score (0-10)
        price_score: Normalized price score (0-10, higher is better/cheaper)
        latency_score: Latency score (0-10, higher is better/closer)
        composite_utility: Final weighted utility value (0-10)
        on_demand_price: On-demand price per hour (if available)
        estimated_hourly_cost: Estimated total hourly cost for the fleet
        price_percentile: Price percentile compared to other regions (0-100)
    """

    region: str
    availability_zone_id: str
    spot_score: float
    price_score: float
    latency_score: float
    composite_utility: float
    on_demand_price: Optional[float] = None
    estimated_hourly_cost: Optional[float] = None
    price_percentile: Optional[float] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def _get_on_demand_price(instance_type: str, region: str) -> Optional[float]:
    """
    Fetch on-demand price for an instance type in a region.

    Args:
        instance_type: EC2 instance type
        region: AWS region

    Returns:
        Hourly on-demand price in USD, or None if unavailable
    """
    from botocore.exceptions import BotoCoreError, ClientError

    from ...utils.aws_client import get_pricing_client

    try:
        # Use AWS Pricing API
        pricing_client = get_pricing_client("us-east-1")

        # Map region to pricing API region name
        location = AWS_REGION_NAMES.get(region)
        if not location:
            logger.warning(f"Region {region} not found in AWS_REGION_NAMES mapping")
            return None

        # Query pricing
        response = pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            ],
            MaxResults=1,
        )

        if not response["PriceList"]:
            return None

        # Parse pricing data
        price_item = json.loads(response["PriceList"][0])
        on_demand = price_item["terms"]["OnDemand"]
        price_dimensions = list(on_demand.values())[0]["priceDimensions"]
        price_per_unit = list(price_dimensions.values())[0]["pricePerUnit"]["USD"]

        return float(price_per_unit)

    except ClientError as e:
        logger.warning(f"AWS API error fetching price for {instance_type} in {region}: {e}")
        return None
    except BotoCoreError as e:
        logger.warning(f"BotoCore error fetching price for {instance_type} in {region}: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.warning(f"Error parsing pricing data for {instance_type} in {region}: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid price value for {instance_type} in {region}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching price for {instance_type} in {region}: {e}")
        return None


def _calculate_price_score(prices: List[float], current_price: float) -> Tuple[float, float]:
    """
    Calculate normalized price score and percentile.

    Args:
        prices: List of all prices across regions
        current_price: Price for current region

    Returns:
        Tuple of (price_score 0-10, percentile 0-100)
    """
    if not prices or current_price is None:
        return 5.0, 50.0  # Default neutral score

    min_price = min(prices)
    max_price = max(prices)

    if min_price == max_price:
        return 10.0, 50.0  # All same price

    # Score: 10 for cheapest, 0 for most expensive
    price_score = 10.0 * (1.0 - (current_price - min_price) / (max_price - min_price))

    # Percentile: what % of regions are more expensive
    cheaper_count = sum(1 for p in prices if p < current_price)
    percentile = (cheaper_count / len(prices)) * 100.0

    return price_score, percentile


def _calculate_latency_score(region: str, config: LatencyConfig) -> float:
    """
    Calculate latency score based on network proximity.

    Args:
        region: Target region
        config: Latency configuration

    Returns:
        Latency score (0-10, higher is better)
    """
    if not config.base_region:
        return 10.0  # No preference, perfect score

    if region == config.base_region:
        return 10.0  # Same region, perfect score

    # Different region: apply penalty
    penalty = config.inter_region_penalty
    score = 10.0 * (1.0 - penalty)

    return max(0.0, score)


def calculate_composite_utility(
    job_spec: Dict[str, int],
    region_scores: List[Dict],
    weights: UtilityWeights = None,
    latency_config: LatencyConfig = None,
    include_pricing: bool = True,
) -> List[CompositeUtility]:
    """
    Calculate composite utility values for all regions.

    Args:
        job_spec: Dict mapping instance types to quantities
        region_scores: List of region score dicts from FleetPacking
        weights: UtilityWeights for composite calculation
        latency_config: Latency configuration
        include_pricing: Whether to fetch and include pricing data

    Returns:
        List of CompositeUtility objects sorted by composite utility descending
    """
    if weights is None:
        weights = UtilityWeights()

    if latency_config is None:
        latency_config = LatencyConfig()

    # Collect pricing data if requested
    region_prices = {}
    all_prices = []

    if include_pricing:
        print("Fetching pricing data...")
        for region_data in region_scores:
            region = region_data["region"]
            total_price = 0.0
            price_available = True

            # Calculate total hourly cost for the job spec
            for instance_type, quantity in job_spec.items():
                price = _get_on_demand_price(instance_type, region)
                if price is None:
                    price_available = False
                    break
                total_price += price * quantity

            if price_available:
                region_prices[region] = total_price
                all_prices.append(total_price)
            else:
                region_prices[region] = None

    # Calculate composite utilities
    utilities = []

    for region_data in region_scores:
        region = region_data["region"]
        spot_score = region_data["aggregate_score"]

        # Price score
        price = region_prices.get(region)
        if price and all_prices:
            price_score, percentile = _calculate_price_score(all_prices, price)
        else:
            price_score, percentile = 5.0, 50.0  # Neutral if no pricing

        # Latency score
        latency_score = _calculate_latency_score(region, latency_config)

        # Composite utility (weighted average)
        composite = (
            weights.spot_stability_weight * spot_score
            + weights.price_weight * price_score
            + weights.latency_weight * latency_score
        )

        utility = CompositeUtility(
            region=region,
            availability_zone_id=region_data["availability_zone_id"],
            spot_score=spot_score,
            price_score=price_score,
            latency_score=latency_score,
            composite_utility=composite,
            on_demand_price=price,
            estimated_hourly_cost=price,
            price_percentile=percentile if price else None,
        )

        utilities.append(utility)

    # Sort by composite utility descending
    utilities.sort(key=lambda x: x.composite_utility, reverse=True)

    return utilities


def main(
    job_spec: str = "",
    regions: str = "",
    spot_weight: float = 0.5,
    price_weight: float = 0.3,
    latency_weight: float = 0.2,
    base_region: str = "",
    latency_penalty: float = 0.3,
    output: str = "json",
    ctx: typer.Context = None,
):
    """
    Calculate composite utility scores for fleet placement.

    Args:
        job_spec: JSON string with instance requirements
        regions: Comma-separated regions to check
        spot_weight: Weight for spot stability (0.0-1.0)
        price_weight: Weight for price (0.0-1.0)
        latency_weight: Weight for latency (0.0-1.0)
        base_region: Reference region for latency calculations
        latency_penalty: Penalty for inter-region latency (0.0-1.0)
        output: Output format (json or table)
        ctx: Typer context for CLI help display
    """
    from .pack import main as fleet_packing

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

    # Parse job spec
    try:
        job_requirements = json.loads(job_spec)
    except json.JSONDecodeError as e:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(f"\nError: Invalid job_spec JSON: {e}", err=True)
            raise typer.Exit(1)
        raise typer.BadParameter(f"Invalid job_spec JSON: {e}")

    # Parse regions
    region_list = [r.strip() for r in regions.split(",") if r.strip()] if regions else None

    # Create weights
    try:
        weights = UtilityWeights(
            spot_stability_weight=spot_weight,
            price_weight=price_weight,
            latency_weight=latency_weight,
        )
    except ValueError as e:
        if ctx:
            typer.echo(ctx.get_help())
            typer.echo(f"\nError: {e}", err=True)
            raise typer.Exit(1)
        raise typer.BadParameter(str(e))

    # Create latency config
    latency_config = LatencyConfig(
        base_region=base_region if base_region else None, inter_region_penalty=latency_penalty
    )

    if output != "json":
        print(f"Calculating composite utility for: {job_requirements}")
        print(f"Weights: spot={spot_weight}, price={price_weight}, latency={latency_weight}")
        if base_region:
            print(f"Base region for latency: {base_region}")
        print()

    # Get fleet packing results
    result = fleet_packing(job_spec=job_spec, output="json", regions=region_list)

    if not result or not result.get("region_scores"):
        typer.echo("Error: No regions found", err=True)
        raise typer.Exit(1)

    # Calculate composite utilities
    utilities = calculate_composite_utility(
        job_spec=job_requirements,
        region_scores=result["region_scores"],
        weights=weights,
        latency_config=latency_config,
        include_pricing=True,
    )

    if not utilities:
        typer.echo("Error: No utility scores calculated", err=True)
        raise typer.Exit(1)

    # Format output
    if output == "json":
        result_data = {
            "utilities": [u.to_dict() for u in utilities],
            "best_region": utilities[0].region if utilities else None,
            "best_utility": utilities[0].composite_utility if utilities else None,
        }
        print_json_output(
            data=result_data,
            command="fleet.utility",
            regions_checked=regions,
            metadata={
                "job_requirements": job_requirements,
                "weights": asdict(weights),
                "latency_config": asdict(latency_config),
            },
        )
    else:
        # Table format
        console = Console()
        table = Table(
            title="Composite Utility Rankings", show_header=True, header_style="bold magenta"
        )
        table.add_column("Region", style="cyan", width=15)
        table.add_column("Spot", justify="right", style="green", width=8)
        table.add_column("Price", justify="right", style="green", width=8)
        table.add_column("Latency", justify="right", style="green", width=8)
        table.add_column("Utility", justify="right", style="bold green", width=8)
        table.add_column("Cost/hr", justify="right", width=12)
        table.add_column("Percentile", justify="right", width=10)

        for u in utilities:
            cost_str = f"${u.estimated_hourly_cost:.2f}" if u.estimated_hourly_cost else "N/A"
            percentile_str = f"{u.price_percentile:.0f}%" if u.price_percentile else "N/A"
            table.add_row(
                u.region,
                f"{u.spot_score:.2f}",
                f"{u.price_score:.2f}",
                f"{u.latency_score:.2f}",
                f"{u.composite_utility:.2f}",
                cost_str,
                percentile_str,
            )

        console.print(table)

        if utilities:
            best = utilities[0]
            console.print(
                f"\n[bold green]✓ BEST UTILITY:[/bold green] {best.region} (composite: {best.composite_utility:.2f}/10)"
            )
            if best.estimated_hourly_cost:
                console.print(f"  Estimated cost: ${best.estimated_hourly_cost:.2f}/hour")

    return utilities


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Simple CLI test
        main(job_spec=sys.argv[1], output="table")

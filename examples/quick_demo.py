#!/usr/bin/env python3
"""
AWS Fleet Scout - Comprehensive Demo

This script demonstrates all key functionality of aws-fleet-scout package:
1. Spot Placement Scores
2. Fleet Packing (Multi-Instance Matchmaking)
3. Spot-Aware Placement Engine (with Constraints)
4. Composite Utility Scoring
5. Instance Type Discovery

QUICK START:
============
To run this demo locally:

1. Create and activate a virtual environment:
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv/Scripts/activate

2. Install the package locally in development mode:
   pip install -e .

3. Configure AWS credentials (choose one):
   - Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
   - Use AWS CLI: aws configure
   - Create .env file with credentials (see aws_fleet_scout/.env example)
   - Use IAM roles (if running on EC2)

4. Run the demo:
   python examples/quick_demo.py

Note: This demo makes actual AWS API calls and requires valid AWS credentials.
The demo will query real AWS spot placement scores and instance availability.
"""

import json
import sys


def demo_spot_scores():
    """Demo 1: Query spot placement scores for a single instance type."""
    from aws_fleet_scout.commands.spot.score import main as spot_score

    print("\n" + "=" * 80)
    print("DEMO 1: Spot Placement Scores")
    print("=" * 80)
    print("\nQuery spot placement scores for a single instance type across regions.")
    print("This helps determine availability and capacity for specific instance types.\n")

    try:
        print("Querying spot scores for m7i.4xlarge with target capacity of 10...")
        scores = spot_score(
            instance_type="m7i.4xlarge",
            target_capacity=10,
            output="table",
            regions=["us-east-1", "us-east-2", "us-west-1", "us-west-2"],
        )

        if scores:
            print(f"\n✓ Found spot placement scores for {len(scores)} availability zones")

    except Exception as e:
        print(f"Error: {e}")
        print("Ensure AWS credentials are configured and you have EC2 permissions.")


def demo_fleet_packing():
    """Demo 2: Multi-instance fleet packing."""
    from aws_fleet_scout.commands.fleet.pack import main as fleet_packing

    print("\n" + "=" * 80)
    print("DEMO 2: Fleet Packing (Multi-Instance Matchmaking)")
    print("=" * 80)
    print("\nFind the best region for mixed instance type deployments.")
    print("Ideal for Ray, Slurm, HPC, and distributed computing workloads.\n")

    try:
        job_spec = {"m7i.4xlarge": 5, "c6i.8xlarge": 3}
        print(f"Job specification: {job_spec}")
        print("Finding best region...\n")

        result = fleet_packing(
            job_spec=json.dumps(job_spec),
            output="table",
            regions=["us-east-1", "us-east-2", "us-west-1", "us-west-2"],
        )

        if result and result.get("best_region") and result.get("best_score") is not None:
            print(
                f"\n✓ Best region identified: {result.get('best_region')} (score: {result.get('best_score'):.2f})"
            )

    except Exception as e:
        print(f"Error: {e}")
        print("Ensure AWS credentials are configured.")


def demo_placement_engine():
    """Demo 3: Spot-Aware Placement Engine with constraints."""
    from aws_fleet_scout import PlacementConstraints, recommend_placement

    print("\n" + "=" * 80)
    print("DEMO 3: Spot-Aware Placement Engine (with Constraints)")
    print("=" * 80)
    print("\nGet ranked placement recommendations with configurable constraints.")
    print("Filter by min score, instance families, regions, GPU types, and more.\n")

    try:
        # Example 1: Basic recommendation
        print("Example 3a: Basic recommendation for single instance type")
        print("-" * 60)
        options = recommend_placement(instance="m6i.2xlarge", count=5, output="table")

        if options and len(options) > 0:
            print(f"\n✓ Found {len(options)} viable placement options")
            print(
                f"  Top recommendation: {options[0].region} ({options[0].predicted_stability} stability)"
            )

        # Example 2: With constraints
        print("\n\nExample 3b: Placement with constraints")
        print("-" * 60)
        constraints = PlacementConstraints(
            min_score_threshold=6.0, region_allowlist=["us-east-1", "us-east-2", "us-west-2"]
        )

        print(
            f"Constraints: min_score={constraints.min_score_threshold}, allowed_regions={constraints.region_allowlist}"
        )

        options = recommend_placement(
            job_spec={"m7i.4xlarge": 10, "c6i.8xlarge": 5}, constraints=constraints, output="table"
        )

        if options and len(options) > 0:
            print(f"\n✓ Found {len(options)} options meeting constraints")

    except Exception as e:
        print(f"Error: {e}")
        print("Ensure AWS credentials are configured.")


def demo_composite_utility():
    """Demo 4: Composite utility scoring."""
    from aws_fleet_scout.commands.fleet.utility import main as utility_main

    print("\n" + "=" * 80)
    print("DEMO 4: Composite Utility Scoring")
    print("=" * 80)
    print("\nCombine spot stability, pricing, and latency into a single decision metric.")
    print("Optimize for cost, performance, or network proximity.\n")

    try:
        print("Example 4a: Basic utility calculation (default weights)")
        print("-" * 60)
        result = utility_main(job_spec='{"m6i.2xlarge": 5}', output="table")

        if result:
            print("\n✓ Utility scores calculated successfully")

        print("\n\nExample 4b: Price-optimized weights")
        print("-" * 60)
        print("Weights: spot=0.3, price=0.6, latency=0.1 (prioritize cost)")

        result = utility_main(
            job_spec='{"c6i.4xlarge": 10}',
            spot_weight=0.3,
            price_weight=0.6,
            latency_weight=0.1,
            output="table",
        )

        if result:
            print("\n✓ Price-optimized utility calculated")

    except Exception as e:
        print(f"Error: {e}")
        print("Note: Pricing API may not be available in all regions.")


def demo_instance_discovery():
    """Demo 5: Instance type discovery using --discover flag."""
    from aws_fleet_scout.commands.spot.score import main as spot_score

    print("\n" + "=" * 80)
    print("DEMO 5: Instance Type Discovery")
    print("=" * 80)
    print("\nDiscover available EC2 instance types by prefix using --discover flag.\n")

    try:
        print("Example 5a: Discover all m7i instances in us-east-1")
        print("-" * 60)

        spot_score(
            instance_type="",
            discover="m7i",
            regions=["us-east-1"],
            target_capacity=15,
            output="table",
        )

        print("\n✓ Discovered m7i instance types in us-east-1")

        print("\n\nExample 5b: Discover GPU instances (p5 family)")
        print("-" * 60)

        spot_score(
            instance_type="",
            discover="p5",
            regions=["us-east-1"],
            target_capacity=15,
            output="table",
        )

        print("\n✓ Discovered p5 GPU instance types")

    except Exception as e:
        print(f"Error: {e}")


def demo_capacity_blocks():
    """Demo 6: Capacity Blocks for GPU instances."""
    from aws_fleet_scout.commands.capacity.calendar import main as capacity_calendar
    from aws_fleet_scout.commands.capacity.find import main as capacity_find

    print("\n" + "=" * 80)
    print("DEMO 6: Capacity Blocks")
    print("=" * 80)
    print("\nCapacity blocks provide reserved GPU capacity with guaranteed availability.")
    print("Perfect for scheduled training jobs and critical workloads.\n")

    try:
        print("Example 6a: Find capacity blocks for p5.48xlarge")
        print("-" * 60)

        capacity_find(
            instance_type="p5.48xlarge",
            duration=1,
            max_days=7,
            output="table",
            regions=["us-east-1", "us-west-2"],
        )

        print("\n✓ Searched for capacity blocks in next 7 days")

        print("\n\nExample 6b: Calendar view of capacity blocks")
        print("-" * 60)

        capacity_calendar(
            instance_type="p5.48xlarge",
            duration=1,
            window=7,
            output="table",
            regions=["us-east-1", "us-west-2"],
        )

        print("\n✓ Calendar shows availability across dates and regions")

    except Exception as e:
        print(f"Error: {e}")


def demo_integration_example():
    """Demo 7: Integration example - Complete workflow."""
    print("\n" + "=" * 80)
    print("DEMO 7: Integration Example - Complete Workflow")
    print("=" * 80)
    print("\nComplete workflow: Find optimal placement for a distributed ML training job.\n")

    from aws_fleet_scout import PlacementConstraints, recommend_placement

    try:
        # Define ML training cluster requirements
        job_spec = {"m7i.4xlarge": 2, "p5.48xlarge": 4}  # Coordinator nodes  # GPU training nodes

        print("Scenario: ML Training Cluster")
        print(f"  Requirements: {job_spec}")
        print("  Goal: Find optimal region with high stability and GPU availability\n")

        # Step 1: Set constraints
        constraints = PlacementConstraints(
            min_score_threshold=7.0,
            gpu_families=["p5"],
            region_allowlist=["us-east-1", "us-east-2", "us-west-2"],
        )

        print("Step 1: Apply constraints")
        print(f"  - Minimum score: {constraints.min_score_threshold}")
        print(f"  - Required GPU: {constraints.gpu_families}")
        print(f"  - Allowed regions: {constraints.region_allowlist}\n")

        # Step 2: Get recommendations
        print("Step 2: Get placement recommendations...")
        options = recommend_placement(job_spec=job_spec, constraints=constraints, output="table")

        if options and len(options) > 0:
            best = options[0]
            print("\n✓ RECOMMENDED DEPLOYMENT:")
            print(f"  Region: {best.region}")
            print(f"  Availability Zone: {best.availability_zone_id}")
            print(f"  Aggregate Score: {best.aggregate_score:.2f}/10")
            print(f"  Predicted Stability: {best.predicted_stability}")
            print(f"  Instance Scores: {best.instance_scores}")
            print("\n  Next steps:")
            print(f"    1. Configure Ray/Slurm cluster in {best.region}")
            print("    2. Use spot instances with capacity-optimized allocation")
            print(f"    3. Set up in AZ: {best.availability_zone_id}")
        else:
            print("\n✗ No options found meeting the constraints")
            print("  Consider: relaxing constraints or using different instance types")

    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("AWS FLEET SCOUT - COMPREHENSIVE DEMO")
    print("=" * 80)
    print("\nThis demo showcases all key features of aws-fleet-scout:")
    print("  1. Spot Placement Scores")
    print("  2. Fleet Packing (Multi-Instance Matchmaking)")
    print("  3. Spot-Aware Placement Engine (with Constraints)")
    print("  4. Composite Utility Scoring")
    print("  5. Instance Type Discovery")
    print("  6. Capacity Blocks")
    print("  7. Integration Example\n")
    print("Note: This makes actual AWS API calls. Ensure credentials are configured.")
    print("=" * 80)

    try:
        # Run all demos
        demo_spot_scores()
        demo_fleet_packing()
        demo_placement_engine()
        demo_composite_utility()
        demo_instance_discovery()
        demo_capacity_blocks()
        demo_integration_example()

        print("\n" + "=" * 80)
        print("DEMO COMPLETE!")
        print("=" * 80)
        print("\nFor more examples, see:")
        print("  - examples/programmatic_usage.py")
        print("  - examples/README.md")
        print("\nTo use in your code:")
        print("  from aws_fleet_scout import recommend_placement, PlacementConstraints")
        print("  from aws_fleet_scout import calculate_composite_utility, UtilityWeights")
        print()

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        print("Ensure AWS credentials are configured:")
        print("  - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("  - Or configure via 'aws configure'")
        print("  - Or use IAM roles")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Programmatic API Usage Examples

This demonstrates how to use aws-fleet-scout as a Python library
for integration into custom orchestration systems, CI/CD pipelines,
or automation frameworks.
"""

import json
from aws_fleet_scout.commands.fleet.pack import main as fleet_packing
from aws_fleet_scout.commands.spot.score import main as spot_score


class CapacityOptimizer:
    """
    Wrapper class for capacity optimization operations.
    
    Useful for integration into larger systems or frameworks.
    """
    
    def __init__(self, default_regions=None):
        """
        Initialize the optimizer.
        
        Args:
            default_regions: List of regions to check by default
        """
        self.default_regions = default_regions or [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2"
        ]
    
    def find_best_region_for_fleet(self, requirements):
        """
        Find the best region for a mixed instance fleet.
        
        Args:
            requirements: Dict mapping instance_type -> quantity
        
        Returns:
            Dict with keys: region, score, availability_zone
        """
        job_spec = json.dumps(requirements)
        result = fleet_packing(
            job_spec=job_spec,
            output='json',
            regions=self.default_regions
        )
        
        if not result or not result.get('best_region'):
            return None
        
        return {
            'region': result['best_region'],
            'score': result['best_score'],
            'availability_zone': result['region_scores'][0]['availability_zone_id'],
            'instance_scores': result['region_scores'][0]['instance_scores']
        }
    
    def check_single_instance_availability(self, instance_type, quantity):
        """
        Check availability for a single instance type.
        
        Args:
            instance_type: EC2 instance type (e.g., 'p5.48xlarge')
            quantity: Number of instances needed
        
        Returns:
            List of dicts with region scores, sorted by score descending
        """
        scores = spot_score(
            instance_type=instance_type,
            target_capacity=quantity,
            output='json',
            regions=self.default_regions
        )
        return scores
    
    def validate_deployment_feasibility(self, requirements, min_score=5.0):
        """
        Validate if deployment is feasible with acceptable scores.
        
        Args:
            requirements: Dict mapping instance_type -> quantity
            min_score: Minimum acceptable aggregate score (0-10)
        
        Returns:
            Tuple of (is_feasible: bool, best_option: dict or None)
        """
        result = self.find_best_region_for_fleet(requirements)
        
        if not result:
            return False, None
        
        is_feasible = result['score'] >= min_score
        return is_feasible, result


# Example 1: Simple region selection
def example_simple_region_selection():
    """Basic usage: find best region for a job."""
    print("\n" + "=" * 80)
    print("Example 1: Simple Region Selection")
    print("=" * 80 + "\n")
    
    optimizer = CapacityOptimizer()
    
    requirements = {
        "m7i.4xlarge": 20,
        "p5.48xlarge": 2
    }
    
    result = optimizer.find_best_region_for_fleet(requirements)
    
    if result:
        print(f"Best region: {result['region']}")
        print(f"Score: {result['score']:.2f}/10")
        print(f"Availability Zone: {result['availability_zone']}")
        print(f"Instance Scores: {json.dumps(result['instance_scores'], indent=2)}")
    else:
        print("No suitable region found")


# Example 2: Validate before deployment
def example_validate_before_deployment():
    """Check if deployment is feasible before attempting."""
    print("\n" + "=" * 80)
    print("Example 2: Deployment Validation")
    print("=" * 80 + "\n")
    
    optimizer = CapacityOptimizer()
    
    requirements = {
        "c6i.32xlarge": 50,
        "p4d.24xlarge": 10
    }
    
    is_feasible, result = optimizer.validate_deployment_feasibility(
        requirements,
        min_score=7.0  # Require high confidence
    )
    
    if is_feasible:
        print(f"✓ Deployment is FEASIBLE")
        print(f"  Region: {result['region']}")
        print(f"  Score: {result['score']:.2f}/10 (>= 7.0 threshold)")
    else:
        if result:
            print(f"✗ Deployment has LOW CONFIDENCE")
            print(f"  Best region: {result['region']}")
            print(f"  Score: {result['score']:.2f}/10 (< 7.0 threshold)")
            print(f"  Consider reducing capacity or trying different instance types")
        else:
            print(f"✗ No regions available for this configuration")


# Example 3: Multi-region strategy
def example_multi_region_strategy():
    """Evaluate multiple regions for failover strategy."""
    print("\n" + "=" * 80)
    print("Example 3: Multi-Region Failover Strategy")
    print("=" * 80 + "\n")
    
    requirements = {
        "m6i.16xlarge": 10,
        "r6i.8xlarge": 5
    }
    
    # Check specific regions
    regions_to_check = ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1"]
    
    optimizer = CapacityOptimizer(default_regions=regions_to_check)
    result = optimizer.find_best_region_for_fleet(requirements)
    
    print("Primary deployment target:")
    print(f"  Region: {result['region']}")
    print(f"  Score: {result['score']:.2f}/10")
    
    # Get scores for all regions for failover planning
    job_spec = json.dumps(requirements)
    full_result = fleet_packing(
        job_spec=job_spec,
        output='json',
        regions=regions_to_check
    )
    
    print("\nFailover priority (by score):")
    for idx, region_data in enumerate(full_result['region_scores'][:3], 1):
        print(f"  {idx}. {region_data['region']}: {region_data['aggregate_score']:.2f}/10")


# Example 4: Integration with CI/CD
def example_cicd_integration():
    """Simulate CI/CD pipeline integration."""
    print("\n" + "=" * 80)
    print("Example 4: CI/CD Pipeline Integration")
    print("=" * 80 + "\n")
    
    # Configuration from environment or config file
    DEPLOYMENT_CONFIG = {
        "dev": {"m6i.2xlarge": 2, "c6i.8xlarge": 3},
        "staging": {"m6i.8xlarge": 5, "p4d.24xlarge": 1},
        "production": {"m7i.16xlarge": 20, "p5.48xlarge": 8}
    }
    
    environment = "staging"  # Could come from CI/CD environment variable
    
    print(f"Deploying to: {environment}")
    print(f"Requirements: {DEPLOYMENT_CONFIG[environment]}")
    
    optimizer = CapacityOptimizer()
    is_feasible, result = optimizer.validate_deployment_feasibility(
        DEPLOYMENT_CONFIG[environment],
        min_score=6.0
    )
    
    if is_feasible:
        print(f"\n✓ Proceeding with deployment to {result['region']}")
        # In real CI/CD: export region to environment, trigger deployment
        print(f"  export DEPLOY_REGION={result['region']}")
        print(f"  export DEPLOY_AZ={result['availability_zone']}")
        print(f"  # Continue with terraform/cloudformation/ansible...")
        return 0  # Success exit code
    else:
        print(f"\n✗ Deployment blocked - insufficient capacity")
        print(f"  Consider: scaling down, different instance types, or manual override")
        return 1  # Failure exit code


if __name__ == "__main__":
    # Run all examples
    example_simple_region_selection()
    example_validate_before_deployment()
    example_multi_region_strategy()
    exit_code = example_cicd_integration()
    
    print("\n" + "=" * 80)
    print("Examples complete!")
    print("=" * 80)

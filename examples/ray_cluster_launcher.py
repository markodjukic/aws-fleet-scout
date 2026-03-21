#!/usr/bin/env python3
"""
Ray Cluster Launcher with Optimal Region Selection

This example shows how to use aws-fleet-scout to find the best AWS region
for deploying a Ray cluster with mixed instance types.
"""

import json
import sys
from aws_fleet_scout.commands.fleet.pack import main as fleet_packing


def launch_ray_cluster(head_instances, worker_instances, regions=None):
    """
    Find optimal region and launch Ray cluster.
    
    Args:
        head_instances: Dict of instance types and counts for head nodes
        worker_instances: Dict of instance types and counts for worker nodes
        regions: List of regions to check (None = use defaults)
    """
    # Combine head and worker requirements
    all_requirements = {**head_instances, **worker_instances}
    
    print("=" * 80)
    print("Ray Cluster Optimization with AWS Fleet Scout")
    print("=" * 80)
    print(f"\nHead nodes: {head_instances}")
    print(f"Worker nodes: {worker_instances}")
    print(f"Total requirements: {all_requirements}\n")
    
    # Find best region using fleet packing
    job_spec = json.dumps(all_requirements)
    result = fleet_packing(
        job_spec=job_spec,
        output='json',
        regions=regions
    )
    
    if not result or not result.get('best_region'):
        print("ERROR: Could not find suitable region for cluster deployment")
        sys.exit(1)
    
    best_region = result['best_region']
    best_score = result['best_score']
    best_az = result['region_scores'][0]['availability_zone_id']
    
    print("\n" + "=" * 80)
    print(f"RECOMMENDATION: Deploy Ray cluster in {best_region}")
    print(f"Availability Zone: {best_az}")
    print(f"Aggregate Spot Score: {best_score:.2f}/10")
    print("=" * 80)
    
    # Generate Ray cluster configuration
    cluster_config = generate_ray_config(
        head_instances=head_instances,
        worker_instances=worker_instances,
        region=best_region,
        availability_zone_id=best_az
    )
    
    print("\nGenerated Ray cluster configuration:")
    print(json.dumps(cluster_config, indent=2))
    
    # Optionally save to file
    output_file = f"ray_cluster_{best_region}.yaml"
    print(f"\nTo deploy, save configuration and run:")
    print(f"  ray up {output_file}")
    
    return cluster_config


def generate_ray_config(head_instances, worker_instances, region, availability_zone_id):
    """Generate a Ray cluster configuration dict."""
    # This is a simplified example - adapt to your Ray version and needs
    return {
        "cluster_name": f"ray-cluster-{region}",
        "provider": {
            "type": "aws",
            "region": region,
            "availability_zone": availability_zone_id.replace(region + "-", "")
        },
        "head_node": {
            "instance_type": list(head_instances.keys())[0],
            "min_workers": 0,
            "max_workers": 0
        },
        "worker_nodes": [
            {
                "instance_type": itype,
                "min_workers": count,
                "max_workers": count,
                "spot": True,
                "spot_options": {
                    "allocation_strategy": "capacity-optimized"
                }
            }
            for itype, count in worker_instances.items()
        ]
    }


if __name__ == "__main__":
    # Example 1: GPU-accelerated ML training cluster
    print("\n### Example 1: GPU ML Training Cluster ###\n")
    launch_ray_cluster(
        head_instances={"m7i.4xlarge": 1},
        worker_instances={"p5.48xlarge": 4, "p4d.24xlarge": 2},
        regions=["us-east-1", "us-east-2", "us-west-2"]
    )
    
    print("\n\n")
    
    # Example 2: CPU-heavy data processing cluster
    print("\n### Example 2: CPU Data Processing Cluster ###\n")
    launch_ray_cluster(
        head_instances={"m6i.2xlarge": 1},
        worker_instances={"c7i.16xlarge": 10, "r6i.8xlarge": 5},
        regions=["us-east-1", "us-west-2"]
    )

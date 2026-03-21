#!/bin/bash
#
# Slurm Cluster Provisioning with Optimal Region Selection
#
# This example shows how to use aws-fleet-scout CLI to find the best AWS region
# for deploying a Slurm cluster with mixed instance types.
#
# Usage:
#   ./slurm_cluster_provision.sh
#

set -e

echo "=============================================================================="
echo "Slurm Cluster Optimization with AWS Fleet Scout"
echo "=============================================================================="

# Define Slurm cluster requirements
# - 1 head node for scheduler/controller
# - 10 compute nodes (general purpose)
# - 4 GPU nodes for accelerated jobs

FLEET_SPEC='{
  "m6i.2xlarge": 1,
  "c6i.32xlarge": 10,
  "p4d.24xlarge": 4
}'

echo ""
echo "Cluster Requirements:"
echo "  - Head node: 1x m6i.2xlarge"
echo "  - Compute nodes: 10x c6i.32xlarge"
echo "  - GPU nodes: 4x p4d.24xlarge"
echo ""

# Query aws-fleet-scout for best region
echo "Querying AWS for optimal region..."
RESULT=$(aws-fleet-scout fleet pack --job-spec "$FLEET_SPEC" --output json)

# Extract best region and score
BEST_REGION=$(echo "$RESULT" | jq -r '.best_region')
BEST_SCORE=$(echo "$RESULT" | jq -r '.best_score')
BEST_AZ=$(echo "$RESULT" | jq -r '.region_scores[0].availability_zone_id')

if [ -z "$BEST_REGION" ] || [ "$BEST_REGION" = "null" ]; then
    echo "ERROR: Could not find suitable region for cluster deployment"
    exit 1
fi

echo ""
echo "=============================================================================="
echo "RECOMMENDATION: Deploy Slurm cluster in $BEST_REGION"
echo "Availability Zone: $BEST_AZ"
echo "Aggregate Spot Score: $BEST_SCORE/10"
echo "=============================================================================="
echo ""

# Generate AWS ParallelCluster configuration
CONFIG_FILE="slurm-cluster-${BEST_REGION}.yaml"

cat > "$CONFIG_FILE" << EOF
Region: ${BEST_REGION}
Image:
  Os: alinux2
HeadNode:
  InstanceType: m6i.2xlarge
  Networking:
    SubnetId: subnet-xxxxxxxxx  # Replace with your subnet ID in ${BEST_REGION}
  Ssh:
    KeyName: your-key-pair      # Replace with your SSH key pair name
  Iam:
    AdditionalIamPolicies:
      - Policy: arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
Scheduling:
  Scheduler: slurm
  SlurmQueues:
    - Name: compute
      ComputeResources:
        - Name: compute-nodes
          InstanceType: c6i.32xlarge
          MinCount: 0
          MaxCount: 10
          SpotPrice: 0  # Use spot with capacity-optimized
      Networking:
        SubnetIds:
          - subnet-xxxxxxxxx  # Replace with your subnet ID
        PlacementGroup:
          Enabled: true
      CapacityType: SPOT
      AllocationStrategy: lowest-price
    - Name: gpu
      ComputeResources:
        - Name: gpu-nodes
          InstanceType: p4d.24xlarge
          MinCount: 0
          MaxCount: 4
          SpotPrice: 0
      Networking:
        SubnetIds:
          - subnet-xxxxxxxxx
        PlacementGroup:
          Enabled: true
      CapacityType: SPOT
      AllocationStrategy: capacity-optimized
EOF

echo "Generated AWS ParallelCluster configuration: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_FILE and replace placeholder values (subnet IDs, key pair)"
echo "  2. Install AWS ParallelCluster: pip install aws-parallelcluster"
echo "  3. Create cluster: pcluster create-cluster --cluster-name my-slurm-cluster --cluster-configuration $CONFIG_FILE"
echo ""
echo "Alternative deployment methods:"
echo "  - Use terraform with this region: $BEST_REGION"
echo "  - Use CloudFormation with this region: $BEST_REGION"
echo "  - Manual EC2 instance provisioning in AZ: $BEST_AZ"
echo ""

# Show detailed scoring breakdown
echo "Detailed Region Scoring:"
echo "$RESULT" | jq -r '.region_scores[] | "  \(.region): \(.aggregate_score) - AZ: \(.availability_zone_id)"'

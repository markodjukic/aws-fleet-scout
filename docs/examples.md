# Examples and Usage

This guide explains the runnable examples in [examples](../examples), what each one demonstrates, and how to run them.

## Prerequisites

- Pixi installed: https://pixi.sh/latest/
- Python 3.9+
- AWS credentials configured (environment variables, `aws configure`, or IAM role)
- Environment installed from repository root:

```bash
pixi install
```

Optional tools:

- `jq` for shell JSON parsing in the Slurm example
- Ray and AWS ParallelCluster if you want to deploy the generated configs

## Quick Demo

File: [examples/quick_demo.py](../examples/quick_demo.py)

Purpose:
- End-to-end walkthrough of major features in one run
- Spot score checks, fleet packing, placement recommendations, utility scoring, discovery, and capacity blocks

Run:

```bash
pixi run python examples/quick_demo.py
```

Best for:
- First validation that your environment and permissions are working
- Seeing command output formats quickly

## Programmatic Usage

File: [examples/programmatic_usage.py](../examples/programmatic_usage.py)

Purpose:
- Shows library-style usage from Python code rather than CLI-only usage
- Includes a reusable `CapacityOptimizer` class for orchestration pipelines
- Demonstrates feasibility checks and simple CI/CD style decision gates

Run:

```bash
pixi run python examples/programmatic_usage.py
```

Best for:
- Integrating AWS Fleet Scout into Python automation, deployment controllers, or schedulers

## Ray Cluster Launcher

File: [examples/ray_cluster_launcher.py](../examples/ray_cluster_launcher.py)

Purpose:
- Finds an optimal region/AZ for mixed head and worker node requirements
- Generates a Ray cluster configuration structure from that recommendation

Run:

```bash
pixi run python examples/ray_cluster_launcher.py
```

Best for:
- Teams using Ray that need region selection based on spot availability before cluster launch

Notes:
- The script prints generated config content; adapt fields for your Ray version and environment.

## Slurm Provisioning Script

File: [examples/slurm_cluster_provision.sh](../examples/slurm_cluster_provision.sh)

Purpose:
- Uses CLI output to pick a best region for a mixed Slurm cluster
- Generates a starter AWS ParallelCluster YAML file for that region

Run:

```bash
chmod +x examples/slurm_cluster_provision.sh
pixi run ./examples/slurm_cluster_provision.sh
```

Best for:
- Slurm / HPC workflows where cluster placement is decided from real-time AWS capacity signals

Notes:
- Requires `jq` in your shell environment.
- The generated YAML contains placeholders (subnet IDs, key pair) that must be replaced.

## Common CLI Usage Patterns

The examples are built around these command patterns:

```bash
# Spot scoring for one instance type
aws-fleet-scout spot score --instance-type p5.48xlarge --target-capacity 15

# Fleet packing for mixed instance requirements
aws-fleet-scout fleet pack --job-spec '{"m7i.4xlarge": 20, "p5.48xlarge": 2}'

# Placement recommendations with constraints
aws-fleet-scout fleet recommend --job-spec '{"m7i.4xlarge": 20}' --min-score 6.0

# Capacity blocks search and calendar
aws-fleet-scout capacity find --instance-type p5.48xlarge --duration 1 --max-days 7
aws-fleet-scout capacity calendar --instance-type p5.48xlarge --window 7 --duration 1
```

## Troubleshooting

- If examples fail with AWS auth errors, verify credentials and IAM permissions.
- If results are empty, widen regions or reduce requested capacity.
- If capacity block queries return no offerings, try a different instance family, region, or time window.

## Non-Pixi Alternative

If you prefer not to use Pixi for local testing, you can still run the examples with a standard virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python examples/quick_demo.py
```

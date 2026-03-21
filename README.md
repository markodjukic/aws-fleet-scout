# AWS Fleet Scout

Scout optimal AWS compute for cluster workloads. Compare spot, capacity blocks, and on-demand pricing across regions and instance types. Auto-discover instances for CPU and GPU deployments with HPC schedulers.

## Features

- **Compare**: Side-by-side comparison of Spot, Capacity Blocks, and On-Demand pricing
- **Auto-Discovery**: Automatically find all instances matching a prefix (e.g., all P-series, G-series)
- **Quota Validation**: Automatic checking against AWS Service Quotas with actionable warnings
- **Smart Caching**: Reference data cached locally to minimize API calls and improve performance
- **Capacity Calendar**: Flight-booking style calendar view of capacity block availability
- **Fleet Packing**: Find optimal regions for mixed instance type deployments
- **Placement Engine**: Ranked recommendations with customizable constraints
- **Composite Utility**: Combine spot stability, pricing, and latency scores
- **Spot Scores**: Query placement scores and pricing for spot instances
- **Read-Only**: Safe to use - only queries AWS APIs, never creates/modifies resources

## Installation

Per PyPI:

```bash
pip install aws-fleet-scout
```

From source:

```bash
git clone https://github.com/markodjukic/aws-fleet-scout.git
cd aws-fleet-scout
pip install -e .
```

## Quick Start

### Interactive Mode (Easiest!)

Launch the interactive menu for a guided experience:

```bash
aws-fleet-scout interactive
```

### Compare All Procurement Methods

```bash
# Compare spot, capacity blocks, and on-demand
aws-fleet-scout compare --instance-type p4d.24xlarge

# Compare with multiple instances
aws-fleet-scout compare --instance-type p4d.24xlarge --count 4

# Auto-discover all P-series GPU instances
aws-fleet-scout compare --discover-p-series --regions us-east-1,us-west-2

# Auto-discover by instance family prefix
aws-fleet-scout compare --discover g5 --regions us-east-1
aws-fleet-scout compare --discover m7i,c7i,r7i --regions us-east-1
```

### Spot Instance Commands

```bash
# Check spot placement scores
aws-fleet-scout spot score --instance-type p5.48xlarge --target-capacity 15

# Use wildcards for regions
aws-fleet-scout spot score --instance-type p5.48xlarge --regions "us-*"

# Auto-discover all P-series and check scores
aws-fleet-scout spot score --discover-p-series --regions us-east-1
```

### Find Best Region for Fleet

```bash
# Mixed instance fleet (Ray/Slurm/HPC)
aws-fleet-scout fleet pack --job-spec '{"m7i.4xlarge": 20, "p5.48xlarge": 2}'
```

### Capacity Blocks

```bash
# Find reserved GPU capacity
aws-fleet-scout capacity find --instance-type p5.48xlarge --duration 1

# View availability calendar
aws-fleet-scout capacity calendar --instance-type p4d.24xlarge --window 7 --duration 1
```

## Configuration

### AWS Credentials

Set AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

Or use AWS CLI:

```bash
aws configure
```

### Caching

AWS Fleet Scout caches reference data locally to improve performance:

**Cache Location** (platform-specific):
- macOS: `~/Library/Caches/aws-fleet-scout/`
- Linux: `~/.cache/aws-fleet-scout/`
- Windows: `C:\Users\<user>\AppData\Local\aws-fleet-scout\Cache\`

**What's Cached**:
- Quota codes (7 days TTL)
- vCPU counts per instance type (7 days TTL)
- Instance type offerings per region (7 days TTL)
- Current quota values (1 hour TTL)
- AWS region mapping (30 days TTL)
- Spot placement scores (10 minutes TTL)

## Development Workflow (Pixi)

This repository uses Pixi as the single development workflow manager.

### Prerequisites

- Install Pixi: https://pixi.sh/latest/
- Configure AWS credentials for functional tests and runtime CLI usage

### Setup

```bash
pixi install
```

### Common Commands

```bash
# Run unit tests
pixi run test

# Run all tests
pixi run test-all

# Run functional tests only (requires AWS credentials)
pixi run test-functional

# Lint + type check + unit tests
pixi run check

# Build package artifacts
pixi run build

# Show CLI help
pixi run cli-help
```

### Versioning

Current version comes from `aws_fleet_scout/__init__.py`.

```bash
# Show current version
pixi run version-current

# Bump next release version
pixi run bump-patch
pixi run bump-minor
pixi run bump-major
```

## Documentation

- Architecture: [docs/architecture.md](docs/architecture.md)
- Development scripts: [docs/scripts.md](docs/scripts.md)
- Development tools and linting: [docs/development.md](docs/development.md)

## Packaging and Publishing

- TestPyPI workflow: `.github/workflows/publish-testpypi.yml`
- PyPI workflow: `.github/workflows/publish-pypi.yml`

Both workflows use GitHub Actions with trusted publishing.
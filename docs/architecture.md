# AWS Fleet Scout - Architecture

This document provides implementation-level context beyond the quickstart README.

## What the Tool Does

AWS Fleet Scout helps choose AWS regions and procurement options for compute-heavy workloads. It compares spot placement, capacity blocks, and on-demand considerations with a CLI-first workflow.

Key capabilities:
- Compare procurement options for one or more instance types
- Discover instance families by prefix (for example, `p5`, `g5`, `m7i`)
- Evaluate quota constraints and report actionable warnings
- Produce table output for humans and JSON output for automation

## Project Structure

Core package layout:
- `aws_fleet_scout/cli.py`: CLI entrypoint
- `aws_fleet_scout/commands/compare.py`: high-level compare command
- `aws_fleet_scout/commands/spot/`: spot placement scoring
- `aws_fleet_scout/commands/capacity/`: capacity block commands
- `aws_fleet_scout/commands/fleet/`: packing/recommendation/utility logic
- `aws_fleet_scout/utils/`: AWS client, caching, output, quotas, regions

Tests:
- `tests/unit/`: mocked, fast, no AWS dependency
- `tests/functional/`: real AWS integration tests

## Development with Pixi

This repository uses Pixi as the standard workflow layer for local development.

Environment setup:
```bash
pixi install
```

Common tasks:
```bash
pixi run test
pixi run test-all
pixi run test-functional
pixi run lint
pixi run typecheck
pixi run check
pixi run build
```

Version tasks:
```bash
pixi run version-current
pixi run bump-patch
pixi run bump-minor
pixi run bump-major
```

For more details on working with scripts, see [scripts.md](scripts.md).

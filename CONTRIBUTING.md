# Contributing to AWS Fleet Scout

## Development Setup

```bash
git clone https://github.com/markodjukic/aws-fleet-scout.git
cd aws-fleet-scout
pixi install
```

Configure AWS credentials for functional tests:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

## Project Structure

```
aws_fleet_scout/
├── cli.py              # CLI entrypoint
├── commands/           # Command modules (spot, fleet, capacity, compare)
└── utils/              # AWS client, caching, output, quotas, regions
tests/
├── unit/               # Mocked, no AWS needed
└── functional/         # Real AWS calls, requires credentials
```

## Conventional Commits

This repository follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.
Release-please uses these commit types to automatically version and generate changelog entries.

| Type       | When to use                                   | Version bump |
|------------|-----------------------------------------------|--------------|
| `feat`     | New feature                                   | minor        |
| `fix`      | Bug fix                                       | patch        |
| `perf`     | Performance improvement                        | patch        |
| `docs`     | Documentation only                            | none         |
| `chore`    | Build, CI, tooling changes                    | none         |
| `refactor` | Code restructuring without behaviour change   | none         |
| `BREAKING CHANGE` | Breaking API or behaviour change       | major        |

Examples:
```
feat: add wildcard support for multi-region capacity search
fix: handle missing quota code in ServiceQuotas response
docs: update README with pixi install instructions
chore: add release-please workflow
feat!: change JSON output envelope structure (BREAKING CHANGE)
```

A breaking change can also be noted with a `!` after the type:
```
feat!: rename --discover-p-series flag to --discover-gpu
```

## Code Style

```bash
# Format
pixi run format

# Lint and typecheck
pixi run check
```

## Pull Requests

1. Fork and create a branch
2. Follow conventional commit format in all commit messages
3. Open a PR — CI will run automatically
4. Squash-merge using a conventional commit message as the PR title

## Release Workflow

Releases are fully automated via release-please:

1. All conventional commits merged to `main` are tracked automatically.
2. release-please opens a Release PR updating `CHANGELOG.md` and `__version__`.
3. Review and merge the Release PR to create a GitHub Release and tag.
4. Merging the Release PR automatically triggers the PyPI and TestPyPI publish workflows.

**No manual version bumping, tagging, or changelog editing is required.**

## Areas for Contribution

- New commands (cost analysis, benchmarking)
- Integrations (Kubernetes, Terraform)
- Better error handling
- Unit tests
- Documentation and examples

## License

Contributions licensed under MIT License.

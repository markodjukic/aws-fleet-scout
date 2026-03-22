# Development Scripts

This document describes the utility scripts in the `scripts/` directory.

## bump_version.py

Automates semantic versioning for releases.

### Purpose

The `bump_version.py` script manages version bumps across the project by:
- Reading the current version from `aws_fleet_scout/__init__.py`
- Computing the new version based on the bump type (patch, minor, major)
- Updating the version string in `__init__.py`
- Adding a new entry to `CHANGELOG.md` with the new version and timestamp placeholder

### Usage

Run via Pixi:
```bash
pixi run bump-patch    # Bump patch version (e.g., 1.2.3 -> 1.2.4)
pixi run bump-minor    # Bump minor version (e.g., 1.2.3 -> 1.3.0)
pixi run bump-major    # Bump major version (e.g., 1.2.3 -> 2.0.0)
```

Or directly:
```bash
python scripts/bump_version.py patch
python scripts/bump_version.py minor
python scripts/bump_version.py major
```

### Output

The script prints the new version to stdout on success and exits with code 0.
On error, it prints an error message to stderr and exits with code 1.

### How It Works

1. Validates input: must be one of `patch`, `minor`, or `major`
2. Parses semantic version (MAJOR.MINOR.PATCH) from `__version__` in `__init__.py`
3. Calculates new version:
   - Patch: increments patch, keeps major and minor
   - Minor: increments minor, resets patch to 0, keeps major
   - Major: increments major, resets minor and patch to 0
4. Rewrites `__version__` in `__init__.py` with new version
5. Inserts new changelog entry after the semantic versioning statement with:
   - New version header with placeholder date (YYYY-MM-DD)
   - An "Unreleased" section for work since the last release

### Integration with Release Workflow

This script is typically run as part of the release process before publishing to PyPI.
After bumping, manually update the date in `CHANGELOG.md` and fill in release notes before publishing.

The version bump affects:
- Package metadata (visible in `pip show aws-fleet-scout`)
- GitHub release tags and documentation
- CI/CD workflows that reference the version

### Files Modified

- `aws_fleet_scout/__init__.py`: Updates `__version__` string
- `CHANGELOG.md`: Adds new version entry with changelog template

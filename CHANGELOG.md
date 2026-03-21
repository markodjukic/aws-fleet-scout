# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-02-04

### Changed
- **Standardized on Pixi for dependency and task management**
- **Minimum Python version bumped to 3.9**: Python 3.8 is EOL
- Removed redundant `setup.py` (pyproject.toml is now the single source of truth)
- Updated Makefile and task workflow to use Pixi commands
- Updated README with Pixi commands for development workflow

### Added
- Pixi environment and task definitions for reproducible local workflows

[0.2.1]: https://github.com/markodjukic/aws-fleet-scout/releases/tag/v0.2.1

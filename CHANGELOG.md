# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1](https://github.com/markodjukic/aws-fleet-scout/compare/aws-fleet-scout-v1.0.0...aws-fleet-scout-v1.0.1) (2026-03-22)


### Bug Fixes

* resolve all flake8 lint errors and fix broken unit tests ([5c7f650](https://github.com/markodjukic/aws-fleet-scout/commit/5c7f6500544be3b54df4fa4bb65d9ac116332085))
* resolve mypy type errors in command and utility modules ([c4eeae4](https://github.com/markodjukic/aws-fleet-scout/commit/c4eeae425d5eb4015c0f2bfe1983a9a528720730))


### Documentation

* add pixi-first examples and usage guide ([91f4f31](https://github.com/markodjukic/aws-fleet-scout/commit/91f4f31ca3f09eb2f510225f78f27126039e79fd))

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

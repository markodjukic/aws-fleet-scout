# Linting and Code Quality

This document describes the linting and code quality tools configured for AWS Fleet Scout.

## Tools

The project uses a suite of Python code quality tools to maintain consistency and catch issues:

- **isort**: Automatic import sorting
- **black**: Code formatting
- **flake8**: Style guide enforcement
- **mypy**: Static type checking

## Configuration

All tools are configured in:

- `pyproject.toml`: Configuration for isort, black, mypy
- `.flake8`: Flake8 specific configuration
- `pixi.toml`: Dev tasks for running the tools

Pre-commit hooks are available in `.pre-commit-config.yaml` for automatic checks on commit.

## Running Checks

### Import Sorting

Automatically sort and organize imports:

```bash
pixi run sort-imports
```

This uses isort with a black-compatible profile, meaning it coordinates with black formatting.

### Code Formatting

Auto-format code according to black style:

```bash
pixi run format
```

Black uses a line length of 100 characters.

### Linting

Check code for style issues and common mistakes:

```bash
pixi run lint
```

Flake8 enforces PEP 8 style guide with:
- Max line length: 100 characters
- Ignored rules: E203 (whitespace before ':'), W503 (line break before binary operator)
- Special handling for `__init__.py` files to allow star imports (F401, F403)

### Type Checking

Validate type hints and detect type errors:

```bash
pixi run typecheck
```

Uses mypy with Python 3.9+ compatibility.

### Full Quality Check

Run all checks together (sort imports, format, lint, type check, and unit tests):

```bash
pixi run check
```

This is the recommended command before committing.

## Import Sorting Details

The isort configuration ensures consistent import ordering:

1. Future imports (`from __future__ import ...`)
2. Standard library imports
3. Third-party imports
4. Local application imports

Within each group, imports are sorted alphabetically.

### Example

Before:

```python
import os
from typing import Any
from aws_fleet_scout.utils import cache
import boto3
from __future__ import annotations
```

After isort + black:

```python
from __future__ import annotations

import os
from typing import Any

import boto3

from aws_fleet_scout.utils import cache
```

## Pre-commit Hooks

For automatic checks on every commit, install pre-commit:

```bash
pixi run pre-commit install
pip install pre-commit
```

Then hooks will run on every commit, checking:
- Trailing whitespace
- End-of-file fixers
- YAML validation
- Private key detection
- Import sorting
- Code formatting (black)
- Style violations (flake8)

If checks fail, fix the issues and re-stage files.

## Integration with Development

When developing:

1. Write code normally
2. Before committing, run `pixi run check`
3. Fix any issues reported
4. Or install pre-commit hooks to automate this

The combination of isort, black, and flake8 ensures:
- Consistent import organization
- Consistent code style
- Consistent spacing and formatting
- Prevention of common mistakes

"""
Entry point for running aws_fleet_scout as a module.

Usage: python -m aws_fleet_scout [command] [options]
"""

from .cli import app

if __name__ == "__main__":
    app()

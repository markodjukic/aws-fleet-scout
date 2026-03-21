from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "aws_fleet_scout" / "__init__.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
VERSION_PATTERN = re.compile(r'__version__ = "(\d+)\.(\d+)\.(\d+)"')


def bump_version(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))

    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"

    raise ValueError(f"Unsupported bump part: {part}")


def read_current_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise RuntimeError(f"Could not find __version__ in {VERSION_FILE}")
    return ".".join(match.groups())


def write_new_version(current_version: str, new_version: str) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated = content.replace(
        f'__version__ = "{current_version}"',
        f'__version__ = "{new_version}"',
        1,
    )
    VERSION_FILE.write_text(updated, encoding="utf-8")


def update_changelog(new_version: str) -> None:
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    version_header = f"## [{new_version}] - YYYY-MM-DD"

    if version_header in content:
        return

    marker = "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    if marker not in content:
        raise RuntimeError(f"Could not find insertion point in {CHANGELOG_FILE}")

    insertion = (
        f"\n## [Unreleased]\n\n### Changed\n- TBD\n\n"
        f"{version_header}\n\n### Changed\n- TBD\n"
    )
    updated = content.replace(marker, marker + insertion, 1)
    CHANGELOG_FILE.write_text(updated, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"patch", "minor", "major"}:
        print("Usage: python scripts/bump_version.py [patch|minor|major]", file=sys.stderr)
        return 1

    part = argv[1]
    current_version = read_current_version()
    new_version = bump_version(current_version, part)
    write_new_version(current_version, new_version)
    update_changelog(new_version)
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
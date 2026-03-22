"""
Interactive menu for AWS Fleet Scout using Questionary.

Provides a guided interface to build and execute commands.
"""

import subprocess
import sys
from typing import List, Optional

try:
    import questionary
    from questionary import Style
except ImportError:
    print("Error: questionary is required for interactive mode")
    print("Install with: pip install questionary")
    sys.exit(1)

from .config import DEFAULT_REGIONS, PRICING_REGION_MAP

# Custom style for AWS Fleet Scout
custom_style = Style(
    [
        ("qmark", "fg:#673ab7 bold"),  # Question mark
        ("question", "bold"),  # Question text
        ("answer", "fg:#f44336 bold"),  # Selected answer
        ("pointer", "fg:#673ab7 bold"),  # Pointer
        ("highlighted", "fg:#673ab7 bold"),  # Highlighted choice
        ("selected", "fg:#cc5454"),  # Selected choice
        ("separator", "fg:#cc5454"),  # Separator
        ("instruction", ""),  # Instructions
        ("text", ""),  # Plain text
        ("disabled", "fg:#858585 italic"),  # Disabled choice
    ]
)


def prompt_regions() -> Optional[str]:
    """
    Prompt user to select regions using checkbox.

    Returns:
        Comma-separated region string or None if cancelled
    """
    use_custom_regions = questionary.confirm(
        "Specify custom regions?", default=False, style=custom_style
    ).ask()

    if use_custom_regions is None:
        return None

    if not use_custom_regions:
        return ""  # Use defaults

    # Get all available regions from config, sorted alphabetically
    all_regions = sorted(PRICING_REGION_MAP.keys())

    regions = questionary.checkbox(
        "Select regions (space to select, enter to confirm):",
        choices=all_regions,
        style=custom_style,
    ).ask()

    if regions is None:
        return None

    return ",".join(regions) if regions else ""


def prompt_discovery() -> Optional[str]:
    """
    Prompt user to enter instance prefix(es) for discovery.

    Returns:
        The prefix value(s) for --discover or None if cancelled
    """
    print("\nExamples: p5, g5, m7i, c7i, r7i, t3, inf2, p4")

    prefix = questionary.text(
        "Instance prefix(es) to discover (comma-separated):", default="p5", style=custom_style
    ).ask()

    return prefix


def build_compare_command() -> Optional[List[str]]:
    """Build compare command interactively."""
    cmd = ["aws-fleet-scout", "compare"]

    # Input method
    input_method = questionary.select(
        "How do you want to specify instances?",
        choices=[
            "Single instance type",
            "Multiple instances (job spec)",
            "Auto-discover by prefix",
            "← Back",
        ],
        style=custom_style,
    ).ask()

    if input_method == "← Back" or input_method is None:
        return None

    if input_method == "Single instance type":
        instance = questionary.text(
            "Instance type:", default="p5.48xlarge", style=custom_style
        ).ask()

        if instance is None:
            return None

        cmd.extend(["--instance-type", instance])

        count = questionary.text("Instance count:", default="1", style=custom_style).ask()

        if count is None:
            return None

        if count != "1":
            cmd.extend(["--count", count])

    elif input_method == "Multiple instances (job spec)":
        job_spec = questionary.text(
            "Job spec (JSON):", default='{"p5.48xlarge": 2}', style=custom_style
        ).ask()

        if job_spec is None:
            return None

        cmd.extend(["--job-spec", job_spec])

    else:  # Auto-discover
        prefix = prompt_discovery()
        if prefix is None:
            return None

        cmd.extend(["--discover", prefix])

    # Regions
    regions = prompt_regions()
    if regions is None:
        return None
    if regions:
        cmd.extend(["--regions", regions])

    # Output format
    output_table = questionary.confirm("Table output?", default=True, style=custom_style).ask()

    if output_table is None:
        return None

    if output_table:
        cmd.extend(["--output", "table"])
    else:
        cmd.extend(["--output", "json"])

    return cmd


def build_spot_score_command() -> Optional[List[str]]:
    """Build spot score command interactively."""
    cmd = ["aws-fleet-scout", "spot", "score"]

    # Input method
    input_method = questionary.select(
        "How do you want to specify instances?",
        choices=["Single instance type", "Auto-discover by prefix", "← Back"],
        style=custom_style,
    ).ask()

    if input_method == "← Back" or input_method is None:
        return None

    if input_method == "Single instance type":
        instance = questionary.text(
            "Instance type:", default="p5.48xlarge", style=custom_style
        ).ask()

        if instance is None:
            return None

        cmd.extend(["--instance-type", instance])
    else:  # Auto-discover
        prefix = prompt_discovery()
        if prefix is None:
            return None

        cmd.extend(["--discover", prefix])

    # Target capacity
    capacity = questionary.text(
        "Target capacity (number of instances):", default="15", style=custom_style
    ).ask()

    if capacity is None:
        return None

    if capacity != "15":
        cmd.extend(["--target-capacity", capacity])

    # Regions
    regions = prompt_regions()
    if regions is None:
        return None
    if regions:
        cmd.extend(["--regions", regions])

    # Output format
    output_table = questionary.confirm("Table output?", default=True, style=custom_style).ask()

    if output_table is None:
        return None

    if output_table:
        cmd.extend(["--output", "table"])
    else:
        cmd.extend(["--output", "json"])

    return cmd


def build_capacity_find_command() -> Optional[List[str]]:
    """Build capacity find command interactively."""
    cmd = ["aws-fleet-scout", "capacity", "find"]

    # Input method
    input_method = questionary.select(
        "How do you want to specify instances?",
        choices=[
            "Single instance type",
            "Multiple instances (job spec)",
            "Auto-discover by prefix",
            "← Back",
        ],
        style=custom_style,
    ).ask()

    if input_method == "← Back" or input_method is None:
        return None

    if input_method == "Single instance type":
        instance = questionary.text(
            "Instance type:", default="p5.48xlarge", style=custom_style
        ).ask()

        if instance is None:
            return None

        cmd.extend(["--instance-type", instance])

    elif input_method == "Multiple instances (job spec)":
        job_spec = questionary.text(
            "Job spec (JSON):", default='{"p5.48xlarge": 2}', style=custom_style
        ).ask()

        if job_spec is None:
            return None

        cmd.extend(["--job-spec", job_spec])

    else:  # Auto-discover
        prefix = prompt_discovery()
        if prefix is None:
            return None

        cmd.extend(["--discover", prefix])

    # Duration
    duration = questionary.text(
        "Duration in days (1-14 daily, or 21-182 in 7-day steps):", default="1", style=custom_style
    ).ask()

    if duration is None:
        return None

    if duration != "1":
        cmd.extend(["--duration", duration])

    # Search window
    max_days = questionary.text(
        "Search window (days ahead, typically max ~10 days):", default="7", style=custom_style
    ).ask()

    if max_days is None:
        return None

    if max_days != "7":
        cmd.extend(["--max-days", max_days])

    # Regions
    regions = prompt_regions()
    if regions is None:
        return None
    if regions:
        cmd.extend(["--regions", regions])

    # Output format
    output_table = questionary.confirm("Table output?", default=True, style=custom_style).ask()

    if output_table is None:
        return None

    if output_table:
        cmd.extend(["--output", "table"])
    else:
        cmd.extend(["--output", "json"])

    return cmd


def build_capacity_calendar_command() -> Optional[List[str]]:
    """Build capacity calendar command interactively."""
    cmd = ["aws-fleet-scout", "capacity", "calendar"]

    # Input method
    input_method = questionary.select(
        "How do you want to specify instances?",
        choices=[
            "Single instance type",
            "Multiple instances (job spec)",
            "Auto-discover by prefix (single region only)",
            "← Back",
        ],
        style=custom_style,
    ).ask()

    if input_method == "← Back" or input_method is None:
        return None

    discovery_mode = False

    if input_method == "Single instance type":
        instance = questionary.text(
            "Instance type:", default="p5.48xlarge", style=custom_style
        ).ask()

        if instance is None:
            return None

        cmd.extend(["--instance-type", instance])

    elif input_method == "Multiple instances (job spec)":
        job_spec = questionary.text(
            "Job spec (JSON):", default='{"p5.48xlarge": 2}', style=custom_style
        ).ask()

        if job_spec is None:
            return None

        cmd.extend(["--job-spec", job_spec])

    else:  # Auto-discover
        discovery_mode = True

        prefix = prompt_discovery()
        if prefix is None:
            return None

        cmd.extend(["--discover", prefix])

        # Force single region for discovery
        region = questionary.text(
            "Region (single region required for discovery):",
            default=DEFAULT_REGIONS[0],
            style=custom_style,
        ).ask()

        if region is None:
            return None

        cmd.extend(["--regions", region])

    # Duration
    duration = questionary.text(
        "Duration in days (1-14 daily, or 21-182 in 7-day steps):", default="1", style=custom_style
    ).ask()

    if duration is None:
        return None

    if duration != "1":
        cmd.extend(["--duration", duration])

    # Window
    window = questionary.text(
        "Search window (days ahead, typically max ~10 days):", default="7", style=custom_style
    ).ask()

    if window is None:
        return None

    if window != "7":
        cmd.extend(["--window", window])

    # Regions (if not discovery mode)
    if not discovery_mode:
        regions = prompt_regions()
        if regions is None:
            return None
        if regions:
            cmd.extend(["--regions", regions])

    # Output format
    output_table = questionary.confirm("Table output?", default=True, style=custom_style).ask()

    if output_table is None:
        return None

    if output_table:
        cmd.extend(["--output", "table"])
    else:
        cmd.extend(["--output", "json"])

    return cmd


def build_fleet_pack_command() -> Optional[List[str]]:
    """Build fleet pack command interactively."""
    cmd = ["aws-fleet-scout", "fleet", "pack"]

    job_spec = questionary.text(
        "Job spec (JSON):", default='{"m7i.4xlarge": 20, "p5.48xlarge": 2}', style=custom_style
    ).ask()

    if job_spec is None:
        return None

    cmd.extend(["--job-spec", job_spec])

    # Regions
    regions = prompt_regions()
    if regions is None:
        return None
    if regions:
        cmd.extend(["--regions", regions])

    # Output format
    output_table = questionary.confirm("Table output?", default=True, style=custom_style).ask()

    if output_table is None:
        return None

    if output_table:
        cmd.extend(["--output", "table"])
    else:
        cmd.extend(["--output", "json"])

    return cmd


def main():
    """Interactive menu entry point."""
    print("\n" + "=" * 60)
    print("🔍 AWS Fleet Scout - Interactive Mode")
    print("=" * 60 + "\n")

    try:
        while True:
            command_type = questionary.select(
                "What would you like to do?",
                choices=[
                    "Compare spot vs capacity blocks vs on-demand",
                    "Check spot availability",
                    "Find capacity block offerings",
                    "View capacity block calendar",
                    "Find best region for fleet packing",
                    "Exit",
                ],
                style=custom_style,
            ).ask()

            if command_type == "Exit" or command_type is None:
                print("\n👋 Goodbye!\n")
                sys.exit(0)

            # Build command based on selection
            if "Compare spot" in command_type:
                cmd = build_compare_command()
            elif "spot availability" in command_type:
                cmd = build_spot_score_command()
            elif "Find capacity block" in command_type:
                cmd = build_capacity_find_command()
            elif "capacity block calendar" in command_type:
                cmd = build_capacity_calendar_command()
            elif "fleet packing" in command_type:
                cmd = build_fleet_pack_command()
            else:
                continue

            if not cmd:
                continue  # User went back or cancelled

            # Show command
            print("\n" + "=" * 60)
            print("📋 Executing command:")
            print("   " + " ".join(cmd))
            print("=" * 60 + "\n")

            # Execute command
            try:
                result = subprocess.run(cmd, check=False)

                if result.returncode != 0:
                    print(f"\n⚠️  Command exited with code {result.returncode}")
            except Exception as e:
                print(f"\n❌ Error executing command: {e}")

            # Ask if user wants to continue
            print("\n" + "=" * 60)
            continue_running = questionary.confirm(
                "Run another command?", default=True, style=custom_style
            ).ask()

            if not continue_running:
                print("\n👋 Goodbye!\n")
                break

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

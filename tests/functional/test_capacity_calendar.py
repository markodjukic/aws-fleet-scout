"""
Functional tests for capacity calendar command.

These tests make real AWS API calls and require valid credentials.
Run with: pytest tests/functional/test_capacity_calendar.py -v
"""

import pytest

from aws_fleet_scout.commands.capacity.calendar import main as capacity_calendar


@pytest.mark.functional
class TestCapacityCalendar:
    """Test capacity calendar command with real AWS calls."""

    def test_calendar_single_instance(self):
        """Test calendar view for single instance type."""
        result = capacity_calendar(
            instance_type="p4d.24xlarge",
            window=7,
            duration=1,  # 1 day
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None
        assert "calendar" in result
        assert "p4d.24xlarge" in result["calendar"]
        assert isinstance(result["calendar"]["p4d.24xlarge"], dict)

    def test_calendar_multiple_instances(self):
        """Test calendar view for multiple instance types."""
        result = capacity_calendar(
            job_spec='{"p4d.24xlarge": 1, "p4de.24xlarge": 1}',
            window=7,
            duration=1,  # 1 day
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None
        assert "calendar" in result
        assert "p4d.24xlarge" in result["calendar"]
        assert "p4de.24xlarge" in result["calendar"]

    def test_calendar_extended_days(self):
        """Test calendar with extended day range."""
        result = capacity_calendar(
            instance_type="p4d.24xlarge",
            window=14,
            duration=1,  # 1 day
            output="json",
            regions=["us-east-1", "us-west-2"],
        )

        assert result is not None
        assert "calendar" in result
        assert "p4d.24xlarge" in result["calendar"]

    def test_calendar_longer_duration(self):
        """Test calendar with longer duration (7 days)."""
        result = capacity_calendar(
            instance_type="p4d.24xlarge",
            window=7,
            duration=7,  # 7 days
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None
        assert "calendar" in result
        assert "p4d.24xlarge" in result["calendar"]

    def test_calendar_invalid_duration(self):
        """Test that invalid duration raises error."""
        from click.exceptions import BadParameter

        with pytest.raises(BadParameter):
            capacity_calendar(
                instance_type="p4d.24xlarge",
                window=7,
                duration=15,  # Invalid: not 1-14 or 21-182 in 7-day steps
                output="json",
                regions=["us-east-1"],
            )

    def test_calendar_missing_instance_type(self):
        """Test that missing instance type raises error."""
        from click.exceptions import BadParameter

        with pytest.raises(BadParameter):
            capacity_calendar(window=7, duration=1, output="json", regions=["us-east-1"])


class TestCapacityCalendarEdgeCases:
    """Test capacity calendar edge cases with real AWS."""

    def test_calendar_with_longer_duration(self):
        """Should work with longer durations."""
        from aws_fleet_scout.commands.capacity.calendar import main

        result = main(
            instance_type="p4d.24xlarge",
            duration=7,  # 7 days
            window=14,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

    def test_calendar_with_multiple_regions(self):
        """Should work with multiple regions."""
        from aws_fleet_scout.commands.capacity.calendar import main

        result = main(
            instance_type="p4d.24xlarge",
            duration=1,
            window=7,
            output="json",
            regions=["us-east-1", "us-west-2"],
        )

        assert result is not None

    def test_calendar_with_job_spec(self):
        """Should work with job spec."""
        from aws_fleet_scout.commands.capacity.calendar import main

        result = main(
            job_spec='{"p4d.24xlarge": 2}',
            duration=1,
            window=7,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

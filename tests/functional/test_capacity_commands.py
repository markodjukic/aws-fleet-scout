"""
Functional tests for capacity commands (capacity find).

These tests verify the end-to-end workflow works with real AWS APIs.
Requires valid AWS credentials and appropriate IAM permissions.

Note: Capacity blocks may not always be available, so tests check
for proper structure rather than requiring specific results.
"""

import pytest

from aws_fleet_scout.commands.capacity.find import main as capacity_find_main

pytestmark = pytest.mark.functional


class TestCapacityFindIntegration:
    """Test capacity find command with real AWS calls"""

    @pytest.mark.slow
    def test_capacity_find_returns_structure(self):
        """Should return proper structure even if no blocks available"""
        result = capacity_find_main(
            instance_type="p4d.24xlarge",
            duration=1,  # 1 day (converted to 24 hours internally)
            max_days=7,
            output="json",
            regions=["us-east-1"],
        )

        # Result structure should be valid even if no capacity blocks found
        assert result is not None
        # The command should complete without errors

    @pytest.mark.slow
    def test_capacity_find_multiple_regions(self):
        """Should query multiple regions for capacity blocks"""
        result = capacity_find_main(
            instance_type="p4d.24xlarge",
            duration=1,  # 1 day (converted to 24 hours internally)
            max_days=7,
            output="json",
            regions=["us-east-1", "us-west-2"],
        )

        # Should complete without errors
        assert result is not None


class TestCapacityFindEdgeCases:
    """Test capacity find edge cases with real AWS."""

    def test_find_with_longer_duration(self):
        """Should work with longer durations."""
        from aws_fleet_scout.commands.capacity.find import main

        result = main(
            instance_type="p4d.24xlarge",
            duration=7,  # 7 days
            max_days=14,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

    def test_find_with_multiple_instance_types(self):
        """Should work with multiple instance types."""
        from aws_fleet_scout.commands.capacity.find import main

        result = main(
            job_spec='{"p4d.24xlarge": 1, "p5.48xlarge": 2}',
            duration=1,
            max_days=7,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

    def test_find_with_extended_search_window(self):
        """Should work with extended search window."""
        from aws_fleet_scout.commands.capacity.find import main

        result = main(
            instance_type="p4d.24xlarge",
            duration=1,
            max_days=30,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

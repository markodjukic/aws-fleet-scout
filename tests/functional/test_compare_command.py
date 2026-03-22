"""
Functional tests for compare command.

These tests verify the end-to-end workflow works with real AWS APIs.
Requires valid AWS credentials and appropriate IAM permissions.
"""

import pytest

from aws_fleet_scout.commands.compare import main as compare_main

pytestmark = pytest.mark.functional


class TestCompareIntegration:
    """Test compare command with real AWS calls"""

    @pytest.mark.slow
    def test_compare_returns_results(self):
        """Should compare all procurement methods"""
        result = compare_main(
            instance_type="t3.micro",
            count=1,
            duration=24,
            max_days=7,
            output="json",
            regions=["us-east-1"],
        )

        assert isinstance(result, dict)
        # Should have results for t3.micro
        assert "t3.micro" in result

        instance_result = result["t3.micro"]
        assert "spot" in instance_result
        assert "capacity_blocks" in instance_result
        assert "on_demand" in instance_result

    @pytest.mark.slow
    def test_compare_multiple_regions(self):
        """Should compare across multiple regions"""
        result = compare_main(
            instance_type="t3.micro",
            count=1,
            duration=24,
            max_days=7,
            output="json",
            regions=["us-east-1", "us-west-2"],
        )

        assert isinstance(result, dict)
        assert "t3.micro" in result


class TestCompareEdgeCases:
    """Test compare command edge cases with real AWS."""

    def test_compare_with_default_regions(self):
        """Should work with default regions."""
        from aws_fleet_scout.commands.compare import main

        result = main(instance_type="t3.micro", count=1, output="json")

        assert result is not None
        assert "t3.micro" in result

    def test_compare_with_custom_duration(self):
        """Should accept custom duration for capacity blocks."""
        from aws_fleet_scout.commands.compare import main

        result = main(
            instance_type="t3.micro",
            count=1,
            duration=7,  # 7 days
            max_days=14,
            output="json",
            regions=["us-east-1"],
        )

        assert result is not None

    def test_compare_with_large_count(self):
        """Should handle large instance counts."""
        from aws_fleet_scout.commands.compare import main

        result = main(instance_type="t3.micro", count=100, output="json", regions=["us-east-1"])

        assert result is not None

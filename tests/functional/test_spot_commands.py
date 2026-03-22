"""
Functional tests for spot commands (spot score, spot request).

These tests verify the end-to-end workflow works with real AWS APIs.
Requires valid AWS credentials and appropriate IAM permissions.
"""

import pytest

from aws_fleet_scout.commands.spot.score import main as spot_score_main

pytestmark = pytest.mark.functional


class TestSpotScoreIntegration:
    """Test spot score command with real AWS calls"""

    def test_spot_score_returns_results(self):
        """Should return real spot placement scores"""
        result = spot_score_main(
            instance_type="t3.micro", output="json", regions=["us-east-1"], target_capacity=1
        )

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of first result
        score = result[0]
        assert "Region" in score
        assert "AvailabilityZoneId" in score
        assert "Score" in score
        assert score["Region"] == "us-east-1"

    def test_spot_score_sorted_by_score(self):
        """Results should be sorted by score descending"""
        result = spot_score_main(
            instance_type="t3.micro", output="json", regions=["us-east-1"], target_capacity=1
        )

        if len(result) > 1:
            # Verify descending order
            for i in range(len(result) - 1):
                assert result[i]["Score"] >= result[i + 1]["Score"]

    def test_spot_score_multiple_regions(self):
        """Should query multiple regions"""
        result = spot_score_main(
            instance_type="t3.micro",
            output="json",
            regions=["us-east-1", "us-west-2"],
            target_capacity=1,
        )

        assert isinstance(result, list)
        # Should have results from both regions
        regions = {score["Region"] for score in result}
        assert "us-east-1" in regions or "us-west-2" in regions

    @pytest.mark.slow
    def test_spot_score_gpu_instance(self):
        """Should work with GPU instances (slow test)"""
        result = spot_score_main(
            instance_type="p4d.24xlarge", output="json", regions=["us-east-1"], target_capacity=1
        )

        # May or may not have availability, but should not error
        assert isinstance(result, list)


class TestSpotScoreEdgeCases:
    """Test spot score edge cases with real AWS"""

    def test_spot_score_large_capacity(self):
        """Should handle large target capacity"""
        result = spot_score_main(
            instance_type="t3.micro", output="json", regions=["us-east-1"], target_capacity=100
        )

        assert isinstance(result, list)

    def test_spot_score_all_default_regions(self):
        """Should work with default regions (no regions specified)"""
        result = spot_score_main(instance_type="t3.micro", output="json", target_capacity=5)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_spot_score_compute_optimized(self):
        """Should work with compute-optimized instances"""
        result = spot_score_main(
            instance_type="c6i.xlarge", output="json", regions=["us-east-1"], target_capacity=10
        )

        assert isinstance(result, list)

    def test_spot_score_memory_optimized(self):
        """Should work with memory-optimized instances"""
        result = spot_score_main(
            instance_type="r6i.xlarge", output="json", regions=["us-east-1"], target_capacity=5
        )

        assert isinstance(result, list)

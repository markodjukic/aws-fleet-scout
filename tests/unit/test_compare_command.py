"""
Unit tests for compare command.

These tests use mocking and don't make real AWS API calls.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest


class TestCompareCommand:
    """Test compare command functionality."""

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_instance_type(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare with single instance type."""
        from aws_fleet_scout.commands.compare import main

        # Mock spot data
        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        # Mock on-demand availability
        mock_check_od.return_value = {"us-east-1": True}

        # Mock pricing
        mock_pricing_client = Mock()
        mock_pricing_client.get_products.return_value = {"PriceList": []}
        mock_pricing.return_value = mock_pricing_client

        result = main(instance_type="t3.micro", count=1, output="json", regions=["us-east-1"])

        assert result is not None
        assert "t3.micro" in result
        assert "spot" in result["t3.micro"]
        assert "on_demand" in result["t3.micro"]

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_job_spec(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare with job spec."""
        from aws_fleet_scout.commands.compare import main

        # Mock responses
        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {"SpotPlacementScores": []}
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": False}
        mock_pricing.return_value = Mock()

        result = main(job_spec='{"t3.micro": 2}', output="json", regions=["us-east-1"])

        assert result is not None
        assert "t3.micro" in result

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_multiple_regions(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare across multiple regions."""
        from aws_fleet_scout.commands.compare import main

        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8},
                {"Region": "us-west-2", "AvailabilityZoneId": "usw2-az1", "Score": 7},
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True, "us-west-2": True}
        mock_pricing.return_value = Mock()

        result = main(
            instance_type="t3.micro", count=1, output="json", regions=["us-east-1", "us-west-2"]
        )

        assert result is not None
        assert "t3.micro" in result


class TestCompareEdgeCases:
    """Test edge cases for compare command."""

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_no_spot_availability(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare when spot is not available."""
        from aws_fleet_scout.commands.compare import main

        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {"SpotPlacementScores": []}
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(instance_type="t3.micro", count=1, output="json", regions=["us-east-1"])

        assert result is not None
        assert "t3.micro" in result

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_capacity_blocks(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare with capacity block availability."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": [
                {
                    "StartDate": datetime(2026, 1, 25, 10, 0, tzinfo=timezone.utc),
                    "CapacityBlockDurationHours": 24,
                    "UpfrontFee": "300.00",
                    "AvailabilityZone": "us-east-1a",
                    "CapacityBlockOfferingId": "cb-123",
                }
            ]
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(instance_type="p4d.24xlarge", count=1, output="json", regions=["us-east-1"])

        assert result is not None
        assert "p4d.24xlarge" in result
        assert "capacity_blocks" in result["p4d.24xlarge"]

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_multiple_instance_types(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare with multiple instance types in job spec."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(
            job_spec='{"t3.micro": 2, "t3.small": 3}', output="json", regions=["us-east-1"]
        )

        assert result is not None
        assert "t3.micro" in result
        assert "t3.small" in result


class TestCompareValidation:
    """Test validation and error handling in compare command."""

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_invalid_json(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare with invalid job spec JSON."""
        import typer

        from aws_fleet_scout.commands.compare import main

        mock_ec2.return_value = Mock()
        mock_pricing.return_value = Mock()
        mock_check_od.return_value = {}

        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(job_spec="invalid json", output="json", regions=["us-east-1"])

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_requires_instance_or_job_spec(self, mock_check_od, mock_pricing, mock_ec2):
        """Test that either instance_type or job_spec is required."""
        import typer

        from aws_fleet_scout.commands.compare import main

        mock_ec2.return_value = Mock()
        mock_pricing.return_value = Mock()
        mock_check_od.return_value = {}

        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(output="json", regions=["us-east-1"])

    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_error_handling(self, mock_check_od, mock_pricing, mock_ec2):
        """Test compare handles API errors gracefully."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.side_effect = Exception("API Error")
        mock_ec2_client.describe_spot_price_history.return_value = {"SpotPriceHistory": []}
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": False}
        mock_pricing.return_value = Mock()

        result = main(instance_type="t3.micro", count=1, output="json", regions=["us-east-1"])

        # Should handle error and return result
        assert result is not None


class TestCompareDiscovery:
    """Test discovery functionality in compare command."""

    @patch("aws_fleet_scout.utils.aws_client.discover_instances_by_prefix")
    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_discover_p_series(
        self, mock_check_od, mock_pricing, mock_ec2, mock_discover
    ):
        """Test compare with --discover-p-series flag."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        # Mock discovery
        mock_discover.return_value = ["p5.48xlarge", "p5.4xlarge"]

        # Mock spot data
        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(discover_p_series=True, output="json", regions=["us-east-1"])

        # Should have called discovery with P-series prefixes
        mock_discover.assert_called_once_with(["us-east-1"], ["p4", "p5", "p6"])

        # Should have results for discovered instances
        assert result is not None
        assert "p5.48xlarge" in result
        assert "p5.4xlarge" in result

    @patch("aws_fleet_scout.utils.aws_client.discover_instances_by_prefix")
    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_discover_custom_prefix(
        self, mock_check_od, mock_pricing, mock_ec2, mock_discover
    ):
        """Test compare with --discover flag and custom prefix."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        # Mock discovery
        mock_discover.return_value = ["g5.xlarge", "g5.2xlarge"]

        # Mock spot data
        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(discover="g5", output="json", regions=["us-east-1"])

        # Should have called discovery with g5 prefix
        mock_discover.assert_called_once_with(["us-east-1"], ["g5"])

        # Should have results for discovered instances
        assert result is not None
        assert "g5.xlarge" in result
        assert "g5.2xlarge" in result

    @patch("aws_fleet_scout.utils.aws_client.discover_instances_by_prefix")
    @patch("aws_fleet_scout.commands.compare.get_ec2_client")
    @patch("aws_fleet_scout.commands.compare.get_pricing_client")
    @patch("aws_fleet_scout.commands.compare.check_on_demand_availability")
    def test_compare_with_discover_multiple_prefixes(
        self, mock_check_od, mock_pricing, mock_ec2, mock_discover
    ):
        """Test compare with multiple comma-separated prefixes."""
        from datetime import datetime, timezone

        from aws_fleet_scout.commands.compare import main

        # Mock discovery
        mock_discover.return_value = ["m7i.large", "c7i.xlarge"]

        # Mock spot data
        mock_ec2_client = Mock()
        mock_ec2_client.get_spot_placement_scores.return_value = {
            "SpotPlacementScores": [
                {"Region": "us-east-1", "AvailabilityZoneId": "use1-az1", "Score": 8}
            ]
        }
        mock_ec2_client.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "1.50", "Timestamp": datetime.now(timezone.utc)}]
        }
        mock_ec2_client.describe_capacity_block_offerings.return_value = {
            "CapacityBlockOfferings": []
        }
        mock_ec2.return_value = mock_ec2_client

        mock_check_od.return_value = {"us-east-1": True}
        mock_pricing.return_value = Mock()

        result = main(discover="m7i,c7i", output="json", regions=["us-east-1"])

        # Should have called discovery with both prefixes
        mock_discover.assert_called_once_with(["us-east-1"], ["m7i", "c7i"])

        # Should have results for discovered instances
        assert result is not None

    @patch("aws_fleet_scout.utils.aws_client.discover_instances_by_prefix")
    def test_compare_with_discover_no_instances_found(self, mock_discover):
        """Test compare when discovery finds no instances."""
        from aws_fleet_scout.commands.compare import main

        # Mock discovery returning empty list
        mock_discover.return_value = []

        result = main(discover="p99", output="json", regions=["us-east-1"])  # Non-existent prefix

        # Should return empty dict
        assert result == {}

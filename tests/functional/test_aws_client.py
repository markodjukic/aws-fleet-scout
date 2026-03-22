"""
Functional tests for AWS client utilities.

These tests make real AWS API calls to verify client functionality.
Requires valid AWS credentials and appropriate IAM permissions.

Run with: pytest tests/functional/test_aws_client.py -v
"""

import pytest

from aws_fleet_scout.config import DEFAULT_REGIONS
from aws_fleet_scout.utils.aws_client import (
    check_on_demand_availability,
    discover_instances_by_prefix,
    discover_p_series_instances,
    get_available_regions_for_instance,
    get_ec2_client,
    get_pricing_client,
)

pytestmark = pytest.mark.functional


class TestEC2ClientIntegration:
    """Test real EC2 API calls"""

    def test_get_ec2_client_creates_valid_client(self):
        """Should create a working EC2 client"""
        client = get_ec2_client("us-east-1")

        assert client is not None
        assert hasattr(client, "describe_instances")
        assert hasattr(client, "get_spot_placement_scores")

    def test_describe_availability_zones(self):
        """Should fetch real availability zones"""
        client = get_ec2_client("us-east-1")

        response = client.describe_availability_zones()

        assert "AvailabilityZones" in response
        assert len(response["AvailabilityZones"]) > 0

        # Check structure
        az = response["AvailabilityZones"][0]
        assert "ZoneName" in az
        assert "ZoneId" in az
        assert az["ZoneName"].startswith("us-east-1")


class TestInstanceTypeAvailability:
    """Test real instance type availability checks"""

    def test_check_common_instance_availability(self):
        """Should check availability for common instance types"""
        # Use a common instance type that should be available
        result = check_on_demand_availability("t3.micro", ["us-east-1"])

        assert "us-east-1" in result
        assert isinstance(result["us-east-1"], bool)
        # t3.micro should be available in us-east-1
        assert result["us-east-1"] is True

    def test_check_gpu_instance_availability(self):
        """Should check availability for GPU instances"""
        # P4d instances should be available in some regions
        result = check_on_demand_availability("p4d.24xlarge", ["us-east-1", "us-west-2"])

        assert "us-east-1" in result
        assert "us-west-2" in result
        # At least one should be available
        assert any(result.values())

    def test_get_available_regions_filters_correctly(self):
        """Should return only regions where instance is available"""
        # t3.micro should be available in most regions
        result = get_available_regions_for_instance("t3.micro", DEFAULT_REGIONS)

        assert isinstance(result, list)
        assert len(result) > 0
        # Should be a subset of DEFAULT_REGIONS
        assert all(r in DEFAULT_REGIONS for r in result)


class TestSpotPlacementScores:
    """Test real spot placement score queries"""

    def test_get_spot_placement_scores(self):
        """Should fetch real spot placement scores"""
        client = get_ec2_client("us-east-1")

        response = client.get_spot_placement_scores(
            InstanceTypes=["t3.micro"],
            TargetCapacity=1,
            TargetCapacityUnitType="units",
            RegionNames=["us-east-1"],
            SingleAvailabilityZone=True,
        )

        assert "SpotPlacementScores" in response
        scores = response["SpotPlacementScores"]

        if len(scores) > 0:
            score = scores[0]
            assert "Region" in score
            assert "AvailabilityZoneId" in score
            assert "Score" in score
            assert 0 <= score["Score"] <= 10


class TestPricingAPI:
    """Test real pricing API calls"""

    def test_pricing_client_works(self):
        """Should create working pricing client"""
        client = get_pricing_client("us-east-1")

        assert client is not None
        assert hasattr(client, "get_products")

    @pytest.mark.slow
    def test_get_on_demand_pricing(self):
        """Should fetch real on-demand pricing (slow test)"""
        client = get_pricing_client("us-east-1")

        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t3.micro"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            ],
            MaxResults=1,
        )

        assert "PriceList" in response
        # Pricing API should return results for t3.micro
        assert len(response["PriceList"]) > 0


class TestInstanceDiscovery:
    """Test real instance discovery functionality"""

    def test_discover_p_series_instances(self):
        """Should discover real P-series instances"""
        result = discover_p_series_instances(["us-east-1"])

        assert isinstance(result, list)
        # Should find at least some P-series instances
        assert len(result) > 0
        # All should start with p4, p5, or p6
        assert all(i.startswith(("p4", "p5", "p6")) for i in result)
        # Should be sorted
        assert result == sorted(result)

    def test_discover_instances_by_prefix_single(self):
        """Should discover instances by single prefix"""
        result = discover_instances_by_prefix(["us-east-1"], ["t3"])

        assert isinstance(result, list)
        # Should find t3 instances
        assert len(result) > 0
        # All should start with t3
        assert all(i.startswith("t3") for i in result)
        # Should include common types
        assert "t3.micro" in result
        assert "t3.small" in result

    def test_discover_instances_by_prefix_multiple(self):
        """Should discover instances by multiple prefixes"""
        result = discover_instances_by_prefix(["us-east-1"], ["t3", "t2"])

        assert isinstance(result, list)
        # Should find both t3 and t2 instances
        assert len(result) > 0
        # All should start with t3 or t2
        assert all(i.startswith(("t3", "t2")) for i in result)
        # Should be deduplicated and sorted
        assert result == sorted(set(result))

    def test_discover_instances_multiple_regions(self):
        """Should discover and deduplicate across regions"""
        result = discover_instances_by_prefix(["us-east-1", "us-west-2"], ["t3"])

        assert isinstance(result, list)
        # Should find t3 instances
        assert len(result) > 0
        # Should be deduplicated (no duplicates)
        assert len(result) == len(set(result))
        # Should be sorted
        assert result == sorted(result)

    def test_discover_instances_gpu_families(self):
        """Should discover GPU instance families"""
        result = discover_instances_by_prefix(["us-east-1"], ["g5"])

        assert isinstance(result, list)
        # Should find g5 instances if available
        if len(result) > 0:
            assert all(i.startswith("g5") for i in result)

    def test_discover_instances_no_matches(self):
        """Should return empty list for non-existent prefix"""
        result = discover_instances_by_prefix(["us-east-1"], ["xyz999"])

        assert isinstance(result, list)
        assert len(result) == 0

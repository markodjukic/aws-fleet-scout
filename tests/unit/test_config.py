"""Unit tests for configuration constants"""

from aws_fleet_scout.config import DEFAULT_REGIONS, PRICING_REGION_MAP


class TestConfig:
    """Test configuration constants (no AWS calls)"""

    def test_default_regions_not_empty(self):
        """Default regions should be defined"""
        assert len(DEFAULT_REGIONS) > 0
        assert isinstance(DEFAULT_REGIONS, list)

    def test_default_regions_valid(self):
        """Default regions should be valid AWS region codes"""
        for region in DEFAULT_REGIONS:
            assert region.startswith("us-")
            assert "-" in region

    def test_pricing_region_map_coverage(self):
        """Pricing map should cover major regions"""
        expected_regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"]
        for region in expected_regions:
            assert region in PRICING_REGION_MAP

    def test_pricing_region_map_format(self):
        """Pricing region names should be properly formatted"""
        for region_code, region_name in PRICING_REGION_MAP.items():
            assert isinstance(region_code, str)
            assert isinstance(region_name, str)
            assert len(region_name) > 0
            # Should be human-readable format like "US East (N. Virginia)"
            assert "(" in region_name or "Asia" in region_name or "EU" in region_name

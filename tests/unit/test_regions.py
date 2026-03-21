"""Unit tests for region utilities"""

import pytest
from aws_fleet_scout.utils.regions import (
    expand_region_wildcards,
    get_all_regions,
    validate_regions,
    parse_region_input
)


class TestExpandRegionWildcards:
    """Test wildcard expansion for regions."""
    
    def test_expand_us_wildcard(self):
        """Should expand us-* to all US regions."""
        result = expand_region_wildcards(['us-*'])
        assert 'us-east-1' in result
        assert 'us-east-2' in result
        assert 'us-west-1' in result
        assert 'us-west-2' in result
        assert 'eu-west-1' not in result
    
    def test_expand_us_east_wildcard(self):
        """Should expand us-east-* to US East regions only."""
        result = expand_region_wildcards(['us-east-*'])
        assert 'us-east-1' in result
        assert 'us-east-2' in result
        assert 'us-west-1' not in result
        assert 'eu-east-1' not in result
    
    def test_expand_eu_wildcard(self):
        """Should expand eu-* to all EU regions."""
        result = expand_region_wildcards(['eu-*'])
        assert 'eu-west-1' in result
        assert 'eu-central-1' in result
        assert 'us-east-1' not in result
    
    def test_expand_multiple_wildcards(self):
        """Should expand multiple wildcard patterns."""
        result = expand_region_wildcards(['us-east-*', 'eu-west-*'])
        assert 'us-east-1' in result
        assert 'us-east-2' in result
        assert 'eu-west-1' in result
        assert 'eu-west-2' in result
        assert 'us-west-1' not in result
    
    def test_expand_all_wildcard(self):
        """Should expand * to all regions."""
        result = expand_region_wildcards(['*'])
        assert len(result) > 20  # AWS has many regions
        assert 'us-east-1' in result
        assert 'eu-west-1' in result
        assert 'ap-southeast-1' in result
    
    def test_no_wildcard_returns_exact(self):
        """Should return exact region when no wildcard."""
        result = expand_region_wildcards(['us-east-1'])
        assert result == ['us-east-1']
    
    def test_mixed_wildcard_and_exact(self):
        """Should handle mix of wildcards and exact regions."""
        result = expand_region_wildcards(['us-east-*', 'eu-west-1'])
        assert 'us-east-1' in result
        assert 'us-east-2' in result
        assert 'eu-west-1' in result
        assert 'us-west-1' not in result
    
    def test_deduplication(self):
        """Should deduplicate overlapping patterns."""
        result = expand_region_wildcards(['us-*', 'us-east-1'])
        # us-east-1 should only appear once
        assert result.count('us-east-1') == 1
    
    def test_sorted_output(self):
        """Should return sorted list."""
        result = expand_region_wildcards(['us-west-*', 'us-east-*'])
        assert result == sorted(result)
    
    def test_empty_input(self):
        """Should return empty list for empty input."""
        result = expand_region_wildcards([])
        assert result == []


class TestGetAllRegions:
    """Test getting all available regions."""
    
    def test_returns_list(self):
        """Should return a list of regions."""
        result = get_all_regions()
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_contains_common_regions(self):
        """Should contain common AWS regions."""
        result = get_all_regions()
        assert 'us-east-1' in result
        assert 'us-west-2' in result
        assert 'eu-west-1' in result
    
    def test_is_sorted(self):
        """Should return sorted list."""
        result = get_all_regions()
        assert result == sorted(result)


class TestValidateRegions:
    """Test region validation."""
    
    def test_all_valid(self):
        """Should return all regions as valid."""
        valid, invalid = validate_regions(['us-east-1', 'us-west-2'])
        assert valid == ['us-east-1', 'us-west-2']
        assert invalid == []
    
    def test_all_invalid(self):
        """Should return all regions as invalid."""
        valid, invalid = validate_regions(['invalid-1', 'fake-region'])
        assert valid == []
        assert invalid == ['invalid-1', 'fake-region']
    
    def test_mixed_valid_invalid(self):
        """Should separate valid and invalid regions."""
        valid, invalid = validate_regions(['us-east-1', 'invalid-1', 'eu-west-1'])
        assert 'us-east-1' in valid
        assert 'eu-west-1' in valid
        assert 'invalid-1' in invalid
    
    def test_empty_input(self):
        """Should handle empty input."""
        valid, invalid = validate_regions([])
        assert valid == []
        assert invalid == []


class TestParseRegionInput:
    """Test parsing region input strings."""
    
    def test_parse_comma_separated(self):
        """Should parse comma-separated regions."""
        result = parse_region_input("us-east-1,us-west-2")
        assert result == ['us-east-1', 'us-west-2']
    
    def test_parse_with_spaces(self):
        """Should handle spaces around commas."""
        result = parse_region_input("us-east-1 , us-west-2 , eu-west-1")
        assert result == ['eu-west-1', 'us-east-1', 'us-west-2']  # Sorted
    
    def test_parse_wildcard(self):
        """Should expand wildcards."""
        result = parse_region_input("us-east-*")
        assert 'us-east-1' in result
        assert 'us-east-2' in result
        assert 'us-west-1' not in result
    
    def test_parse_multiple_wildcards(self):
        """Should expand multiple wildcards."""
        result = parse_region_input("us-east-*,eu-west-*")
        assert 'us-east-1' in result
        assert 'eu-west-1' in result
    
    def test_parse_none(self):
        """Should return None for None input."""
        result = parse_region_input(None)
        assert result is None
    
    def test_parse_empty_string(self):
        """Should return None for empty string."""
        result = parse_region_input("")
        assert result is None
    
    def test_parse_whitespace_only(self):
        """Should return None for whitespace-only string."""
        result = parse_region_input("   ")
        assert result is None
    
    def test_parse_single_region(self):
        """Should handle single region."""
        result = parse_region_input("us-east-1")
        assert result == ['us-east-1']

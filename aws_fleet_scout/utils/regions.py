"""
Region utilities for AWS Fleet Scout.

Provides functions for working with AWS regions, including wildcard expansion.
"""

import fnmatch
from typing import List, Optional
from ..config import PRICING_REGION_MAP


def expand_region_wildcards(region_patterns: List[str]) -> List[str]:
    """
    Expand region wildcard patterns to actual region names.
    
    Supports Unix-style wildcards:
    - `*` matches any characters
    - `?` matches a single character
    - `[seq]` matches any character in seq
    - `[!seq]` matches any character not in seq
    
    Args:
        region_patterns: List of region patterns (e.g., ['us-*', 'eu-west-*'])
    
    Returns:
        List of matching region names, sorted and deduplicated
    
    Examples:
        >>> expand_region_wildcards(['us-east-*'])
        ['us-east-1', 'us-east-2']
        
        >>> expand_region_wildcards(['us-*', 'eu-west-1'])
        ['eu-west-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
        
        >>> expand_region_wildcards(['*'])
        ['af-south-1', 'ap-east-1', ...]  # All regions
    """
    if not region_patterns:
        return []
    
    # Get all available regions from the pricing map
    all_regions = list(PRICING_REGION_MAP.keys())
    
    matched_regions = set()
    
    for pattern in region_patterns:
        # If pattern has no wildcards, add it directly
        if '*' not in pattern and '?' not in pattern and '[' not in pattern:
            matched_regions.add(pattern)
        else:
            # Match pattern against all regions
            matches = fnmatch.filter(all_regions, pattern)
            matched_regions.update(matches)
    
    # Return sorted list
    return sorted(matched_regions)


def get_all_regions() -> List[str]:
    """
    Get all available AWS regions.
    
    Returns:
        Sorted list of all AWS region names
    """
    return sorted(PRICING_REGION_MAP.keys())


def validate_regions(regions: List[str]) -> tuple[List[str], List[str]]:
    """
    Validate that regions exist in AWS.
    
    Args:
        regions: List of region names to validate
    
    Returns:
        Tuple of (valid_regions, invalid_regions)
    """
    all_regions = set(PRICING_REGION_MAP.keys())
    valid = []
    invalid = []
    
    for region in regions:
        if region in all_regions:
            valid.append(region)
        else:
            invalid.append(region)
    
    return valid, invalid


def parse_region_input(region_input: Optional[str]) -> Optional[List[str]]:
    """
    Parse region input string and expand wildcards.
    
    Args:
        region_input: Comma-separated region patterns (e.g., "us-*,eu-west-1")
                     or None for default regions
    
    Returns:
        List of expanded region names, or None if input is None
    
    Examples:
        >>> parse_region_input("us-east-1,us-west-2")
        ['us-east-1', 'us-west-2']
        
        >>> parse_region_input("us-*")
        ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
        
        >>> parse_region_input(None)
        None
    """
    if region_input is None:
        return None
    
    # Split by comma and strip whitespace
    patterns = [p.strip() for p in region_input.split(',') if p.strip()]
    
    if not patterns:
        return None
    
    # Expand wildcards
    return expand_region_wildcards(patterns)

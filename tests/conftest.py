"""Shared test fixtures and utilities"""

import pytest
from unittest.mock import Mock


# Register pytest markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "functional: marks tests as functional (require AWS access)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


@pytest.fixture
def mock_ec2_client():
    """Mock EC2 client with common responses"""
    client = Mock()
    
    # Mock spot placement scores
    client.get_spot_placement_scores.return_value = {
        'SpotPlacementScores': [
            {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9},
            {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az2', 'Score': 7}
        ]
    }
    
    # Mock spot price history
    client.describe_spot_price_history.return_value = {
        'SpotPriceHistory': [
            {
                'InstanceType': 'p5.48xlarge',
                'AvailabilityZone': 'us-east-1a',
                'SpotPrice': '15.5080',
                'Timestamp': '2026-01-23T00:00:00Z'
            }
        ]
    }
    
    # Mock instance type offerings
    client.describe_instance_type_offerings.return_value = {
        'InstanceTypeOfferings': [
            {'InstanceType': 'p5.48xlarge', 'Location': 'us-east-1'}
        ]
    }
    
    # Mock AZ mapping
    client.describe_availability_zones.return_value = {
        'AvailabilityZones': [
            {'ZoneName': 'us-east-1a', 'ZoneId': 'use1-az1'},
            {'ZoneName': 'us-east-1b', 'ZoneId': 'use1-az2'}
        ]
    }
    
    return client


@pytest.fixture
def mock_pricing_client():
    """Mock Pricing client"""
    client = Mock()
    
    client.get_products.return_value = {
        'PriceList': [
            '''{
                "product": {
                    "attributes": {
                        "preInstalledSw": "NA",
                        "capacitystatus": "Used"
                    }
                },
                "terms": {
                    "OnDemand": {
                        "term1": {
                            "priceDimensions": {
                                "dim1": {
                                    "pricePerUnit": {"USD": "32.7726"}
                                }
                            }
                        }
                    }
                }
            }'''
        ]
    }
    
    return client


@pytest.fixture
def sample_regions():
    """Sample region list for testing"""
    return ["us-east-1", "us-west-2"]

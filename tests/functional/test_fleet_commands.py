"""
Functional tests for fleet commands (pack, recommend, utility).

These tests verify the end-to-end workflow works with real AWS APIs.
Requires valid AWS credentials and appropriate IAM permissions.
"""

import pytest
from aws_fleet_scout.commands.fleet.pack import main as fleet_pack_main


pytestmark = pytest.mark.functional


class TestFleetPackIntegration:
    """Test fleet pack command with real AWS calls"""
    
    def test_fleet_pack_returns_results(self):
        """Should return best region for fleet packing"""
        result = fleet_pack_main(
            job_spec='{"t3.micro": 2, "t3.small": 1}',
            output='json',
            regions=['us-east-1', 'us-west-2']
        )
        
        assert isinstance(result, dict)
        assert 'best_region' in result
        assert 'best_score' in result
        assert 'region_scores' in result
        
        # Best region should be one of the queried regions
        assert result['best_region'] in ['us-east-1', 'us-west-2']
    
    def test_fleet_pack_single_region(self):
        """Should work with single region"""
        result = fleet_pack_main(
            job_spec='{"t3.micro": 5}',
            output='json',
            regions=['us-east-1']
        )
        
        assert isinstance(result, dict)
        assert result['best_region'] == 'us-east-1'
        assert result['best_score'] > 0
    
    @pytest.mark.slow
    def test_fleet_pack_mixed_instances(self):
        """Should handle mixed instance types (slow test)"""
        result = fleet_pack_main(
            job_spec='{"m6i.2xlarge": 2, "c6i.4xlarge": 3}',
            output='json',
            regions=['us-east-1', 'us-east-2']
        )
        
        assert isinstance(result, dict)
        assert 'best_region' in result
        assert 'region_scores' in result
        assert len(result['region_scores']) > 0



class TestFleetRecommendIntegration:
    """Test fleet recommend command with real AWS calls"""
    
    def test_recommend_with_instance(self):
        """Should recommend placement for single instance type"""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        result = main(
            instance='t3.micro',
            count=5,
            min_score=0.0,  # Accept any score
            output='json'
        )
        assert result is not None
    
    def test_recommend_with_job_spec(self):
        """Should recommend placement for job spec"""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        result = main(
            job_spec='{"t3.micro": 5, "t3.small": 2}',
            min_score=0.0,  # Accept any score
            output='json'
        )
        assert result is not None
    
    def test_recommend_with_region_filter(self):
        """Should respect region allowlist"""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        result = main(
            instance='t3.micro',
            count=10,
            min_score=0.0,  # Accept any score
            region_allowlist='us-east-1,us-west-2',
            output='json'
        )
        assert result is not None


class TestFleetUtilityIntegration:
    """Test fleet utility command with real AWS calls"""
    
    def test_utility_with_job_spec(self):
        """Should calculate utility scores for job spec"""
        from aws_fleet_scout.commands.fleet.utility import main
        
        result = main(
            job_spec='{"t3.micro": 5}',
            output='json',
            regions='us-east-1'
        )
        assert result is not None
    
    def test_utility_with_multiple_instances(self):
        """Should calculate utility scores for multiple instance types"""
        from aws_fleet_scout.commands.fleet.utility import main
        
        result = main(
            job_spec='{"t3.micro": 5, "t3.small": 2}',
            output='json',
            regions='us-east-1,us-west-2'
        )
        assert result is not None
    
    def test_utility_with_custom_weights(self):
        """Should accept custom utility weights"""
        from aws_fleet_scout.commands.fleet.utility import main
        
        result = main(
            job_spec='{"t3.micro": 5}',
            spot_weight=0.6,
            price_weight=0.3,
            latency_weight=0.1,
            output='json',
            regions='us-east-1'
        )
        assert result is not None

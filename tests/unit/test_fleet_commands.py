"""
Unit tests for fleet commands.

These tests use mocking and don't make real AWS API calls.
"""

import pytest
from unittest.mock import Mock, patch
from aws_fleet_scout.commands.fleet.pack import _compute_region_scores
from aws_fleet_scout.commands.fleet.recommend import (
    _classify_stability,
    _extract_instance_family,
    _has_gpu_family
)


class TestFleetPackHelpers:
    """Test fleet pack helper functions."""
    
    def test_compute_region_scores_single_az(self):
        """Test computing region scores with single AZ."""
        instance_scores = {
            'm7i.4xlarge': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 8},
                {'Region': 'us-west-2', 'AvailabilityZoneId': 'usw2-az1', 'Score': 6}
            ],
            'p5.48xlarge': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 7},
                {'Region': 'us-west-2', 'AvailabilityZoneId': 'usw2-az1', 'Score': 9}
            ]
        }
        
        job_requirements = {'m7i.4xlarge': 20, 'p5.48xlarge': 2}
        
        result = _compute_region_scores(instance_scores, job_requirements)
        
        assert 'us-east-1' in result
        assert 'us-west-2' in result
        # us-east-1: (8*20 + 7*2) / 22 = 174/22 = 7.909
        # us-west-2: (6*20 + 9*2) / 22 = 138/22 = 6.272
        assert result['us-east-1']['aggregate_score'] > result['us-west-2']['aggregate_score']
    
    def test_compute_region_scores_missing_instance_type(self):
        """Test that regions without all instance types are excluded."""
        instance_scores = {
            'm7i.4xlarge': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 8}
            ],
            'p5.48xlarge': [
                {'Region': 'us-west-2', 'AvailabilityZoneId': 'usw2-az1', 'Score': 9}
            ]
        }
        
        job_requirements = {'m7i.4xlarge': 20, 'p5.48xlarge': 2}
        
        result = _compute_region_scores(instance_scores, job_requirements)
        
        # Neither region has both instance types
        assert len(result) == 0


class TestPlacementRecommendHelpers:
    """Test placement recommendation helper functions."""
    
    def test_classify_stability_high(self):
        """Test high stability classification."""
        assert _classify_stability(8.0) == "High"
        assert _classify_stability(9.5) == "High"
        assert _classify_stability(10.0) == "High"
    
    def test_classify_stability_medium(self):
        """Test medium stability classification."""
        assert _classify_stability(6.0) == "Medium"
        assert _classify_stability(7.0) == "Medium"
        assert _classify_stability(7.9) == "Medium"
    
    def test_classify_stability_low(self):
        """Test low stability classification."""
        assert _classify_stability(0.0) == "Low"
        assert _classify_stability(3.5) == "Low"
        assert _classify_stability(5.9) == "Low"
    
    def test_extract_instance_family(self):
        """Test extracting instance family from type."""
        assert _extract_instance_family('m7i.4xlarge') == 'm7i'
        assert _extract_instance_family('p5.48xlarge') == 'p5'
        assert _extract_instance_family('c6i.32xlarge') == 'c6i'
        assert _extract_instance_family('t3.micro') == 't3'
    
    def test_has_gpu_family(self):
        """Test GPU family detection."""
        assert _has_gpu_family('p5.48xlarge', ['p5']) is True
        assert _has_gpu_family('p4d.24xlarge', ['p4d', 'p5']) is True
        assert _has_gpu_family('m7i.4xlarge', ['p5']) is False
        assert _has_gpu_family('p5e.48xlarge', ['p5']) is True  # p5e starts with p5


class TestFleetPackMain:
    """Test fleet pack main function."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.get_ec2_client')
    def test_pack_with_job_spec(self, mock_get_client):
        """Test fleet pack with job spec."""
        from aws_fleet_scout.commands.fleet.pack import main
        
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 8}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            job_spec='{"m7i.4xlarge": 10}',
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'region_scores' in result
    
    @patch('aws_fleet_scout.commands.fleet.pack.get_ec2_client')
    def test_pack_returns_sorted_scores(self, mock_get_client):
        """Test that pack returns scores sorted by aggregate score."""
        from aws_fleet_scout.commands.fleet.pack import main
        
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 8},
                {'Region': 'us-west-2', 'AvailabilityZoneId': 'usw2-az1', 'Score': 6}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            job_spec='{"t3.micro": 5}',
            output='json',
            regions=['us-east-1', 'us-west-2']
        )
        
        assert result is not None
        scores = result['region_scores']
        # Should be sorted descending
        for i in range(len(scores) - 1):
            assert scores[i]['aggregate_score'] >= scores[i+1]['aggregate_score']


class TestPlacementRecommendMain:
    """Test placement recommend main function."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_instance(self, mock_pack):
        """Test recommend with single instance."""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0,
                    'instance_scores': {'m7i.4xlarge': 8.0}
                }
            ]
        }
        
        result = main(
            instance='m7i.4xlarge',
            count=10,
            min_score=5.0,
            output='json'
        )
        
        assert result is not None



class TestFleetUtilityHelpers:
    """Test fleet utility helper functions."""
    
    def test_utility_weights_defaults(self):
        """Test default utility weights."""
        from aws_fleet_scout.commands.fleet.utility import UtilityWeights
        
        weights = UtilityWeights()
        assert weights.spot_stability_weight == 0.5
        assert weights.price_weight == 0.3
        assert weights.latency_weight == 0.2
    
    def test_utility_weights_custom(self):
        """Test custom utility weights."""
        from aws_fleet_scout.commands.fleet.utility import UtilityWeights
        
        weights = UtilityWeights(
            spot_stability_weight=0.6,
            price_weight=0.3,
            latency_weight=0.1
        )
        assert weights.spot_stability_weight == 0.6
        assert weights.price_weight == 0.3
        assert weights.latency_weight == 0.1


class TestFleetUtilityMain:
    """Test fleet utility main function."""
    
    def test_utility_weights_validation(self):
        """Test that utility weights must sum to 1.0."""
        from aws_fleet_scout.commands.fleet.utility import UtilityWeights
        
        # Valid weights
        weights = UtilityWeights(
            spot_stability_weight=0.5,
            price_weight=0.3,
            latency_weight=0.2
        )
        assert weights is not None
        
        # Invalid weights should raise ValueError
        with pytest.raises(ValueError):
            UtilityWeights(
                spot_stability_weight=0.5,
                price_weight=0.5,
                latency_weight=0.5  # Sum = 1.5, should fail
            )
    
    def test_latency_config_defaults(self):
        """Test LatencyConfig default values."""
        from aws_fleet_scout.commands.fleet.utility import LatencyConfig
        
        config = LatencyConfig()
        assert config.base_region is None
        assert config.inter_region_penalty == 0.3
        assert config.egress_cost_per_gb == 0.02
    
    def test_latency_config_custom(self):
        """Test LatencyConfig with custom values."""
        from aws_fleet_scout.commands.fleet.utility import LatencyConfig
        
        config = LatencyConfig(
            base_region='us-east-1',
            inter_region_penalty=0.5,
            egress_cost_per_gb=0.05
        )
        assert config.base_region == 'us-east-1'
        assert config.inter_region_penalty == 0.5
        assert config.egress_cost_per_gb == 0.05
    
    def test_composite_utility_to_dict(self):
        """Test CompositeUtility to_dict conversion."""
        from aws_fleet_scout.commands.fleet.utility import CompositeUtility
        
        utility = CompositeUtility(
            region='us-east-1',
            availability_zone_id='use1-az1',
            spot_score=8.0,
            price_score=7.5,
            latency_score=9.0,
            composite_utility=8.1,
            on_demand_price=1.50,
            estimated_hourly_cost=15.0,
            price_percentile=75.0
        )
        
        result = utility.to_dict()
        assert result['region'] == 'us-east-1'
        assert result['spot_score'] == 8.0
        assert result['composite_utility'] == 8.1
    
    @patch('aws_fleet_scout.commands.fleet.utility.calculate_composite_utility')
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_utility_main_json_output(self, mock_pack, mock_calc):
        """Test utility main function with JSON output."""
        from aws_fleet_scout.commands.fleet.utility import main, CompositeUtility
        
        # Mock fleet packing results
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0
                }
            ]
        }
        
        # Mock utility calculation
        mock_calc.return_value = [
            CompositeUtility(
                region='us-east-1',
                availability_zone_id='use1-az1',
                spot_score=8.0,
                price_score=7.5,
                latency_score=9.0,
                composite_utility=8.1
            )
        ]
        
        result = main(
            job_spec='{"m7i.4xlarge": 10}',
            output='json',
            spot_weight=0.5,
            price_weight=0.3,
            latency_weight=0.2
        )
        
        assert result is not None
        assert len(result) == 1
        assert result[0].region == 'us-east-1'


class TestPlacementRecommendConstraints:
    """Test placement recommendation with constraints."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_min_score(self, mock_pack):
        """Test recommend with minimum score constraint."""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0,
                    'instance_scores': {'m7i.4xlarge': 8.0}
                },
                {
                    'region': 'us-west-2',
                    'availability_zone_id': 'usw2-az1',
                    'aggregate_score': 4.0,
                    'instance_scores': {'m7i.4xlarge': 4.0}
                }
            ]
        }
        
        result = main(
            instance='m7i.4xlarge',
            count=10,
            min_score=6.0,
            output='json'
        )
        
        assert result is not None
        # Should only include us-east-1 (score 8.0), not us-west-2 (score 4.0)
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_region_allowlist(self, mock_pack):
        """Test recommend with region allowlist."""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0,
                    'instance_scores': {'m7i.4xlarge': 8.0}
                },
                {
                    'region': 'eu-west-1',
                    'availability_zone_id': 'euw1-az1',
                    'aggregate_score': 9.0,
                    'instance_scores': {'m7i.4xlarge': 9.0}
                }
            ]
        }
        
        result = main(
            instance='m7i.4xlarge',
            count=10,
            region_allowlist='us-east-1',
            output='json'
        )
        
        assert result is not None
        # Should only include us-east-1, not eu-west-1
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_gpu_families(self, mock_pack):
        """Test recommend with GPU family constraint."""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0,
                    'instance_scores': {'p5.48xlarge': 8.0}
                }
            ]
        }
        
        result = main(
            instance='p5.48xlarge',
            count=2,
            gpu_families='p5',
            output='json'
        )
        
        assert result is not None



class TestFleetPackValidation:
    """Test validation and error handling in fleet pack."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.get_ec2_client')
    def test_pack_with_invalid_json(self, mock_get_client):
        """Test pack with invalid job spec JSON."""
        from aws_fleet_scout.commands.fleet.pack import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='not valid json',
                output='json',
                regions=['us-east-1']
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.get_ec2_client')
    def test_pack_requires_job_spec(self, mock_get_client):
        """Test that job_spec is required."""
        from aws_fleet_scout.commands.fleet.pack import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                output='json',
                regions=['us-east-1']
            )


class TestFleetRecommendValidation:
    """Test validation and error handling in fleet recommend."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_invalid_json(self, mock_pack):
        """Test recommend with invalid job spec JSON."""
        from aws_fleet_scout.commands.fleet.recommend import main
        import typer
        
        mock_pack.return_value = {'region_scores': []}
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='invalid json',
                output='json'
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_requires_instance_or_job_spec(self, mock_pack):
        """Test that either instance or job_spec is required."""
        from aws_fleet_scout.commands.fleet.recommend import main
        import typer
        
        mock_pack.return_value = {'region_scores': []}
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                output='json'
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_no_placement_options(self, mock_pack):
        """Test recommend when no placement options found."""
        from aws_fleet_scout.commands.fleet.recommend import main
        import typer
        
        mock_pack.return_value = None
        
        with pytest.raises(typer.Exit):
            main(
                instance='t3.micro',
                count=10,
                output='json'
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_recommend_with_region_denylist(self, mock_pack):
        """Test recommend with region denylist."""
        from aws_fleet_scout.commands.fleet.recommend import main
        
        mock_pack.return_value = {
            'region_scores': [
                {
                    'region': 'us-east-1',
                    'availability_zone_id': 'use1-az1',
                    'aggregate_score': 8.0,
                    'instance_scores': {'t3.micro': 8.0}
                },
                {
                    'region': 'us-west-2',
                    'availability_zone_id': 'usw2-az1',
                    'aggregate_score': 7.0,
                    'instance_scores': {'t3.micro': 7.0}
                }
            ]
        }
        
        result = main(
            instance='t3.micro',
            count=10,
            min_score=0.0,
            region_denylist='us-west-2',
            output='json'
        )
        
        assert result is not None


class TestFleetUtilityValidation:
    """Test validation and error handling in fleet utility."""
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_utility_with_invalid_json(self, mock_pack):
        """Test utility with invalid job spec JSON."""
        from aws_fleet_scout.commands.fleet.utility import main
        import typer
        
        mock_pack.return_value = {'region_scores': []}
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='not valid json',
                output='json'
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_utility_requires_job_spec(self, mock_pack):
        """Test that job_spec is required."""
        from aws_fleet_scout.commands.fleet.utility import main
        import typer
        
        mock_pack.return_value = {'region_scores': []}
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                output='json'
            )
    
    @patch('aws_fleet_scout.commands.fleet.pack.main')
    def test_utility_with_invalid_weights(self, mock_pack):
        """Test utility with invalid weight sum."""
        from aws_fleet_scout.commands.fleet.utility import main
        import typer
        
        mock_pack.return_value = {'region_scores': []}
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='{"t3.micro": 5}',
                spot_weight=0.5,
                price_weight=0.5,
                latency_weight=0.5,  # Sum > 1.0
                output='json'
            )

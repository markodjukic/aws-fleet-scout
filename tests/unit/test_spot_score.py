"""Unit tests for SpotScore command (mocked)"""

import pytest
from unittest.mock import Mock, patch
from aws_fleet_scout.commands.spot.score import main


class TestSpotScoreCommand:
    """Test SpotScore command logic"""
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_success(self, mock_get_client, mock_validate):
        """Should return sorted spot scores"""
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az2', 'Score': 7},
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=15
        )
        
        # Should be sorted by score descending
        assert len(result) == 2
        assert result[0]['Score'] == 9
        assert result[1]['Score'] == 7
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_uses_default_regions(self, mock_get_client, mock_validate):
        """Should use DEFAULT_REGIONS when regions is None"""
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=None,
            target_capacity=15,
            force_refresh=True  # Bypass cache to test API call
        )
        
        # Should have called with DEFAULT_REGIONS
        call_args = mock_client.get_spot_placement_scores.call_args
        assert 'RegionNames' in call_args[1]
        assert len(call_args[1]['RegionNames']) > 0
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_error_handling(self, mock_get_client, mock_validate, capsys):
        """Should handle API errors gracefully"""
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=15,
            force_refresh=True  # Bypass cache to test error handling
        )
        
        # Should return empty list on error
        assert result == []

    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_target_capacity(self, mock_get_client, mock_validate):
        """Should pass target capacity to API"""
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': []
        }
        mock_get_client.return_value = mock_client
        
        main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=50,
            force_refresh=True  # Bypass cache to test API call
        )
        
        call_args = mock_client.get_spot_placement_scores.call_args
        assert call_args[1]['TargetCapacity'] == 50
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_quota_warning(self, mock_get_client, mock_validate, capsys):
        """Should display quota warning but continue (table output)"""
        mock_validate.return_value = (False, "⚠️  Warning: Exceeds quota")
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='table',  # Changed from 'json' to 'table'
            regions=['us-east-1'],
            target_capacity=100
        )
        
        # Should still return results
        assert len(result) == 1
        
        # Should have printed warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out
    
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_skip_quota_check(self, mock_get_client):
        """Should skip quota validation when requested"""
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=100,
            skip_quota_check=True
        )
        
        # Should not raise any errors
        assert result is not None



class TestSpotScoreEdgeCases:
    """Test edge cases for spot score command."""
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_multiple_regions(self, mock_get_client, mock_validate):
        """Test spot score across multiple regions."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 8},
                {'Region': 'us-west-2', 'AvailabilityZoneId': 'usw2-az1', 'Score': 7}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='t3.micro',
            target_capacity=10,
            regions=['us-east-1', 'us-west-2'],
            output='json'
        )
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_no_results(self, mock_get_client, mock_validate):
        """Test spot score when no scores are returned."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='t3.micro',
            target_capacity=10,
            output='json'
        )
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_large_capacity(self, mock_get_client, mock_validate):
        """Test spot score with large target capacity."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='m7i.4xlarge',
            target_capacity=100,
            output='json'
        )
        
        assert result is not None
        assert isinstance(result, list)



class TestSpotScoreValidation:
    """Test validation and error handling in spot score."""
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_error_handling(self, mock_get_client, mock_validate):
        """Test spot score handles API errors gracefully."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='t3.micro',
            target_capacity=10,
            output='json'
        )
        
        # Should handle error and return empty list
        assert result is not None
        assert isinstance(result, list)
    
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_with_zero_capacity(self, mock_get_client, mock_validate):
        """Test spot score with zero target capacity."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='t3.micro',
            target_capacity=0,
            output='json'
        )
        
        assert result is not None
        assert isinstance(result, list)


class TestSpotScoreCaching:
    """Test spot score caching functionality."""
    
    @patch('aws_fleet_scout.commands.spot.score._get_cached_spot_scores')
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_uses_cache(self, mock_get_client, mock_validate, mock_get_cached):
        """Should use cached scores when available."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_get_cached.return_value = [
            {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
        ]
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=15
        )
        
        # Should return cached data
        assert len(result) == 1
        assert result[0]['Score'] == 9
        # Should not call AWS API
        mock_get_client.assert_not_called()
    
    @patch('aws_fleet_scout.commands.spot.score._get_cached_spot_scores')
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_force_refresh_bypasses_cache(self, mock_get_client, mock_validate, mock_get_cached):
        """Should bypass cache with force_refresh flag."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_get_cached.return_value = [
            {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 5}
        ]
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=15,
            force_refresh=True
        )
        
        # Should call AWS API despite cache
        mock_get_client.assert_called_once()
        # Should return fresh data, not cached
        assert result[0]['Score'] == 9
    
    @patch('aws_fleet_scout.commands.spot.score._cache_spot_scores')
    @patch('aws_fleet_scout.commands.spot.score._get_cached_spot_scores')
    @patch('aws_fleet_scout.commands.spot.score.validate_instance_request')
    @patch('aws_fleet_scout.commands.spot.score.get_ec2_client')
    def test_spot_score_caches_results(self, mock_get_client, mock_validate, mock_get_cached, mock_cache):
        """Should cache results after fetching from AWS."""
        from aws_fleet_scout.commands.spot.score import main
        
        mock_validate.return_value = (True, None)
        mock_get_cached.return_value = None  # Cache miss
        mock_client = Mock()
        mock_client.get_spot_placement_scores.return_value = {
            'SpotPlacementScores': [
                {'Region': 'us-east-1', 'AvailabilityZoneId': 'use1-az1', 'Score': 9}
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            output='json',
            regions=['us-east-1'],
            target_capacity=15
        )
        
        # Should cache the results
        mock_cache.assert_called_once()
        # Verify cache was called with correct data
        call_args = mock_cache.call_args
        assert call_args[0][0] == 'p5.48xlarge'  # instance_type
        assert call_args[0][1] == 15  # target_capacity
        assert len(call_args[0][3]) == 1  # scores
        assert call_args[0][3][0]['Score'] == 9

"""
Unit tests for capacity commands.

These tests use mocking and don't make real AWS API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from aws_fleet_scout.commands.capacity.find import (
    _is_valid_duration,
    _days_to_hours,
    _find_best_offerings
)
from aws_fleet_scout.commands.capacity.calendar import (
    _is_valid_duration as calendar_is_valid_duration,
    _days_to_hours as calendar_days_to_hours
)


class TestDurationValidation:
    """Test duration validation for capacity blocks."""
    
    def test_valid_daily_durations(self):
        """Test that 1-14 days are valid."""
        for days in range(1, 15):
            assert _is_valid_duration(days) is True
    
    def test_valid_weekly_durations(self):
        """Test that 21, 28, 35... up to 182 days are valid."""
        for days in [21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98, 105, 112, 119, 126, 133, 140, 147, 154, 161, 168, 175, 182]:
            assert _is_valid_duration(days) is True
    
    def test_invalid_durations(self):
        """Test that invalid durations are rejected."""
        invalid = [0, 15, 16, 17, 18, 19, 20, 22, 23, 183, 200]
        for days in invalid:
            assert _is_valid_duration(days) is False
    
    def test_days_to_hours_conversion(self):
        """Test conversion from days to hours."""
        assert _days_to_hours(1) == 24
        assert _days_to_hours(7) == 168
        assert _days_to_hours(14) == 336
        assert _days_to_hours(21) == 504


class TestCalendarDurationValidation:
    """Test duration validation for calendar command."""
    
    def test_calendar_valid_durations(self):
        """Test that calendar uses same validation."""
        assert calendar_is_valid_duration(1) is True
        assert calendar_is_valid_duration(7) is True
        assert calendar_is_valid_duration(14) is True
        assert calendar_is_valid_duration(21) is True
        assert calendar_is_valid_duration(15) is False
    
    def test_calendar_days_to_hours(self):
        """Test calendar days to hours conversion."""
        assert calendar_days_to_hours(1) == 24
        assert calendar_days_to_hours(7) == 168


class TestFindBestOfferings:
    """Test finding best capacity block offerings."""
    
    def test_find_best_with_multiple_offerings(self):
        """Test selecting best offering from multiple options."""
        all_offerings = {
            'p4d.24xlarge': {
                'us-east-1': [
                    {
                        'StartDate': datetime(2026, 1, 25, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '300.00',
                        'AvailabilityZone': 'us-east-1a',
                        'CapacityBlockOfferingId': 'cb-123'
                    },
                    {
                        'StartDate': datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '250.00',
                        'AvailabilityZone': 'us-east-1b',
                        'CapacityBlockOfferingId': 'cb-456'
                    }
                ],
                'us-west-2': [
                    {
                        'StartDate': datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '280.00',
                        'AvailabilityZone': 'us-west-2a',
                        'CapacityBlockOfferingId': 'cb-789'
                    }
                ]
            }
        }
        
        requirements = {'p4d.24xlarge': 1}
        results = _find_best_offerings(all_offerings, requirements)
        
        assert len(results) == 1
        assert results[0]['region'] == 'us-east-1'
        assert results[0]['upfront_fee'] == 250.00
        assert results[0]['offering_id'] == 'cb-456'
    
    def test_find_best_with_no_offerings(self):
        """Test handling when no offerings available."""
        all_offerings = {
            'p5.48xlarge': {
                'us-east-1': [],
                'us-west-2': []
            }
        }
        
        requirements = {'p5.48xlarge': 2}
        results = _find_best_offerings(all_offerings, requirements)
        
        assert len(results) == 1
        assert results[0]['region'] == 'No availability'
        assert results[0]['start_date'] is None
    
    def test_find_best_prefers_earliest_start(self):
        """Test that earliest start date is preferred."""
        all_offerings = {
            'p4d.24xlarge': {
                'us-east-1': [
                    {
                        'StartDate': datetime(2026, 1, 26, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '200.00',
                        'AvailabilityZone': 'us-east-1a',
                        'CapacityBlockOfferingId': 'cb-later'
                    },
                    {
                        'StartDate': datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '250.00',
                        'AvailabilityZone': 'us-east-1b',
                        'CapacityBlockOfferingId': 'cb-earlier'
                    }
                ]
            }
        }
        
        requirements = {'p4d.24xlarge': 1}
        results = _find_best_offerings(all_offerings, requirements)
        
        # Should prefer earlier start even though it's more expensive
        assert results[0]['offering_id'] == 'cb-earlier'
        assert results[0]['start_date'].day == 24


class TestCapacityFindMain:
    """Test capacity find main function."""
    
    @patch('aws_fleet_scout.commands.capacity.find.get_ec2_client')
    def test_find_with_instance_type(self, mock_get_client):
        """Test find with single instance type."""
        from aws_fleet_scout.commands.capacity.find import main
        
        mock_client = Mock()
        mock_client.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p4d.24xlarge',
            duration=1,
            max_days=7,
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'offerings' in result
    
    @patch('aws_fleet_scout.commands.capacity.find.get_ec2_client')
    def test_find_with_job_spec(self, mock_get_client):
        """Test find with job spec."""
        from aws_fleet_scout.commands.capacity.find import main
        
        mock_client = Mock()
        mock_client.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            job_spec='{"p4d.24xlarge": 2}',
            duration=1,
            max_days=7,
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'offerings' in result


class TestCapacityCalendarMain:
    """Test capacity calendar main function."""
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_with_instance_type(self, mock_get_client):
        """Test calendar with single instance type."""
        from aws_fleet_scout.commands.capacity.calendar import main
        
        mock_client = Mock()
        mock_client.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p4d.24xlarge',
            duration=1,
            window=7,
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'calendar' in result
        assert 'p4d.24xlarge' in result['calendar']



class TestCapacityFindEdgeCases:
    """Test edge cases for capacity find command."""
    
    def test_invalid_duration_error(self):
        """Test that invalid durations are rejected."""
        from aws_fleet_scout.commands.capacity.find import _is_valid_duration
        
        # Test boundary cases
        assert _is_valid_duration(0) is False
        assert _is_valid_duration(15) is False
        assert _is_valid_duration(16) is False
        assert _is_valid_duration(183) is False
        assert _is_valid_duration(200) is False
    
    def test_find_best_offerings_multiple_instance_types(self):
        """Test finding best offerings with multiple instance types."""
        from aws_fleet_scout.commands.capacity.find import _find_best_offerings
        from datetime import datetime, timezone
        
        all_offerings = {
            'p4d.24xlarge': {
                'us-east-1': [
                    {
                        'StartDate': datetime(2026, 1, 25, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '300.00',
                        'AvailabilityZone': 'us-east-1a',
                        'CapacityBlockOfferingId': 'cb-123'
                    }
                ]
            },
            'p5.48xlarge': {
                'us-east-1': [
                    {
                        'StartDate': datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
                        'CapacityBlockDurationHours': 24,
                        'UpfrontFee': '500.00',
                        'AvailabilityZone': 'us-east-1b',
                        'CapacityBlockOfferingId': 'cb-456'
                    }
                ]
            }
        }
        
        requirements = {'p4d.24xlarge': 1, 'p5.48xlarge': 2}
        results = _find_best_offerings(all_offerings, requirements)
        
        assert len(results) == 2
        # Should have results for both instance types
        instance_types = [r['instance_type'] for r in results]
        assert 'p4d.24xlarge' in instance_types
        assert 'p5.48xlarge' in instance_types


class TestCapacityCalendarEdgeCases:
    """Test edge cases for capacity calendar command."""
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_with_no_availability(self, mock_get_client):
        """Test calendar when no capacity is available."""
        from aws_fleet_scout.commands.capacity.calendar import main
        
        mock_client = Mock()
        mock_client.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': []
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            instance_type='p5.48xlarge',
            duration=1,
            window=7,
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'calendar' in result
        # Should have empty calendar
        assert 'p5.48xlarge' in result['calendar']
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_with_multiple_instances(self, mock_get_client):
        """Test calendar with multiple instance types."""
        from aws_fleet_scout.commands.capacity.calendar import main
        from datetime import datetime, timezone
        
        mock_client = Mock()
        mock_client.describe_capacity_block_offerings.return_value = {
            'CapacityBlockOfferings': [
                {
                    'StartDate': datetime(2026, 1, 25, 10, 0, tzinfo=timezone.utc),
                    'CapacityBlockDurationHours': 24,
                    'UpfrontFee': '300.00',
                    'AvailabilityZone': 'us-east-1a',
                    'CapacityBlockOfferingId': 'cb-123'
                }
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = main(
            job_spec='{"p4d.24xlarge": 1, "p5.48xlarge": 2}',
            duration=1,
            window=7,
            output='json',
            regions=['us-east-1']
        )
        
        assert result is not None
        assert 'calendar' in result



class TestCapacityFindValidation:
    """Test validation and error handling in capacity find."""
    
    @patch('aws_fleet_scout.commands.capacity.find.get_ec2_client')
    def test_find_with_invalid_json(self, mock_get_client):
        """Test find with invalid job spec JSON."""
        from aws_fleet_scout.commands.capacity.find import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='invalid json',
                duration=1,
                max_days=7,
                output='json',
                regions=['us-east-1']
            )
    
    @patch('aws_fleet_scout.commands.capacity.find.get_ec2_client')
    def test_find_requires_instance_or_job_spec(self, mock_get_client):
        """Test that either instance_type or job_spec is required."""
        from aws_fleet_scout.commands.capacity.find import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                duration=1,
                max_days=7,
                output='json',
                regions=['us-east-1']
            )


class TestCapacityCalendarValidation:
    """Test validation and error handling in capacity calendar."""
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_with_invalid_json(self, mock_get_client):
        """Test calendar with invalid job spec JSON."""
        from aws_fleet_scout.commands.capacity.calendar import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                job_spec='not valid json',
                duration=1,
                window=7,
                output='json',
                regions=['us-east-1']
            )
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_requires_instance_or_job_spec(self, mock_get_client):
        """Test that either instance_type or job_spec is required."""
        from aws_fleet_scout.commands.capacity.calendar import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                duration=1,
                window=7,
                output='json',
                regions=['us-east-1']
            )
    
    @patch('aws_fleet_scout.commands.capacity.calendar.get_ec2_client')
    def test_calendar_with_invalid_duration(self, mock_get_client):
        """Test calendar with invalid duration."""
        from aws_fleet_scout.commands.capacity.calendar import main
        import typer
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        with pytest.raises((typer.Exit, typer.BadParameter)):
            main(
                instance_type='p4d.24xlarge',
                duration=15,  # Invalid duration
                window=7,
                output='json',
                regions=['us-east-1']
            )

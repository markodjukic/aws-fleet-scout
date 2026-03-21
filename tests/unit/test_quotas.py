"""
Unit tests for quota utilities.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from aws_fleet_scout.utils.quotas import (
    get_instance_family,
    get_quota_code_for_family,
    get_vcpu_count,
    get_quota_for_instance,
    validate_instance_request,
    check_discovered_instances_quotas,
    print_quota_summary
)


class TestInstanceFamily:
    """Test instance family extraction."""
    
    def test_p_series(self):
        """Should extract P-series families."""
        assert get_instance_family('p5.48xlarge') == 'p5'
        assert get_instance_family('p4d.24xlarge') == 'p4'
        assert get_instance_family('p3.2xlarge') == 'p3'
    
    def test_g_series(self):
        """Should extract G-series families."""
        assert get_instance_family('g5.xlarge') == 'g5'
        assert get_instance_family('g4dn.xlarge') == 'g4'
    
    def test_inf_series(self):
        """Should extract Inf families."""
        assert get_instance_family('inf2.xlarge') == 'inf'
        assert get_instance_family('inf1.xlarge') == 'inf'
    
    def test_standard_families(self):
        """Should map standard families."""
        assert get_instance_family('m7i.4xlarge') == 'standard'
        assert get_instance_family('c7i.8xlarge') == 'standard'
        assert get_instance_family('r7i.2xlarge') == 'standard'
        assert get_instance_family('t3.medium') == 'standard'


class TestQuotaCodeLookup:
    """Test quota code lookup."""
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    def test_quota_code_from_cache(self, mock_cache):
        """Should return quota code from cache."""
        mock_cache.return_value = {'p5': 'L-C4BD4855'}
        
        result = get_quota_code_for_family('p5', 'us-east-1')
        
        assert result == 'L-C4BD4855'
        mock_cache.assert_called_once()
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    def test_quota_code_not_found(self, mock_cache):
        """Should return None if quota code not found."""
        mock_cache.return_value = {}
        
        result = get_quota_code_for_family('unknown', 'us-east-1')
        
        assert result is None


class TestVCPUCount:
    """Test vCPU count lookup."""
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    def test_vcpu_from_cache(self, mock_cache):
        """Should return vCPU count from cache."""
        mock_cache.return_value = {'p5.48xlarge': 192}
        
        result = get_vcpu_count('p5.48xlarge', 'us-east-1')
        
        assert result == 192
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    @patch('boto3.client')
    def test_vcpu_fallback_to_api(self, mock_boto, mock_cache):
        """Should fallback to API if not in cache."""
        mock_cache.return_value = {}
        
        mock_client = Mock()
        mock_client.describe_instance_types.return_value = {
            'InstanceTypes': [
                {'VCpuInfo': {'DefaultVCpus': 192}}
            ]
        }
        mock_boto.return_value = mock_client
        
        result = get_vcpu_count('p5.48xlarge', 'us-east-1')
        
        assert result == 192
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    @patch('boto3.client')
    def test_vcpu_not_found(self, mock_boto, mock_cache):
        """Should return None if instance type not found."""
        mock_cache.return_value = {}
        
        mock_client = Mock()
        mock_client.describe_instance_types.side_effect = Exception("Not found")
        mock_boto.return_value = mock_client
        
        result = get_vcpu_count('unknown.type', 'us-east-1')
        
        assert result is None


class TestQuotaForInstance:
    """Test quota information retrieval."""
    
    @patch('aws_fleet_scout.utils.quotas.get_cached_data')
    @patch('aws_fleet_scout.utils.quotas.get_quota_code_for_family')
    def test_get_quota_success(self, mock_quota_code, mock_cache):
        """Should return quota information."""
        mock_quota_code.return_value = 'L-C4BD4855'
        mock_cache.return_value = {
            'quota_name': 'All P5 Spot Instance Requests',
            'quota_code': 'L-C4BD4855',
            'value': 768.0,
            'unit': 'vCPUs',
            'adjustable': True
        }
        
        result = get_quota_for_instance('p5.48xlarge', 'us-east-1')
        
        assert result is not None
        assert result['quota_code'] == 'L-C4BD4855'
        assert result['value'] == 768.0
    
    @patch('aws_fleet_scout.utils.quotas.get_quota_code_for_family')
    def test_get_quota_no_code(self, mock_quota_code):
        """Should return None if quota code not found."""
        mock_quota_code.return_value = None
        
        result = get_quota_for_instance('unknown.type', 'us-east-1')
        
        assert result is None


class TestValidateInstanceRequest:
    """Test instance request validation."""
    
    def test_skip_check(self):
        """Should skip validation when requested."""
        is_valid, warning = validate_instance_request(
            'p5.48xlarge', 10, 'us-east-1', skip_check=True
        )
        
        assert is_valid is True
        assert warning is None
    
    @patch('aws_fleet_scout.utils.quotas.get_vcpu_count')
    def test_unknown_instance_type(self, mock_vcpu):
        """Should pass validation for unknown instance types."""
        mock_vcpu.return_value = None
        
        is_valid, warning = validate_instance_request(
            'unknown.type', 10, 'us-east-1'
        )
        
        assert is_valid is True
        assert warning is None
    
    @patch('aws_fleet_scout.utils.quotas.get_vcpu_count')
    @patch('aws_fleet_scout.utils.quotas.get_quota_for_instance')
    def test_within_quota(self, mock_quota, mock_vcpu):
        """Should pass validation when within quota."""
        mock_vcpu.return_value = 192
        mock_quota.return_value = {
            'quota_name': 'All P5 Spot Instance Requests',
            'quota_code': 'L-C4BD4855',
            'value': 2000.0,
            'unit': 'vCPUs',
            'adjustable': True
        }
        
        is_valid, warning = validate_instance_request(
            'p5.48xlarge', 5, 'us-east-1'
        )
        
        assert is_valid is True
        assert warning is None
    
    @patch('aws_fleet_scout.utils.quotas.get_vcpu_count')
    @patch('aws_fleet_scout.utils.quotas.get_quota_for_instance')
    def test_exceeds_quota(self, mock_quota, mock_vcpu):
        """Should fail validation when exceeding quota."""
        mock_vcpu.return_value = 192
        mock_quota.return_value = {
            'quota_name': 'All P5 Spot Instance Requests',
            'quota_code': 'L-C4BD4855',
            'value': 768.0,
            'unit': 'vCPUs',
            'adjustable': True
        }
        
        is_valid, warning = validate_instance_request(
            'p5.48xlarge', 10, 'us-east-1'
        )
        
        assert is_valid is False
        assert warning is not None
        assert '10x p5.48xlarge' in warning
        assert '1,920 vCPUs' in warning
        assert '768' in warning


class TestCheckDiscoveredInstancesQuotas:
    """Test quota checking for multiple instances."""
    
    def test_skip_check(self):
        """Should return empty dict when skipping check."""
        result = check_discovered_instances_quotas(
            ['p5.48xlarge'], 10, 'us-east-1', skip_check=True
        )
        
        assert result == {}
    
    @patch('aws_fleet_scout.utils.quotas.get_vcpu_count')
    @patch('aws_fleet_scout.utils.quotas.get_quota_for_instance')
    def test_check_multiple_instances(self, mock_quota, mock_vcpu):
        """Should check quotas for multiple instance types."""
        mock_vcpu.side_effect = [192, 96]  # p5.48xlarge, p4d.24xlarge
        mock_quota.side_effect = [
            {
                'quota_name': 'All P5 Spot Instance Requests',
                'quota_code': 'L-C4BD4855',
                'value': 768.0,
                'unit': 'vCPUs',
                'adjustable': True
            },
            {
                'quota_name': 'All P4, P3 and P2 Spot Instance Requests',
                'quota_code': 'L-7212CCBC',
                'value': 384.0,
                'unit': 'vCPUs',
                'adjustable': True
            }
        ]
        
        result = check_discovered_instances_quotas(
            ['p5.48xlarge', 'p4d.24xlarge'], 5, 'us-east-1'
        )
        
        assert 'p5.48xlarge' in result
        assert 'p4d.24xlarge' in result
        assert result['p5.48xlarge']['status'] == 'insufficient'
        assert result['p4d.24xlarge']['status'] == 'insufficient'


class TestPrintQuotaSummary:
    """Test quota summary printing."""
    
    @patch('builtins.print')
    def test_print_empty_results(self, mock_print):
        """Should not print anything for empty results."""
        print_quota_summary({}, 10)
        
        mock_print.assert_not_called()
    
    @patch('builtins.print')
    def test_print_quota_summary(self, mock_print):
        """Should print quota summary."""
        results = {
            'p5.48xlarge': {
                'status': 'ok',
                'max_instances': 10,
                'quota_vcpus': 1920.0,
                'vcpu_per_instance': 192
            },
            'p4d.24xlarge': {
                'status': 'insufficient',
                'max_instances': 4,
                'quota_vcpus': 384.0,
                'vcpu_per_instance': 96,
                'requested_vcpus': 960
            }
        }
        
        print_quota_summary(results, 10)
        
        # Should print header and results
        assert mock_print.call_count > 0

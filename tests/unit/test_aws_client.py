"""Unit tests for AWS client utilities (mocked)"""

from unittest.mock import Mock, patch

from aws_fleet_scout.utils.aws_client import (
    AWSClientManager,
    check_on_demand_availability,
    discover_instances_by_prefix,
    discover_p_series_instances,
    get_available_regions_for_instance,
    get_ec2_client,
    get_pricing_client,
)


class TestAWSClientManager:
    """Test AWS client manager caching"""

    def test_client_manager_initialization(self):
        """Client manager should initialize with empty cache"""
        manager = AWSClientManager()
        assert manager._clients == {}

    @patch("boto3.client")
    def test_client_caching(self, mock_boto_client):
        """Clients should be cached and reused"""
        manager = AWSClientManager()
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        # First call creates client
        client1 = manager.get_client("ec2", "us-east-1")
        # Second call reuses cached client
        client2 = manager.get_client("ec2", "us-east-1")

        assert client1 is client2
        mock_boto_client.assert_called_once_with("ec2", region_name="us-east-1")

    @patch("boto3.client")
    def test_different_regions_different_clients(self, mock_boto_client):
        """Different regions should get different clients"""
        manager = AWSClientManager()

        manager.get_client("ec2", "us-east-1")
        # Second call returns different client
        manager.get_client("ec2", "us-west-2")

        assert mock_boto_client.call_count == 2

    def test_clear_cache(self):
        """Clear cache should empty the client cache"""
        manager = AWSClientManager()
        manager._clients[("ec2", "us-east-1")] = Mock()

        manager.clear_cache()

        assert manager._clients == {}


class TestClientGetters:
    """Test convenience getter functions"""

    @patch("aws_fleet_scout.utils.aws_client._client_manager")
    def test_get_ec2_client(self, mock_manager):
        """get_ec2_client should call manager with correct params"""
        mock_client = Mock()
        mock_manager.get_client.return_value = mock_client

        result = get_ec2_client("us-west-2")

        mock_manager.get_client.assert_called_once_with("ec2", "us-west-2")
        assert result is mock_client

    @patch("aws_fleet_scout.utils.aws_client._client_manager")
    def test_get_pricing_client(self, mock_manager):
        """get_pricing_client should call manager with correct params"""
        mock_client = Mock()
        mock_manager.get_client.return_value = mock_client

        result = get_pricing_client("us-east-1")

        mock_manager.get_client.assert_called_once_with("pricing", "us-east-1")
        assert result is mock_client


class TestOnDemandAvailability:
    """Test on-demand availability checking"""

    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_check_availability_found(self, mock_get_client):
        """Should return True when instance type is available"""
        mock_client = Mock()
        mock_client.describe_instance_type_offerings.return_value = {
            "InstanceTypeOfferings": [{"InstanceType": "p5.48xlarge", "Location": "us-east-1"}]
        }
        mock_get_client.return_value = mock_client

        result = check_on_demand_availability("p5.48xlarge", ["us-east-1"])

        assert result == {"us-east-1": True}

    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_check_availability_not_found(self, mock_get_client):
        """Should return False when instance type is not available"""
        mock_client = Mock()
        mock_client.describe_instance_type_offerings.return_value = {"InstanceTypeOfferings": []}
        mock_get_client.return_value = mock_client

        result = check_on_demand_availability("p5.48xlarge", ["us-east-1"])

        assert result == {"us-east-1": False}

    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_check_availability_error_handling(self, mock_get_client):
        """Should return False on API errors"""
        mock_client = Mock()
        mock_client.describe_instance_type_offerings.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        result = check_on_demand_availability("p5.48xlarge", ["us-east-1"])

        assert result == {"us-east-1": False}

    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_check_availability_multiple_regions(self, mock_get_client):
        """Should check multiple regions"""
        mock_client = Mock()
        mock_client.describe_instance_type_offerings.side_effect = [
            {"InstanceTypeOfferings": [{"InstanceType": "p5.48xlarge"}]},
            {"InstanceTypeOfferings": []},
        ]
        mock_get_client.return_value = mock_client

        result = check_on_demand_availability("p5.48xlarge", ["us-east-1", "us-west-2"])

        assert result == {"us-east-1": True, "us-west-2": False}


class TestGetAvailableRegions:
    """Test getting available regions for instance type"""

    @patch("aws_fleet_scout.utils.aws_client.check_on_demand_availability")
    def test_filters_available_regions(self, mock_check):
        """Should return only regions where instance is available"""
        mock_check.return_value = {"us-east-1": True, "us-west-2": False, "eu-west-1": True}

        result = get_available_regions_for_instance(
            "p5.48xlarge", ["us-east-1", "us-west-2", "eu-west-1"]
        )

        assert set(result) == {"us-east-1", "eu-west-1"}

    @patch("aws_fleet_scout.utils.aws_client.check_on_demand_availability")
    def test_uses_default_regions_when_none(self, mock_check):
        """Should use DEFAULT_REGIONS when regions param is None"""
        mock_check.return_value = {"us-east-1": True}

        get_available_regions_for_instance("p5.48xlarge", regions=None)

        # Should have called check with DEFAULT_REGIONS
        call_args = mock_check.call_args[0]
        assert "us-east-1" in call_args[1]  # DEFAULT_REGIONS contains us-east-1


class TestInstanceDiscovery:
    """Test instance type discovery functions"""

    @patch("aws_fleet_scout.utils.aws_client.get_cached_data")
    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_discover_by_prefix_single_prefix(self, mock_get_client, mock_cache):
        """Should discover instances matching single prefix"""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "InstanceTypeOfferings": [
                    {"InstanceType": "p5.48xlarge"},
                    {"InstanceType": "p5.4xlarge"},
                    {"InstanceType": "p5en.48xlarge"},
                    {"InstanceType": "m7i.large"},  # Should be filtered out
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_get_client.return_value = mock_client

        def cache_side_effect(key, fetch_func, region):
            return fetch_func()

        mock_cache.side_effect = cache_side_effect

        result = discover_instances_by_prefix(["us-east-1"], ["p5"])

        assert result == ["p5.48xlarge", "p5.4xlarge", "p5en.48xlarge"]

    @patch("aws_fleet_scout.utils.aws_client.get_cached_data")
    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_discover_by_prefix_multiple_prefixes(self, mock_get_client, mock_cache):
        """Should discover instances matching multiple prefixes"""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "InstanceTypeOfferings": [
                    {"InstanceType": "p5.48xlarge"},
                    {"InstanceType": "g5.xlarge"},
                    {"InstanceType": "m7i.large"},  # Should be filtered out
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_get_client.return_value = mock_client

        def cache_side_effect(key, fetch_func, region):
            return fetch_func()

        mock_cache.side_effect = cache_side_effect

        result = discover_instances_by_prefix(["us-east-1"], ["p5", "g5"])

        assert result == ["g5.xlarge", "p5.48xlarge"]

    @patch("aws_fleet_scout.utils.aws_client.get_cached_data")
    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_discover_by_prefix_multiple_regions(self, mock_get_client, mock_cache):
        """Should deduplicate instances across regions"""
        mock_client = Mock()
        paginator1 = Mock()
        paginator1.paginate.return_value = [
            {
                "InstanceTypeOfferings": [
                    {"InstanceType": "p5.48xlarge"},
                    {"InstanceType": "p5.4xlarge"},
                ]
            }
        ]
        paginator2 = Mock()
        paginator2.paginate.return_value = [
            {
                "InstanceTypeOfferings": [
                    {"InstanceType": "p5.48xlarge"},
                    {"InstanceType": "p5en.48xlarge"},
                ]
            }
        ]
        mock_client.get_paginator.side_effect = [paginator1, paginator2]
        mock_get_client.return_value = mock_client

        def cache_side_effect(key, fetch_func, region):
            return fetch_func()

        mock_cache.side_effect = cache_side_effect

        result = discover_instances_by_prefix(["us-east-1", "us-west-2"], ["p5"])

        assert result == ["p5.48xlarge", "p5.4xlarge", "p5en.48xlarge"]

    @patch("aws_fleet_scout.utils.aws_client.get_cached_data")
    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_discover_by_prefix_error_handling(self, mock_get_client, mock_cache):
        """Should continue on region errors"""
        mock_client = Mock()

        # Mock cache to call fetch function
        def cache_side_effect(key, fetch_func, region):
            return fetch_func()

        mock_cache.side_effect = cache_side_effect

        mock_paginator_err = Mock()
        mock_paginator_err.paginate.side_effect = Exception("API Error")
        mock_paginator_ok = Mock()
        mock_paginator_ok.paginate.return_value = [
            {"InstanceTypeOfferings": [{"InstanceType": "p5.48xlarge"}]}
        ]
        mock_client.get_paginator.side_effect = [mock_paginator_err, mock_paginator_ok]
        mock_get_client.return_value = mock_client

        result = discover_instances_by_prefix(["us-east-1", "us-west-2"], ["p5"])

        assert result == ["p5.48xlarge"]

    @patch("aws_fleet_scout.utils.aws_client.get_cached_data")
    @patch("aws_fleet_scout.utils.aws_client.get_ec2_client")
    def test_discover_by_prefix_no_matches(self, mock_get_client, mock_cache):
        """Should return empty list when no matches"""
        mock_client = Mock()

        # Mock cache to call fetch function
        def cache_side_effect(key, fetch_func, region):
            return fetch_func()

        mock_cache.side_effect = cache_side_effect

        mock_client.describe_instance_type_offerings.return_value = {
            "InstanceTypeOfferings": [{"InstanceType": "m7i.large"}, {"InstanceType": "c7i.xlarge"}]
        }
        mock_get_client.return_value = mock_client

        result = discover_instances_by_prefix(["us-east-1"], ["p5"])

        assert result == []

    @patch("aws_fleet_scout.utils.aws_client.discover_instances_by_prefix")
    def test_discover_p_series_instances(self, mock_discover):
        """Should call discover_instances_by_prefix with P-series prefixes"""
        mock_discover.return_value = ["p4d.24xlarge", "p5.48xlarge", "p6.48xlarge"]

        result = discover_p_series_instances(["us-east-1"])

        mock_discover.assert_called_once_with(["us-east-1"], ["p4", "p5", "p6"])
        assert result == ["p4d.24xlarge", "p5.48xlarge", "p6.48xlarge"]

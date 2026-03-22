"""
Unit tests for cache utility.
"""

import json
import time
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

from aws_fleet_scout.utils.cache import CACHE_DIR, clear_cache, get_cache_info, get_cached_data


class TestCacheDirectory:
    """Test cache directory configuration."""

    def test_cache_dir_uses_platformdirs(self):
        """Should use platformdirs for cache location."""
        from platformdirs import user_cache_dir

        expected = Path(user_cache_dir("aws-fleet-scout", appauthor=False))
        assert CACHE_DIR == expected

    def test_cache_dir_is_path(self):
        """Should be a Path object."""
        assert isinstance(CACHE_DIR, Path)


class TestCacheUtility:
    """Test cache utility functions."""

    def test_get_cached_data_cache_miss(self):
        """Should fetch fresh data on cache miss."""
        fetch_func = Mock(return_value={"key": "value"})

        with patch("aws_fleet_scout.utils.cache._load_cache", return_value=None):
            with patch("aws_fleet_scout.utils.cache._save_cache") as mock_save:
                result = get_cached_data("test_key", fetch_func, region="us-east-1")

        assert result == {"key": "value"}
        fetch_func.assert_called_once()
        mock_save.assert_called_once()

    def test_get_cached_data_cache_hit(self):
        """Should return cached data without fetching."""
        fetch_func = Mock(return_value={"key": "new_value"})
        cached_data = {"key": "cached_value"}

        with patch("aws_fleet_scout.utils.cache._load_cache", return_value=cached_data):
            result = get_cached_data("test_key", fetch_func, region="us-east-1")

        assert result == cached_data
        fetch_func.assert_not_called()

    def test_get_cached_data_fetch_failure(self):
        """Should return None if fetch fails."""
        fetch_func = Mock(side_effect=Exception("API Error"))

        with patch("aws_fleet_scout.utils.cache._load_cache", return_value=None):
            result = get_cached_data("test_key", fetch_func, region="us-east-1")

        assert result is None

    def test_get_cached_data_custom_ttl(self):
        """Should respect custom TTL."""
        fetch_func = Mock(return_value={"key": "value"})

        with patch("aws_fleet_scout.utils.cache._load_cache", return_value=None):
            with patch("aws_fleet_scout.utils.cache._save_cache"):
                result = get_cached_data("test_key", fetch_func, ttl=3600, region="us-east-1")

        assert result == {"key": "value"}

    def test_load_cache_valid(self):
        """Should load valid cache data."""
        from aws_fleet_scout.utils.cache import _load_cache

        cache_data = {"timestamp": time.time(), "data": {"key": "value"}}

        mock_file = mock_open(read_data=json.dumps(cache_data))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_file):
                result = _load_cache(Path("/fake/cache.json"), ttl=3600)

        assert result == {"key": "value"}

    def test_load_cache_expired(self):
        """Should return None for expired cache."""
        from aws_fleet_scout.utils.cache import _load_cache

        cache_data = {"timestamp": time.time() - 10000, "data": {"key": "value"}}  # Old timestamp

        mock_file = mock_open(read_data=json.dumps(cache_data))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_file):
                result = _load_cache(Path("/fake/cache.json"), ttl=3600)

        assert result is None

    def test_load_cache_missing(self):
        """Should return None for missing cache file."""
        from aws_fleet_scout.utils.cache import _load_cache

        with patch("pathlib.Path.exists", return_value=False):
            result = _load_cache(Path("/fake/cache.json"), ttl=3600)

        assert result is None

    def test_save_cache(self):
        """Should save cache data."""
        from aws_fleet_scout.utils.cache import _save_cache

        data = {"key": "value"}
        mock_file = mock_open()

        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", mock_file):
                _save_cache(Path("/fake/cache.json"), data)

        # Verify file was written
        mock_file.assert_called_once()

    def test_save_cache_failure(self):
        """Should silently fail on save errors."""
        from aws_fleet_scout.utils.cache import _save_cache

        data = {"key": "value"}

        with patch("pathlib.Path.mkdir", side_effect=Exception("Permission denied")):
            # Should not raise exception
            _save_cache(Path("/fake/cache.json"), data)

    def test_clear_cache_specific(self):
        """Should clear specific cache file."""
        mock_file = Mock()
        mock_file.exists.return_value = True

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.__truediv__", return_value=mock_file):
                clear_cache("test_key", "us-east-1")

        mock_file.unlink.assert_called_once()

    def test_clear_cache_all(self):
        """Should clear all cache files."""
        mock_files = [Mock(), Mock()]

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob", return_value=mock_files):
                clear_cache()

        for mock_file in mock_files:
            mock_file.unlink.assert_called_once()

    def test_get_cache_info(self):
        """Should return cache information."""
        mock_file = Mock()
        mock_file.name = "test_cache_us-east-1.json"
        mock_file.stat.return_value.st_size = 1024

        cache_data = {"timestamp": time.time() - 3600, "data": {"key": "value"}}  # 1 hour ago

        mock_open_file = mock_open(read_data=json.dumps(cache_data))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob", return_value=[mock_file]):
                with patch("builtins.open", mock_open_file):
                    info = get_cache_info()

        assert info["exists"] is True
        assert info["total_files"] == 1
        assert len(info["files"]) == 1
        assert info["files"][0]["name"] == "test_cache_us-east-1.json"

    def test_get_cache_info_missing(self):
        """Should handle missing cache directory."""
        with patch("pathlib.Path.exists", return_value=False):
            info = get_cache_info()

        assert info["exists"] is False
        assert info["files"] == []

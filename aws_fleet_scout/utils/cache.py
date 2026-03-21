"""
Generic caching utility for AWS Fleet Scout.

Provides a simple file-based cache for reference data that doesn't change frequently.
Uses platform-appropriate cache directory with configurable TTL.
"""

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional
from platformdirs import user_cache_dir


# Cache directory - uses platform-appropriate location
# macOS: ~/Library/Caches/aws-fleet-scout
# Linux: ~/.cache/aws-fleet-scout
# Windows: C:\Users\<user>\AppData\Local\aws-fleet-scout\Cache
CACHE_DIR = Path(user_cache_dir('aws-fleet-scout', appauthor=False))
DEFAULT_TTL = 86400 * 7  # 7 days in seconds


def get_cached_data(
    cache_key: str,
    fetch_func: Callable[[], Any],
    ttl: int = DEFAULT_TTL,
    region: str = 'us-east-1'
) -> Optional[Any]:
    """
    Get data from cache or fetch from AWS if cache is stale/missing.
    
    This is a generic caching wrapper that:
    1. Checks if cached data exists and is fresh
    2. Returns cached data if valid
    3. Otherwise calls fetch_func() to get fresh data
    4. Caches the fresh data for future use
    
    Args:
        cache_key: Unique identifier for this cache (e.g., 'quota_codes', 'vcpu_counts')
        fetch_func: Function to call to fetch fresh data from AWS
        ttl: Time-to-live in seconds (default: 7 days)
        region: AWS region (included in cache key for region-specific data)
    
    Returns:
        Cached or freshly fetched data, or None if fetch fails
    
    Example:
        >>> def fetch_quotas():
        ...     # Fetch from AWS
        ...     return {"p5": "L-C4BD4855", ...}
        >>> 
        >>> quotas = get_cached_data('quota_codes', fetch_quotas)
    """
    cache_file = CACHE_DIR / f'{cache_key}_{region}.json'
    
    # Try to load from cache
    cached_data = _load_cache(cache_file, ttl)
    if cached_data is not None:
        return cached_data
    
    # Cache miss or stale - fetch fresh data
    try:
        fresh_data = fetch_func()
        if fresh_data is not None:
            _save_cache(cache_file, fresh_data)
        return fresh_data
    except Exception:
        # If fetch fails, return None
        return None


def _load_cache(cache_file: Path, ttl: int) -> Optional[Any]:
    """
    Load data from cache file if it exists and is fresh.
    
    Args:
        cache_file: Path to cache file
        ttl: Time-to-live in seconds
    
    Returns:
        Cached data or None if cache is stale/missing
    """
    try:
        if not cache_file.exists():
            return None
        
        with open(cache_file, 'r') as f:
            cache = json.load(f)
        
        # Check if cache is still valid
        timestamp = cache.get('timestamp', 0)
        if time.time() - timestamp < ttl:
            return cache.get('data')
        
        return None
    except Exception:
        return None


def _save_cache(cache_file: Path, data: Any):
    """
    Save data to cache file.
    
    Args:
        cache_file: Path to cache file
        data: Data to cache (must be JSON-serializable)
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        cache = {
            'timestamp': time.time(),
            'data': data
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        # Silently fail if can't write cache
        pass


def clear_cache(cache_key: Optional[str] = None, region: Optional[str] = None):
    """
    Clear cached data.
    
    Args:
        cache_key: Specific cache to clear (e.g., 'quota_codes'). If None, clears all caches.
        region: Specific region to clear. If None, clears all regions.
    
    Examples:
        >>> clear_cache('quota_codes', 'us-east-1')  # Clear specific cache
        >>> clear_cache('quota_codes')  # Clear quota codes for all regions
        >>> clear_cache()  # Clear all caches
    """
    try:
        if not CACHE_DIR.exists():
            return
        
        if cache_key and region:
            # Clear specific cache file
            cache_file = CACHE_DIR / f'{cache_key}_{region}.json'
            if cache_file.exists():
                cache_file.unlink()
        elif cache_key:
            # Clear all region variants of this cache
            for cache_file in CACHE_DIR.glob(f'{cache_key}_*.json'):
                cache_file.unlink()
        else:
            # Clear all caches
            for cache_file in CACHE_DIR.glob('*.json'):
                cache_file.unlink()
    except Exception:
        pass


def get_cache_info() -> dict:
    """
    Get information about cached data.
    
    Returns:
        Dict with cache statistics and file info
    """
    try:
        if not CACHE_DIR.exists():
            return {'cache_dir': str(CACHE_DIR), 'exists': False, 'files': []}
        
        files = []
        for cache_file in CACHE_DIR.glob('*.json'):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                
                timestamp = cache.get('timestamp', 0)
                age_days = (time.time() - timestamp) / 86400
                
                files.append({
                    'name': cache_file.name,
                    'age_days': round(age_days, 1),
                    'size_kb': round(cache_file.stat().st_size / 1024, 1)
                })
            except Exception:
                continue
        
        return {
            'cache_dir': str(CACHE_DIR),
            'exists': True,
            'files': files,
            'total_files': len(files)
        }
    except Exception:
        return {'cache_dir': str(CACHE_DIR), 'exists': False, 'error': True}

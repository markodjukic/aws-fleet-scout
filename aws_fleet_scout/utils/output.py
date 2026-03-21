"""Standardized output formatting utilities"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich import print_json
import json


def print_json_output(
    data: Any,
    command: str,
    regions_checked: Optional[List[str]] = None,
    metadata: Optional[Dict] = None
):
    """
    Print standardized JSON output with consistent envelope structure.
    
    Args:
        data: The actual data payload
        command: Command name (e.g., 'spot.score', 'compare', 'fleet.pack')
        regions_checked: List of regions that were queried
        metadata: Additional metadata to include
    """
    envelope = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "data": data
    }
    
    if regions_checked:
        envelope["regions_checked"] = regions_checked
    
    if metadata:
        envelope["metadata"] = metadata
    
    # Use rich.print_json for better formatting and automatic serialization
    print_json(json.dumps(envelope, default=str))


def print_error_output(
    error: str,
    command: str,
    details: Optional[Dict] = None
):
    """
    Print standardized error output.
    
    Args:
        error: Error message
        command: Command name
        details: Additional error details
    """
    envelope = {
        "status": "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "error": error
    }
    
    if details:
        envelope["details"] = details
    
    print_json(json.dumps(envelope, default=str))

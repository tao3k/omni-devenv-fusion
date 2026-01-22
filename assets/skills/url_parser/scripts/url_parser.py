"""Generated skill: url_parser."""

from typing import Any
from omni.core.skills.script_loader import skill_command


import json
from urllib.parse import urlparse, parse_qs, urlencode


def parse_url(url: str) -> dict:
    """
    Parse a URL and extract all its components.

    Args:
        url: The URL string to parse

    Returns:
        dict with success, data containing parsed components, and error keys
    """
    try:
        if not url or not isinstance(url, str):
            return {"success": False, "data": None, "error": "URL must be a non-empty string"}

        parsed = urlparse(url)

        query_params = parse_qs(parsed.query)
        query_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

        result = {
            "original_url": url,
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
            "params": parsed.params,
            "query": parsed.query,
            "query_params": query_params,
            "fragment": parsed.fragment,
            "username": parsed.username,
            "password": parsed.password,
            "is_absolute": bool(parsed.scheme and parsed.netloc),
            "is_secure": parsed.scheme == "https" if parsed.scheme else False,
        }

        return {"success": True, "data": result, "error": None}

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


# Export the main function as skill_command
parse_url = skill_command(
    name="url_parser",
    category="generated",
    description="Auto-generated skill",
)(parse_url)

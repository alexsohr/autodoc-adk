"""Utility functions for data transformation and validation."""

from __future__ import annotations


def validate_input(data: dict) -> bool:
    """Validate that input data meets required schema."""
    required_keys = {"name", "type"}
    return required_keys.issubset(data.keys())


def transform_output(data: dict, format: str = "json") -> str:
    """Transform processed data into the specified output format."""
    if format == "json":
        import json

        return json.dumps(data, indent=2)
    return str(data)


def merge_configs(base: dict, override: dict) -> dict:
    """Deep merge two configuration dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result

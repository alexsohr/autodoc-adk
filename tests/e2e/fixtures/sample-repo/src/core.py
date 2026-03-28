"""Core module with primary business logic."""

from __future__ import annotations


class DataProcessor:
    """Processes input data through a configurable pipeline."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self._pipeline: list[str] = []

    def add_step(self, step_name: str) -> None:
        """Add a processing step to the pipeline."""
        self._pipeline.append(step_name)

    def execute(self, data: dict) -> dict:
        """Execute the processing pipeline on input data."""
        result = data.copy()
        for step in self._pipeline:
            result["processed_by"] = result.get("processed_by", [])
            result["processed_by"].append(step)
        return result


def create_processor(config: dict | None = None) -> DataProcessor:
    """Factory function to create a configured DataProcessor."""
    return DataProcessor(config=config)

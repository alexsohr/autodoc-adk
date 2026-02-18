"""Application entry point.

Configures OpenTelemetry BEFORE any other application imports
so that ADK picks up the global TracerProvider.

Run with::

    uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
"""

from src.config.telemetry import configure_telemetry

# Configure tracing + structured logging BEFORE any ADK-related imports
configure_telemetry()

from src.api.app import create_app  # noqa: E402

app = create_app()

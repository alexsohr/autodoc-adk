class TransientError(Exception):
    """Retryable errors: rate limits, timeouts, temporary network failures.

    Caught by Prefect for retry logic. Maps to HTTP 503.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"TransientError: {self.message}"


class PermanentError(Exception):
    """Non-retryable errors: invalid config, repo not found, validation failures.

    Maps to HTTP 400.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"PermanentError: {self.message}"


class QualityError(Exception):
    """Agent quality gate failures: below minimum score floor.

    Handled by the agent loop. Maps to HTTP 422.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"QualityError: {self.message}"

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.flows.tasks.callback import deliver_callback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kwargs(**overrides) -> dict:
    """Return a valid set of keyword arguments for ``deliver_callback``."""
    defaults = {
        "job_id": uuid.uuid4(),
        "status": "COMPLETED",
        "repository_id": uuid.uuid4(),
        "branch": "main",
        "callback_url": "https://example.com/webhook",
        "pull_request_url": "https://github.com/org/repo/pull/42",
        "quality_report": {"overall_score": 8.5},
        "token_usage": {"total_tokens": 1200},
        "error_message": None,
    }
    defaults.update(overrides)
    return defaults


def _mock_response(status_code: int) -> MagicMock:
    """Create a mock ``httpx.Response`` with the given status code."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.request = MagicMock(spec=httpx.Request)
    return resp


def _build_client_mock(post_side_effect):
    """Return a mock ``httpx.AsyncClient`` whose ``post`` has the given side effect.

    ``post_side_effect`` can be a single value, a list (for ``side_effect``), or
    an exception class/instance.
    """
    mock_client = AsyncMock()
    if isinstance(post_side_effect, list):
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_client.post = AsyncMock(return_value=post_side_effect)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeliverCallback:
    """Unit tests for the ``deliver_callback`` Prefect task."""

    # 1. Successful delivery ------------------------------------------------

    async def test_successful_delivery(self):
        """A 200 response results in a single POST and no error."""
        ctx, client = _build_client_mock(_mock_response(200))
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 1
        call_args = client.post.call_args
        assert call_args.args[0] == kwargs["callback_url"]
        posted_json = call_args.kwargs["json"]
        assert posted_json["job_id"] == str(kwargs["job_id"])
        assert posted_json["repository_id"] == str(kwargs["repository_id"])

    # 2. 4xx permanent failure -- no retry ----------------------------------

    async def test_4xx_permanent_failure_no_retry(self):
        """A 4xx response is treated as permanent and no retry is attempted."""
        ctx, client = _build_client_mock(_mock_response(400))
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 1
        mock_sleep.assert_not_awaited()

    # 3. 5xx transient retry then success -----------------------------------

    async def test_5xx_transient_retry_then_success(self):
        """A 5xx followed by a 200 should retry once and succeed."""
        responses = [_mock_response(500), _mock_response(200)]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 2

    # 4. 5xx exhausts all retries -------------------------------------------

    async def test_5xx_exhausts_retries(self):
        """3 consecutive 5xx responses exhaust retries without raising."""
        responses = [_mock_response(500), _mock_response(502), _mock_response(503)]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            # Must not raise
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 3

    # 5. Connection error triggers retry ------------------------------------

    async def test_connection_error_retry(self):
        """A ConnectError on the first attempt is retried, and the second succeeds."""
        responses = [
            httpx.ConnectError("connection refused"),
            _mock_response(200),
        ]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 2

    # 6. Timeout error triggers retry ---------------------------------------

    async def test_timeout_error_retry(self):
        """A TimeoutException on the first attempt is retried."""
        responses = [
            httpx.TimeoutException("read timed out"),
            _mock_response(200),
        ]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 2

    # 7. All retries exhausted with connection errors -----------------------

    async def test_all_retries_exhausted_connection_error(self):
        """3 ConnectErrors exhaust retries without raising."""
        responses = [
            httpx.ConnectError("refused"),
            httpx.ConnectError("refused"),
            httpx.ConnectError("refused"),
        ]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 3

    # 8. Payload structure --------------------------------------------------

    async def test_payload_structure(self):
        """The JSON payload POSTed to the callback URL has all expected fields."""
        ctx, client = _build_client_mock(_mock_response(200))
        kwargs = _make_kwargs(
            status="FAILED",
            pull_request_url=None,
            quality_report={"overall": 7.0},
            token_usage={"prompt": 500, "completion": 300},
            error_message="scope worker crashed",
        )

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        posted = client.post.call_args.kwargs["json"]

        # All expected keys present
        expected_keys = {
            "job_id",
            "status",
            "repository_id",
            "branch",
            "pull_request_url",
            "quality_report",
            "token_usage",
            "error_message",
            "completed_at",
        }
        assert set(posted.keys()) == expected_keys

        # Types and values
        assert posted["job_id"] == str(kwargs["job_id"])
        assert posted["status"] == "FAILED"
        assert posted["repository_id"] == str(kwargs["repository_id"])
        assert posted["branch"] == "main"
        assert posted["pull_request_url"] is None
        assert posted["quality_report"] == {"overall": 7.0}
        assert posted["token_usage"] == {"prompt": 500, "completion": 300}
        assert posted["error_message"] == "scope worker crashed"
        # completed_at should be an ISO-format datetime string
        assert isinstance(posted["completed_at"], str)
        assert "T" in posted["completed_at"]

    # 9. Exponential backoff delays -----------------------------------------

    async def test_exponential_backoff_delays(self):
        """Backoff delays follow the formula base * 2^(attempt-1): 2s, 4s."""
        responses = [_mock_response(500), _mock_response(500), _mock_response(500)]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await deliver_callback.fn(**kwargs)

        # After attempt 1: delay = 2 * 2^0 = 2
        # After attempt 2: delay = 2 * 2^1 = 4
        # After attempt 3: no sleep (last attempt)
        assert mock_sleep.await_count == 2
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [2, 4]

    # 10. 201 response is treated as success --------------------------------

    async def test_2xx_non_200_is_success(self):
        """Any 2xx/3xx status (< 400) is treated as a successful delivery."""
        ctx, client = _build_client_mock(_mock_response(201))
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 1

    # 11. Various 4xx codes are permanent -----------------------------------

    @pytest.mark.parametrize("status_code", [401, 403, 404, 422, 429])
    async def test_various_4xx_codes_no_retry(self, status_code: int):
        """All 4xx status codes are permanent failures -- no retry."""
        ctx, client = _build_client_mock(_mock_response(status_code))
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 1
        mock_sleep.assert_not_awaited()

    # 12. Mixed transient errors then success -------------------------------

    async def test_mixed_transient_errors_then_success(self):
        """A 5xx followed by a ConnectError followed by success uses 3 attempts."""
        responses = [
            _mock_response(503),
            httpx.ConnectError("refused"),
            _mock_response(200),
        ]
        ctx, client = _build_client_mock(responses)
        kwargs = _make_kwargs()

        with (
            patch("src.flows.tasks.callback.httpx.AsyncClient", return_value=ctx),
            patch("src.flows.tasks.callback.asyncio.sleep", new_callable=AsyncMock),
        ):
            await deliver_callback.fn(**kwargs)

        assert client.post.await_count == 3

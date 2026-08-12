"""Property 17: API Response Schema Conformance.

For any API request (successful or failed), the response SHALL conform
to the defined envelope structure: successful responses use
`ApiResponse[T]` with data and optional pagination meta, and error
responses use `ApiError` with code, message, and optional field-level
details.

Feature: watari-case-management, Property 17: API Response Schema Conformance
**Validates: Requirements 15.3, 15.4**

This test runs against the FastAPI TestClient and does not need a
database — we only exercise the error paths (404, 405, 422) which are
handled by global handlers wired in `src.api.error_handlers`.
"""

from __future__ import annotations

import string

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.api.main import app
from src.schemas.common import ApiError


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# Path segments that cannot match any route in the API (no real route
# uses these prefixes, and the characters are URL-safe).
_path_segments = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-",
    min_size=1,
    max_size=30,
)


@given(
    path_parts=st.lists(_path_segments, min_size=1, max_size=4),
)
@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_404_responses_conform_to_api_error(
    path_parts: list[str], client: TestClient
) -> None:
    """Any 404 from a GET to an unknown path returns a well-formed ApiError."""
    path = "/" + "/".join(path_parts)
    response = client.get(path)
    # We only care about 4xx/5xx for error-envelope checks. If a generated
    # path happens to hit a real route (unlikely given the prefixes), skip it.
    if response.status_code < 400:
        return
    body = response.json()
    # Must parse as ApiError
    parsed = ApiError.model_validate(body)
    # Required fields are present and non-empty
    assert parsed.code, "code must be set"
    assert parsed.message, "message must be set"
    assert parsed.request_id, "request_id must be set"


def test_405_method_not_allowed_conforms_to_api_error(client: TestClient) -> None:
    """Using an unsupported method on an existing path produces ApiError."""
    response = client.delete("/health")
    assert response.status_code in (404, 405)
    body = response.json()
    ApiError.model_validate(body)


def test_root_redoc_and_docs_are_not_errors(client: TestClient) -> None:
    """The auto-generated docs endpoints return HTML, not ApiError."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_request_id_is_echoed_and_propagated(client: TestClient) -> None:
    """The X-Request-ID header is honored inbound and echoed outbound."""
    incoming = "0123456789abcdef-custom-id"
    response = client.get("/health", headers={"X-Request-ID": incoming})
    assert response.headers.get("x-request-id") == incoming

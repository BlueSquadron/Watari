"""Request ID middleware.

Assigns a UUID to each incoming request, stores it on `request.state.request_id`,
and echoes it back in the `X-Request-ID` response header. Honors an incoming
`X-Request-ID` header when present so callers can correlate traces across hops.
"""

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request/response pair."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

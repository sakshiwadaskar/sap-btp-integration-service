"""Async HTTP client for querying a SAP OData V4 service.

Mirrors the patterns used against real SAP systems (S-4HANA / BTP
destinations): OData V4 query options, an `x-csrf-token: fetch` handshake
before state-changing calls, and parsing of SAP's `{"error": {...}}`
inner-error response shape on failure.
"""

from typing import Any, Optional

import httpx

from app.config import settings


class ODataError(Exception):
    """Raised when an OData request fails, carrying the parsed SAP error."""

    def __init__(self, status_code: int, code: Optional[str], message: Optional[str]):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"OData request failed ({status_code}): {message or code}")


def _parse_inner_error(response: httpx.Response) -> tuple[Optional[str], Optional[str]]:
    """Extract `code`/`message` from a SAP-style `{"error": {...}}` body.

    Falls back to the raw response text when the body isn't JSON or doesn't
    follow the expected shape, since upstream failures (proxies, gateways)
    don't always return a well-formed OData error payload.
    """
    try:
        body = response.json()
    except ValueError:
        return None, response.text or None

    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None, response.text or None

    code = error.get("code")
    message = error.get("message")
    # SAP Gateway often nests the human-readable message as {"value": "..."}.
    if isinstance(message, dict):
        message = message.get("value")
    return code, message


class ODataClient:
    """Thin async wrapper around `httpx` for SAP OData V4 query/write calls."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = base_url or settings.odata_base_url
        self.timeout = timeout or settings.request_timeout_seconds

    async def fetch_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Perform the SAP CSRF handshake required before write operations.

        SAP OData services reject POST/PUT/DELETE without a token obtained
        via a preceding GET that carries `x-csrf-token: fetch`.
        """
        response = await client.get(
            self.base_url,
            headers={"x-csrf-token": "fetch"},
            timeout=self.timeout,
        )
        token = response.headers.get("x-csrf-token")
        if not token:
            raise ODataError(
                response.status_code,
                "CSRF_TOKEN_MISSING",
                "Upstream service did not return an x-csrf-token header",
            )
        return token

    async def query_entity(
        self,
        entity_set: str,
        select: Optional[str] = None,
        filter_: Optional[str] = None,
        top: Optional[int] = None,
        expand: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Query an OData entity set with standard `$select`/`$filter`/`$top`/`$expand`.

        Returns the raw list of entity dicts from the response's `value` array.
        """
        params: dict[str, Any] = {}
        if select:
            params["$select"] = select
        if filter_:
            params["$filter"] = filter_
        if top is not None:
            params["$top"] = top
        if expand:
            params["$expand"] = expand

        url = f"{self.base_url.rstrip('/')}/{entity_set.lstrip('/')}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                raise ODataError(502, "UPSTREAM_UNREACHABLE", str(exc)) from exc

            if response.status_code >= 400:
                code, message = _parse_inner_error(response)
                raise ODataError(response.status_code, code, message)

            payload = response.json()
            return payload.get("value", [])

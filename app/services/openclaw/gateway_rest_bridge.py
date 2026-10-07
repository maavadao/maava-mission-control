"""HTTP/JSON bridge client for per-tenant tenant-platform Cloud Run services.

Mission Control natively talks to OpenClaw gateways using JSON-RPC v3 over
WebSocket. For multi-tenant deployments, however, each user has their own
``tenant-platform`` Cloud Run service that does NOT expose a WebSocket gateway
— instead it exposes the same OpenClaw RPC methods over a thin HTTP/JSON
bridge:

  - ``GET  {url}/healthz``                — liveness + protocol announcement
  - ``POST {url}/api/v1/rpc/{method}``    — invoke any OpenClaw RPC method

This module performs that translation when ``GatewayConfig.integration_mode``
is set to ``"rest_bridge"``. The contract mirrors the WebSocket flow: a
successful response is unwrapped to its ``data`` payload, anything else raises
``OpenClawGatewayError``.

The bridge endpoint is authenticated with the gateway's ``token`` value
(forwarded as a JWT in the ``Authorization: Bearer`` header — tenant-platform
verifies the JWT against its shared ``JWT_SECRET``).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.logging import get_logger
from app.services.openclaw.gateway_rpc import GatewayConfig, OpenClawGatewayError

logger = get_logger(__name__)

# Reasonable upper bound for a single bridge call (matches the worst-case
# duration of long-running OpenClaw RPCs like ``status`` or ``models.list``).
_DEFAULT_TIMEOUT_SECONDS = 30.0
# A single fast probe used by the version compatibility check.
_HEALTH_TIMEOUT_SECONDS = 10.0
# Static CalVer version reported by tenant-platform's REST bridge. Bumped only
# when the bridge contract changes in a backwards-incompatible way.
REST_BRIDGE_PROTOCOL_VERSION = "2026.3.4"


def _normalize_base_url(raw_url: str) -> str:
    """Coerce the configured gateway URL into an http(s) base for HTTP calls.

    Accepts ``ws://``/``wss://`` (legacy values left over from when the same
    URL was used for the WebSocket protocol) and rewrites them to the matching
    HTTP scheme. Strips any trailing slash so callers can safely append a path.
    """
    base = (raw_url or "").strip()
    if not base:
        message = "Gateway URL is not configured."
        raise OpenClawGatewayError(message)

    parsed = urlsplit(base)
    scheme = parsed.scheme.lower()
    if scheme == "wss":
        scheme = "https"
    elif scheme == "ws":
        scheme = "http"
    elif scheme not in ("http", "https"):
        # Bare host like ``my-tenant.example.com`` — assume https.
        return f"https://{base.rstrip('/')}"

    rebuilt = urlunsplit((scheme, parsed.netloc, parsed.path, "", ""))
    return rebuilt.rstrip("/")


def _bearer_headers(config: GatewayConfig) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = (config.token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _client(config: GatewayConfig, *, timeout: float) -> httpx.AsyncClient:
    verify = not config.allow_insecure_tls
    return httpx.AsyncClient(timeout=timeout, verify=verify)


def _unwrap_payload(method: str, body: object) -> object:
    """Mirror the success-envelope contract used by the existing WS client.

    ``tenant-platform`` returns ``{"success": true, "data": ...}`` on success.
    Older bridge endpoints may return the bare payload — we tolerate both.
    """
    if isinstance(body, dict):
        if body.get("success") is False:
            err = body.get("error") or body.get("message") or "RPC call failed"
            raise OpenClawGatewayError(f"gateway.rpc.{method}: {err}")
        if "data" in body:
            return body["data"]
    return body


async def rest_bridge_call(
    method: str,
    params: dict[str, Any] | None,
    *,
    config: GatewayConfig,
) -> object:
    """Invoke an OpenClaw RPC method against the tenant-platform REST bridge."""
    base_url = _normalize_base_url(config.url)
    url = f"{base_url}/api/v1/rpc/{method}"
    payload = {"params": params or {}}

    async with _client(config, timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(url, headers=_bearer_headers(config), json=payload)
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            logger.error(
                "gateway.rest_bridge.call.transport_error method=%s error_type=%s",
                method,
                exc.__class__.__name__,
            )
            raise OpenClawGatewayError(str(exc)) from exc

    if response.status_code >= 400:
        # Try to surface the bridge's structured error message for easier debugging.
        try:
            err_body = response.json()
        except (ValueError, json.JSONDecodeError):
            err_body = response.text
        logger.warning(
            "gateway.rest_bridge.call.http_error method=%s status=%s body=%s",
            method,
            response.status_code,
            err_body,
        )
        raise OpenClawGatewayError(
            f"REST bridge {method} failed with HTTP {response.status_code}: {err_body!r}",
        )

    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise OpenClawGatewayError(
            f"REST bridge {method} returned non-JSON body",
        ) from exc

    return _unwrap_payload(method, body)


async def rest_bridge_connect_metadata(*, config: GatewayConfig) -> dict[str, object]:
    """Synthesize a connect/hello payload from the bridge's ``/healthz`` probe.

    The WebSocket gateway returns a structured connect message containing
    ``server.version`` (CalVer). The REST bridge has no equivalent handshake,
    so we fabricate one from ``GET /healthz`` for compatibility-check call sites.
    """
    base_url = _normalize_base_url(config.url)
    url = f"{base_url}/healthz"

    async with _client(config, timeout=_HEALTH_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(url, headers=_bearer_headers(config))
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise OpenClawGatewayError(str(exc)) from exc

    if response.status_code >= 400:
        raise OpenClawGatewayError(
            f"REST bridge healthz failed with HTTP {response.status_code}",
        )

    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        body = {}

    version = REST_BRIDGE_PROTOCOL_VERSION
    if isinstance(body, dict):
        candidate = body.get("version")
        if isinstance(candidate, str) and candidate.strip():
            version = candidate.strip()

    return {
        "type": "connect",
        "ok": True,
        "transport": "rest_bridge",
        "server": {"version": version, "protocol": "rest_bridge"},
    }

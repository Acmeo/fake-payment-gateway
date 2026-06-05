"""HTTP-level tests for POST /v1/authorizations.

Verify byte-for-byte conformance with the Sales payment_gateway_client
contract and the idempotency semantics specified in the README:
- 5xx is never cached (this is what lets pm-503-once recover).
- 200 and 402 are cached and replayed identically per Idempotency-Key.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient


def _post(
    client: TestClient,
    *,
    idempotency_key: str,
    payment_method_token: str = "pm-integration",
    amount: str = "100.00",
    currency: str = "EUR",
) -> Any:
    return client.post(
        "/v1/authorizations",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "amount": amount,
            "currency": currency,
            "payment_method_token": payment_method_token,
        },
    )


def test_default_token_returns_200_authorized(client: TestClient) -> None:
    response = _post(client, idempotency_key=str(uuid4()))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert body["authorization_id"]
    assert body["reference"]
    assert set(body.keys()) == {"authorization_id", "status", "reference"}


def test_idempotency_replays_identical_authorized_response(client: TestClient) -> None:
    key = str(uuid4())
    first = _post(client, idempotency_key=key)
    second = _post(client, idempotency_key=key)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    # The deterministic id is derived from the key, so it must reference the key.
    assert key in first.json()["authorization_id"]


def test_pm_decline_returns_402_insufficient_funds(client: TestClient) -> None:
    response = _post(client, idempotency_key=str(uuid4()), payment_method_token="pm-decline")
    assert response.status_code == 402
    body = response.json()
    assert body == {"status": "declined", "reason": "insufficient_funds"}


def test_pm_decline_fraud_returns_402_fraud_suspected(client: TestClient) -> None:
    response = _post(
        client, idempotency_key=str(uuid4()), payment_method_token="pm-decline-fraud"
    )
    assert response.status_code == 402
    body = response.json()
    assert body == {"status": "declined", "reason": "fraud_suspected"}


def test_pm_decline_is_idempotent_per_key(client: TestClient) -> None:
    key = str(uuid4())
    first = _post(client, idempotency_key=key, payment_method_token="pm-decline")
    second = _post(client, idempotency_key=key, payment_method_token="pm-decline")
    assert first.status_code == second.status_code == 402
    assert first.json() == second.json()


def test_pm_503_always_returns_503_and_is_never_cached(client: TestClient) -> None:
    key = str(uuid4())
    first = _post(client, idempotency_key=key, payment_method_token="pm-503")
    second = _post(client, idempotency_key=key, payment_method_token="pm-503")
    assert first.status_code == 503
    assert second.status_code == 503
    # The key is *not* stored, so switching tokens on the same key still re-decides.
    third = _post(client, idempotency_key=key, payment_method_token="pm-integration")
    assert third.status_code == 200


def test_pm_503_once_first_attempt_503_then_recovers(client: TestClient) -> None:
    # This is the headline test for transient recovery: same key, the 503
    # does *not* poison the key, the second call succeeds, the third
    # replays the cached success identically.
    key = str(uuid4())
    first = _post(client, idempotency_key=key, payment_method_token="pm-503-once")
    assert first.status_code == 503

    second = _post(client, idempotency_key=key, payment_method_token="pm-503-once")
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "authorized"

    third = _post(client, idempotency_key=key, payment_method_token="pm-503-once")
    assert third.status_code == 200
    assert third.json() == body


def test_amount_decimal_string_is_preserved(client: TestClient) -> None:
    # The client transmits amount as a string; a malformed amount must be
    # rejected at the boundary, not silently coerced.
    bad = _post(client, idempotency_key=str(uuid4()), amount="not-a-number")
    assert bad.status_code == 400

    # A well-formed decimal string with explicit scale is accepted.
    good = _post(client, idempotency_key=str(uuid4()), amount="121.00")
    assert good.status_code == 200


def test_idempotency_key_is_required(client: TestClient) -> None:
    response = client.post(
        "/v1/authorizations",
        json={
            "amount": "10.00",
            "currency": "EUR",
            "payment_method_token": "pm-integration",
        },
    )
    # Missing required header surfaces as 422 from FastAPI; the Sales
    # client never omits it, so this branch is only here to lock down the
    # invariant that the fake will not silently authorize without one.
    assert response.status_code in (400, 422)

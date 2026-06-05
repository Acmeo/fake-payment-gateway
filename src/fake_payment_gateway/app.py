"""FastAPI app for the fake payment gateway.

Implements POST /v1/authorizations matching the contract consumed by
the Sales payment_gateway_client. Behaviour is routed deterministically
by ``payment_method_token``; see the README for the magic-token table.

The fake is intentionally thin: no DB, no domain model, no invariants.
It is a third party, not a totality. The idempotency store is a plain
in-memory dict.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from fake_payment_gateway.store import Store, TerminalResponse


class AuthorizationRequest(BaseModel):
    # ``amount`` is transmitted as a decimal string to preserve scale;
    # we parse it as Decimal here so a malformed value can be rejected at
    # the boundary rather than treated as authorized.
    amount: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    payment_method_token: str = Field(min_length=1)


app = FastAPI(title="fake-payment-gateway", version="0.1.0")
app.state.store = Store()


def _store() -> Store:
    return app.state.store  # type: ignore[no-any-return]


def _authorized_response(idempotency_key: str) -> TerminalResponse:
    # Deterministic ids derived from the key so replays are byte-identical
    # without us needing to remember a freshly generated value.
    return TerminalResponse(
        status_code=200,
        body={
            "authorization_id": f"auth-{idempotency_key}",
            "status": "authorized",
            "reference": f"gw-ref-{idempotency_key}",
        },
    )


def _declined_response(reason: str) -> TerminalResponse:
    return TerminalResponse(
        status_code=402,
        body={"status": "declined", "reason": reason},
    )


@app.post("/v1/authorizations")
def authorize(
    body: AuthorizationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
) -> JSONResponse:
    try:
        amount = Decimal(body.amount)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amount must be a decimal string",
        ) from exc
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amount must be strictly positive",
        )

    store = _store()

    # Replay terminal result if we have one for this key.
    cached = store.get(idempotency_key)
    if cached is not None:
        return JSONResponse(status_code=cached.status_code, content=cached.body)

    token = body.payment_method_token
    if token == "pm-decline":
        response = _declined_response("insufficient_funds")
        store.put(idempotency_key, response)
        return JSONResponse(status_code=response.status_code, content=response.body)
    if token == "pm-decline-fraud":
        response = _declined_response("fraud_suspected")
        store.put(idempotency_key, response)
        return JSONResponse(status_code=response.status_code, content=response.body)
    if token == "pm-503":
        # Permanent transient failure. Never cached -- a retry must be free
        # to reach a different outcome (which, for pm-503, it won't).
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "service unavailable"},
        )
    if token == "pm-503-once":
        if not store.has_seen_503_once(idempotency_key):
            store.mark_503_once_seen(idempotency_key)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "service unavailable (transient)"},
            )
        response = _authorized_response(idempotency_key)
        store.put(idempotency_key, response)
        return JSONResponse(status_code=response.status_code, content=response.body)

    # Default: authorize.
    response = _authorized_response(idempotency_key)
    store.put(idempotency_key, response)
    return JSONResponse(status_code=response.status_code, content=response.body)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

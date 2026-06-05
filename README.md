# fake-payment-gateway

Deterministic in-memory fake of the external payment gateway, consumed
by the Sales totality over HTTP. **The payment gateway is a third party,
not a Sales-internal totality**, so this service has no database and no
domain model. The asymmetry with the real `catalog` and `identity`
services is intentional and part of the reference architecture's
argument: not everything a system touches is a totality of that system.

## HTTP contract

```
POST /v1/authorizations
  headers: Idempotency-Key: <uuid-string>
  body:    { "amount": "<decimal-string>", "currency": "<str>",
             "payment_method_token": "<str>" }
  200 -> { "authorization_id", "status": "authorized", "reference" }
  402 -> { "status": "declined", "reason": "<str>" }
  5xx -> service unavailable (body irrelevant)
```

- `amount` is a decimal string (never a number).
- `Idempotency-Key` is a UUID string.
- The Sales client treats `>= 500` as `PaymentGatewayUnavailable` and any
  other non-`200` non-`402` as `PaymentGatewayProtocolError`. So the fake
  only ever responds `200`, `402`, or `5xx`.

## Behaviour — magic `payment_method_token`s

| `payment_method_token` | response |
|---|---|
| `pm-decline` | `402 { status: "declined", reason: "insufficient_funds" }` (terminal, cached) |
| `pm-decline-fraud` | `402 { status: "declined", reason: "fraud_suspected" }` (terminal, cached) |
| `pm-503` | `503` always (permanent failure; never cached) |
| `pm-503-once` | First call per Idempotency-Key: `503`. Subsequent calls: `200 authorized` (transient → **recovery**). |
| anything else (e.g. `pm-integration`) | `200 authorized` (terminal, cached) |

## Idempotency semantics

The point of `Idempotency-Key` is that retries are safe: the same key
produces the same response, with no double charge.

- Only **terminal** results (`200`, `402`) are stored. A replay with the
  same key returns the byte-for-byte same response, including the same
  `authorization_id` and `reference`.
- **`5xx` is never stored**. That is what lets `pm-503-once` recover on
  retry: the failed attempt does not poison the key.
- In `200` responses, `authorization_id` and `reference` are derived
  deterministically from the `Idempotency-Key` (so replays are
  byte-identical without us having to remember a freshly generated id).

## Running

```
uv sync
uv run uvicorn fake_payment_gateway.app:app --host 0.0.0.0 --port 8003
```

## Validation

```
uv run ruff check .
uv run mypy src
uv run pytest
```

# fake-payment-gateway

Deterministic in-memory fake of the external payment gateway, consumed
by the Sales totality over HTTP. **The payment gateway is a third party,
not a Sales-internal totality**, so this service has no database and no
domain model. The asymmetry with the real `catalog` and `identity`
services is intentional and part of the reference architecture's
argument: not everything a system touches is a totality of that system.

## About this reference

This repository is part of a reference implementation accompanying a
six-article series on distributed systems architecture by Alberto Casado
Martin. The series argues that most distributed systems are *attributive
totalities* — their parts only acquire meaning in relation to the whole — and
that the canonical microservices reparto routinely confuses them with
*distributive totalities* (sets of independent peers). The full list of
articles is at the bottom of this README; the fourth article in particular
gives the framing that explains why this repository looks the way it does.

### Where this repo sits in that frame

A real payment provider — Stripe, Adyen, whatever — is itself an attributive
totality at its own level of analysis, with a domain as intricate as Sales'.
But from the cut at which we are designing the e-commerce, the payment
provider is **not a totality of ours**. It is a **material part** of the
e-commerce: it sustains the totality (Sales cannot subsist without something
that authorizes payments) but it does not constitute its identity (the same
provider could equally sustain a hospital records system or a logistics
platform; that it serves us is contingent). Per the fourth article, what
happens when an outside totality becomes a material part of ours is
*determination*: our contract, our retry policy, our idempotency-key
scheme determine how that provider is consumed from inside Sales.

The consequence in code is that there is **nothing of ours to implement**
inside this repository. A real payment gateway is someone else's totality; a
faithful stub of the contract is the correct and complete thing to build for
the reference. The poverty of this fake is the argument: enriching it with a
fake domain model, a fake state machine of refunds, or a fake "totality
shape" would betray the cut and confuse the reader about what kind of thing
the payment gateway is.

What this fake **does** model precisely is the contract Sales actually relies
on at this boundary: the **idempotency key**. The Sales `payment-handler`
sends one per attempt; the fake remembers terminal outcomes per key (200 /
402) so a retry produces the same result, and intentionally does not cache
5xx so transient failures can recover on retry (`pm-503-once`). That single
mechanism — idempotency at the boundary with a third party — is what the
fifth and sixth articles point to as the canonical sign of a real boundary:
where Sales has to send an idempotency key, the cut is genuine.

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

## Article series

URLs will be filled in once each article is published; placeholders below are
search-and-replaceable.

1. [The Illusion of Microservices Independence](TODO-article-1-url)
2. [Is Going Back to Monoliths Really the Solution?](TODO-article-2-url)
3. [The Forgotten Transition: From Analysis to Design, in a Field That Stopped Asking](TODO-article-3-url)
4. [The Illusion of Method: How Domain-Driven Design Hides the Question It Claims to Answer](TODO-article-4-url)
5. [Place Order: Anatomy of a Bad Cut](TODO-article-5-url)
6. [Place Order: A Cut That Holds](TODO-article-6-url)

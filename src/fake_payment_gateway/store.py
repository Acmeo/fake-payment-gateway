"""In-memory idempotency store for the fake payment gateway.

The point of the Idempotency-Key is that retries are safe: the same key
produces the same response. We only cache **terminal** results (200, 402).
5xx is never cached -- a 5xx is transient by contract, so a retry after a
5xx must be allowed to reach a different outcome. That is what lets the
``pm-503-once`` token model a recoverable failure.

Single-process state. The fake is deliberately not built for horizontal
scaling -- it stands in for a third party in a single test container.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TerminalResponse:
    """A terminal HTTP response we are willing to replay for retries.

    ``status_code`` is either 200 or 402. ``body`` is the JSON payload
    we return verbatim.
    """

    status_code: int
    body: dict[str, str]


@dataclass
class Store:
    """Idempotency store.

    ``terminals`` maps an Idempotency-Key to the terminal response we
    handed back the first time. ``seen_503_once`` records the keys that
    have already failed once with the ``pm-503-once`` token, so a second
    attempt with the same key succeeds.
    """

    terminals: dict[str, TerminalResponse] = field(default_factory=dict)
    seen_503_once: set[str] = field(default_factory=set)

    def get(self, key: str) -> TerminalResponse | None:
        return self.terminals.get(key)

    def put(self, key: str, response: TerminalResponse) -> None:
        self.terminals[key] = response

    def mark_503_once_seen(self, key: str) -> None:
        self.seen_503_once.add(key)

    def has_seen_503_once(self, key: str) -> bool:
        return key in self.seen_503_once

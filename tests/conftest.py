"""Shared fixtures for fake-payment-gateway tests.

Each test gets a fresh in-memory idempotency store, so behaviour for
keys carried across tests is isolated.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from fake_payment_gateway.app import app
from fake_payment_gateway.store import Store


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app.state.store = Store()
    with TestClient(app) as c:
        yield c

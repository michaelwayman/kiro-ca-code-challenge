"""Liveness and readiness (Req 11.1)."""

from collections.abc import Iterator
from unittest import mock

import pytest
from django.db import OperationalError
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


def test_live_is_200_without_authentication(client: Client) -> None:
    response = client.get("/healthz/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_is_200_when_database_answers(client: Client) -> None:
    response = client.get("/healthz/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


@pytest.fixture
def broken_database() -> Iterator[None]:
    with mock.patch(
        "config.health.connection.cursor", side_effect=OperationalError("connection refused")
    ):
        yield


@pytest.mark.usefixtures("broken_database")
def test_ready_is_503_when_database_is_down(client: Client) -> None:
    response = client.get("/healthz/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "down"}


def test_health_endpoints_reject_non_get(client: Client) -> None:
    assert client.post("/healthz/live").status_code == 405

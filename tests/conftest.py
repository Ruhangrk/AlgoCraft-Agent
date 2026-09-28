"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.llm.catalog import clear_catalog_cache
from app.llm.factory import clear_model_cache
from app.main import app


@pytest.fixture(autouse=True)
def _clear_llm_caches() -> None:
    from app.llm.discover import clear_discovery_cache

    clear_catalog_cache()
    clear_model_cache()
    clear_discovery_cache()
    yield
    clear_catalog_cache()
    clear_model_cache()
    clear_discovery_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

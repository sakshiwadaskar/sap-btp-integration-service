"""Tests covering schema validation, OData query serialization, and
mocked upstream failure handling.

Async calls are driven with `asyncio.run` directly (no pytest-asyncio
dependency, per the project's minimal-dependency requirement). `httpx`
calls are mocked via `monkeypatch` so no network access is required.
"""

import asyncio

import httpx
import pytest

from app.odata_client import ODataClient, ODataError
from app.schemas import Product
from app.services import find_critical_stock, normalize_products


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_product_validates_sap_field_aliases():
    raw = {
        "ProductID": 1,
        "ProductName": "Chai",
        "UnitPrice": 18.0,
        "UnitsInStock": 39,
        "Discontinued": False,
        "@odata.etag": "W/\"1\"",  # extra field SAP adds; should be ignored
    }
    product = Product.model_validate(raw)
    assert product.product_id == 1
    assert product.product_name == "Chai"
    assert product.units_in_stock == 39


def test_product_rejects_negative_unit_price():
    raw = {
        "ProductID": 1,
        "ProductName": "Chai",
        "UnitPrice": -1.0,
        "UnitsInStock": 39,
        "Discontinued": False,
    }
    with pytest.raises(Exception):
        Product.model_validate(raw)


def test_normalize_products_skips_malformed_entries():
    raw_products = [
        {
            "ProductID": 1,
            "ProductName": "Chai",
            "UnitPrice": 18.0,
            "UnitsInStock": 39,
            "Discontinued": False,
        },
        {"ProductID": 2, "ProductName": "Missing fields"},  # malformed
    ]
    products = normalize_products(raw_products)
    assert len(products) == 1
    assert products[0].product_id == 1


def test_find_critical_stock_filters_by_threshold():
    products = [
        Product.model_validate(
            {
                "ProductID": 1,
                "ProductName": "Low Stock",
                "UnitPrice": 10.0,
                "UnitsInStock": 2,
                "Discontinued": False,
            }
        ),
        Product.model_validate(
            {
                "ProductID": 2,
                "ProductName": "High Stock",
                "UnitPrice": 10.0,
                "UnitsInStock": 100,
                "Discontinued": False,
            }
        ),
        Product.model_validate(
            {
                "ProductID": 3,
                "ProductName": "Low Stock Discontinued",
                "UnitPrice": 10.0,
                "UnitsInStock": 1,
                "Discontinued": True,
            }
        ),
    ]
    result = find_critical_stock(products, threshold=10)
    assert result.count == 1
    assert result.items[0].product_id == 1


# ---------------------------------------------------------------------------
# OData query serialization + mocked upstream behavior
# ---------------------------------------------------------------------------


def test_query_entity_serializes_odata_params(monkeypatch):
    captured = {}

    async def fake_get(self, url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"value": []}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = ODataClient(base_url="https://example.test/svc/")
    asyncio.run(
        client.query_entity(
            "Products", select="ProductName,UnitPrice", filter_="UnitsInStock lt 10", top=5, expand="Category"
        )
    )

    assert captured["url"] == "https://example.test/svc/Products"
    assert captured["params"] == {
        "$select": "ProductName,UnitPrice",
        "$filter": "UnitsInStock lt 10",
        "$top": 5,
        "$expand": "Category",
    }


def test_query_entity_raises_odata_error_on_sap_inner_error(monkeypatch):
    async def fake_get(self, url, params=None, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(
            400,
            json={"error": {"code": "BAD_REQUEST", "message": {"value": "Invalid filter"}}},
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = ODataClient(base_url="https://example.test/svc/")
    with pytest.raises(ODataError) as exc_info:
        asyncio.run(client.query_entity("Products"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.message == "Invalid filter"


def test_query_entity_raises_odata_error_on_network_failure(monkeypatch):
    async def fake_get(self, url, params=None, headers=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = ODataClient(base_url="https://example.test/svc/")
    with pytest.raises(ODataError) as exc_info:
        asyncio.run(client.query_entity("Products"))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "UPSTREAM_UNREACHABLE"

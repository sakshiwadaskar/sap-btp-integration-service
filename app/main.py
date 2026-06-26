"""FastAPI entrypoint exposing REST endpoints over the SAP OData integration.

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI, HTTPException, Query

from app.odata_client import ODataClient, ODataError
from app.schemas import CriticalStockResponse, ProductQueryResponse
from app.services import find_critical_stock, normalize_products

app = FastAPI(
    title="SAP OData Side-by-Side Integration & Validation Service",
    description=(
        "Integrates with a SAP OData V4 service (Northwind V4 as a stand-in), "
        "validates/normalizes entities, and exposes a clean REST API."
    ),
    version="1.0.0",
)

odata_client = ODataClient()


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness check for the integration service itself."""
    return {"status": "ok"}


@app.get("/api/products/query", response_model=ProductQueryResponse)
async def query_products(
    select: str | None = Query(None, description="OData $select, e.g. 'ProductName,UnitPrice'"),
    filter_: str | None = Query(None, alias="filter", description="OData $filter expression"),
    top: int | None = Query(None, ge=1, le=500, description="OData $top"),
    expand: str | None = Query(None, description="OData $expand, e.g. 'Category'"),
) -> ProductQueryResponse:
    """Query the upstream `Products` entity set and return validated results."""
    try:
        raw_products = await odata_client.query_entity(
            "Products", select=select, filter_=filter_, top=top, expand=expand
        )
    except ODataError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message or exc.code) from exc

    products = normalize_products(raw_products)
    return ProductQueryResponse(count=len(products), products=products)


@app.get("/api/inventory/critical-stock", response_model=CriticalStockResponse)
async def critical_stock(
    threshold: int | None = Query(None, ge=0, description="Override the default critical-stock threshold"),
) -> CriticalStockResponse:
    """Return products at or below the critical stock threshold."""
    try:
        raw_products = await odata_client.query_entity("Products")
    except ODataError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message or exc.code) from exc

    products = normalize_products(raw_products)
    return find_critical_stock(products, threshold=threshold)

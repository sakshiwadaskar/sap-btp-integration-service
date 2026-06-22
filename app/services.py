"""Business/transformation logic: reconciliation, filtering, normalization.

Keeps the FastAPI layer (`main.py`) thin by owning the rules for turning
raw OData entity dicts into validated `Product` models and derived
inventory views.
"""

from pydantic import ValidationError

from app.config import settings
from app.schemas import CriticalStockItem, CriticalStockResponse, Product


def normalize_products(raw_products: list[dict]) -> list[Product]:
    """Validate and normalize raw OData product dicts into `Product` models.

    Raw SAP/OData payloads may include extra fields (e.g. `@odata.etag`)
    or fields in varying case; `Product` only pulls the fields it declares,
    so extras are ignored and the result is a strict, typed contract.
    """
    products: list[Product] = []
    for raw in raw_products:
        try:
            products.append(Product.model_validate(raw))
        except ValidationError:
            # Skip entities that don't satisfy the schema rather than
            # failing the whole batch on one malformed upstream record.
            continue
    return products


def find_critical_stock(
    products: list[Product], threshold: int | None = None
) -> CriticalStockResponse:
    """Identify products at or below the critical stock threshold."""
    effective_threshold = threshold if threshold is not None else settings.critical_stock_threshold

    critical_items = [
        CriticalStockItem(
            product_id=product.product_id,
            product_name=product.product_name,
            units_in_stock=product.units_in_stock,
            threshold=effective_threshold,
        )
        for product in products
        if not product.discontinued and product.units_in_stock <= effective_threshold
    ]

    return CriticalStockResponse(
        threshold=effective_threshold,
        count=len(critical_items),
        items=critical_items,
    )

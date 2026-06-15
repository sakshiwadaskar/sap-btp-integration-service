"""Pydantic models for SAP OData entity structures and API responses.

These models validate/normalize raw OData JSON payloads (field names and
types can drift between SAP systems and versions) into a strict, typed
contract the rest of the service and its consumers can rely on.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    """Validated representation of a Northwind/SAP `Product` entity."""

    product_id: int = Field(alias="ProductID")
    product_name: str = Field(alias="ProductName")
    unit_price: float = Field(alias="UnitPrice")
    units_in_stock: int = Field(alias="UnitsInStock")
    discontinued: bool = Field(alias="Discontinued")

    model_config = {"populate_by_name": True}

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("unit_price must not be negative")
        return value

    @field_validator("units_in_stock")
    @classmethod
    def units_in_stock_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("units_in_stock must not be negative")
        return value


class ODataCollectionResponse(BaseModel):
    """Generic envelope for an OData V4 collection response (`value` array)."""

    value: list[dict]


class CriticalStockItem(BaseModel):
    """A single product flagged as low/critical inventory."""

    product_id: int
    product_name: str
    units_in_stock: int
    threshold: int


class CriticalStockResponse(BaseModel):
    """Response payload for the critical-stock inventory endpoint."""

    threshold: int
    count: int
    items: list[CriticalStockItem]


class ProductQueryResponse(BaseModel):
    """Response payload for the products query endpoint."""

    count: int
    products: list[Product]


class ODataInnerError(BaseModel):
    """Parsed `error` object from a SAP/OData error response body."""

    code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[list[dict]] = None

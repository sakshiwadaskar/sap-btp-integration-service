# SAP OData Side-by-Side Integration & Validation Service

A lightweight Python/FastAPI service that demonstrates a **side-by-side extension**
pattern for SAP: it integrates with a SAP OData V4 service, validates and
normalizes the data it receives, and re-exposes it through a clean, typed REST
API — the same shape an SAP BTP extension would take in front of an S-4HANA or
ECC backend.

It targets the public **Northwind V4 OData service** as a stand-in for a real
SAP OData V4 endpoint, so the project runs out of the box with no SAP tenant
required, while still exercising the integration patterns (OData query
options, CSRF handshake, SAP-style error payloads) that a real SAP integration
needs.

## Architecture

```
+--------------------------+        OData V4 (JSON)        +----------------------------+        REST / JSON        +----------------------------+
|                          |  <-------------------------->  |                            |  <--------------------->  |                            |
|   SAP OData V4 / BTP     |   $select, $filter, $top,       |  Python Integration        |   /api/health              |  Fiori Elements /          |
|   (Northwind V4 stand-in)|   $expand, x-csrf-token         |  Service (FastAPI)         |   /api/products/query      |  Consumers                 |
|                          |                                 |  - odata_client.py          |   /api/inventory/          |  (dashboards, UIs, other   |
|                          |                                 |  - schemas.py (Pydantic)    |     critical-stock         |   backend services)        |
|                          |                                 |  - services.py               |                            |                            |
+--------------------------+                                 +----------------------------+                            +----------------------------+
```

The service sits **side-by-side** with the SAP backend rather than modifying
it: it reads via OData, validates/reshapes the payload into a strict schema,
and publishes a stable REST contract that downstream consumers (Fiori
Elements apps, dashboards, other services) can rely on even if the upstream
SAP field names or types drift.

## Features

- **Async OData client** (`app/odata_client.py`) — queries entity sets with
  OData V4 `$select` / `$filter` / `$top` / `$expand`, performs the
  `x-csrf-token: fetch` handshake SAP requires ahead of write operations, and
  parses SAP's `{"error": {...}}` inner-error shape into a typed exception.
- **Strict validation** (`app/schemas.py`) — Pydantic models validate and
  normalize raw OData entities (`ProductID`, `ProductName`, `UnitPrice`,
  `UnitsInStock`, `Discontinued`), rejecting malformed records instead of
  silently propagating bad data.
- **Business logic** (`app/services.py`) — normalizes ERP field names into a
  standard JSON contract and flags critical/low-stock items against a
  configurable threshold.
- **REST API** (`app/main.py`) — `/api/health`, `/api/products/query`,
  `/api/inventory/critical-stock`, fully documented via Swagger/OpenAPI.

## Project layout

```
sap-btp-integration-service/
├── app/
│   ├── __init__.py
│   ├── config.py        # Settings (OData base URL, timeout, thresholds)
│   ├── odata_client.py   # HTTP client for SAP OData queries & CSRF handshake
│   ├── schemas.py        # Pydantic models for SAP entity validation
│   ├── services.py       # Transformation, reconciliation & filtering logic
│   └── main.py           # FastAPI entrypoint exposing REST endpoints
├── tests/
│   ├── __init__.py
│   └── test_integration.py
├── requirements.txt
└── README.md
```

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/products/query` | Query `Products` with `$select`, `$filter`, `$top`, `$expand` |
| GET | `/api/inventory/critical-stock` | Products at/below a configurable stock threshold |

### Configuration

Environment variables (all optional, sensible defaults point at the public
Northwind V4 service):

| Variable | Default |
|---|---|
| `SAP_ODATA_BASE_URL` | `https://services.odata.org/V4/Northwind/Northwind.svc/` |
| `SAP_ODATA_TIMEOUT_SECONDS` | `15.0` |
| `SAP_ODATA_CRITICAL_STOCK_THRESHOLD` | `10` |

## Testing

```bash
pytest tests/ -v
```

Tests cover Pydantic schema validation (including rejection of malformed
entities), OData query-parameter serialization, and mocked upstream failure
handling (SAP inner-error parsing, network errors) — no live network calls
required.

## Resume talking points

- Built an async Python/FastAPI integration service that connects to a SAP
  OData V4 backend, implementing enterprise patterns (OData query
  composition, CSRF token handshake, SAP inner-error parsing) with strict
  Pydantic-validated data contracts and full Swagger/OpenAPI documentation.
- Designed a side-by-side extension architecture that decouples downstream
  consumers (Fiori Elements, dashboards) from upstream SAP schema drift by
  validating, normalizing, and re-exposing ERP data through a stable,
  independently versioned REST API.

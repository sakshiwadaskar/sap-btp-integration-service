"""Service configuration.

Settings are read from environment variables so the service can be pointed
at a real SAP BTP/S-4HANA OData endpoint in production without any code
changes. Kept dependency-free (no pydantic-settings) per the project's
minimal-dependency requirement.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the OData integration service."""

    # Public Northwind V4 OData service used as a stand-in for a real
    # SAP OData V4 endpoint (e.g. an S-4HANA or BTP destination service).
    odata_base_url: str = os.getenv(
        "SAP_ODATA_BASE_URL", "https://services.odata.org/V4/Northwind/Northwind.svc/"
    )

    # Network timeout (seconds) for all outbound OData calls.
    request_timeout_seconds: float = float(os.getenv("SAP_ODATA_TIMEOUT_SECONDS", "15.0"))

    # Threshold below which a product is flagged as "critical stock".
    critical_stock_threshold: int = int(os.getenv("SAP_ODATA_CRITICAL_STOCK_THRESHOLD", "10"))


settings = Settings()

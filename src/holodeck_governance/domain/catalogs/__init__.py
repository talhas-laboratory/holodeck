"""Versioned machine-readable governance catalogs (M1-031)."""

from holodeck_governance.domain.catalogs.errors import (
    CATALOG_VERSION as ERROR_CATALOG_VERSION,
)
from holodeck_governance.domain.catalogs.errors import DOMAIN_ERRORS, DomainErrorCode
from holodeck_governance.domain.catalogs.events import (
    CATALOG_VERSION as EVENT_CATALOG_VERSION,
)
from holodeck_governance.domain.catalogs.events import EVENT_SCHEMAS, EventType
from holodeck_governance.domain.catalogs.reasons import (
    CATALOG_VERSION as REASON_CATALOG_VERSION,
)
from holodeck_governance.domain.catalogs.reasons import REASON_CODES, ReasonCode
from holodeck_governance.domain.catalogs.scenario_map import SCENARIO_CATALOG_EXPECTATIONS

__all__ = [
    "DOMAIN_ERRORS",
    "DomainErrorCode",
    "ERROR_CATALOG_VERSION",
    "EVENT_CATALOG_VERSION",
    "EVENT_SCHEMAS",
    "EventType",
    "REASON_CATALOG_VERSION",
    "REASON_CODES",
    "ReasonCode",
    "SCENARIO_CATALOG_EXPECTATIONS",
]

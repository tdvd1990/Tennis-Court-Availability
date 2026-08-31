from .base import Adapter
from .mock import MockAdapter
from .court_reserve import CourtReserveAdapter
from .club_automation import ClubAutomationAdapter

ADAPTERS_BY_SYSTEM = {
    "court_reserve": CourtReserveAdapter,
    "club_automation": ClubAutomationAdapter,
}

__all__ = [
    "Adapter",
    "MockAdapter",
    "CourtReserveAdapter",
    "ClubAutomationAdapter",
    "ADAPTERS_BY_SYSTEM",
]

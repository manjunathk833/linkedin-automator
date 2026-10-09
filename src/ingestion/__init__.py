"""Multi-source job ingestion package for ATS boards and stealth LinkedIn discovery."""

from src.ingestion.ashby import AshbyCollector
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.ingestion.greenhouse import GreenhouseCollector
from src.ingestion.lever import LeverCollector
from src.ingestion.workday import WorkdayCollector

__all__ = [
    "ATSDiscoveryCoordinator",
    "AshbyCollector",
    "GreenhouseCollector",
    "LeverCollector",
    "WorkdayCollector",
]

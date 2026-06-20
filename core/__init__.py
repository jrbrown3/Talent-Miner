"""Core package for the AI Opportunity Finder."""
from . import (analysis, clustering, config, exporting, ingestion, providers,
               roi, scoring, storage)
from .models import Opportunity, SourceDocument

__all__ = [
    "analysis",
    "clustering",
    "config",
    "exporting",
    "ingestion",
    "providers",
    "roi",
    "scoring",
    "storage",
    "Opportunity",
    "SourceDocument",
]

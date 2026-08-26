"""Discovery source adapters."""

from cv_optimizer.discovery.sources.ashby import AshbySource
from cv_optimizer.discovery.sources.base import (
    HttpJobSource,
    JobSource,
    RateLimited,
    SourceError,
)
from cv_optimizer.discovery.sources.greenhouse import GreenhouseSource
from cv_optimizer.discovery.sources.lever import LeverSource
from cv_optimizer.discovery.sources.serpapi import SerpApiSource

__all__ = [
    "JobSource",
    "HttpJobSource",
    "SourceError",
    "RateLimited",
    "SerpApiSource",
    "LeverSource",
    "AshbySource",
    "GreenhouseSource",
]

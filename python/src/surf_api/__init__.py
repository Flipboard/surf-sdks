"""Surf API Python SDK — programmatic access to the Surf social platform."""

from .client import SurfClient
from .exceptions import (
    SurfAPIError,
    SurfAuthError,
    SurfNotFoundError,
    SurfRateLimitError,
    SurfScopeError,
)

__version__ = "0.2.0"
__all__ = [
    "SurfClient",
    "SurfAPIError",
    "SurfAuthError",
    "SurfNotFoundError",
    "SurfRateLimitError",
    "SurfScopeError",
]

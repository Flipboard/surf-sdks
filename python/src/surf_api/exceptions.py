"""Surf API exceptions."""


class SurfAPIError(Exception):
    """Base exception for Surf API errors."""

    def __init__(self, message, status_code=None, error_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response = response


class SurfAuthError(SurfAPIError):
    """401 Unauthorized — invalid or missing API token."""
    pass


class SurfScopeError(SurfAPIError):
    """403 Forbidden — token lacks required scope."""
    pass


class SurfNotFoundError(SurfAPIError):
    """404 Not Found."""
    pass


class SurfRateLimitError(SurfAPIError):
    """429 Too Many Requests — rate limit exceeded."""

    def __init__(self, message, retry_after=None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

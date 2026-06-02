"""
Surf Python SDK integration test configuration.

Set environment variables:
    SURF_API_TEST_TOKEN=surf_sk_live_...  (required)
    SURF_API_BASE_URL=https://api.surf.social  (optional — SDK adds /v1 internally)

Run:
    cd python
    pip install -e .
    pytest tests/ -v
"""

import os
import sys
import pytest

# Ensure the SDK source is importable without pip install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope="session")
def client():
    """Create a SurfClient for integration tests, skip if no token."""
    token = os.environ.get("SURF_API_TEST_TOKEN", "")
    if not token:
        pytest.skip("SURF_API_TEST_TOKEN not set")

    from surf_api import SurfClient

    base_url = os.environ.get("SURF_API_BASE_URL", "")
    if base_url:
        # SDK adds /v1 internally, strip if present
        base_url = base_url.rstrip("/").removesuffix("/v1")
        return SurfClient(token, base_url=base_url)
    return SurfClient(token)

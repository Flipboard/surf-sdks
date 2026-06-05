"""Unit tests for SurfAgent -- no API calls, no claude-agent-sdk required."""

import pytest


def test_surf_agent_importable():
    """SurfAgent can be imported without claude-agent-sdk installed."""
    from surf_api import SurfAgent
    assert SurfAgent is not None


def test_surf_agent_importable_from_module():
    """SurfAgent can be imported directly from surf_api.agent."""
    from surf_api.agent import SurfAgent
    assert SurfAgent is not None


def test_surf_agent_instantiates():
    """SurfAgent can be instantiated with just an API key."""
    from surf_api.agent import SurfAgent
    agent = SurfAgent(surf_api_key="test_key")
    assert agent.surf_api_key == "test_key"
    assert agent.model == "claude-sonnet-4-6"
    assert agent.allow_writes is False


def test_surf_agent_default_read_only():
    """By default, only read tools are allowed."""
    from surf_api.agent import SurfAgent
    agent = SurfAgent(surf_api_key="test")
    tools = agent._get_allowed_tools()
    assert "mcp__surf__search_surf_feeds" in tools
    assert "mcp__surf__summarize_feed" in tools
    assert "mcp__surf__create_post" not in tools
    assert "mcp__surf__save_custom_feed" not in tools
    assert "mcp__surf__favourite_post" not in tools


def test_surf_agent_allow_writes():
    """With allow_writes=True, write tools are included."""
    from surf_api.agent import SurfAgent
    agent = SurfAgent(surf_api_key="test", allow_writes=True)
    tools = agent._get_allowed_tools()
    assert "mcp__surf__search_surf_feeds" in tools
    assert "mcp__surf__create_post" in tools
    assert "mcp__surf__save_custom_feed" in tools
    assert "mcp__surf__favourite_post" in tools
    assert "mcp__surf__set_feed_theme" in tools


def test_surf_agent_run_raises_without_sdk():
    """run() raises ImportError with helpful message when claude-agent-sdk is missing."""
    import sys
    from unittest.mock import patch
    from surf_api.agent import SurfAgent
    agent = SurfAgent(surf_api_key="test")
    # Temporarily hide claude_agent_sdk so the lazy import fails
    with patch.dict(sys.modules, {"claude_agent_sdk": None}):
        with pytest.raises(ImportError, match="claude-agent-sdk"):
            import asyncio
            asyncio.run(agent.run("test"))

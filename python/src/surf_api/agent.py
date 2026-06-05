"""SurfAgent -- AI agent with Surf tools pre-loaded via MCP.

Wraps the Claude Agent SDK with the Surf MCP server connected, giving
developers a batteries-included agent that can search feeds, discover
content, create custom feeds, and interact with the social web using
natural language.

Requires the ``claude-agent-sdk`` package::

    pip install claude-agent-sdk

Example::

    from surf_api.agent import SurfAgent

    agent = SurfAgent(surf_api_key="surf_sk_live_...")

    # One-shot query
    result = await agent.run(
        "Find the top AI feeds on Surf and summarize the latest posts"
    )
    print(result)

    # With budget control
    result = await agent.run(
        "Create a custom feed about climate technology",
        max_turns=10,
        max_budget_usd=0.50,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

MCP_SERVER_URL = "https://mcp.surf.social/mcp"

SYSTEM_PROMPT = """\
You are a helpful assistant with access to the Surf social platform via MCP tools.
Surf aggregates content from Mastodon, Bluesky, and RSS into unified feeds.

Search & Discovery:
- search_surf_feeds: Search for feeds by topic or keyword
- search_posts: Search individual posts across all platforms
- search_accounts: Search accounts across Mastodon and Bluesky
- search_bluesky_users: Search Bluesky users specifically
- search_podcasts: Search podcast feeds
- get_feed_posts: Get posts from any feed
- get_feed_details: Get metadata about a feed
- get_trending_feeds: Discover trending feeds
- get_account: Look up a user profile by handle

AI & Analysis:
- summarize_feed: Get an AI summary of a feed
- ask_about_content: Ask questions about content
- ask_surf: Semantic search via NLWeb

Content & Media:
- resolve_url: Resolve shortened URLs to their destination
- extract_article: Extract article text from a URL
- get_image_info: Get image dimensions and size variants
- text_to_speech: Convert text to speech audio

Create & Manage (authenticated):
- build_custom_feed: Compose a custom feed from sources
- save_custom_feed: Save a custom feed to the user's account
- create_post: Publish a post -- ALWAYS confirm with the user first
- favourite_post: Favourite/like a post
- set_feed_theme: Set visual theme on a custom feed

When searching, use specific terms. When creating feeds, suggest diverse sources.
When summarizing content, be concise and highlight key themes.
Never post without explicit user approval.
"""


@dataclass
class SurfAgentResult:
    """Result from a SurfAgent run."""
    text: str
    messages: list
    turns: int
    stop_reason: str | None = None


@dataclass
class SurfAgent:
    """AI agent with Surf MCP tools pre-loaded.

    Args:
        surf_api_key: Surf API token (``surf_sk_live_...``). Passed as a
            header to the MCP server for authenticated operations like
            saving custom feeds.
        model: Claude model to use. Defaults to ``claude-sonnet-4-6``.
        system_prompt: Custom system prompt. Defaults to a Surf-aware prompt.
        mcp_server_url: Surf MCP server URL. Defaults to production.
        max_turns: Default max agent turns per run. Can be overridden per call.
        max_budget_usd: Default max spend per run. Can be overridden per call.
    """
    surf_api_key: str
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    mcp_server_url: str = MCP_SERVER_URL
    max_turns: int | None = None
    max_budget_usd: float | None = None

    async def run(
        self,
        prompt: str,
        *,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
    ) -> SurfAgentResult:
        """Run a one-shot agent query.

        The agent connects to Surf via MCP and can use any of the 8 Surf
        tools to fulfill the request. All Claude compute runs on your
        Agent SDK credit.

        Args:
            prompt: Natural language instruction for the agent.
            max_turns: Max agent loop iterations (overrides instance default).
            max_budget_usd: Max spend in USD (overrides instance default).

        Returns:
            SurfAgentResult with the agent's text response, full message
            history, turn count, and stop reason.
        """
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "SurfAgent requires the claude-agent-sdk package. "
                "Install it with: pip install claude-agent-sdk"
            )

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=self.system_prompt,
            max_turns=max_turns if max_turns is not None else self.max_turns,
            max_budget_usd=max_budget_usd if max_budget_usd is not None else self.max_budget_usd,
            mcp_servers={
                "surf": {
                    "type": "http",
                    "url": self.mcp_server_url,
                    "headers": {
                        "X-API-Key": self.surf_api_key,
                    },
                },
            },
            permission_mode="auto",
            allowed_tools=["mcp__surf__*"],
        )

        messages = []
        text_parts = []
        turns = 0
        stop_reason = None

        async for message in query(prompt=prompt, options=options):
            messages.append(message)
            msg_type = getattr(message, 'type', None)

            if msg_type == 'assistant':
                content = getattr(message, 'content', None)
                if isinstance(content, list):
                    for block in content:
                        if getattr(block, 'type', None) == 'text':
                            text_parts.append(block.text)
                elif isinstance(content, str):
                    text_parts.append(content)
                turns += 1

            if msg_type == 'result':
                stop_reason = getattr(message, 'stop_reason', None)

        return SurfAgentResult(
            text="\n".join(text_parts),
            messages=messages,
            turns=turns,
            stop_reason=stop_reason,
        )

    async def stream(
        self,
        prompt: str,
        *,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
    ) -> AsyncIterator:
        """Stream agent messages as they arrive.

        Yields raw Message objects from the Agent SDK. Useful for
        building interactive UIs or processing tool calls as they happen.

        Args:
            prompt: Natural language instruction for the agent.
            max_turns: Max agent loop iterations.
            max_budget_usd: Max spend in USD.

        Yields:
            Message objects from the Claude Agent SDK.
        """
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions
        except ImportError:
            raise ImportError(
                "SurfAgent requires the claude-agent-sdk package. "
                "Install it with: pip install claude-agent-sdk"
            )

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=self.system_prompt,
            max_turns=max_turns if max_turns is not None else self.max_turns,
            max_budget_usd=max_budget_usd if max_budget_usd is not None else self.max_budget_usd,
            mcp_servers={
                "surf": {
                    "type": "http",
                    "url": self.mcp_server_url,
                    "headers": {
                        "X-API-Key": self.surf_api_key,
                    },
                },
            },
            permission_mode="auto",
            allowed_tools=["mcp__surf__*"],
        )

        async for message in query(prompt=prompt, options=options):
            yield message

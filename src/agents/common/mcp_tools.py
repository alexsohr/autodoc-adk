from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)


async def create_filesystem_toolset(
    repo_path: str,
) -> tuple[McpToolset, AsyncExitStack]:
    """Create filesystem MCP tools scoped to a repository directory.

    Uses ``@modelcontextprotocol/server-filesystem`` via ``npx`` to provide
    read-only filesystem access to the cloned repository.

    Args:
        repo_path: Absolute path to the cloned repository directory.

    Returns:
        Tuple of ``(toolset, exit_stack)`` where *toolset* is an
        :class:`McpToolset` instance that can be passed directly to an
        :class:`LlmAgent`'s ``tools`` list, and *exit_stack* must be closed
        by the caller via ``await exit_stack.aclose()`` when the agent is
        done using the tools.
    """
    exit_stack = AsyncExitStack()

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", repo_path],
            ),
        ),
    )

    # Register the toolset's close method so the MCP server subprocess is
    # cleaned up when the exit stack is closed.
    exit_stack.push_async_callback(toolset.close)

    logger.info("Created filesystem MCP toolset scoped to %s", repo_path)
    return toolset, exit_stack

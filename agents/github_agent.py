import sys
import logging
from typing import Optional
from pathlib import Path

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path when executed directly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from config.settings import settings
from core.llm import get_llm
from mcp_servers.github_mcp import get_github_tools

logger = logging.getLogger(__name__)

GITHUB_SYSTEM_PROMPT = """You are an expert GitHub Sub-Agent powered by the Model Context Protocol (MCP).
Your mission is to answer ANY GitHub-related questions, discover all relevant information about repositories requested in chat, and perform GitHub actions.

YOUR CAPABILITIES & MCP TOOLS:
1. 'github_search_repositories': Find repositories by name, topic, or keyword.
2. 'github_get_repository': Retrieve comprehensive metadata (stars, forks, open issues, language, license, branch).
3. 'github_list_issues': Inspect active bugs, feature requests, and discussions.
4. 'github_list_pull_requests': Review code contributions and active PRs.
5. 'github_get_file_contents': Inspect README files, source code, config files, or directory trees.
6. 'github_list_commits': Trace commit history, recent authors, and changelogs.
7. 'github_create_issue': Open new issues for bug reports or feature requests.

GUIDELINES:
- When a user asks about a repository (e.g. 'tell me about langchain-ai/langgraph'), first retrieve its metadata and README or recent issues to provide a complete, informative answer.
- Always provide clear formatting with bullet points and code blocks where appropriate.
"""

def create_github_agent(llm=None):
    """
    Builds the LangGraph ReAct agent for GitHub MCP operations.
    """
    agent_llm = llm or get_llm(temperature=0.1)
    tools = get_github_tools()
    return create_react_agent(agent_llm, tools=tools, prompt=GITHUB_SYSTEM_PROMPT)


if __name__ == "__main__":
    print("=" * 70)
    print("🐙 GitHub MCP Sub-Agent — Autonomous Repository Intelligence")
    print("=" * 70)

    query = sys.argv[1] if len(sys.argv) > 1 else "Find information about the repository langchain-ai/langgraph"
    print(f"\n[1] Running GitHub Sub-Agent query: '{query}'")
    agent = create_github_agent()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    answer = result["messages"][-1].content
    print("\n🤖 GitHub Agent Answer:\n")
    print(answer)
    print("\n" + "=" * 70)
    print("✅ GitHub MCP Sub-Agent Completed Successfully!")
    print("=" * 70)

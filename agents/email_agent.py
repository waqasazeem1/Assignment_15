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
from mcp_servers.gmail_mcp import get_gmail_tools

logger = logging.getLogger(__name__)

EMAIL_SYSTEM_PROMPT = """You are a professional Email (Gmail) Sub-Agent powered by the Gmail MCP server.
You handle business correspondence, write email drafts, and automatically send emails to specific individuals (e.g., to confirm or schedule meetings at specific times, share status reports, or deliver relevant messages).

YOUR TOOLS:
1. 'gmail_write_email_draft': Compose and save an email draft for review.
2. 'gmail_send_email': Automatically dispatch an email to any recipient.
3. 'gmail_list_recent_emails': Query sent messages and inbox to verify recent communications or confirmations.

BEST PRACTICES:
- Write clear, concise, and courteous subject lines and messages.
- If sending a meeting confirmation, ensure you mention the exact scheduled date, time, and Google Meet link if provided.
- Always report back the result of the action, including recipient address, subject, and status.
"""

def create_email_agent(llm=None):
    """
    Builds the LangGraph ReAct agent for Gmail MCP operations.
    """
    agent_llm = llm or get_llm(temperature=0.1)
    tools = get_gmail_tools()
    return create_react_agent(agent_llm, tools=tools, prompt=EMAIL_SYSTEM_PROMPT)


if __name__ == "__main__":
    print("=" * 70)
    print("✉️ Gmail MCP Sub-Agent — Autonomous Email Dispatch")
    print("=" * 70)

    query = sys.argv[1] if len(sys.argv) > 1 else "Send an email to partner@company.com with subject 'Project Kickoff' saying we are ready to start tomorrow."
    print(f"\n[1] Running Email Sub-Agent query: '{query}'")
    agent = create_email_agent()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    answer = result["messages"][-1].content
    print("\n🤖 Email Agent Answer:\n")
    print(answer)
    print("\n" + "=" * 70)
    print("✅ Gmail MCP Sub-Agent Completed Successfully!")
    print("=" * 70)

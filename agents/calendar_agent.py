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
from mcp_servers.calendar_mcp import get_calendar_tools

logger = logging.getLogger(__name__)

CALENDAR_SYSTEM_PROMPT = """You are a dedicated Google Calendar Sub-Agent powered by the Google Calendar MCP server.
You specialize in managing events, reading upcoming and past meetings, checking availability, and scheduling Google Meet conferences.

YOUR TOOLS:
1. 'calendar_list_meetings': Read upcoming/past meetings, their scheduled start/end times, attendees, and Google Meet video links.
2. 'calendar_check_availability': Query free/busy status for specific time windows to detect scheduling conflicts.
3. 'calendar_create_meeting': Schedule new meetings with title, ISO 8601 start/end timestamps, attendees, description, and automatic Google Meet video links.

BEST PRACTICES:
- Before scheduling any new meeting, ALWAYS check availability using 'calendar_check_availability' to prevent double booking.
- When listing meetings, always explicitly highlight the Google Meet link, attendee emails, and scheduled time.
- If dates are specified relatively (e.g. 'tomorrow at 2 PM', 'next Monday'), resolve them into standard ISO 8601 UTC strings.
"""

def create_calendar_agent(llm=None):
    """
    Builds the LangGraph ReAct agent for Google Calendar MCP operations.
    """
    agent_llm = llm or get_llm(temperature=0.1)
    tools = get_calendar_tools()
    return create_react_agent(agent_llm, tools=tools, prompt=CALENDAR_SYSTEM_PROMPT)


if __name__ == "__main__":
    print("=" * 70)
    print("📅 Google Calendar MCP Sub-Agent — Automated Meeting Scheduling")
    print("=" * 70)

    query = sys.argv[1] if len(sys.argv) > 1 else "List my upcoming Google Calendar meetings and show the Google Meet links"
    print(f"\n[1] Running Calendar Sub-Agent query: '{query}'")
    agent = create_calendar_agent()
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    answer = result["messages"][-1].content
    print("\n🤖 Calendar Agent Answer:\n")
    print(answer)
    print("\n" + "=" * 70)
    print("✅ Google Calendar MCP Sub-Agent Completed Successfully!")
    print("=" * 70)

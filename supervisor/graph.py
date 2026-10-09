import logging
import re
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from config.settings import settings
from core.state import AgentState, SubAgentType
from core.llm import get_llm
from agents.rag_agent import create_rag_agent
from agents.github_agent import create_github_agent
from agents.calendar_agent import create_calendar_agent
from agents.email_agent import create_email_agent

logger = logging.getLogger(__name__)

class SupervisorDecision(BaseModel):
    """Structured routing classification returned by the Supervisor."""
    next_agent: Literal["rag_agent", "github_agent", "calendar_agent", "email_agent", "FINISH"] = Field(
        description="The target sub-agent best suited to resolve the user request."
    )
    reasoning: str = Field(description="Short rationale explaining the routing decision.")


SUPERVISOR_PROMPT = """You are the Lead Supervisor in a LangGraph Multi-Agent Architecture.
Your role is to classify the user's intent and route the request to EXACTLY ONE of four specialized sub-agents:

1. 'rag_agent':
   - Questions about uploaded PDF documents, manuals, whitepapers, benchmarks, technical specs, or documents.
   - Example: "What does the PDF say about benchmark scores?", "Summarize the technical specs in the document."

2. 'github_agent':
   - Inquiries about GitHub repositories, finding open source code, repo stars/forks, issues, PRs, file contents, commits, or creating GitHub issues.
   - Example: "Search repos for langgraph", "How many stars does langchain-ai/langgraph have?", "List open issues in repo X."

3. 'calendar_agent':
   - Checking calendar availability (free/busy), reading upcoming/past meetings, checking Google Meet links, or scheduling a new meeting.
   - Example: "Do I have any meetings today?", "Check my availability for tomorrow 2 PM", "Schedule a meeting with Alex on Friday."

4. 'email_agent':
   - Writing email drafts, composing messages, or automatically sending an email to a specific person (e.g. to confirm/schedule a meeting or deliver notes).
   - Example: "Send an email to sarah@company.com confirming our meeting", "Draft an email to client@example.com."

5. 'FINISH':
   - Direct greetings, pleasantries, or general system help requests where no sub-agent action is necessary.
   - Example: "Hello", "What agents do you have?", "Help me understand your capabilities."

Analyze the latest user message and choose the single most appropriate destination.
"""


def _heuristic_classify(user_text: str) -> str:
    """
    High-accuracy intent classifier fallback for offline or zero-API-key testing.
    """
    text = (user_text or "").strip().lower()
    if not text:
        return "FINISH"

    # Greetings / Help / Capabilities
    if any(k in text for k in ["hi", "hello", "hey", "help", "who are you", "what can you do", "assalam", "salam", "kya kar"]):
        return "FINISH"

    # Meeting Scheduling & Calendar intent takes precedence if fixing/scheduling a meeting
    is_meeting = any(k in text for k in ["meeting", "calendar", "calender", "clender", "appointment", "meet"])
    is_scheduling = any(k in text for k in ["fix", "schedule", "create", "set", "book", "rakh", "rakho", "availability", "free/busy", "free or busy", "check"])
    if is_meeting and is_scheduling:
        return "calendar_agent"

    # Direct email action commands take precedence if explicitly asking to send/draft email
    if any(k in text for k in ["send an email", "send email", "draft an email", "draft email", "write an email", "write email", "send a mail", "send mail", "bhej do email", "email send"]):
        return "email_agent"

    # Calendar general intent
    if is_meeting:
        return "calendar_agent"

    # GitHub intent (keywords, profile, avatar, or direct username handles)
    if any(k in text for k in ["github", "repo", "repository", "pull request", "pr", "commit", "fork", "issue", "branch", "username", "avatar", "picture", "octocat"]):
        return "github_agent"

    # Single handle or username like '@waqasazeem1' or 'waqasazeem1'
    clean_text = text.lstrip("@").strip()
    if re.match(r"^[a-zA-Z0-9_\-]{3,39}$", clean_text) and not any(w in clean_text for w in ["email", "test", "demo", "none"]):
        return "github_agent"

    # RAG / PDF intent (documents, files, briefings, summaries)
    words = set(re.findall(r"\w+", text))
    if any(k in text for k in ["pdf", "document", "documents", "paper", "spec", "benchmark", "elena rostova", "apollo", "summary", "khulasa", "point", "brief", "parh", "kisan"]) or any(w in words for w in ["file", "doc", "context"]):
        return "rag_agent"

    # Email intent
    if any(k in text for k in ["email", "mail", "gmail", "draft", "inbox", "sent folder", "send message", "khat", "bhej"]):
        return "email_agent"

    # Default to supervisor direct guidance
    return "FINISH"


# Initialize lazy-loaded sub-agents
_rag_agent_instance = None
_github_agent_instance = None
_calendar_agent_instance = None
_email_agent_instance = None

def get_rag_subagent():
    global _rag_agent_instance
    if _rag_agent_instance is None:
        _rag_agent_instance = create_rag_agent()
    return _rag_agent_instance

def get_github_subagent():
    global _github_agent_instance
    if _github_agent_instance is None:
        _github_agent_instance = create_github_agent()
    return _github_agent_instance

def get_calendar_subagent():
    global _calendar_agent_instance
    if _calendar_agent_instance is None:
        _calendar_agent_instance = create_calendar_agent()
    return _calendar_agent_instance

def get_email_subagent():
    global _email_agent_instance
    if _email_agent_instance is None:
        _email_agent_instance = create_email_agent()
    return _email_agent_instance


# ----------------------------------------------------
# Graph Nodes
# ----------------------------------------------------

def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    Supervisor router node that inspects chat history and decides the next agent.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"next_agent": "FINISH"}

    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or (isinstance(msg, BaseMessage) and getattr(msg, 'type', '') == 'human'):
            last_user_msg = str(msg.content)
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Attempt structured LLM classification if API key is configured
    decision = None
    api_key = settings.OPENAI_API_KEY
    if api_key and not api_key.startswith("your_") and api_key != "sk-placeholder-multi-agent-system":
        try:
            llm = get_llm(temperature=0.0)
            structured_llm = llm.with_structured_output(SupervisorDecision)
            prompt_msgs = [
                SystemMessage(content=SUPERVISOR_PROMPT),
                HumanMessage(content=f"User Request: {last_user_msg}")
            ]
            decision = structured_llm.invoke(prompt_msgs)
        except Exception as e:
            logger.warning(f"Structured supervisor routing failed: {e}. Using heuristic classifier.")

    if not decision:
        chosen = _heuristic_classify(last_user_msg)
        decision = SupervisorDecision(
            next_agent=chosen,
            reasoning=f"Heuristic classification based on keyword matching for: '{last_user_msg[:60]}'"
        )

    logger.info(f"Supervisor routed request to: {decision.next_agent} (Reason: {decision.reasoning})")
    return {
        "next_agent": decision.next_agent,
        "context": {"routing_reason": decision.reasoning, "selected_agent": decision.next_agent}
    }


def rag_node(state: AgentState) -> Dict[str, Any]:
    """Invokes the RAG Sub-Agent to retrieve PDF context and answer strictly."""
    agent = get_rag_subagent()
    res = agent.invoke({"messages": state["messages"]})
    last_msg = res["messages"][-1]
    formatted_msg = AIMessage(
        content=f"[RAG Sub-Agent]\n\n{last_msg.content}",
        name="rag_agent"
    )
    return {
        "messages": [formatted_msg],
        "active_agent": "rag_agent"
    }


def github_node(state: AgentState) -> Dict[str, Any]:
    """Invokes the GitHub MCP Sub-Agent for repository searches, issues, and code."""
    agent = get_github_subagent()
    res = agent.invoke({"messages": state["messages"]})
    last_msg = res["messages"][-1]
    formatted_msg = AIMessage(
        content=f"[GitHub MCP Sub-Agent]\n\n{last_msg.content}",
        name="github_agent"
    )
    return {
        "messages": [formatted_msg],
        "active_agent": "github_agent"
    }


def calendar_node(state: AgentState) -> Dict[str, Any]:
    """Invokes the Google Calendar MCP Sub-Agent for scheduling, Meet links, and availability."""
    agent = get_calendar_subagent()
    res = agent.invoke({"messages": state["messages"]})
    last_msg = res["messages"][-1]
    formatted_msg = AIMessage(
        content=f"[Google Calendar MCP Sub-Agent]\n\n{last_msg.content}",
        name="calendar_agent"
    )
    return {
        "messages": [formatted_msg],
        "active_agent": "calendar_agent"
    }


def email_node(state: AgentState) -> Dict[str, Any]:
    """Invokes the Gmail MCP Sub-Agent for drafting, confirming, and sending emails."""
    agent = get_email_subagent()
    res = agent.invoke({"messages": state["messages"]})
    last_msg = res["messages"][-1]
    formatted_msg = AIMessage(
        content=f"[Gmail MCP Sub-Agent]\n\n{last_msg.content}",
        name="email_agent"
    )
    return {
        "messages": [formatted_msg],
        "active_agent": "email_agent"
    }


def direct_reply_node(state: AgentState) -> Dict[str, Any]:
    """Supervisor directly answers general greetings, system inquiries, and routing summaries."""
    reply = (
        "Hello! I am the Central Multi-Agent Supervisor.\n\n"
        "I coordinate 4 specialized sub-agents:\n"
        "1. **RAG Sub-Agent**: Answers queries strictly using retrieved PDF documents.\n"
        "2. **GitHub MCP Sub-Agent**: Discovers repo metadata, issues, PRs, code files, and commits.\n"
        "3. **Google Calendar MCP Sub-Agent**: Checks availability, lists meetings with Google Meet links, and schedules events.\n"
        "4. **Gmail MCP Sub-Agent**: Composes drafts and sends automated emails (e.g. meeting confirmations).\n\n"
        "How can I assist you today?"
    )
    return {
        "messages": [AIMessage(content=reply, name="supervisor")],
        "active_agent": "supervisor"
    }


def route_supervisor(state: AgentState) -> str:
    """Conditional edge router reading next_agent from supervisor_node."""
    next_dest = state.get("next_agent", "FINISH")
    if next_dest == "rag_agent":
        return "rag_node"
    elif next_dest == "github_agent":
        return "github_node"
    elif next_dest == "calendar_agent":
        return "calendar_node"
    elif next_dest == "email_agent":
        return "email_node"
    else:
        return "direct_reply_node"


# ----------------------------------------------------
# Build the LangGraph StateGraph
# ----------------------------------------------------

def build_multi_agent_graph():
    """
    Constructs and compiles the complete LangGraph StateGraph:
    START -> supervisor -> [sub_agent_node] -> END
    """
    builder = StateGraph(AgentState)

    # Register Nodes
    builder.add_node("supervisor_node", supervisor_node)
    builder.add_node("rag_node", rag_node)
    builder.add_node("github_node", github_node)
    builder.add_node("calendar_node", calendar_node)
    builder.add_node("email_node", email_node)
    builder.add_node("direct_reply_node", direct_reply_node)

    # Add Edges
    builder.add_edge(START, "supervisor_node")

    builder.add_conditional_edges(
        "supervisor_node",
        route_supervisor,
        {
            "rag_node": "rag_node",
            "github_node": "github_node",
            "calendar_node": "calendar_node",
            "email_node": "email_node",
            "direct_reply_node": "direct_reply_node",
        }
    )

    # Every sub-agent returns its result back to the user / completes the turn
    builder.add_edge("rag_node", END)
    builder.add_edge("github_node", END)
    builder.add_edge("calendar_node", END)
    builder.add_edge("email_node", END)
    builder.add_edge("direct_reply_node", END)

    return builder.compile()

# Global compiled graph
supervisor_graph = build_multi_agent_graph()

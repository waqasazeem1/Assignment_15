from typing import Annotated, Optional, Literal, Dict, Any, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Allowed sub-agent targets
SubAgentType = Literal["rag_agent", "github_agent", "calendar_agent", "email_agent", "FINISH"]

class AgentState(TypedDict):
    """
    Unified multi-agent system state passed through the LangGraph StateGraph.
    """
    # Append-only message history
    messages: Annotated[List[BaseMessage], add_messages]
    # Routing decision made by supervisor
    next_agent: Optional[SubAgentType]
    # Sub-agent currently or previously executing
    active_agent: Optional[str]
    # Shared contextual dictionary (e.g., loaded documents, cached tool outputs)
    context: Optional[Dict[str, Any]]

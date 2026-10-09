import os
import re
import uuid
import logging
from typing import Optional, List, Any, Dict
from pydantic import Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from config.settings import settings

logger = logging.getLogger(__name__)

class DeterministicMockEmbeddings(Embeddings):
    """
    Fallback deterministic bag-of-words embeddings generator for offline/local testing.
    """
    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    def _embed(self, text: str) -> List[float]:
        import hashlib
        vec = [0.0] * self.dimension
        if not text:
            return vec
        tokens = text.lower().split()
        for token in tokens:
            clean_token = "".join(c for c in token if c.isalnum())
            if clean_token:
                h = int(hashlib.sha256(clean_token.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dimension
                vec[idx] += 1.0
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


class OfflineToolCallingLLM(BaseChatModel):
    """
    Intelligent simulated LLM for offline testing and zero-API-key demonstration.
    Automatically inspects available tools and generates appropriate tool calls and responses.
    """
    bound_tools: List[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "offline_mock_llm"

    def bind_tools(self, tools: List[Any], **kwargs) -> "OfflineToolCallingLLM":
        # Create a copy with tools bound
        model_copy = OfflineToolCallingLLM(bound_tools=list(tools))
        return model_copy

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kwargs) -> ChatResult:
        last = messages[-1]

        # Case 1: Processing after a Tool execution
        if isinstance(last, ToolMessage) or (hasattr(last, 'type') and last.type == 'tool'):
            tool_content = str(last.content)
            # Synthesize answer from the tool output
            synthesized = (
                f"Based on the tool output:\n\n"
                f"{tool_content}\n\n"
                f"The requested action has been completed successfully."
            )
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=synthesized))])

        # Case 2: User input turn -> determine which tool to call
        user_text = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage) or getattr(m, 'type', '') == 'human':
                user_text = str(m.content)
                break
        
        tool_names = [getattr(t, 'name', '') for t in self.bound_tools]
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # 1. RAG tool
        if any("pdf" in n for n in tool_names):
            if "get_pdf_summary_and_key_points" in tool_names and any(k in user_text.lower() for k in ["summar", "key point", "important", "overview", "point", "kya hai", "points", "extract"]):
                pdf_match = re.search(r"([\w\-_\.\\]+\.pdf)", user_text, re.IGNORECASE)
                f_path = pdf_match.group(1) if pdf_match else None
                tc = {
                    "name": "get_pdf_summary_and_key_points",
                    "args": {"file_path": f_path} if f_path else {},
                    "id": call_id
                }
            else:
                tc = {
                    "name": "search_pdf_knowledge",
                    "args": {"query": user_text},
                    "id": call_id
                }
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[tc]))])

        # 2. GitHub tools
        if any("github" in n for n in tool_names):
            repo_match = re.search(r"([\w\-]+)/([\w\-]+)", user_text)
            if repo_match and "github_get_repository" in tool_names and not any(k in user_text.lower() for k in ["user", "username", "profile", "picture", "avatar"]):
                owner, repo = repo_match.groups()
                tc = {
                    "name": "github_get_repository",
                    "args": {"owner": owner, "repo": repo},
                    "id": call_id
                }
            elif "github_get_user_profile" in tool_names:
                user_match = re.search(r"(?:username|user|profile|account|of|for|handle|id)\s*[:=]?\s*([@\w\-]+)", user_text, re.IGNORECASE)
                if user_match:
                    uname = user_match.group(1).lstrip("@")
                else:
                    ignore = {"github", "show", "find", "tell", "me", "about", "give", "info", "picture", "repo", "repository", "ki", "ka", "b", "kisi", "dy", "bta", "hai", "information", "important", "wali", "kary", "krwae", "kren", "karo", "check", "please", "search", "get", "username", "profile"}
                    tokens = [w.strip("@.,?!:;\"'") for w in user_text.split() if w.lower().strip("@.,?!:;\"'") not in ignore and len(w) >= 2]
                    uname = tokens[0] if tokens else "octocat"
                tc = {
                    "name": "github_get_user_profile",
                    "args": {"username": uname},
                    "id": call_id
                }
            else:
                tc = {
                    "name": "github_search_repositories",
                    "args": {"query": user_text},
                    "id": call_id
                }
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[tc]))])

        # 3. Calendar tools
        if any("calendar" in n for n in tool_names):
            if any(k in user_text.lower() for k in ["schedule", "fix", "create", "meeting fix", "meeting rakh", "book", "new meeting"]) and "calendar_create_meeting" in tool_names:
                dates = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?", user_text)
                t_start = dates[0] if len(dates) > 0 else "2026-10-06T14:00:00Z"
                t_end = dates[1] if len(dates) > 1 else "2026-10-06T15:00:00Z"
                emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", user_text)
                tc = {
                    "name": "calendar_create_meeting",
                    "args": {
                        "summary": "Project Sync & Strategy Meeting",
                        "start_time": t_start,
                        "end_time": t_end,
                        "attendees": emails if emails else ["partner@example.com"],
                        "description": "Discussion and sync scheduled via Multi-Agent System",
                        "create_meet_link": True
                    },
                    "id": call_id
                }
            elif "availability" in user_text.lower() and "calendar_check_availability" in tool_names:
                dates = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?", user_text)
                t_min = dates[0] if len(dates) > 0 else "2026-10-06T14:00:00Z"
                t_max = dates[1] if len(dates) > 1 else "2026-10-06T15:00:00Z"
                tc = {
                    "name": "calendar_check_availability",
                    "args": {"time_min": t_min, "time_max": t_max},
                    "id": call_id
                }
            else:
                tc = {
                    "name": "calendar_list_meetings",
                    "args": {"max_results": 5},
                    "id": call_id
                }
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[tc]))])

        # 4. Gmail tools
        if any("gmail" in n for n in tool_names):
            emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", user_text)
            to_addr = emails[0] if emails else "recipient@example.com"
            body_msg = user_text
            quotes = re.findall(r'["\']([^"\']+)["\']', user_text)
            if quotes:
                body_msg = quotes[0]
            elif ":" in user_text:
                body_msg = user_text.split(":", 1)[1].strip()
            elif "saying" in user_text.lower():
                body_msg = re.split(r"saying", user_text, flags=re.IGNORECASE)[1].strip()
            elif "msg" in user_text.lower() or "message" in user_text.lower():
                parts = re.split(r"msg|message", user_text, flags=re.IGNORECASE)
                if len(parts) > 1:
                    body_msg = parts[1].strip()

            if "draft" in user_text.lower() and "gmail_write_email_draft" in tool_names:
                tc = {
                    "name": "gmail_write_email_draft",
                    "args": {
                        "to": to_addr,
                        "subject": "Follow-up Notification",
                        "body": body_msg
                    },
                    "id": call_id
                }
            else:
                tc = {
                    "name": "gmail_send_email",
                    "args": {
                        "to": to_addr,
                        "subject": "Message from Multi-Agent Orchestrator",
                        "body": f"Hello,\n\n{body_msg}\n\nBest regards,\nMulti-Agent Orchestrator"
                    },
                    "id": call_id
                }
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[tc]))])

        # Default fallback answer if no tools
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"Received: {user_text}"))])


def get_llm(temperature: Optional[float] = None, model: Optional[str] = None) -> BaseChatModel:
    """
    Returns ChatOpenAI if OPENAI_API_KEY is configured, otherwise returns OfflineToolCallingLLM.
    """
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    base_url = settings.OPENAI_BASE_URL or os.getenv("OPENAI_BASE_URL")
    model_name = model or settings.OPENAI_MODEL
    temp = temperature if temperature is not None else settings.TEMPERATURE

    if api_key and not api_key.startswith("your_") and api_key != "sk-placeholder-multi-agent-system":
        kwargs = {
            "model": model_name,
            "temperature": temp,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    logger.info("Using OfflineToolCallingLLM (no valid OPENAI_API_KEY detected in .env).")
    return OfflineToolCallingLLM()


def get_embeddings() -> Embeddings:
    """
    Returns OpenAIEmbeddings if OPENAI_API_KEY is present,
    otherwise provides DeterministicMockEmbeddings.
    """
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    base_url = settings.OPENAI_BASE_URL or os.getenv("OPENAI_BASE_URL")

    if api_key and not api_key.startswith("your_") and api_key != "sk-placeholder-multi-agent-system":
        kwargs = {
            "model": settings.EMBEDDING_MODEL,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)

    return DeterministicMockEmbeddings()

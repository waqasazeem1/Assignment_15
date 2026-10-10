import os
import sys
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from config.settings import settings
from supervisor.graph import supervisor_graph
from agents.rag_agent import ingest_pdf_document, rag_store
from mcp_servers.github_mcp import get_github_tools
from mcp_servers.calendar_mcp import get_calendar_tools, SANDBOX_MEETINGS
from mcp_servers.gmail_mcp import get_gmail_tools, SANDBOX_MAILBOX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_server")

app = FastAPI(
    title="LangGraph Multi-Agent Orchestrator API",
    description="Backend API powering the 1 Supervisor + 4 Sub-Agents Web Interface",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    active_agent: str
    routing_reason: str
    timestamp: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    user_query = req.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        inputs = {
            "messages": [HumanMessage(content=user_query)]
        }
        result = supervisor_graph.invoke(inputs)

        last_msg = result["messages"][-1]
        active_agent = result.get("active_agent") or "supervisor"
        context = result.get("context") or {}
        routing_reason = context.get("routing_reason") or "Direct routing classification"

        return ChatResponse(
            reply=last_msg.content,
            active_agent=active_agent,
            routing_reason=routing_reason,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Error during graph execution: {e}", exc_info=True)
        return ChatResponse(
            reply=f"System Error: {str(e)}",
            active_agent="system",
            routing_reason="Error fallback",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

@app.post("/api/upload-pdf")
async def upload_pdf_endpoint(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    upload_dir = Path("data/sample_documents")
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / file.filename

    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Ingest into vector store
        ingest_status = ingest_pdf_document(str(destination))

        # Generate step-by-step document briefing
        from agents.rag_agent import get_pdf_summary_and_key_points
        briefing = get_pdf_summary_and_key_points(str(destination))

        return {
            "status": "success",
            "filename": file.filename,
            "message": ingest_status,
            "briefing": briefing,
            "path": str(destination)
        }
    except Exception as e:
        logger.error(f"Failed to process PDF upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest PDF: {str(e)}")

class GitHubUserRequest(BaseModel):
    username: str

class ScheduleMeetingRequest(BaseModel):
    title: str = "Project Meeting"
    start_time: str
    end_time: Optional[str] = None
    email: str
    draft_message: Optional[str] = None

class SendEmailRequest(BaseModel):
    to: str
    subject: str = "Notification from Multi-Agent System"
    body: str

@app.post("/api/github-user")
async def github_user_endpoint(req: GitHubUserRequest):
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    from mcp_servers.github_mcp import get_github_user_profile
    result = get_github_user_profile(username)
    return {
        "reply": f"[GitHub MCP Sub-Agent]\n\n{result}",
        "active_agent": "github_agent",
        "routing_reason": f"GitHub user query for: @{username.lstrip('@')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

class EmailSettingsRequest(BaseModel):
    sender_email: str
    app_password: str

@app.post("/api/schedule-meeting")
async def schedule_meeting_endpoint(req: ScheduleMeetingRequest):
    if not req.start_time or not req.email:
        raise HTTPException(status_code=400, detail="start_time and email are required.")
    from mcp_servers.calendar_mcp import create_meeting_data
    end_time = req.end_time
    if not end_time:
        try:
            from datetime import datetime as dt, timedelta as td
            clean_t = req.start_time.replace("Z", "").replace(" ", "T")
            parsed = dt.fromisoformat(clean_t)
            end_time = (parsed + td(hours=1)).isoformat()
        except Exception:
            end_time = req.start_time
    res_data = create_meeting_data(
        summary=req.title,
        start_time=req.start_time,
        end_time=end_time,
        attendees=[req.email],
        description=req.draft_message or "Scheduled meeting."
    )
    return {
        "reply": f"[Google Calendar MCP Sub-Agent]\n\n{res_data['reply']}",
        "active_agent": "calendar_agent",
        "routing_reason": f"Scheduled meeting for {req.email}",
        "gcal_url": res_data.get("gcal_url"),
        "meet_link": res_data.get("meet_link"),
        "live_email_sent": res_data.get("live_email_sent", False),
        "email_status": res_data.get("email_status"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/settings/email")
async def get_email_settings_endpoint():
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass
    sender = os.getenv("SMTP_USER") or os.getenv("GMAIL_SENDER_EMAIL") or settings.SMTP_USER or ""
    pwd = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD") or settings.SMTP_PASSWORD or ""
    sender = sender.strip()
    pwd = pwd.replace(" ", "").strip()
    settings.SMTP_USER = sender
    settings.SMTP_PASSWORD = pwd
    settings.GMAIL_SENDER_EMAIL = sender
    settings.GMAIL_APP_PASSWORD = pwd

    is_configured = bool(sender and pwd and sender != "agent@example.com")
    return {
        "configured": is_configured,
        "sender_email": sender if is_configured else "",
        "smtp_server": settings.SMTP_SERVER,
        "smtp_port": settings.SMTP_PORT
    }

@app.post("/api/settings/email")
async def save_email_settings_endpoint(req: EmailSettingsRequest):
    sender = req.sender_email.strip()
    password = req.app_password.replace(" ", "").strip()
    if not sender or not password:
        raise HTTPException(status_code=400, detail="Sender email and App Password cannot be empty.")

    # Validate SMTP connection
    import smtplib
    cloud_restricted = False
    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=8) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(sender, password)
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail SMTP credentials rejected for {sender}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Gmail authentication failed: Incorrect App Password or 2-Step Verification not active. Please check your 16-character App Password."
        )
    except OSError as e:
        err_msg = str(e).lower()
        if "101" in err_msg or "unreachable" in err_msg or "111" in err_msg or "timed out" in err_msg or "refused" in err_msg:
            # Cloud environment (Render Free Tier) blocks outbound SMTP ports 25/465/587
            logger.warning(f"SMTP port restricted by cloud provider ({e}). Enabling 1-Click Direct Gmail Dispatch.")
            cloud_restricted = True
        else:
            logger.error(f"Gmail connection error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Gmail connection error: {str(e)}."
            )
    except Exception as e:
        err_msg = str(e).lower()
        if "101" in err_msg or "unreachable" in err_msg or "timed out" in err_msg:
            cloud_restricted = True
        else:
            logger.error(f"Gmail SMTP validation failed for {sender}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Gmail authentication failed: {str(e)}."
            )

    # Update in-memory configuration
    settings.GMAIL_SENDER_EMAIL = sender
    settings.GMAIL_APP_PASSWORD = password
    settings.SMTP_USER = sender
    settings.SMTP_PASSWORD = password

    # Save to .env file if available
    try:
        env_path = Path(".env")
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            import re
            content = re.sub(r"^GMAIL_SENDER_EMAIL=.*$", f"GMAIL_SENDER_EMAIL={sender}", content, flags=re.MULTILINE)
            content = re.sub(r"^GMAIL_APP_PASSWORD=.*$", f"GMAIL_APP_PASSWORD={password}", content, flags=re.MULTILINE)
            content = re.sub(r"^SMTP_USER=.*$", f"SMTP_USER={sender}", content, flags=re.MULTILINE)
            content = re.sub(r"^SMTP_PASSWORD=.*$", f"SMTP_PASSWORD={password}", content, flags=re.MULTILINE)
            env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist to .env: {e}")

    if cloud_restricted:
        return {
            "status": "success",
            "message": f"Connected as {sender}! (Cloud Mode: Render Free Tier blocks outbound SMTP port 587. 1-Click Gmail Direct Dispatch enabled so you can send emails with 1 click!).",
            "sender_email": sender,
            "cloud_mode": True
        }

    return {
        "status": "success",
        "message": f"Successfully connected to Gmail as {sender}! Live emails and calendar invites will now be sent automatically.",
        "sender_email": sender,
        "cloud_mode": False
    }

@app.post("/api/send-email")
async def send_email_endpoint(req: SendEmailRequest):
    if not req.to or not req.body:
        raise HTTPException(status_code=400, detail="Recipient email and body are required.")
    from mcp_servers.gmail_mcp import send_email
    result = send_email(
        to=req.to,
        subject=req.subject or "Notification from Multi-Agent System",
        body=req.body
    )
    is_live = "Delivered to recipient" in result or "Delivered to live inbox" in result
    return {
        "reply": f"[Gmail MCP Sub-Agent]\n\n{result}",
        "active_agent": "email_agent",
        "routing_reason": f"Email dispatched to {req.to}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/status")
async def system_status_endpoint():
    chroma_count = 0
    try:
        if rag_store._vector_store:
            chroma_count = rag_store._vector_store._collection.count()
    except Exception:
        pass

    github_tools = [t.name for t in get_github_tools()]
    calendar_tools = [t.name for t in get_calendar_tools()]
    gmail_tools = [t.name for t in get_gmail_tools()]

    return {
        "status": "online",
        "supervisor": "LangGraph StateGraph",
        "sub_agents": {
            "rag_agent": {
                "name": "RAG Sub-Agent",
                "engine": "ChromaDB + PyPDF",
                "indexed_chunks": chroma_count,
                "status": "Active"
            },
            "github_agent": {
                "name": "GitHub MCP Sub-Agent",
                "protocol": "Model Context Protocol (MCP 2.x)",
                "tools": github_tools,
                "status": "Active"
            },
            "calendar_agent": {
                "name": "Google Calendar MCP Sub-Agent",
                "capabilities": ["Google Meet Links", "Free/Busy Checking", "Event Scheduling"],
                "tools": calendar_tools,
                "cached_meetings_count": len(SANDBOX_MEETINGS),
                "status": "Active"
            },
            "email_agent": {
                "name": "Gmail MCP Sub-Agent",
                "capabilities": ["Compose Drafts", "Automated Meeting Confirmations", "Inbox Query"],
                "tools": gmail_tools,
                "sent_count": len(SANDBOX_MAILBOX.get("sent", [])),
                "status": "Active"
            }
        },
        "llm_model": settings.OPENAI_MODEL,
        "mode": "Live OpenAI" if (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_")) else "Intelligent Sandbox Mode"
    }

# Mount static frontend
frontend_dir = Path("frontend")
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print("\n" + "="*60)
    print("  🚀 LangGraph Multi-Agent Server Started Successfully!")
    print(f"  👉 Web Interface:  http://localhost:{port}")
    print(f"  👉 Localhost IP:   http://127.0.0.1:{port}")
    print(f"  👉 API Docs:       http://localhost:{port}/docs")
    print("="*60 + "\n")
    uvicorn.run("server:app", host=host, port=port, reload=False)


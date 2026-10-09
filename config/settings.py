import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

class Settings:
    # App Information
    APP_NAME: str = "LangGraph Multi-Agent Supervisor System"
    VERSION: str = "1.0.0"

    # OpenAI / LLM Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

    # Vector Store / RAG Configuration
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"))
    DEFAULT_PDF_PATH: str = str(BASE_DIR / os.getenv("DEFAULT_PDF_PATH", "data/sample_documents/sample_agent_guide.pdf"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    RETRIEVER_K: int = int(os.getenv("RETRIEVER_K", "4"))

    # GitHub Configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", ""))
    GITHUB_MCP_SERVER_COMMAND: str = os.getenv("GITHUB_MCP_SERVER_COMMAND", "npx -y @modelcontextprotocol/server-github")
    USE_NATIVE_GITHUB_MCP: bool = os.getenv("USE_NATIVE_GITHUB_MCP", "true").lower() in ("true", "1", "yes")

    # Google Calendar & Gmail Configuration
    GOOGLE_CREDENTIALS_FILE: str = str(BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"))
    GOOGLE_TOKEN_FILE: str = str(BASE_DIR / os.getenv("GOOGLE_TOKEN_FILE", "token.json"))
    GMAIL_SENDER_EMAIL: str = os.getenv("GMAIL_SENDER_EMAIL", "agent@example.com")
    
    # SMTP Configuration (Send real emails via Gmail App Password or any SMTP provider)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", os.getenv("GMAIL_SENDER_EMAIL", ""))
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", ""))

    # Mock / Sandbox Mode for offline testing without real OAuth tokens
    MOCK_MCP_IF_UNCONFIGURED: bool = os.getenv("MOCK_MCP_IF_UNCONFIGURED", "true").lower() in ("true", "1", "yes")

settings = Settings()


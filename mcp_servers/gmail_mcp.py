import os
import json
import base64
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formatdate, make_msgid
from email import encoders
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from mcp.server.mcpserver import MCPServer
from langchain_core.tools import StructuredTool
from config.settings import settings

logger = logging.getLogger(__name__)

# Initialize MCP Server for Gmail
gmail_mcp_server = MCPServer("gmail-mcp")

# In-memory sandbox mailbox for offline / zero-setup demo
_now = datetime.now(timezone.utc)
SANDBOX_MAILBOX: Dict[str, List[Dict[str, Any]]] = {
    "sent": [
        {
            "id": "msg_001",
            "to": "client@enterprise.com",
            "subject": "Initial Project Discussion - LangGraph Architecture",
            "body": "Hi team,\n\nFollowing up on our discussion regarding multi-agent orchestrations. Looking forward to our next sync.\n\nBest,\nAgent System",
            "timestamp": (_now).isoformat(),
            "status": "SENT"
        }
    ],
    "drafts": [],
    "inbox": [
        {
            "id": "msg_in_10",
            "from": "sarah@company.com",
            "subject": "Confirming Meeting for Sprint Review",
            "body": "Hi,\nCould you confirm if you are free for our sprint review meeting on Thursday?\nThanks,\nSarah",
            "timestamp": (_now).isoformat()
        }
    ]
}

def _get_gmail_service():
    """Attempts to construct Gmail API client if credentials exist."""
    cred_file = settings.GOOGLE_CREDENTIALS_FILE
    token_file = settings.GOOGLE_TOKEN_FILE
    
    if os.path.exists(token_file) or os.path.exists(cred_file):
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            SCOPES = [
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/gmail.compose',
                'https://www.googleapis.com/auth/gmail.readonly'
            ]
            creds = None
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(cred_file):
                    flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                if creds:
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
            if creds:
                return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.warning(f"Gmail API initialization failed: {e}. Falling back to Sandbox mode.")
    return None


@gmail_mcp_server.tool()
def write_email_draft(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None
) -> str:
    """
    Compose and save an email draft to any specific person.
    Parameters:
      to: Recipient email address (e.g. 'client@example.com')
      subject: Email subject line
      body: Full email body text / message
      cc: Optional carbon-copy email address(es)
    """
    service = _get_gmail_service()
    if service:
        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            draft = service.users().drafts().create(userId='me', body={'message': {'raw': raw}}).execute()
            return f"Successfully created Gmail draft (ID: {draft.get('id')}) to {to} with subject '{subject}'."
        except Exception as e:
            logger.warning(f"Error creating live Gmail draft: {e}. Using Sandbox mode.")

    # Sandbox / In-Memory Mock Mode
    import uuid
    draft_id = f"draft_{uuid.uuid4().hex[:6]}"
    record = {
        "id": draft_id,
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "DRAFT"
    }
    SANDBOX_MAILBOX["drafts"].append(record)
    return (
        f"[Sandbox Mode] Email Draft Created Successfully!\n"
        f"- Draft ID: {draft_id}\n"
        f"- To: {to}\n"
        f"- Subject: {subject}\n"
        f"- CC: {cc or 'None'}\n"
        f"- Body Preview:\n{body}\n"
        f"(Ready to be sent or reviewed)."
    )


@gmail_mcp_server.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    ics_attachment: Optional[str] = None
) -> str:
    """
    Send an email automatically to any specific person (e.g. to confirm/schedule a meeting,
    send calendar updates, or deliver any relevant message).
    Parameters:
      to: Recipient email address (e.g. 'partner@company.com')
      subject: Email subject line (e.g. 'Meeting Confirmation: Thursday 2 PM')
      body: Email message body content
      cc: Optional CC email address(es)
      ics_attachment: Optional iCalendar (.ics) format string for meeting invitations
    """
    # 1. Attempt Live Gmail API (OAuth2)
    service = _get_gmail_service()
    if service:
        try:
            if ics_attachment:
                message = MIMEMultipart("mixed")
                message['to'] = to
                message['subject'] = subject
                if cc:
                    message['cc'] = cc
                message.attach(MIMEText(body, 'plain', 'utf-8'))
                part = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
                part.set_payload(ics_attachment.encode('utf-8'))
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
                message.attach(part)
            else:
                message = MIMEText(body)
                message['to'] = to
                message['subject'] = subject
                if cc:
                    message['cc'] = cc
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return (
                f"Successfully sent email via Gmail API!\n"
                f"- Message ID: {sent.get('id')}\n"
                f"- To: {to}\n"
                f"- Subject: {subject}\n"
                f"- Status: Delivered to live inbox."
            )
        except Exception as e:
            logger.warning(f"Failed to send email via live Gmail API: {e}. Checking SMTP fallback...")

    # 2. Attempt Live SMTP (Gmail App Password / Custom SMTP)
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass
    smtp_user = (os.getenv("SMTP_USER") or os.getenv("GMAIL_SENDER_EMAIL") or settings.SMTP_USER or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD") or settings.SMTP_PASSWORD or "").replace(" ", "").strip()
    settings.SMTP_USER = smtp_user
    settings.SMTP_PASSWORD = smtp_pass

    if smtp_user and smtp_pass and smtp_user != "agent@example.com":
        try:
            msg = MIMEMultipart("mixed")
            domain = smtp_user.split('@')[-1] if '@' in smtp_user else 'gmail.com'
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=domain)
            msg['From'] = f"Meeting Coordinator <{smtp_user}>"
            msg['To'] = to
            msg['Subject'] = subject
            msg['Reply-To'] = smtp_user
            msg['MIME-Version'] = '1.0'
            msg['X-Mailer'] = 'MultiAgent-System-1.0'
            if cc:
                msg['Cc'] = cc

            # Dual plain text and styled HTML to satisfy anti-spam filters
            alt_container = MIMEMultipart("alternative")
            alt_container.attach(MIMEText(body, 'plain', 'utf-8'))

            escaped_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b; line-height: 1.6;">
  <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
    <div style="background: #2563eb; color: #ffffff; padding: 16px 20px;">
      <h2 style="margin: 0; font-size: 18px; font-weight: 600;">{subject}</h2>
    </div>
    <div style="padding: 24px; font-size: 15px; color: #334155;">
      {escaped_body}
    </div>
    <div style="background: #f1f5f9; padding: 12px 20px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b;">
      Official notification sent via Multi-Agent System.
    </div>
  </div>
</body>
</html>"""
            alt_container.attach(MIMEText(html_body, 'html', 'utf-8'))
            msg.attach(alt_container)

            # Optional iCalendar attachment for Google Calendar automatic sync
            if ics_attachment:
                # 1. Native calendar part for RSVP cards
                cal_part = MIMEText(ics_attachment, 'calendar; method=REQUEST; charset="UTF-8"')
                cal_part.add_header('Content-Class', 'urn:content-classes:calendarmessage')
                msg.attach(cal_part)

                # 2. File attachment for legacy clients
                part = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
                part.set_payload(ics_attachment.encode('utf-8'))
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="invite.ics"')
                part.add_header('Content-Class', 'urn:content-classes:calendarmessage')
                msg.attach(part)

            recipients = [to]
            if cc:
                recipients.extend([c.strip() for c in cc.split(',') if c.strip()])

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, recipients, msg.as_string())

            logger.info(f"Email successfully delivered via SMTP to {to}")
            return (
                f"Successfully sent live email via SMTP!\n"
                f"- From: {smtp_user}\n"
                f"- To: {to}\n"
                f"- Subject: {subject}\n"
                f"- Status: 100% Delivered to recipient's real inbox."
            )
        except Exception as e:
            logger.error(f"Live SMTP email delivery failed: {e}")
            return (
                f"❌ Failed to send live email via SMTP: {str(e)}\n"
                f"Please check your Gmail address and 16-character App Password in `.env`."
            )

    # 3. Sandbox / Preview Mode (When no credentials exist yet)
    import uuid
    msg_id = f"sent_{uuid.uuid4().hex[:6]}"
    sent_record = {
        "id": msg_id,
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "SIMULATED_PREVIEW"
    }
    SANDBOX_MAILBOX["sent"].append(sent_record)

    return (
        f"[Sandbox Mode] Email Automatically Sent to Local Store!\n"
        f"- Message ID: `{msg_id}`\n"
        f"- Status: Stored in local preview memory (Not delivered to external internet inbox)\n"
        f"- To: `{to}`\n"
        f"- Subject: `{subject}`\n\n"
        f"⚠️ **Real Inbox Delivery Note:**\n"
        f"Attendee `{to}` ko real email pohanchane ke liye `.env` file mein Gmail App Password configure karein:\n"
        f"```bash\n"
        f"GMAIL_SENDER_EMAIL=your_email@gmail.com\n"
        f"GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx\n"
        f"```\n"
        f"*(Google Account > Security > 2-Step Verification > App passwords se 16-digit password banayein)*"
    )


@gmail_mcp_server.tool()
def list_recent_emails(query: Optional[str] = None, max_results: int = 5) -> str:
    """
    List recent emails from inbox or sent items to verify correspondence or confirmations.
    Parameters:
      query: Search filter query (e.g. 'meeting', 'from:sarah@company.com')
      max_results: Max items to return (default 5)
    """
    service = _get_gmail_service()
    if service:
        try:
            q = query or ""
            res = service.users().messages().list(userId='me', q=q, maxResults=max_results).execute()
            messages = res.get('messages', [])
            if not messages:
                return f"No emails found matching query '{query}'."
            lines = [f"Found {len(messages)} email(s) in Gmail:"]
            for m in messages:
                detail = service.users().messages().get(userId='me', id=m['id']).execute()
                snippet = detail.get('snippet', '')
                lines.append(f"- ID {m['id']}: {snippet}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Error querying live Gmail: {e}. Using Sandbox mode.")

    # Sandbox / In-Memory Mock Mode
    lines = [f"[Sandbox Mailbox] Sent Messages ({len(SANDBOX_MAILBOX['sent'])} items):"]
    for s in SANDBOX_MAILBOX["sent"][:max_results]:
        lines.append(
            f"- [{s['id']}] To: {s['to']} | Subject: '{s['subject']}' | Time: {s['timestamp']}\n"
            f"  Preview: {s['body'][:100]}..."
        )
    if SANDBOX_MAILBOX["inbox"]:
        lines.append(f"\n[Sandbox Mailbox] Inbox Messages ({len(SANDBOX_MAILBOX['inbox'])} items):")
        for i in SANDBOX_MAILBOX["inbox"][:max_results]:
            lines.append(
                f"- [{i['id']}] From: {i['from']} | Subject: '{i['subject']}'\n"
                f"  Preview: {i['body'][:100]}..."
            )
    return "\n".join(lines)


def get_gmail_tools() -> List[Any]:
    """
    Returns LangChain StructuredTools wrapping Gmail MCP tools.
    """
    return [
        StructuredTool.from_function(
            func=write_email_draft,
            name="gmail_write_email_draft",
            description="Write and compose an email draft to any specific recipient with subject, body text, and CC."
        ),
        StructuredTool.from_function(
            func=send_email,
            name="gmail_send_email",
            description="Send an email automatically to any specific person (e.g. to confirm/schedule a meeting at a specific time or deliver important notifications)."
        ),
        StructuredTool.from_function(
            func=list_recent_emails,
            name="gmail_list_recent_emails",
            description="List recent emails in inbox and sent folder to check sent messages and confirmations."
        ),
    ]

if __name__ == "__main__":
    print("Starting Gmail MCP Server on stdio transport...")
    gmail_mcp_server.run()

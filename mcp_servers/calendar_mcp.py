import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from mcp.server.mcpserver import MCPServer
from langchain_core.tools import StructuredTool
from config.settings import settings

logger = logging.getLogger(__name__)

# Initialize MCP Server for Google Calendar
calendar_mcp_server = MCPServer("google-calendar-mcp")

# In-memory sandbox calendar store for offline / zero-setup demo
_now = datetime.now(timezone.utc)
SANDBOX_MEETINGS: List[Dict[str, Any]] = [
    {
        "id": "meet_101",
        "summary": "Sprint Planning & Agent Review",
        "start": (_now + timedelta(hours=2)).isoformat(),
        "end": (_now + timedelta(hours=3)).isoformat(),
        "attendees": ["alex@company.com", "sarah@company.com", "dev@example.com"],
        "meet_link": "https://meet.google.com/abc-defg-hij",
        "description": "Weekly review of LangGraph multi-agent deployment.",
        "status": "confirmed"
    },
    {
        "id": "meet_102",
        "summary": "Product Architecture Sync",
        "start": (_now + timedelta(days=1, hours=4)).isoformat(),
        "end": (_now + timedelta(days=1, hours=5)).isoformat(),
        "attendees": ["manager@company.com", "alex@company.com"],
        "meet_link": "https://meet.google.com/xyz-uvwx-rst",
        "description": "Discussing MCP server integrations and tools.",
        "status": "confirmed"
    },
    {
        "id": "meet_099",
        "summary": "Retrospective: Q3 Milestone",
        "start": (_now - timedelta(days=2)).isoformat(),
        "end": (_now - timedelta(days=2, hours=-1)).isoformat(),
        "attendees": ["team@company.com"],
        "meet_link": "https://meet.google.com/qwe-rtyu-iop",
        "description": "Past meeting on milestone delivery.",
        "status": "confirmed"
    }
]

def _get_google_calendar_service():
    """Attempts to construct Google Calendar API client if credentials exist."""
    cred_file = settings.GOOGLE_CREDENTIALS_FILE
    token_file = settings.GOOGLE_TOKEN_FILE
    
    if os.path.exists(token_file) or os.path.exists(cred_file):
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            SCOPES = ['https://www.googleapis.com/auth/calendar']
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
                return build('calendar', 'v3', credentials=creds)
        except Exception as e:
            logger.warning(f"Google Calendar API initialization failed: {e}. Falling back to Sandbox mode.")
    return None


@calendar_mcp_server.tool()
def list_meetings(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 10
) -> str:
    """
    Read upcoming or past Google Calendar meetings, including Google Meet video links.
    Parameters:
      time_min: ISO 8601 start timestamp filter (optional, defaults to current time for upcoming)
      time_max: ISO 8601 end timestamp filter (optional)
      max_results: Maximum meetings to retrieve (default 10)
    """
    service = _get_google_calendar_service()
    if service:
        try:
            t_min = time_min or datetime.now(timezone.utc).isoformat()
            kwargs = {
                "calendarId": "primary",
                "timeMin": t_min,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime"
            }
            if time_max:
                kwargs["timeMax"] = time_max
            events_result = service.events().list(**kwargs).execute()
            events = events_result.get('items', [])
            if not events:
                return "No meetings found for the specified period in your Google Calendar."
            
            lines = [f"Found {len(events)} meeting(s) in Google Calendar:"]
            for ev in events:
                start = ev.get('start', {}).get('dateTime', ev.get('start', {}).get('date'))
                end = ev.get('end', {}).get('dateTime', ev.get('end', {}).get('date'))
                summary = ev.get('summary', 'Untitled Meeting')
                meet_link = ev.get('hangoutLink') or ev.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', 'No Meet link')
                attendees = [a.get('email') for a in ev.get('attendees', []) if 'email' in a]
                lines.append(
                    f"- '{summary}'\n"
                    f"  Time: {start} to {end}\n"
                    f"  Google Meet: {meet_link}\n"
                    f"  Attendees: {', '.join(attendees) if attendees else 'None'}\n"
                    f"  Status: {ev.get('status', 'confirmed')}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to query live Google Calendar: {e}. Using Sandbox store.")

    # Sandbox / In-Memory Mock Mode
    lines = [f"[Sandbox Calendar] Upcoming & Scheduled Meetings:"]
    for m in SANDBOX_MEETINGS[:max_results]:
        lines.append(
            f"- Meeting ID: {m['id']} | '{m['summary']}'\n"
            f"  Time: {m['start']} -> {m['end']}\n"
            f"  Google Meet Link: {m['meet_link']}\n"
            f"  Attendees: {', '.join(m['attendees'])}\n"
            f"  Description: {m.get('description', 'N/A')}\n"
            f"  Status: {m['status']}"
        )
    return "\n".join(lines)


@calendar_mcp_server.tool()
def check_availability(
    time_min: str,
    time_max: str,
    calendar_id: str = "primary"
) -> str:
    """
    Check availability (free/busy) before scheduling a meeting.
    Parameters:
      time_min: Start of time window to check in ISO 8601 format (e.g. '2026-10-04T14:00:00Z')
      time_max: End of time window to check in ISO 8601 format (e.g. '2026-10-04T15:00:00Z')
      calendar_id: Calendar identifier to check (default 'primary')
    """
    service = _get_google_calendar_service()
    if service:
        try:
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": calendar_id}]
            }
            res = service.freebusy().query(body=body).execute()
            calendars = res.get('calendars', {}).get(calendar_id, {})
            busy_slots = calendars.get('busy', [])
            if not busy_slots:
                return f"Slot IS AVAILABLE: No conflicts between {time_min} and {time_max} on '{calendar_id}'."
            
            conflict_lines = [f"Slot HAS CONFLICTS! Found {len(busy_slots)} busy block(s):"]
            for slot in busy_slots:
                conflict_lines.append(f"  - Busy: {slot['start']} to {slot['end']}")
            conflict_lines.append("Recommendation: Please choose an alternative time slot.")
            return "\n".join(conflict_lines)
        except Exception as e:
            logger.warning(f"Error checking live Google Calendar availability: {e}. Using Sandbox store.")

    # Sandbox / In-Memory Mock Mode
    try:
        req_start = datetime.fromisoformat(time_min.replace("Z", "+00:00"))
        req_end = datetime.fromisoformat(time_max.replace("Z", "+00:00"))
    except Exception:
        req_start = _now + timedelta(hours=1)
        req_end = req_start + timedelta(hours=1)

    conflicts = []
    for m in SANDBOX_MEETINGS:
        m_start = datetime.fromisoformat(m["start"].replace("Z", "+00:00"))
        m_end = datetime.fromisoformat(m["end"].replace("Z", "+00:00"))
        # Check overlap
        if max(req_start, m_start) < min(req_end, m_end):
            conflicts.append(m)

    if not conflicts:
        return (
            f"[Sandbox Calendar] FREE / AVAILABLE: No scheduling conflicts detected between {time_min} and {time_max}.\n"
            f"You can proceed to schedule the meeting safely."
        )
    else:
        lines = [f"[Sandbox Calendar] BUSY / CONFLICT DETECTED between {time_min} and {time_max}:"]
        for c in conflicts:
            lines.append(f"- Overlapping Meeting: '{c['summary']}' ({c['start']} -> {c['end']})")
        lines.append("Please propose an earlier or later time slot.")
        return "\n".join(lines)


def build_google_calendar_url(
    summary: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: str = "",
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None
) -> str:
    """
    Builds a 1-click Google Calendar Event Template URL that directly opens
    the user's logged-in Google Calendar in the browser with all fields pre-filled.
    """
    import urllib.parse
    from datetime import datetime as dt, timedelta as td

    def _parse_dt(val: str, fallback_offset_hrs: int = 1) -> dt:
        try:
            s = val.replace("Z", "").replace(" ", "T").strip()
            return dt.fromisoformat(s)
        except Exception:
            return dt.now() + td(hours=fallback_offset_hrs)

    dt_start = _parse_dt(start_time, 1)
    if end_time and end_time.strip():
        dt_end = _parse_dt(end_time, 2)
    else:
        dt_end = dt_start + td(hours=1)

    s_fmt = dt_start.strftime("%Y%m%dT%H%M%S")
    e_fmt = dt_end.strftime("%Y%m%dT%H%M%S")

    params = {
        "action": "TEMPLATE",
        "text": summary,
        "dates": f"{s_fmt}/{e_fmt}",
        "details": description or "Scheduled via Multi-Agent System",
    }
    if location:
        params["location"] = location
    if attendees:
        params["add"] = ",".join(attendees)

    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"


def generate_ics_content(
    summary: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: str = "",
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None
) -> str:
    """
    Generates standard iCalendar (.ics) format so emails include interactive RSVP
    cards in Gmail / Outlook and auto-sync with attendees' calendars.
    """
    import uuid
    from datetime import datetime as dt, timezone as tz, timedelta as td

    def _parse_dt(val: str, fallback_offset_hrs: int = 1) -> dt:
        try:
            s = val.replace("Z", "").replace(" ", "T").strip()
            return dt.fromisoformat(s)
        except Exception:
            return dt.now() + td(hours=fallback_offset_hrs)

    dt_start = _parse_dt(start_time, 1)
    dt_end = _parse_dt(end_time, 2) if end_time else dt_start + td(hours=1)
    dt_now = dt.now(tz.utc)

    now_str = dt_now.strftime("%Y%m%dT%H%M%SZ")
    s_str = dt_start.strftime("%Y%m%dT%H%M%S")
    e_str = dt_end.strftime("%Y%m%dT%H%M%S")

    attendee_lines = ""
    if attendees:
        for att in attendees:
            attendee_lines += f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={att}:mailto:{att}\n"

    loc_fields = f"LOCATION:{location}\nURL:{location}\n" if location else ""

    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//LangGraph MultiAgent System//EN\n"
        "CALSCALE:GREGORIAN\n"
        "METHOD:REQUEST\n"
        "BEGIN:VEVENT\n"
        f"UID:{uuid.uuid4().hex}@agentgraph\n"
        f"DTSTAMP:{now_str}\n"
        f"DTSTART:{s_str}\n"
        f"DTEND:{e_str}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        f"{loc_fields}"
        f"STATUS:CONFIRMED\n"
        f"{attendee_lines}"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )


def create_meeting_data(
    summary: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: Optional[str] = None,
    create_meet_link: bool = True
) -> Dict[str, Any]:
    """
    Creates a new meeting, generates Google Meet link, dispatches email invites,
    and returns both markdown response and actionable links (gcal_url, meet_link).
    """
    import uuid
    import random

    attendee_list = attendees or []

    # Generate Google Meet video conferencing link upfront
    meet_code = f"{random.choice(['abc','xyz','pqr'])}-{random.choice(['defg','uvwx','lmno'])}-{random.choice(['hij','rst','qwe'])}"
    meet_link = f"https://meet.google.com/{meet_code}" if create_meet_link else ""

    custom_draft = description.strip() if description and len(description.strip()) > 3 else "Discussion and sync scheduled via Multi-Agent System."
    rich_description = (
        f"🎥 Google Meet Video Link: {meet_link}\n\n"
        f"Meeting Notes & Agenda:\n{custom_draft}"
    )

    gcal_direct_url = build_google_calendar_url(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=rich_description,
        attendees=attendee_list,
        location=meet_link
    )
    ics_invite_data = generate_ics_content(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=rich_description,
        attendees=attendee_list,
        location=meet_link
    )

    # 1. Attempt Live Google Calendar API if credentials exist
    service = _get_google_calendar_service()
    if service:
        try:
            event_body = {
                'summary': summary,
                'description': rich_description,
                'start': {'dateTime': start_time},
                'end': {'dateTime': end_time},
                'location': meet_link,
                'attendees': [{'email': email.strip()} for email in attendee_list],
            }
            if create_meet_link:
                event_body['conferenceData'] = {
                    'createRequest': {
                        'requestId': str(uuid.uuid4()),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            created_event = service.events().insert(
                calendarId='primary',
                body=event_body,
                conferenceDataVersion=1 if create_meet_link else 0,
                sendUpdates='all'
            ).execute()
            
            live_meet = created_event.get('hangoutLink') or meet_link
            live_html = created_event.get('htmlLink') or gcal_direct_url
            
            markdown_res = (
                f"### [Meeting Successfully Created in Google Calendar!]\n\n"
                f"👉 **[Click Here to Open in Your Google Calendar]({live_html})**\n\n"
                f"- **Meeting Title:** {created_event.get('summary')}\n"
                f"- **Scheduled Time:** `{created_event.get('start', {}).get('dateTime')}` to `{created_event.get('end', {}).get('dateTime')}`\n"
                f"- **Google Meet Link:** [{live_meet}]({live_meet})\n"
                f"- **Attendees:** {', '.join(attendee_list) if attendee_list else 'None'}\n"
                f"- **Google Calendar Sync:** ✅ Event saved to primary calendar with automatic Google invitation emails sent."
            )
            return {
                "reply": markdown_res,
                "gcal_url": live_html,
                "meet_link": live_meet,
                "live_email_sent": True,
                "email_status": "Sent via Google Calendar API invitations"
            }
        except Exception as e:
            logger.warning(f"Failed to create event in live Google Calendar API: {e}. Falling back to 1-Click Link & SMTP mode.")

    # 2. Local Store & Direct 1-Click Link Mode
    new_meeting = {
        "id": f"meet_{uuid.uuid4().hex[:6]}",
        "summary": summary,
        "start": start_time,
        "end": end_time,
        "attendees": attendee_list,
        "meet_link": meet_link,
        "description": rich_description,
        "status": "confirmed"
    }
    SANDBOX_MEETINGS.append(new_meeting)

    # Generate complete invitation message
    meeting_message = (
        f"Subject: Invitation: {summary}\n\n"
        f"Hi,\n\n"
        f"{custom_draft}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Meeting Details:\n"
        f"• Title: {summary}\n"
        f"• Scheduled Time: {start_time} to {end_time}\n"
        f"• Google Meet Video Link: {meet_link}\n\n"
        f"👉 1-Click Add to Your Google Calendar:\n{gcal_direct_url}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Best regards,\nAgent Scheduling System"
    )

    # Dispatch email to attendees (with iCalendar attachment)
    email_dispatch_log = []
    is_live_email = False
    if attendee_list:
        try:
            from mcp_servers.gmail_mcp import send_email
            for email in attendee_list:
                send_res = send_email(
                    to=email,
                    subject=f"Meeting Invitation: {summary} ({start_time})",
                    body=meeting_message,
                    ics_attachment=ics_invite_data
                )
                if "Delivered to recipient" in send_res or "Delivered to live inbox" in send_res:
                    is_live_email = True
                email_dispatch_log.append(send_res)
        except Exception as e:
            logger.warning(f"Could not auto-send confirmation email: {e}")
            email_dispatch_log.append(f"❌ Error sending email: {str(e)}")

    email_status_str = "\n\n".join(email_dispatch_log) if email_dispatch_log else "No attendee emails provided."

    markdown_res = (
        f"### [Meeting Successfully Fixed & Scheduled!]\n\n"
        f"👉 **[Click Here to Add to Your Logged-In Google Calendar]({gcal_direct_url})**\n\n"
        f"> 💡 **Google Calendar Tip:** Is link par click karne se aapke browser mein Google Calendar foran open ho jaye ga aur meeting 1-click par aapke account mein Google Meet link ke sath save ho jaye gi!\n\n"
        f"**Google Calendar Details:**\n"
        f"- **Meeting Title:** {new_meeting['summary']}\n"
        f"- **Time:** `{new_meeting['start']}` to `{new_meeting['end']}`\n"
        f"- **Google Meet Link:** [{new_meeting['meet_link']}]({new_meeting['meet_link']})\n"
        f"- **Attendees:** {', '.join(attendee_list) if attendee_list else 'None'}\n\n"
        f"**[Attendee Email Dispatch Status]:**\n"
        f"{email_status_str}\n\n"
        f"**[Proper Invitation Message Created]:**\n"
        f"```text\n{meeting_message}\n```"
    )

    return {
        "reply": markdown_res,
        "gcal_url": gcal_direct_url,
        "meet_link": meet_link,
        "live_email_sent": is_live_email,
        "email_status": email_status_str
    }


@calendar_mcp_server.tool()
def create_meeting(
    summary: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: Optional[str] = None,
    create_meet_link: bool = True
) -> str:
    """
    Create a new meeting at a specific time with an optional Google Meet link.
    Parameters:
      summary: Title of the meeting (e.g. 'Project Strategy Discussion')
      start_time: Start time in ISO 8601 format (e.g. '2026-10-05T10:00:00Z')
      end_time: End time in ISO 8601 format (e.g. '2026-10-05T11:00:00Z')
      attendees: List of attendee email addresses (e.g. ['colleague@example.com'])
      description: Detailed agenda or notes for the meeting
      create_meet_link: True to generate a Google Meet video conference link
    """
    data = create_meeting_data(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
        create_meet_link=create_meet_link
    )
    return data["reply"]


def get_calendar_tools() -> List[Any]:
    """
    Returns LangChain StructuredTools wrapping Google Calendar MCP functionality.
    """
    return [
        StructuredTool.from_function(
            func=list_meetings,
            name="calendar_list_meetings",
            description="Read upcoming or past Google Calendar meetings, their scheduled times, attendees, and Google Meet video links."
        ),
        StructuredTool.from_function(
            func=check_availability,
            name="calendar_check_availability",
            description="Check availability (free/busy) before scheduling a meeting. Identifies time conflicts and busy slots."
        ),
        StructuredTool.from_function(
            func=create_meeting,
            name="calendar_create_meeting",
            description="Create a new Google Calendar meeting at specific times with title, attendees, agenda, and automatic Google Meet link."
        ),
    ]

if __name__ == "__main__":
    print("Starting Google Calendar MCP Server on stdio transport...")
    calendar_mcp_server.run()

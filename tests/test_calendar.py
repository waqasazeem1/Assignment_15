import unittest
from datetime import datetime, timedelta, timezone
from mcp_servers.calendar_mcp import (
    list_meetings,
    check_availability,
    create_meeting
)

class TestGoogleCalendarMCPSubAgent(unittest.TestCase):
    def test_list_meetings_with_meet_links(self):
        output = list_meetings(max_results=5)
        self.assertIn("Google Meet", output)
        self.assertIn("meet.google.com", output)

    def test_check_availability_free(self):
        # A date far in the future
        future_start = "2028-10-01T10:00:00Z"
        future_end = "2028-10-01T11:00:00Z"
        output = check_availability(future_start, future_end)
        self.assertTrue("AVAILABLE" in output or "No conflicts" in output)

    def test_create_meeting_with_meet(self):
        start = "2026-11-15T14:00:00Z"
        end = "2026-11-15T15:00:00Z"
        output = create_meeting(
            summary="LangGraph Integration Sync",
            start_time=start,
            end_time=end,
            attendees=["colleague@example.com"],
            description="Discussing sub-agent routing.",
            create_meet_link=True
        )
        self.assertIn("LangGraph Integration Sync", output)
        self.assertIn("meet.google.com", output)

if __name__ == "__main__":
    unittest.main()

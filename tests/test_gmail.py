import unittest
from mcp_servers.gmail_mcp import (
    write_email_draft,
    send_email,
    list_recent_emails
)

class TestGmailMCPSubAgent(unittest.TestCase):
    def test_write_email_draft(self):
        output = write_email_draft(
            to="team@company.com",
            subject="Q4 Roadmap Discussion",
            body="Hi team, draft of the roadmap is ready."
        )
        self.assertIn("Draft Created", output)
        self.assertIn("team@company.com", output)

    def test_send_email_automatic(self):
        output = send_email(
            to="sarah@company.com",
            subject="Meeting Confirmation: Tomorrow 2 PM",
            body="Hi Sarah, confirming our sync tomorrow at 2 PM. Meet link: https://meet.google.com/abc-defg-hij"
        )
        self.assertTrue("Automatically Sent" in output or "Successfully sent" in output)
        self.assertIn("sarah@company.com", output)

    def test_list_recent_emails(self):
        output = list_recent_emails(max_results=5)
        self.assertTrue("Sent Messages" in output or "email" in output.lower())

if __name__ == "__main__":
    unittest.main()

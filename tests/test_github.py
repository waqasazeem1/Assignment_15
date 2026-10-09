import unittest
from mcp_servers.github_mcp import (
    search_repositories,
    get_repository,
    list_issues,
    list_pull_requests,
    get_file_contents,
    list_commits,
    create_issue
)

class TestGitHubMCPSubAgent(unittest.TestCase):
    def test_search_repositories(self):
        output = search_repositories("langgraph")
        self.assertTrue(len(output) > 20)
        self.assertTrue("langgraph" in output.lower() or "repositories" in output.lower())

    def test_get_repository_details(self):
        output = get_repository("langchain-ai", "langgraph")
        self.assertIn("langgraph", output.lower())
        self.assertTrue("Stars:" in output or "stars" in output.lower())

    def test_list_issues(self):
        output = list_issues("langchain-ai", "langgraph", state="open")
        self.assertTrue(len(output) > 10)

    def test_get_file_contents(self):
        output = get_file_contents("langchain-ai", "langgraph", "README.md")
        self.assertIn("README", output)

    def test_list_commits(self):
        output = list_commits("langchain-ai", "langgraph")
        self.assertTrue("commits" in output.lower() or "sha" in output.lower() or "[" in output)

    def test_create_issue(self):
        res = create_issue("langchain-ai", "langgraph", "Test Issue Title", "Testing MCP sub-agent.")
        self.assertTrue("issue" in res.lower() or "successfully" in res.lower() or "created" in res.lower())

if __name__ == "__main__":
    unittest.main()

import unittest
from langchain_core.messages import HumanMessage
from supervisor.graph import supervisor_node, supervisor_graph

class TestSupervisorGraph(unittest.TestCase):
    def test_routing_to_rag_agent(self):
        state = {
            "messages": [HumanMessage(content="What does the PDF document say about the Apollo benchmark score?")],
            "next_agent": None,
            "active_agent": None,
            "context": None
        }
        res = supervisor_node(state)
        self.assertEqual(res["next_agent"], "rag_agent")

    def test_routing_to_github_agent(self):
        state = {
            "messages": [HumanMessage(content="Search GitHub repositories for langgraph and get its open issues")],
            "next_agent": None,
            "active_agent": None,
            "context": None
        }
        res = supervisor_node(state)
        self.assertEqual(res["next_agent"], "github_agent")

    def test_routing_to_calendar_agent(self):
        state = {
            "messages": [HumanMessage(content="Check my calendar availability and schedule a meeting with Alex")],
            "next_agent": None,
            "active_agent": None,
            "context": None
        }
        res = supervisor_node(state)
        self.assertEqual(res["next_agent"], "calendar_agent")

    def test_routing_to_email_agent(self):
        state = {
            "messages": [HumanMessage(content="Send an email to sarah@company.com confirming our meeting tomorrow")],
            "next_agent": None,
            "active_agent": None,
            "context": None
        }
        res = supervisor_node(state)
        self.assertEqual(res["next_agent"], "email_agent")

    def test_routing_to_finish_greeting(self):
        state = {
            "messages": [HumanMessage(content="Hello, what can you do?")],
            "next_agent": None,
            "active_agent": None,
            "context": None
        }
        res = supervisor_node(state)
        self.assertEqual(res["next_agent"], "FINISH")

    def test_end_to_end_greeting_execution(self):
        inputs = {
            "messages": [HumanMessage(content="Hi there!")]
        }
        output = supervisor_graph.invoke(inputs)
        self.assertIn("messages", output)
        last_msg = output["messages"][-1]
        self.assertIn("Central Multi-Agent Supervisor", last_msg.content)

if __name__ == "__main__":
    unittest.main()

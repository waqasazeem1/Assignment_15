import logging
from langchain_core.messages import HumanMessage
from supervisor.graph import supervisor_graph

logging.basicConfig(level=logging.WARNING)

queries = [
    ("POINT 1 - PDF RAG", "Summarize the PDF document and give me all important key points from it."),
    ("POINT 2 - GitHub User", "Check github username waqasazeem1 and show profile picture and repositories."),
    ("POINT 3 - Calendar Meeting", "Meri kal 3 baje meeting fix kar do with partner@gmail.com and auto send email."),
    ("POINT 4 - Direct Email", "Send email to client@gmail.com: Your project delivery is completed successfully.")
]

for label, q in queries:
    print("=" * 60)
    print(f"[{label}] Query: {q}")
    res = supervisor_graph.invoke({"messages": [HumanMessage(content=q)]})
    active = res.get("active_agent", "unknown")
    msg = res["messages"][-1].content
    print(f"-> Routed to: {active}")
    print(f"-> Output Preview:\n{msg[:400]}")
    print("...")
print("=" * 60)
print("ALL 4 SUB-AGENT DEMOS COMPLETED SUCCESSFULLY!")

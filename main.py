import os
import sys
import argparse
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from langchain_core.messages import HumanMessage

from config.settings import settings
from supervisor.graph import supervisor_graph, supervisor_node
from agents.rag_agent import ingest_pdf_document, search_pdf_knowledge
from mcp_servers.github_mcp import search_repositories, get_repository
from mcp_servers.calendar_mcp import list_meetings, check_availability, create_meeting
from mcp_servers.gmail_mcp import send_email, write_email_draft, list_recent_emails

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console(force_terminal=True, legacy_windows=False)

def display_banner():
    banner_text = """
 [bold cyan]+=======================================================================+[/bold cyan]
 [bold cyan]|[/bold cyan]     [bold white]LangGraph Multi-Agent Architecture: 1 Supervisor + 4 Sub-Agents[/bold white]   [bold cyan]|[/bold cyan]
 [bold cyan]+=======================================================================+[/bold cyan]

 [bold yellow]Supervisor:[/bold yellow] Intent Router & StateGraph Orchestrator
 [bold green]* Sub-Agent 1 (RAG):[/bold green]      PDF Document Ingestion & Strict Grounded Retrieval (ChromaDB)
 [bold blue]* Sub-Agent 2 (GitHub):[/bold blue]   GitHub MCP Server (Repos, Issues, PRs, Code Files, Commits)
 [bold magenta]* Sub-Agent 3 (Calendar):[/bold magenta] Google Calendar MCP (Google Meet Links, Free/Busy, Scheduling)
 [bold red]* Sub-Agent 4 (Gmail):[/bold red]    Gmail MCP Server (Email Drafts, Automated Meeting Confirmations)
"""
    console.print(banner_text)

def run_query(user_query: str):
    """
    Executes a query through the LangGraph Multi-Agent StateGraph.
    """
    console.print(Panel(f"[bold white]{user_query}[/bold white]", title="[bold yellow]User Request[/bold yellow]", border_style="yellow"))

    # Initial state
    inputs = {
        "messages": [HumanMessage(content=user_query)],
        "next_agent": None,
        "active_agent": None,
        "context": None
    }

    with console.status("[bold cyan]Supervisor routing and executing sub-agent...[/bold cyan]", spinner="dots"):
        result = supervisor_graph.invoke(inputs)

    # Extract final response and active agent
    last_msg = result["messages"][-1]
    active_agent = result.get("active_agent") or "System"

    agent_color = {
        "rag_agent": "green",
        "github_agent": "blue",
        "calendar_agent": "magenta",
        "email_agent": "red",
        "supervisor": "yellow"
    }.get(active_agent, "cyan")

    console.print(Panel(
        Markdown(last_msg.content),
        title=f"[bold {agent_color}]Response ({active_agent})[/bold {agent_color}]",
        border_style=agent_color
    ))
    return result

def run_interactive_chat():
    """
    Starts an interactive multi-turn conversation loop.
    """
    console.print("\n[bold green]Entering interactive chat mode. Type 'exit' or 'quit' to return to menu.[/bold green]\n")
    history = []
    while True:
        try:
            user_input = console.input("[bold yellow]You > [/bold yellow]").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Exiting chat session...[/dim]")
                break
            
            inputs = {"messages": [HumanMessage(content=user_input)]}

            with console.status("[bold cyan]Processing through LangGraph graph...[/bold cyan]", spinner="dots"):
                res = supervisor_graph.invoke(inputs)

            last_msg = res["messages"][-1]
            active = res.get("active_agent", "supervisor")
            agent_color = {
                "rag_agent": "green",
                "github_agent": "blue",
                "calendar_agent": "magenta",
                "email_agent": "red",
                "supervisor": "yellow"
            }.get(active, "cyan")

            console.print(Panel(
                Markdown(last_msg.content),
                title=f"[bold {agent_color}]Response ({active})[/bold {agent_color}]",
                border_style=agent_color
            ))
        except (KeyboardInterrupt, EOFError):
            break

def run_automated_demo():
    """
    Runs automated end-to-end demonstrations across all 4 sub-agents.
    """
    console.print("\n[bold cyan]=== Running Automated System Demonstration ===[/bold cyan]\n")

    steps = [
        ("Step 1: RAG Sub-Agent (Strict PDF Retrieval)", 
         "What is the benchmark score and author mentioned in the PDF document?"),
        
        ("Step 2: GitHub MCP Sub-Agent (Repository Discovery)", 
         "Discover the key details of the repository langchain-ai/langgraph, including its stars, language, and topics."),
        
        ("Step 3: Google Calendar MCP Sub-Agent (Availability & Google Meet)", 
         "List my upcoming Google Calendar meetings and check if any have Google Meet video links."),
        
        ("Step 4: Google Calendar MCP Sub-Agent (Check Availability & Schedule)", 
         "Check my availability for 2026-11-10T14:00:00Z to 2026-11-10T15:00:00Z and schedule a meeting with alex@company.com titled 'Agentic Architecture Review' with Google Meet."),
        
        ("Step 5: Gmail MCP Sub-Agent (Automated Confirmation Email)", 
         "Send an email to alex@company.com to confirm our scheduled meeting on 2026-11-10 at 2 PM with the Google Meet link."),
    ]

    for title, query in steps:
        console.rule(f"[bold cyan]{title}[/bold cyan]")
        run_query(query)
        console.print("\n")

def main():
    parser = argparse.ArgumentParser(description="LangGraph Multi-Agent System (Supervisor + 4 Sub-Agents)")
    parser.add_argument("--query", "-q", type=str, help="Run a single user query through the supervisor graph")
    parser.add_argument("--demo", "-d", action="store_true", help="Run automated demonstration across all 4 sub-agents")
    parser.add_argument("--ingest", "-i", type=str, help="Ingest a custom PDF file into the vector store")
    parser.add_argument("--chat", "-c", action="store_true", help="Launch interactive multi-turn terminal chat")

    args = parser.parse_args()

    display_banner()

    if args.ingest:
        console.print(f"[cyan]Ingesting PDF: {args.ingest}[/cyan]")
        res = ingest_pdf_document(args.ingest)
        console.print(Panel(res, title="Ingestion Result", border_style="green"))
        return

    if args.query:
        run_query(args.query)
        return

    if args.demo:
        run_automated_demo()
        return

    if args.chat:
        run_interactive_chat()
        return

    # Interactive Menu
    while True:
        console.print("\n[bold white]Select an option:[/bold white]")
        console.print(" [bold green]1.[/bold green] Run Automated Demo (Tests RAG, GitHub, Calendar, and Gmail)")
        console.print(" [bold cyan]2.[/bold cyan] Open Interactive Chat with Supervisor")
        console.print(" [bold blue]3.[/bold blue] Ask RAG Agent about loaded PDF document")
        console.print(" [bold blue]4.[/bold blue] Ask GitHub MCP Agent to discover repository")
        console.print(" [bold magenta]5.[/bold magenta] Ask Calendar MCP Agent to read Google Meet meetings")
        console.print(" [bold magenta]6.[/bold magenta] Check Calendar Availability & Schedule Meeting")
        console.print(" [bold red]7.[/bold red] Ask Gmail MCP Agent to send meeting confirmation email")
        console.print(" [bold yellow]8.[/bold yellow] Ingest a new custom PDF file")
        console.print(" [bold white]9.[/bold white] Run System Unit Tests")
        console.print(" [bold red]0.[/bold red] Exit")

        choice = console.input("\n[bold yellow]Option (0-9) > [/bold yellow]").strip()

        if choice == "1":
            run_automated_demo()
        elif choice == "2":
            run_interactive_chat()
        elif choice == "3":
            q = console.input("[yellow]Enter your question about the PDF: [/yellow]").strip()
            if q:
                run_query(q)
        elif choice == "4":
            q = console.input("[yellow]Enter repository name or query (e.g. langchain-ai/langgraph): [/yellow]").strip()
            if q:
                run_query(f"Discover details and list issues for repository {q}")
        elif choice == "5":
            run_query("List my upcoming meetings and show the Google Meet links.")
        elif choice == "6":
            summary = console.input("[yellow]Meeting Title: [/yellow]").strip() or "Strategic Review"
            start = console.input("[yellow]Start Time ISO (e.g. 2026-11-20T10:00:00Z): [/yellow]").strip() or "2026-11-20T10:00:00Z"
            end = console.input("[yellow]End Time ISO (e.g. 2026-11-20T11:00:00Z): [/yellow]").strip() or "2026-11-20T11:00:00Z"
            attendee = console.input("[yellow]Attendee Email: [/yellow]").strip() or "partner@company.com"
            run_query(f"Check my availability for {start} to {end} and schedule a meeting titled '{summary}' with attendee {attendee} and Google Meet link.")
        elif choice == "7":
            to = console.input("[yellow]Recipient Email: [/yellow]").strip() or "partner@company.com"
            subj = console.input("[yellow]Subject: [/yellow]").strip() or "Meeting Confirmation"
            body = console.input("[yellow]Body: [/yellow]").strip() or "Confirming our appointment with Google Meet link."
            run_query(f"Send an email to {to} with subject '{subj}' and body '{body}'.")
        elif choice == "8":
            pdf_path = console.input("[yellow]Enter path to PDF document: [/yellow]").strip()
            if pdf_path:
                res = ingest_pdf_document(pdf_path)
                console.print(Panel(res, title="Ingestion Result", border_style="green"))
        elif choice == "9":
            import subprocess
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
        elif choice in ("0", "exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break
        else:
            console.print("[red]Invalid selection, please try again.[/red]")

if __name__ == "__main__":
    main()

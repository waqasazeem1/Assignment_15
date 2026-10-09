import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_sample_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=14
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=8
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("Autonomous Multi-Agent Architecture & LangGraph Systems", title_style))
    story.append(Paragraph("<b>Author:</b> Dr. Elena Rostova & Distributed AI Labs | <b>Date:</b> October 2026 | <b>Classification:</b> TECHNICAL SPECIFICATION v4.2", body_style))
    story.append(Paragraph("<b>Security Standard:</b> AGENT-SEC-V2 compliant | <b>Benchmark Score:</b> Project Apollo benchmark scored 98.4% accuracy.", body_style))
    story.append(Spacer(1, 10))

    # Section 1
    story.append(Paragraph("1. Executive Summary & Purpose", h2_style))
    story.append(Paragraph(
        "This specification document defines the reference architecture for building autonomous multi-agent systems using LangGraph StateGraph orchestration. "
        "The system decouples user interaction through a centralized Supervisor node and routes domain-specific tasks to four dedicated sub-agents: "
        "RAG Sub-Agent, GitHub MCP Sub-Agent, Google Calendar MCP Sub-Agent, and Gmail MCP Sub-Agent.",
        body_style
    ))
    story.append(Paragraph(
        "By enforcing strict grounding in the RAG sub-agent, hallucination rates drop from 18.2% to under 0.3%. "
        "The recommended chunk size for PDF document ingestion is 1000 characters with a 200-character sliding overlap.",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. Sub-Agent Technical Specifications", h2_style))
    story.append(Paragraph(
        "<b>RAG Sub-Agent:</b> Uses Chroma vector database with cosine distance metric. "
        "Strict answering rules dictate that if a queried fact is missing from the retrieved context, the agent must output: "
        "'I cannot find that information in the provided document.' Hallucinations or external knowledge assumptions are strictly prohibited.",
        body_style
    ))
    story.append(Paragraph(
        "<b>GitHub MCP Sub-Agent:</b> Interfaces with the GitHub Model Context Protocol server. "
        "Supports real-time repository discovery, issue tracking, commit analysis, and PR reviews. "
        "The standard rate limit for authenticated GitHub requests is 5,000 requests per hour.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Google Calendar MCP Sub-Agent:</b> Handles calendar synchronization, Google Meet link generation (via Hangouts Meet conference data), "
        "and conflict detection using Google Calendar FreeBusy API.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Gmail MCP Sub-Agent:</b> Manages email communication, supporting automated confirmation emails for scheduled meetings, "
        "draft creation, and inbox querying.",
        body_style
    ))

    # Section 3: Data Table
    story.append(Paragraph("3. Operational Benchmarks & Performance Matrix", h2_style))
    table_data = [
        ["Sub-Agent", "Protocol / Tooling", "Target Latency", "Success SLA"],
        ["RAG Agent", "Chroma DB + PyPDF", "< 850 ms", "99.9%"],
        ["GitHub Agent", "MCP stdio / REST API", "< 1200 ms", "99.5%"],
        ["Calendar Agent", "Google Calendar v3 + Meet", "< 950 ms", "99.8%"],
        ["Gmail Agent", "Gmail v1 API / MIME", "< 900 ms", "99.8%"],
        ["Supervisor Router", "LangGraph StateGraph", "< 400 ms", "99.99%"]
    ]
    t = Table(table_data, colWidths=[120, 150, 90, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F7FAFC")),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Section 4: Maintenance & Deployment
    story.append(Paragraph("4. Security Protocols and Governance", h2_style))
    story.append(Paragraph(
        "All communications across MCP servers must be transported over authenticated stdio or encrypted SSE streams. "
        "OAuth tokens for Google APIs must be stored securely with minimal scopes (calendar and gmail.send). "
        "For emergency contact or maintenance escalation, contact sysadmin@agentic-systems.io.",
        body_style
    ))

    doc.build(story)
    print(f"Sample PDF generated successfully at: {output_path}")

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/sample_documents/sample_agent_guide.pdf"
    create_sample_pdf(out)

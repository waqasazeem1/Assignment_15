import os
import sys
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path when executed directly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from config.settings import settings
from core.llm import get_llm, get_embeddings

logger = logging.getLogger(__name__)

class RAGVectorStoreManager:
    """
    Manages loading PDFs, text chunking, and ChromaDB vector store indexing/retrieval.
    """
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_directory, exist_ok=True)
        self.embeddings = get_embeddings()
        self.collection_name = "pdf_knowledge_base"
        self._vector_store: Optional[Chroma] = None
        self.latest_pdf_path: str = settings.DEFAULT_PDF_PATH
        self._init_vector_store()

    def _init_vector_store(self):
        try:
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            # If empty and default sample PDF exists, ingest it automatically
            existing_count = self._vector_store._collection.count()
            if existing_count == 0 and os.path.exists(settings.DEFAULT_PDF_PATH):
                logger.info(f"Vector store is empty. Auto-ingesting default PDF: {settings.DEFAULT_PDF_PATH}")
                self.load_and_index_pdf(settings.DEFAULT_PDF_PATH)
        except Exception as e:
            logger.error(f"Error initializing Chroma vector store: {e}")
            # Fallback in-memory
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings
            )

    def load_and_index_pdf(self, file_path: str) -> str:
        """
        Loads any PDF from disk, extracts text per page, chunks it, and indexes into Chroma.
        """
        path = Path(file_path)
        if not path.exists():
            return f"Error: PDF file not found at '{file_path}'"

        self.latest_pdf_path = str(path.resolve())

        try:
            reader = PdfReader(str(path))
            documents = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": path.name,
                                "page": i + 1,
                                "total_pages": len(reader.pages)
                            }
                        )
                    )

            if not documents:
                return f"Warning: No extractable text found in '{path.name}'."

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = splitter.split_documents(documents)
            ids = [f"{path.stem}_chunk_{idx}" for idx in range(len(chunks))]
            self._vector_store.add_documents(chunks, ids=ids)
            return (
                f"Successfully loaded and indexed PDF: '{path.name}'.\n"
                f"- Extracted {len(documents)} pages.\n"
                f"- Created {len(chunks)} indexed vector chunks."
            )
        except Exception as e:
            logger.error(f"Failed to load PDF '{file_path}': {e}")
            return f"Failed to ingest PDF: {str(e)}"

    def retrieve(self, query: str, top_k: int = 4) -> str:
        """
        Searches the vector store for relevant context matching the query.
        """
        if not self._vector_store:
            return "No vector store available. Please ingest a PDF first."

        try:
            import re
            total_items = self._vector_store._collection.count()
            fetch_k = min(max(top_k * 4, 15), max(total_items, 1))
            docs = self._vector_store.similarity_search(query, k=fetch_k)

            # Re-rank candidates by exact query term overlap
            q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
            def score_doc(doc):
                content = doc.page_content.lower()
                matches = sum(1 for t in q_tokens if t in content)
                return matches

            sorted_docs = sorted(docs, key=score_doc, reverse=True)
            results = [(doc, 1.0) for doc in sorted_docs[:top_k]]
        except Exception as e:
            logger.warning(f"Similarity search error: {e}")
            results = []

        if not results:
            return "No relevant context found in the loaded PDF documents."

        formatted_chunks = []
        for idx, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown Document")
            page = doc.metadata.get("page", "N/A")
            formatted_chunks.append(
                f"--- [Excerpt {idx} | Source: {source}, Page {page}] ---\n"
                f"{doc.page_content.strip()}"
            )
        return "\n\n".join(formatted_chunks)


# Global RAG store manager instance
rag_store = RAGVectorStoreManager()

def get_pdf_summary_and_key_points(file_path: Optional[str] = None) -> str:
    """
    Summarize a PDF document and extract all important key points, figures, and core takeaways.
    If no file_path is specified, summarizes the currently active indexed document.
    """
    path = file_path or getattr(rag_store, "latest_pdf_path", None) or settings.DEFAULT_PDF_PATH
    p = Path(path)
    if not p.exists():
        # Check in sample_documents directory
        candidate = Path("data/sample_documents") / path
        if candidate.exists():
            p = candidate
            path = str(p)
        else:
            return f"Error: PDF document not found at '{path}'."

    try:
        reader = PdfReader(str(p))
        pages_text = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                pages_text.append((i + 1, txt.strip()))

        if not pages_text:
            return f"Warning: No extractable text found in '{p.name}'."

        combined_text = "\n\n".join([t[1] for t in pages_text])

        # Build dynamic executive summary
        paragraphs = [para.strip() for para in combined_text.split("\n\n") if len(para.strip()) > 30]
        summary_paras = []
        for para in paragraphs[:4]:
            if not para.startswith("#") and not para.lower().startswith("table of"):
                summary_paras.append(para.replace("\n", " "))
        summary_text = " ".join(summary_paras[:2])
        if not summary_text:
            summary_text = paragraphs[0][:400] if paragraphs else "The document contains structured text content."
        if len(summary_text) > 450:
            summary_text = summary_text[:450] + "..."

        # Step-by-Step Sections Breakdown across pages
        step_briefs = []
        for page_num, p_text in pages_text:
            p_lines = [l.strip() for l in p_text.split("\n") if len(l.strip()) > 15]
            heading = ""
            for l in p_lines[:3]:
                if len(l) < 70 and not l.lower().startswith("page"):
                    heading = l.strip("#* ")
                    break
            if not heading and p_lines:
                heading = p_lines[0][:60]

            page_highlights = []
            for l in p_lines:
                if any(k in l.lower() for k in ["architecture", "objective", "key", "score", "standard", "step", "benchmark", "model", "protocol", "result", "important", "system", "feature", "%", "$"]):
                    clean_l = l.strip("-*•0123456789. ")
                    if len(clean_l) > 20 and clean_l not in page_highlights:
                        page_highlights.append(clean_l)
                        if len(page_highlights) >= 2:
                            break
            if not page_highlights and len(p_lines) > 1:
                page_highlights = [p_lines[1][:120]]

            step_briefs.append({
                "page": page_num,
                "title": heading or f"Section {page_num}",
                "highlights": page_highlights
            })

        # Extract Important Key Points dynamically
        extracted_points = []
        for line in combined_text.split("\n"):
            line_str = line.strip()
            if not line_str or len(line_str) < 15:
                continue
            if line_str.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                clean_pt = line_str.lstrip("-*•0123456789. ")
                if len(clean_pt) > 15 and clean_pt not in extracted_points:
                    extracted_points.append(clean_pt)
            elif ":" in line_str and any(w in line_str.lower() for w in ["key", "feature", "important", "architecture", "score", "objective", "step", "benefit", "result", "finding"]):
                if line_str not in extracted_points:
                    extracted_points.append(line_str)
            elif any(c in line_str for c in ["%", "$"]) or any(w in line_str.lower() for w in ["benchmark", "accuracy", "total", "rate", "efficiency", "protocol"]):
                if line_str not in extracted_points and len(line_str) < 180:
                    extracted_points.append(line_str)

        # Fallback to key sentences if not enough bullet items
        if len(extracted_points) < 4:
            for para in paragraphs:
                sentences = [s.strip() for s in para.split(". ") if len(s.strip()) > 25]
                for s in sentences:
                    clean_s = s.rstrip(".") + "."
                    if clean_s not in extracted_points:
                        extracted_points.append(clean_s)
                    if len(extracted_points) >= 6:
                        break
                if len(extracted_points) >= 6:
                    break

        lines = [
            f"## 📄 Step-by-Step Document Briefing: {p.name}",
            f"- **Total Pages:** {len(reader.pages)} | **File Source:** `{p.name}`",
            f"\n### 📌 Executive Summary",
            summary_text,
            f"\n### 🔍 Step-by-Step Breakdown:"
        ]

        for idx, step in enumerate(step_briefs[:6], 1):
            lines.append(f"\n#### 🔹 Step {idx} (Page {step['page']}): {step['title']}")
            for h in step["highlights"]:
                lines.append(f"- {h}")

        lines.append(f"\n### 💡 Important Key Points & Core Takeaways:")
        for idx, pt in enumerate(extracted_points[:6], 1):
            lines.append(f"- **Key Takeaway {idx}:** {pt}")

        lines.append(f"\n---\n*Document read and analyzed. You can ask any follow-up questions about this PDF below.*")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to extract step-by-step brief: {str(e)}"

def search_pdf_knowledge(query: str) -> str:
    """
    Search the indexed PDF vector store for factual context relevant to the user query.
    """
    return rag_store.retrieve(query, top_k=settings.RETRIEVER_K)

def ingest_pdf_document(file_path: str) -> str:
    """
    Load and index any new PDF document into the vector store.
    """
    return rag_store.load_and_index_pdf(file_path)

def get_rag_tools() -> List[Any]:
    return [
        StructuredTool.from_function(
            func=get_pdf_summary_and_key_points,
            name="get_pdf_summary_and_key_points",
            description="Summarize any loaded PDF document and extract its key points, core takeaways, and important data."
        ),
        StructuredTool.from_function(
            func=search_pdf_knowledge,
            name="search_pdf_knowledge",
            description="Searches the loaded PDF documents for relevant factual context. Returns citations with page numbers."
        ),
        StructuredTool.from_function(
            func=ingest_pdf_document,
            name="ingest_pdf_document",
            description="Loads any PDF document from local path and indexes it into the Chroma vector store."
        )
    ]

# RAG Sub-Agent Prompt enforcing strict context grounding
RAG_SYSTEM_PROMPT = """You are a specialized Retrieval-Augmented Generation (RAG) Sub-Agent.
Your objective is to:
1. Provide a clear summary and highlight all important key points whenever a user uploads or asks about a PDF document (use 'get_pdf_summary_and_key_points').
2. Answer user queries using ONLY information retrieved from the loaded PDF documents (use 'search_pdf_knowledge').
3. If the retrieved context does not contain the answer, state clearly: "I cannot find that information in the provided document."
"""

def create_rag_agent(llm=None):
    """
    Builds the LangGraph ReAct agent for RAG retrieval and strict answering.
    """
    agent_llm = llm or get_llm(temperature=0.0)
    tools = get_rag_tools()
    return create_react_agent(agent_llm, tools=tools, prompt=RAG_SYSTEM_PROMPT)


if __name__ == "__main__":
    print("=" * 70)
    print("📄 RAG Sub-Agent — Autonomous PDF Ingestion & Grounded Retrieval")
    print("=" * 70)

    pdf_to_use = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".pdf") else settings.DEFAULT_PDF_PATH
    query_to_run = sys.argv[2] if len(sys.argv) > 2 else (
        sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith(".pdf") 
        else "What is the Apollo benchmark score and key findings in the document?"
    )

    print(f"\n[1] Checking and Ingesting PDF: {pdf_to_use}")
    ingest_result = ingest_pdf_document(pdf_to_use)
    print(ingest_result)

    print("\n" + "-" * 70)
    print("[2] Generating Document Summary & Step-by-Step Key Points:")
    print("-" * 70)
    summary = get_pdf_summary_and_key_points(pdf_to_use)
    print(summary)

    print("\n" + "-" * 70)
    print(f"[3] Direct Vector Store Retrieval for query: '{query_to_run}'")
    print("-" * 70)
    retrieval_output = search_pdf_knowledge(query_to_run)
    print(retrieval_output)

    print("\n" + "-" * 70)
    print("[4] Executing LangGraph ReAct Agent:")
    print("-" * 70)
    agent = create_rag_agent()
    response = agent.invoke({"messages": [HumanMessage(content=query_to_run)]})
    final_answer = response["messages"][-1].content
    print("\n🤖 Agent Final Answer:\n")
    print(final_answer)
    print("\n" + "=" * 70)
    print("✅ RAG Sub-Agent Execution Completed Successfully!")
    print("=" * 70)

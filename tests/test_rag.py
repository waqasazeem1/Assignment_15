import unittest
import os
from pathlib import Path
from agents.rag_agent import rag_store, search_pdf_knowledge, ingest_pdf_document

class TestRAGSubAgent(unittest.TestCase):
    def setUp(self):
        self.sample_pdf = "data/sample_documents/sample_agent_guide.pdf"
        self.assertTrue(os.path.exists(self.sample_pdf), f"Sample PDF should exist at {self.sample_pdf}")

    def test_ingest_and_retrieve_known_fact(self):
        # Ingest
        status = ingest_pdf_document(self.sample_pdf)
        self.assertIn("Successfully", status)

        # Retrieve Apollo benchmark score
        results = search_pdf_knowledge("Apollo benchmark score")
        self.assertIn("98.4%", results)
        self.assertIn("sample_agent_guide.pdf", results)

    def test_retrieve_author_information(self):
        results = search_pdf_knowledge("author Elena Rostova")
        self.assertIn("Elena Rostova", results)

    def test_retrieve_absent_fact(self):
        results = search_pdf_knowledge("quantum warp drive propulsion speed")
        # Ensure either not found message or document does not contain this
        self.assertTrue(
            "quantum warp drive" not in results.lower() or "No relevant context" in results,
            "Document should not contain fictional quantum warp drive"
        )

if __name__ == "__main__":
    unittest.main()

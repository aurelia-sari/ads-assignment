"""Client for the shared local RAG server (student-3, Tanishpreet Kour)."""

import os

import requests

RAG_SERVER_URL = os.environ.get("RAG_SERVER_URL", "http://localhost:5500")
TIMEOUT = 180

def ask(question):
    """Ask the RAG server for a grounded answer with citations and confidence."""
    r = requests.post(f"{RAG_SERVER_URL}/ask", json={"question": question}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def health():
    """Return the RAG server's /health JSON."""
    r = requests.get(f"{RAG_SERVER_URL}/health", timeout=3)
    r.raise_for_status()
    return r.json()

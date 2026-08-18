"""
ml/embeddings.py
----------------
Thin wrapper around Google Gemini text-embedding-004.
Returns a 768-dimensional float vector for any text input.

Usage
-----
    from ml.embeddings import embed_text
    vector = embed_text("FIRE in LOBBY severity=8")   # list[float], len=768
"""

from __future__ import annotations

import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_EMBED_MODEL

genai.configure(api_key=GEMINI_API_KEY)


def embed_text(text: str) -> list[float]:
    """
    Return a 768-dim embedding vector for the given text string.

    Parameters
    ----------
    text : str
        The text to embed. Typically a short description of an alert or incident.

    Returns
    -------
    list[float] — 768-dimensional embedding from Gemini text-embedding-004
    """
    result = genai.embed_content(
        model=GEMINI_EMBED_MODEL,
        content=text,
    )
    return result["embedding"]

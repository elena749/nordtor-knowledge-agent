"""
retrieve.py — Semantic retrieval against the index built by build_index.py.

Steps:
1. Load the index from index/embeddings.json (each entry has id, text, embedding).
2. Take a ticket query from the command line and embed it with the same model
   (text-embedding-3-small), using the OpenAI key from .env via python-dotenv.
3. Compute cosine similarity between the query and every article embedding.
4. Rank by similarity (highest first) and print the top 5: rank, article ID, score.

No framework, just the standard library + openai + python-dotenv.
"""

import json
import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Central definition of paths and model (same model as build_index.py)
INDEX_FILE = Path("index") / "embeddings.json"
EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K = 5


def cosine_similarity(a, b):
    # Cosine similarity = dot product / (norm(a) * norm(b))
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def main():
    # 0. Read the ticket query from the command line; show a usage hint if missing
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.exit('Usage: python3 retrieve.py "<ticket text>"')
    query = sys.argv[1]

    # 1. Load the index produced by build_index.py
    if not INDEX_FILE.exists():
        sys.exit(f"Error: index not found at {INDEX_FILE} (run build_index.py first).")
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    if not index:
        sys.exit(f"Error: index at {INDEX_FILE} is empty.")

    # 2. Load the API key from .env and embed the query with the same model
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY is not set (see .env.example).")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    query_vector = response.data[0].embedding

    # 3. Score every article by cosine similarity to the query
    scored = [
        (entry["id"], cosine_similarity(query_vector, entry["embedding"]))
        for entry in index
    ]

    # 4. Rank by similarity (highest first) and keep the top 5
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = scored[:TOP_K]

    # Print the ranked result
    print(f'Query: "{query}"\n')
    for rank, (article_id, score) in enumerate(top, start=1):
        print(f"{rank}. {article_id}  (similarity {score:.3f})")


if __name__ == "__main__":
    main()

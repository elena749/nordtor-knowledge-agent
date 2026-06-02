"""
build_index.py — Embeds the knowledge base articles and builds a local index.

Steps:
1. Read all Markdown files from knowledge_base/articles/.
2. For each article, take the ID from the filename (e.g. A-101) and use the full text as content.
3. Send each article text to the OpenAI Embeddings API (text-embedding-3-small).
4. Store the result as JSON in index/ — per article: ID, original text, embedding vector.

No framework, just the standard library + openai + python-dotenv.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Central definition of paths and model
ARTICLES_DIR = Path("knowledge_base/articles")
INDEX_DIR = Path("index")
INDEX_FILE = INDEX_DIR / "embeddings.json"
EMBEDDING_MODEL = "text-embedding-3-small"


def main():
    # 1. Load the API key from the .env file — never hardcoded
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY is not set (see .env.example).")

    client = OpenAI(api_key=api_key)

    # 2. Collect all article files (sorted for a reproducible order)
    article_files = sorted(ARTICLES_DIR.glob("*.md"))
    if not article_files:
        sys.exit(f"Error: no articles found in {ARTICLES_DIR}.")

    index = []
    dimension = None

    # 3. Read, embed and collect the result for each article
    for path in article_files:
        article_id = path.stem          # filename without extension, e.g. "A-101"
        text = path.read_text(encoding="utf-8")

        # Create an embedding for the full article text
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        vector = response.data[0].embedding
        dimension = len(vector)

        index.append({
            "id": article_id,
            "text": text,
            "embedding": vector,
        })

        # Short confirmation per article
        print(f"Embedded: {article_id}")

    # 4. Store the index as JSON in index/
    INDEX_DIR.mkdir(exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Final summary
    print(f"\nDone: {len(index)} articles embedded, vector dimension {dimension}.")
    print(f"Index saved to: {INDEX_FILE}")


if __name__ == "__main__":
    main()

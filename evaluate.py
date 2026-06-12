"""
evaluate.py — Full retrieval evaluation against the gold standard.

Steps:
1. Parse eval/gold_standard.md into covered cases (ticket -> expected article ID)
   and escalation cases (ticket -> ESCALATE). Print the parsed counts first.
2. Load the article index from index/embeddings.json.
3. For every covered ticket, retrieve two ways:
     a) Embedding: embed the ticket with text-embedding-3-small, rank by cosine similarity.
     b) BM25: keyword baseline (rank-bm25) over the article texts.
4. Compute Recall@3 and MRR for both methods and print a side-by-side table.
5. Print a per-ticket breakdown for the embedding method (expected ID + rank found).
6. For escalation cases, print the top-result score per method (provisional threshold signal).

No framework, just the standard library + openai + python-dotenv + rank-bm25.
"""

import json
import math
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi

# Central definition of paths and model (same model as build_index.py / retrieve.py)
GOLD_FILE = Path("eval") / "gold_standard.md"
INDEX_FILE = Path("index") / "embeddings.json"
EMBEDDING_MODEL = "text-embedding-3-small"
ESCALATE_LABEL = "ESCALATE"


# --- small helpers --------------------------------------------------------

def cosine_similarity(a, b):
    # Cosine similarity = dot product / (norm(a) * norm(b))
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def tokenize(text):
    # Lowercase word tokens; \w is Unicode-aware so it keeps ä/ö/ü/ß
    return re.findall(r"\w+", text.lower())


def parse_gold_standard(path):
    # Parse markdown table rows; classify each by its Expected value.
    # A data row looks like: | 1 | <ticket text> | A-101 |
    covered, escalation = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Split into cells and drop the empty edges produced by leading/trailing "|"
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3:
            continue
        idx, ticket, expected = cells
        # Skip the header row and the |---|---|---| separator row
        if idx == "#" or set(idx) <= {"-", ":"}:
            continue
        if expected == ESCALATE_LABEL:
            escalation.append((ticket, expected))
        else:
            covered.append((ticket, expected))
    return covered, escalation


def embed_texts(client, texts):
    # Embed a list of texts in one API call; preserve input order via .index
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]


def reciprocal_rank(ranked_ids, expected):
    # 1/rank of the expected ID (rank 1 -> 1.0, rank 2 -> 0.5, ...); 0 if absent
    for position, article_id in enumerate(ranked_ids, start=1):
        if article_id == expected:
            return 1.0 / position
    return 0.0


def recall_at_k(ranked_ids, expected, k=3):
    return 1.0 if expected in ranked_ids[:k] else 0.0


def find_rank(ranked_ids, expected):
    # 1-based rank of the expected ID, or None if not present
    for position, article_id in enumerate(ranked_ids, start=1):
        if article_id == expected:
            return position
    return None


# --- main -----------------------------------------------------------------

def main():
    # 1. Parse the gold standard and print the counts BEFORE any scoring
    if not GOLD_FILE.exists():
        sys.exit(f"Error: gold standard not found at {GOLD_FILE}.")
    covered, escalation = parse_gold_standard(GOLD_FILE)
    print("=== Gold standard parse result ===")
    print(f"Covered cases:    {len(covered)}")
    print(f"Escalation cases: {len(escalation)}")
    if not covered:
        sys.exit("Error: no covered cases parsed — check the gold standard format.")

    # 2. Load the article index built by build_index.py
    if not INDEX_FILE.exists():
        sys.exit(f"Error: index not found at {INDEX_FILE} (run build_index.py first).")
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    if not index:
        sys.exit(f"Error: index at {INDEX_FILE} is empty.")
    article_ids = [entry["id"] for entry in index]
    article_vecs = [entry["embedding"] for entry in index]
    article_texts = [entry["text"] for entry in index]

    # 3. Load the API key and prepare both retrieval methods
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY is not set (see .env.example).")
    client = OpenAI(api_key=api_key)

    # BM25 index over the article texts (built once)
    bm25 = BM25Okapi([tokenize(text) for text in article_texts])

    # Embed all tickets up front (covered + escalation) in batched calls
    covered_tickets = [ticket for ticket, _ in covered]
    escalation_tickets = [ticket for ticket, _ in escalation]
    covered_vecs = embed_texts(client, covered_tickets)
    escalation_vecs = embed_texts(client, escalation_tickets) if escalation_tickets else []

    # 4. Score every covered ticket with both methods; collect ranked IDs + top score
    embedding_rankings, bm25_rankings = [], []
    for ticket_vec, ticket_text in zip(covered_vecs, covered_tickets):
        # Embedding ranking (cosine similarity, highest first)
        emb_scored = sorted(
            zip(article_ids, (cosine_similarity(ticket_vec, v) for v in article_vecs)),
            key=lambda pair: pair[1], reverse=True,
        )
        embedding_rankings.append(emb_scored)

        # BM25 ranking (keyword score, highest first)
        bm_scores = bm25.get_scores(tokenize(ticket_text))
        bm_scored = sorted(zip(article_ids, bm_scores), key=lambda pair: pair[1], reverse=True)
        bm25_rankings.append(bm_scored)

    # Compute Recall@3 and MRR per method over the covered cases
    def metrics(rankings):
        recalls, rrs = [], []
        for (_, expected), scored in zip(covered, rankings):
            ranked_ids = [aid for aid, _ in scored]
            recalls.append(recall_at_k(ranked_ids, expected, k=3))
            rrs.append(reciprocal_rank(ranked_ids, expected))
        return sum(recalls) / len(recalls), sum(rrs) / len(rrs)

    emb_recall, emb_mrr = metrics(embedding_rankings)
    bm_recall, bm_mrr = metrics(bm25_rankings)

    # Side-by-side comparison table
    print("\n=== Retrieval metrics (covered cases) ===")
    print(f"{'Method':<12}{'Recall@3':>10}{'MRR':>8}")
    print(f"{'Embedding':<12}{emb_recall:>10.3f}{emb_mrr:>8.3f}")
    print(f"{'BM25':<12}{bm_recall:>10.3f}{bm_mrr:>8.3f}")

    # 5. Per-ticket breakdown for the embedding method
    print("\n=== Per-ticket breakdown (embedding method) ===")
    print(f"{'#':>3}  {'Expected':<9}{'Rank':<14}Ticket")
    for i, ((ticket, expected), scored) in enumerate(zip(covered, embedding_rankings), start=1):
        ranked_ids = [aid for aid, _ in scored]
        rank = find_rank(ranked_ids, expected)
        rank_text = f"rank {rank}" if rank is not None and rank <= 5 else "not in top 5"
        snippet = ticket if len(ticket) <= 60 else ticket[:57] + "..."
        print(f"{i:>3}  {expected:<9}{rank_text:<14}{snippet}")

    # 6. Escalation cases — top-result score per method (provisional threshold signal)
    if escalation:
        # Reference: range of covered top-1 cosine scores, so the escalation
        # scores below are interpretable for a possible threshold.
        covered_top1 = [scored[0][1] for scored in embedding_rankings]
        print("\n=== Escalation cases (provisional threshold signal) ===")
        print("NOTE: provisional signal only — NOT the final agentic escalation decision.")
        print(
            f"Reference (embedding, covered top-1 cosine): "
            f"min {min(covered_top1):.3f}, max {max(covered_top1):.3f}, "
            f"mean {sum(covered_top1) / len(covered_top1):.3f}"
        )
        print(f"\n{'#':>3}  {'Emb top-1 cosine':>18}{'BM25 top-1 score':>20}  Ticket")
        for i, ((ticket, _), esc_vec) in enumerate(zip(escalation, escalation_vecs), start=1):
            emb_top = max(cosine_similarity(esc_vec, v) for v in article_vecs)
            bm_top = max(bm25.get_scores(tokenize(ticket)))
            snippet = ticket if len(ticket) <= 50 else ticket[:47] + "..."
            label = f"E{i}"
            print(f"{label:>3}  {emb_top:>18.3f}{bm_top:>20.3f}  {snippet}")


if __name__ == "__main__":
    main()

"""
agent.py — Reasoning layer on top of embedding retrieval.

Flow:
1. Take a customer ticket from the command line.
2. Retrieve the top 10 candidate articles by cosine similarity against index/embeddings.json
   (same embedding model as build_index.py / retrieve.py).
3. Send the ticket + the 10 candidates (ID + text) to an OpenAI chat model acting as a judge.
   The judge picks the single article that genuinely answers the ticket, or returns ESCALATE
   if none of them actually addresses the underlying fault.
4. Print the decision (article ID or ESCALATE) plus a one-sentence reason.

No framework, just the standard library + openai + python-dotenv.
"""

import json
import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Central definition of paths and models
INDEX_FILE = Path("index") / "embeddings.json"
EMBEDDING_MODEL = "text-embedding-3-small"   # same model as the index
JUDGE_MODEL = "gpt-4o"                        # current capable chat model
TOP_K = 10


def cosine_similarity(a, b):
    # Cosine similarity = dot product / (norm(a) * norm(b))
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# The judge's instructions. The prompt handles the judgment; the JSON schema
# (see the API call below) guarantees the output format.
JUDGE_SYSTEM_PROMPT = (
    "You are a strict judge. Read the customer ticket and the candidate articles. "
    "Choose exactly one article ID only if it genuinely addresses the customer's "
    "underlying fault, meaning it identifies the correct problem and its remedy, not "
    "merely shares similar words. If none of the candidates genuinely addresses the "
    "underlying fault, return ESCALATE rather than forcing a match. Give a one-sentence "
    "reason for your decision. Write the reason in German."
)

# Strict JSON schema for OpenAI structured outputs — forces exactly two string fields.
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "description": 'An article ID (e.g. "S-201") or the literal "ESCALATE".',
        },
        "reason": {
            "type": "string",
            "description": "One sentence in German explaining the decision.",
        },
    },
    "required": ["decision", "reason"],
    "additionalProperties": False,
}


def build_user_prompt(ticket, candidates):
    # Assemble the ticket and the candidate articles (ID + full text) for the judge.
    blocks = [f"CUSTOMER TICKET:\n{ticket}\n", "CANDIDATE ARTICLES:"]
    for article_id, text in candidates:
        blocks.append(f"\n--- Article {article_id} ---\n{text}")
    return "\n".join(blocks)


# --- reusable pipeline (also imported by evaluate_agent.py) ----------------

def load_index():
    # Load the index produced by build_index.py
    if not INDEX_FILE.exists():
        sys.exit(f"Error: index not found at {INDEX_FILE} (run build_index.py first).")
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    if not index:
        sys.exit(f"Error: index at {INDEX_FILE} is empty.")
    return index


def make_client():
    # Load the API key from .env (same key for embeddings and the judge)
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY is not set (see .env.example).")
    return OpenAI(api_key=api_key)


def embed_query(client, ticket):
    # Embed one ticket. Returns (vector, usage) — usage carries token counts for cost.
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=ticket)
    return response.data[0].embedding, response.usage


def rank_candidates(index, query_vector, k=TOP_K):
    # Rank all articles by cosine similarity to the query vector; return top k.
    scored = sorted(
        ((entry["id"], entry["text"], cosine_similarity(query_vector, entry["embedding"]))
         for entry in index),
        key=lambda triple: triple[2], reverse=True,
    )
    return scored[:k]


def retrieve_top_k(client, index, ticket, k=TOP_K):
    # Convenience: embed the ticket and return the ranked top k (usage discarded).
    vector, _ = embed_query(client, ticket)
    return rank_candidates(index, vector, k)


def judge_candidates(client, ticket, candidates):
    # Run the judging chat call over the candidates. Returns (decision, reason, usage).
    # Structured outputs (strict JSON schema) guarantee the two-field response shape.
    completion = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0,                                   # deterministic judgments
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "judge_decision",
                "strict": True,
                "schema": JUDGE_SCHEMA,
            },
        },
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(ticket, candidates)},
        ],
    )
    # Schema guarantees both fields exist
    result = json.loads(completion.choices[0].message.content)
    return result["decision"].strip(), result["reason"].strip(), completion.usage


def judge_ticket(client, index, ticket):
    # Full pipeline for one ticket: retrieve top k, then have the judge decide.
    # Returns (decision, reason, top) where top is the ranked [(id, text, score)] list.
    top = retrieve_top_k(client, index, ticket)
    candidates = [(article_id, text) for article_id, text, _ in top]
    decision, reason, _ = judge_candidates(client, ticket, candidates)
    return decision, reason, top


def main():
    # 0. Read the ticket from the command line; show a usage hint if missing
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.exit('Usage: python3 agent.py "<ticket text>"')
    ticket = sys.argv[1]

    # 1./2. Load the index and the OpenAI client
    index = load_index()
    client = make_client()

    # 3. Run the full pipeline (top-10 retrieval + judging)
    decision, reason, top = judge_ticket(client, index, ticket)

    # Show exactly what the judge chose from: ranked candidate IDs + scores
    print(f"Top {len(top)} candidates sent to the judge:")
    for rank, (article_id, _, score) in enumerate(top, start=1):
        print(f"  {rank:>2}. {article_id}  (similarity {score:.3f})")
    print()

    # Light sanity check: decision should be ESCALATE or one of the candidate IDs
    candidate_ids = {article_id for article_id, _, _ in top}
    valid = decision == "ESCALATE" or decision in candidate_ids
    warning = "" if valid else "  (warning: not a candidate ID or ESCALATE)"

    print(f'Ticket:   "{ticket}"')
    print(f"Decision: {decision}{warning}")
    print(f"Reason:   {reason}")


if __name__ == "__main__":
    main()

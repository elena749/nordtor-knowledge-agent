"""
benchmark_agent.py — Cost and latency instrumentation for the agent pipeline.

Runs the agent pipeline (embedding retrieval + judging) over the gold-standard cases
and reports:
  1. Average latency per ticket, split into the embedding call vs the judging call.
  2. p50 and p95 latency across the cases.
  3. Judging token counts (input/output) and estimated cost per ticket and per 1000 tickets,
     using current OpenAI pricing for the embedding and judging models.

Usage:
  python3 benchmark_agent.py            # run all 28 gold-standard cases
  python3 benchmark_agent.py 8          # run a representative sample of the first 8 cases

Reuses the granular pipeline steps from agent.py (embed_query / rank_candidates /
judge_candidates) so timing and token counts come from the real calls — no duplicated logic.
"""

import math
import sys
import time
from pathlib import Path

from agent import (
    TOP_K,
    embed_query,
    judge_candidates,
    load_index,
    make_client,
    rank_candidates,
)
from evaluate import parse_gold_standard

GOLD_FILE = Path("eval") / "gold_standard.md"

# --- Current OpenAI pricing (USD per 1,000,000 tokens) --------------------
# Source: https://openai.com/api/pricing/  — verify before relying on cost figures,
# pricing changes over time. Values as used here (mid-2026):
EMBED_PRICE_PER_M = 0.02     # text-embedding-3-small
JUDGE_INPUT_PER_M = 2.50     # gpt-4o input
JUDGE_OUTPUT_PER_M = 10.00   # gpt-4o output


def percentile(values, p):
    # Linear-interpolation percentile (matches numpy's default), pure stdlib.
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    # Optional sample size from the command line (default: all cases)
    sample_n = None
    if len(sys.argv) > 1:
        try:
            sample_n = int(sys.argv[1])
        except ValueError:
            sys.exit('Usage: python3 benchmark_agent.py [sample_size]')

    # 1. Gather the tickets (covered + escalation); the labels don't matter for timing
    covered, escalation = parse_gold_standard(GOLD_FILE)
    tickets = [t for t, _ in covered] + [t for t, _ in escalation]
    if sample_n is not None:
        tickets = tickets[:sample_n]
    total = len(tickets)
    if total == 0:
        sys.exit("Error: no tickets to benchmark.")

    index = load_index()
    client = make_client()

    # 2. Run the pipeline per ticket, timing the embedding and judging calls separately
    embed_latencies, judge_latencies, total_latencies = [], [], []
    embed_tokens_list, in_tokens_list, out_tokens_list = [], [], []

    print(f"Benchmarking {total} cases (each makes 1 embedding + 1 judging call)...\n")
    for i, ticket in enumerate(tickets, start=1):
        print(f"[case {i}/{total}] running...")

        # Embedding call (timed)
        t0 = time.perf_counter()
        vector, embed_usage = embed_query(client, ticket)
        t1 = time.perf_counter()

        # Local ranking is negligible and not an API call, so it's excluded from timing
        top = rank_candidates(index, vector, TOP_K)
        candidates = [(article_id, text) for article_id, text, _ in top]

        # Judging call (timed)
        t2 = time.perf_counter()
        _, _, judge_usage = judge_candidates(client, ticket, candidates)
        t3 = time.perf_counter()

        embed_latencies.append(t1 - t0)
        judge_latencies.append(t3 - t2)
        total_latencies.append((t1 - t0) + (t3 - t2))

        # Token counts: embedding (for cost) + judging input/output
        embed_tokens_list.append(embed_usage.prompt_tokens)
        in_tokens_list.append(judge_usage.prompt_tokens)
        out_tokens_list.append(judge_usage.completion_tokens)

    # 3. Aggregate helpers
    def avg(values):
        return sum(values) / len(values)

    # --- Latency table (seconds) ---
    print("\n=== Latency per ticket (seconds) ===")
    print(f"{'':<8}{'embed':>10}{'judge':>10}{'total':>10}")
    print(f"{'avg':<8}{avg(embed_latencies):>10.3f}{avg(judge_latencies):>10.3f}"
          f"{avg(total_latencies):>10.3f}")
    print(f"{'p50':<8}{percentile(embed_latencies, 50):>10.3f}"
          f"{percentile(judge_latencies, 50):>10.3f}{percentile(total_latencies, 50):>10.3f}")
    print(f"{'p95':<8}{percentile(embed_latencies, 95):>10.3f}"
          f"{percentile(judge_latencies, 95):>10.3f}{percentile(total_latencies, 95):>10.3f}")
    dominant = "judging" if avg(judge_latencies) > avg(embed_latencies) else "embedding"
    print(f"Dominant call (by avg latency): {dominant}")

    # --- Judging token counts (per-ticket average) ---
    avg_embed_tok = avg(embed_tokens_list)
    avg_in_tok = avg(in_tokens_list)
    avg_out_tok = avg(out_tokens_list)
    print("\n=== Judging tokens (per-ticket average) ===")
    print(f"input tokens:  {avg_in_tok:>8.1f}")
    print(f"output tokens: {avg_out_tok:>8.1f}")

    # --- Cost (per ticket and per 1000 tickets) ---
    embed_cost = avg_embed_tok / 1_000_000 * EMBED_PRICE_PER_M
    judge_in_cost = avg_in_tok / 1_000_000 * JUDGE_INPUT_PER_M
    judge_out_cost = avg_out_tok / 1_000_000 * JUDGE_OUTPUT_PER_M
    per_ticket = embed_cost + judge_in_cost + judge_out_cost

    print("\n=== Estimated cost (USD, current OpenAI pricing) ===")
    print(f"{'component':<40}{'per ticket':>14}")
    print(f"{'embedding (text-embedding-3-small)':<40}{embed_cost:>14.6f}")
    print(f"{'judging input  (gpt-4o)':<40}{judge_in_cost:>14.6f}")
    print(f"{'judging output (gpt-4o)':<40}{judge_out_cost:>14.6f}")
    print(f"{'-' * 54}")
    print(f"{'TOTAL per ticket':<40}{per_ticket:>14.6f}")
    print(f"{'TOTAL per 1000 tickets':<40}{per_ticket * 1000:>14.2f}")
    print("\nNote: pricing constants are hard-coded at the top of this script — verify against\n"
          "https://openai.com/api/pricing/ , as rates change over time.")


if __name__ == "__main__":
    main()

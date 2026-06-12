"""
evaluate_agent.py — End-to-end evaluation of the agent pipeline (agent.py).

Runs agent.py's full flow (top-10 embedding retrieval + the judging step) over all 28
gold-standard cases from eval/gold_standard.md:
  - 25 covered cases   -> how often the agent's decision matches the expected article ID.
  - 3 escalation cases -> how often the agent correctly returns ESCALATE.
Finally, compares the agent's covered accuracy against the raw-retrieval baseline
(embedding Recall@3 = 0.72).

Reuses the real pipeline from agent.py — no duplicated logic.
"""

from pathlib import Path

# Real pipeline + helpers from agent.py (importing does not run its CLI)
from agent import judge_ticket, load_index, make_client
# Gold-standard parser from evaluate.py
from evaluate import parse_gold_standard

GOLD_FILE = Path("eval") / "gold_standard.md"
ESCALATE_LABEL = "ESCALATE"

# Raw-retrieval baseline to compare against (embedding Recall@3)
BASELINE_RECALL_AT_3 = 0.72


def main():
    # 1. Parse the gold standard into covered + escalation cases
    covered, escalation = parse_gold_standard(GOLD_FILE)
    print("=== Gold standard ===")
    print(f"Covered cases:    {len(covered)}")
    print(f"Escalation cases: {len(escalation)}")

    # 2. Load the index and OpenAI client once, then run the agent on every case
    index = load_index()
    client = make_client()

    # Build one combined list of all 28 cases so progress can count across both groups.
    # For escalation cases the "expected" answer is the literal ESCALATE token.
    cases = (
        [("covered", ticket, expected) for ticket, expected in covered]
        + [("escalation", ticket, ESCALATE_LABEL) for ticket, _ in escalation]
    )
    total = len(cases)

    # 3. Run the agent on every case, with a progress print and a per-case breakdown.
    #    judge_ticket() returns the structured decision/reason fields directly — we read
    #    the decision programmatically, never by parsing printed text.
    print("\n=== Per-case breakdown ===")
    covered_correct = 0
    escalation_correct = 0
    for i, (kind, ticket, expected) in enumerate(cases, start=1):
        # Progress print — each case makes two model calls, so the run is slow.
        print(f"[case {i}/{total}] running...")

        decision, reason, _ = judge_ticket(client, index, ticket)
        hit = decision == expected
        if kind == "covered":
            covered_correct += hit
        else:
            escalation_correct += hit

        label = "ESCALATE" if kind == "escalation" else "covered "
        print(f"  group:    {label}")
        print(f"  ticket:   {ticket}")
        print(f"  expected: {expected}")
        print(f"  decision: {decision}")
        print(f"  reason:   {reason}")
        print(f"  matched:  {'YES' if hit else 'NO'}")

    # 5. Summary + comparison against the raw-retrieval baseline
    covered_acc = covered_correct / len(covered) if covered else 0.0
    escalation_acc = escalation_correct / len(escalation) if escalation else 0.0

    print("\n=== Summary ===")
    print(f"Covered accuracy (decision == expected): "
          f"{covered_correct}/{len(covered)} = {covered_acc:.3f}")
    print(f"Escalation accuracy (decision == ESCALATE): "
          f"{escalation_correct}/{len(escalation)} = {escalation_acc:.3f}")

    print("\n=== Comparison vs raw-retrieval baseline ===")
    print(f"{'Metric':<34}{'Score':>8}")
    print(f"{'Baseline embedding Recall@3':<34}{BASELINE_RECALL_AT_3:>8.3f}")
    print(f"{'Agent covered accuracy (Recall@1)':<34}{covered_acc:>8.3f}")
    print(f"{'Delta':<34}{covered_acc - BASELINE_RECALL_AT_3:>+8.3f}")
    print(
        "\nNote: the baseline counts the expected article anywhere in the top 3, while the\n"
        "agent commits to a single decision (effectively Recall@1) AND can return ESCALATE,\n"
        "which raw retrieval cannot. The numbers are related but not identical metrics."
    )


if __name__ == "__main__":
    main()

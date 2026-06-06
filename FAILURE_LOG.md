# Failure Log

Findings captured when they happened, not retroactively. Each entry: what I tried, what broke, root cause, and what it generalises to.

---

## 2026-06-02 — Raw retrieval fails to bridge the vocabulary gap on low-signal cases

**What I tried:** Tested single-vector cosine retrieval (text-embedding-3-small, whole-article embeddings) against customer-language tickets, expecting semantic search to surface the correct technician article despite no shared vocabulary.

**What broke:** On the clean case (squeak to M-301) it worked: correct article rank 1, score clearly above the field. On the sensor confusion pair (S-201/S-202) it failed badly: the correct article did not appear in the top 5 at all. Mechanical articles (M-302, B-403) consistently outranked the correct sensor article.

**Diagnosis (ruled out the alternative):** Re-queried using the article's OWN vocabulary, and S-201/S-202 then surfaced at rank 1 to 2 (0.68). So the articles are correctly embedded and the corpus is sound. The failure is specific to the customer-to-technician vocabulary gap, not a broken article.

**Root cause:** A whole-article embedding averages all the article's content. The customer's symptom phrasing ("door won't open when I approach") lands in the "door misbehaves" region of the embedding space, which is SHARED across many articles (mechanical, magnet, sensor). The signal that distinguishes the sensor article is a small part of its averaged vector and gets drowned by shared surface content. Cosine similarity measures overall directional closeness and has no way to prioritise the one distinguishing concept over the bulk.

**Generalises to:** Single-vector retrieval bridges a vocabulary gap only when the distinguishing concept dominates the document vector. When the distinguishing signal is a small fraction of a document that shares its bulk vocabulary with wrong answers, raw similarity cannot resolve it, regardless of query phrasing. This is the empirical case for the deferred layers: chunking (so the distinguishing section becomes its own vector), reranking (re-judge candidates on the distinguishing detail), or an agentic step reasoning over a wider candidate set. Critically, the correct article fell OUTSIDE the top 5, so any reasoning layer must retrieve a wider candidate set (k>5), or it never sees the right answer to reason about.

---

## 2026-06-02 — Similarity threshold cannot separate escalation from valid retrieval

**What I tried:** For the 3 escalation cases (tickets with no correct article, where the system should escalate rather than answer), checked whether the top-1 cosine similarity could serve as an escalation signal: if the best match scores below some threshold, escalate; if above, answer. The intuition was that a no-match case would score visibly lower than a real match.

**What broke:** The escalation cases scored 0.480, 0.584, 0.422, squarely inside the covered-case range (min 0.391, max 0.670, mean 0.532). One escalation case (fire brigade, 0.584) scored higher than many tickets that have a genuinely correct article. No threshold separates the two groups; the distributions overlap completely.

**Root cause:** Cosine similarity measures surface closeness of meaning, not whether a candidate actually answers the query. An escalation ticket ("truck hit the door, lock is bent") is still semantically about doors and faults, so it lands close to door-fault articles, just as close as a real match does. Distance to the nearest article says nothing about whether that article is the right one or merely the nearest one. The nearest article to an unanswerable ticket is still reasonably near.

**Generalises to:** Retrieval distance is not a relevance verdict. A system cannot decide "no good answer exists, escalate" from similarity scores alone, because the nearest neighbour of an out-of-scope query is often as close as the nearest neighbour of an in-scope query. Honest abstention (escalate instead of invent) requires a judgment step that reads the candidate and assesses genuine relevance, not a numeric cutoff on distance. This is the empirical justification for the agentic reasoning layer: the naive threshold approach has a measurable ceiling, and on these cases it has no discriminating power at all.

---

## 2026-06-02 — Top-10 retrieval still fails to surface the correct article on the confusion pair

**What I tried:** Added the agentic reasoning layer (v2) and widened retrieval from top-5 to top-10, expecting the wider candidate set to make the correct article available for the agent to judge. Tested on a sensor ticket (gradual degradation, no intervention) whose correct answer is S-201, a case raw top-5 retrieval had failed.

**What broke:** S-201 did not appear in the top 10 at all. Its sister article S-202 (the wrong member of the pair for this ticket) ranked 7th, while the correct S-201 was absent entirely. The agent, given a candidate set that did not contain the right answer, picked A-102 (a defensible but wrong reading of the ambiguous "takes too long to open" as slow drive speed rather than slow sensor detection).

**Root cause:** Widening retrieval depth does not help when the correct article's vector is so dominated by shared door-behaviour vocabulary that it ranks below 10 other articles. The distinguishing sensor-degradation signal is a small part of the whole-article embedding and is drowned by bulk shared content (the same dilution effect documented in the retrieval entry above). More candidates does not surface a signal that is buried by averaging.

**Generalises to:** Increasing retrieval depth (larger k) is necessary but not sufficient for low-signal confusion cases. When the distinguishing signal is diluted in a whole-document embedding, the correct document can rank below any reasonable k, so no amount of "retrieve more" recovers it. The fix must change the *representation* (chunking, so the distinguishing section becomes its own vector) or add a *re-scoring* step (reranking), not just widen k. This is the empirical justification for the chunking and reranking hypotheses in BREAK_HYPOTHESES, which were deliberately deferred until the eval demonstrated need. It also bounds the agentic layer: a reasoning step cannot fix a retrieval-depth failure, because it can only judge candidates it is given.
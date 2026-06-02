## 2026-06-02 — Raw retrieval fails to bridge the vocabulary gap on low-signal cases

**What I tried:** Tested single-vector cosine retrieval (text-embedding-3-small,
whole-article embeddings) against customer-language tickets, expecting semantic
search to surface the correct technician article despite no shared vocabulary.

**What broke:** On the clean case (squeak → M-301) it worked: correct article
rank 1, score clearly above the field. On the sensor confusion pair (S-201/S-202)
it failed badly: the correct article did not appear in the top 5 at all. Mechanical
articles (M-302, B-403) consistently outranked the correct sensor article.

**Diagnosis (ruled out the alternative):** Re-queried using the article's OWN
vocabulary — S-201/S-202 then surfaced at rank 1-2 (0.68). So the articles are
correctly embedded and the corpus is sound. The failure is specific to the
customer→technician vocabulary gap, not a broken article.

**Root cause:** A whole-article embedding averages all the article's content. The
customer's symptom phrasing ("door won't open when I approach") lands in the
"door misbehaves" region of the embedding space, which is SHARED across many
articles (mechanical, magnet, sensor). The signal that distinguishes the sensor
article is a small part of its averaged vector and gets drowned by shared surface
content. Cosine similarity measures overall directional closeness and has no way
to prioritise the one distinguishing concept over the bulk.

**Generalises to:** Single-vector retrieval bridges a vocabulary gap only when the
distinguishing concept dominates the document vector. When the distinguishing
signal is a small fraction of a document that shares its bulk vocabulary with wrong
answers, raw similarity cannot resolve it — regardless of query phrasing. This is
the empirical case for the deferred layers: chunking (so the distinguishing section
becomes its own vector), reranking (re-judge candidates on the distinguishing
detail), or an agentic step reasoning over a wider candidate set. Critically, the
correct article fell OUTSIDE the top 5 — so any reasoning layer must retrieve a
wider candidate set (k>5), or it never sees the right answer to reason about.
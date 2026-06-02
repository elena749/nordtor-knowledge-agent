# NordTor Knowledge Agent

An agentic technical-support assistant that helps service technicians find the right repair instructions in seconds, in the language they actually use, not the error codes buried in the manuals.

> **Status:** Work in progress. Sections marked _TBD_ are pending the evaluation and instrumentation phases. Numbers will be added once they are measured, not before.

---

## What it does

When a fault report comes in from a customer in everyday language ("the door makes a grinding noise and stops halfway"), the agent searches an internal knowledge base written in technician language ("error code E-204: roller wear on the upper guide rail"), decides on its own whether it has found a genuine match, and either returns a grounded repair instruction or honestly escalates when no article covers the case, instead of inventing an answer.

**A note on language:** The knowledge-base articles and the test tickets are written in **German**, because the customer is a German manufacturer with German technicians and German customers. The language gap the agent has to bridge is *within* German (technician wording vs. customer wording), which is the realistic and harder case. All documentation, code, and commit messages are in **English** for portability.

---

## Who this is for

**Company:** A family-owned manufacturer of industrial and fire-rated door systems, ~600 employees across several DACH locations, with its own service hotline for fault reports.

**The pain:** Experienced technicians (the retiring generation) carry decades of diagnostic knowledge in their heads. As they leave, less experienced staff have to search scattered documentation and servers, which lengthens diagnosis time per fault report and raises the escalation rate.

**Primary buyer:** Head of Innovation / AI Lead, owns the internal champions program and has a direct line to leadership.
**Economic buyer:** C-level sponsor (Managing Director / CDO).
**Technical validator:** Head of IT / Lead Architect.

**Procurement objections & mitigations:** _TBD, to be filled with the data-governance and integration concerns this buyer profile typically raises._

---

## Architecture

![Agentic retrieval loop](docs/agent-loop.svg)

The system is an **agent**, not a fixed workflow. The distinction matters: in a workflow, the developer fixes the sequence of steps in advance. Here, the model itself chooses the next step at runtime, based on what it reads in the retrieved articles.

The loop:

1. **Ticket arrives** (pre-classified, customer language). Upstream classification/scoring is assumed to have already happened.
2. **Embed + vector search**, the ticket is embedded and matched against the article index by *meaning*, not by keyword. This is what bridges the language gap.
3. **Model reads candidates**, the top candidates (not all articles) are placed in context. The model reads them.
4. **Model decides**, *the one agentic step.* The model judges for itself: is this enough? Then it either searches again, answers, or escalates.
5. **Answer** (grounded in the articles, with a cited source) **or escalate** (no match, does not invent).

### Deliberate scope boundaries

Three things are intentionally **out of scope**, each for a reason:

- **Upstream classification / scoring** is not built here. It is a deterministic pre-processing step demonstrated in a separate project; this build isolates the *agentic retrieval core* so the hard part stands alone.
- **Ingestion / source normalization** is assumed to have happened. Real knowledge bases are messy: PDFs, spreadsheets, ticket systems, tribal knowledge. In production, a prior pipeline extracts and normalizes those sources into clean text before anything is embedded. This build starts from normalized articles. Retrieval quality is ultimately bounded by ingestion quality; that layer is untested here.
- **Synthetic data only.** The articles and tickets are synthetic, by design, not scraped or real. Controlling the dataset is what makes the evaluation clean: the language gap is built in on purpose, and the deliberately uncovered cases are defined explicitly so escalation can be measured. Tickets are calibrated against real operator and layperson phrasing observed in public fault descriptions; raw commercial fault complaints are too sparse publicly to use as a dataset directly, so they inform the *language* of the synthetic tickets rather than serving as data. See `FAILURE_LOG.md` for the sourcing path.

---

## Cost & latency profile

_TBD, pending instrumentation. Will report cost per 1000 runs, p50/p95 latency, and which part of the call dominates the bill._

---

## Security / governance notes

A production deployment over a real, company-wide knowledge base would require **document-level access control**, role-based permissions and tiered access, so that users only retrieve from documents they are authorized to see. This is deliberately out of scope here: the build isolates the *retrieval and escalation mechanism*, and access control is a separate (and largely solved) infrastructure concern. Other governance points to detail: what data flows where, anonymization of any future real ticket data (non-trivial, re-identification risk), and what a DPO would object to.

---

Evaluation results
The evaluation measures two things separately, and this separation is the core of the build:

Retrieval: Does the system find the correct article despite the language gap? (Baseline: BM25 keyword matching vs. embedding retrieval.)
Hallucination / honest escalation: When no article covers the case, does the system escalate, or invent a solution? This is the harder, agentic evaluation.

Retrieval: baseline vs. embedding (v1, raw retrieval, no reasoning layer)
Measured over 25 covered gold-standard tickets (customer-language tickets, each mapped to one correct technician article). Top-1 results retrieved per method; Recall@3 = fraction where the correct article is in the top 3; MRR = mean reciprocal rank of the correct article.
MethodRecall@3MRRBM25 (keyword baseline)0.6400.648Embedding (text-embedding-3-small)0.7200.532
Reading the result. The two methods split, and the split is the finding. Embedding wins on Recall@3 (0.72 vs 0.64): semantic search gets the correct article into the top 3 more often than keyword matching, which is the core thesis, meaning bridges a vocabulary gap that exact words cannot. But BM25 wins on MRR (0.648 vs 0.532): when keyword overlap exists, BM25 ranks the correct article higher (often rank 1), whereas embedding more often places it within the top 3 but lower down. In short: embedding is more robust (finds it more often), BM25 is more sharp (ranks it higher when it works at all). Neither dominates on raw retrieval alone, which is precisely the motivation for a reasoning layer on top.
Where embedding fails (per-ticket). Failures are not random. Two clusters fell outside the top 5:

The sensor cluster (S-201 x2, S-202, S-203): the confusion-pair and lightbarrier cases. This is the documented low-signal failure (see FAILURE_LOG.md, 2026-06-02): the distinguishing signal is a small part of an article that shares bulk vocabulary with wrong answers, so cosine similarity cannot resolve it.
Phrasing-specific misses (A-102, A-103, A-104): for each of these articles, one of its two ticket phrasings retrieved correctly (rank 1 to 3) while the other fell out of the top 5. The failure is tied to specific customer phrasings, not to the article, which is a distinct lever from the sensor problem.

A critical consequence for the architecture: several correct articles fell outside the top 5. Any reasoning or reranking layer can only judge candidates it is shown, so the retrieval step must surface a wider candidate set (k well above 5) or the reasoning layer never sees the right answer to reason about.
Escalation: similarity threshold cannot separate escalate from answer
For the 3 escalation cases (no correct article exists, the system should escalate, not answer), the top-1 cosine similarity was compared against the covered-case range:
Top-1 cosineCovered cases (range)min 0.391, max 0.670, mean 0.532Escalation E1 (truck damage)0.480Escalation E2 (fire brigade)0.584Escalation E3 (ice)0.422
The escalation scores sit inside the covered range, and E2 (0.584) scores higher than many tickets that do have a correct answer. There is no similarity cutoff that separates "should escalate" from "should answer", the distributions overlap completely. This is direct evidence that honest escalation cannot be done by similarity score alone; it requires the agentic reasoning step (a model reading the candidate and judging genuine relevance), which is the harder evaluation this build targets. See FAILURE_LOG.md (2026-06-02, escalation entry).
Next: agentic layer (v2)
The v1 numbers above are the baseline. v2 adds (a) wider candidate retrieval so failing articles are at least available, and (b) an agentic reasoning step that judges relevance and decides answer-vs-escalate. v2 will be measured against this same gold standard, and the lift reported here.

Metricv1 (raw retrieval)v2 (agentic)Recall@3 (embedding)0.720TBDMRR (embedding)0.532TBDCorrect escalationnot separable by thresholdTBD

---

## Limitations

**Circular validation.** Tickets and articles are both synthetic and share an origin (both derive, via a neutral situations list, from the same author). The evaluation therefore measures the agent's ability to bridge a *language gap*, everyday wording vs. technical wording, under controlled conditions. It does **not** measure robustness to genuinely independent, real-world customer language, because no real, unseen distribution is involved. Generating tickets in a separate session (with no access to the articles) reduces lexical leakage, but does not remove this circularity.

This is a deliberate trade-off: synthetic data is what makes the ground truth clean and the two metrics (retrieval, escalation) measurable at all. Synthetic data validates the *mechanism*; production data validates *robustness*. These are two distinct validation stages, in that order. With real deployment data, the first validation step would be to replay actual (anonymized) customer tickets against the knowledge base and compare retrieval accuracy to this synthetic baseline.

---

## ROI math

All parameters below are **estimated / synthetic**, for illustration:

- ~40 fault reports/day x 9 min saved per report (12 to 3 min diagnosis) x 20 working days x €50/h ≈ **€6,000 / month** in diagnosis time alone.

**Honest caveat:** This figure measures *only* diagnosis time. It does **not** capture the larger, harder-to-quantify value: the senior capacity freed up for product work, and the knowledge retention itself.

**Payback period:** _TBD._

---

## What I would improve next

The retrieval finding above gives a concrete reason for the techniques deferred in `BREAK_HYPOTHESES.md`: **wider candidate retrieval** (the correct article fell outside the top 5, so any reranking or reasoning layer must see more candidates or it never gets the right answer to work with), **chunking** (so a distinguishing section becomes its own vector instead of being diluted in a whole-article average), and a **reranking or agentic reasoning step** over the wider candidate set.

Also on the list: the stopping condition (preventing the agent from looping too long or giving up too early), and stress-testing the ingestion assumption above.

---

## What this demonstrates

**As a résumé line:** _TBD._

**As a pre-sales pitch:** _TBD._

---

## Demo

_Loom link, TBD (recorded after v2)._
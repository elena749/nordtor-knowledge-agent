# Break Hypotheses

Known fragilities, deliberately not yet stress-tested. Documenting the gap
rather than overselling completeness.

## Chunking: one article = one chunk
Articles are 200–500 words, well under any context limit, so each article is
embedded as a single chunk. **Untested alternative:** for longer or
multi-topic documents, sub-article chunking (by section header) might improve
retrieval precision. Not relevant at current article length; would need
revisiting if the knowledge base grew to longer documents.

## Retrieval scaling: vector vs. keyword advantage at small N
At ~15 articles the retrieval advantage of vector search over keyword matching
is small. The architecture targets real document scale (hundreds). **Untested:**
whether the measured semantic advantage at demo scale holds, grows, or shifts
at production scale.

## Advanced retrieval techniques: deliberately deferred
Hybrid search (BM25 + vector), reranking, and query rewriting are known
production enhancements, intentionally NOT built in v1. **Rationale:** the goal
is mechanism validation (does semantic retrieval bridge the language gap?), not
recall maximization. These are added only if the eval shows a specific gap they
would close — measured, not pre-emptive.
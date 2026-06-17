# Sample run — Hybrid Graph RAG on YugabyteDB 2026.1
# (Amazon Bedrock: Titan Text Embeddings V2 + Claude Sonnet 4.6)

The query step over-fetches vector candidates, re-ranks them with a
query-anchored graph-proximity signal via Reciprocal Rank Fusion (RRF), and
prunes the graph facts to the query-relevant subgraph (capped to a budget)
instead of dumping the entire one-hop neighbourhood.

```
$ python src/ingest.py
Ingested 2 chunks, 15 node-merges, 17 edge-merges.

$ python src/query.py "What is MAGE and how is Apache AGE related to YugabyteDB?"

=== Question: What is MAGE and how is Apache AGE related to YugabyteDB?

--- Query anchors (entities found in the graph) ---
  MAGE, Apache AGE, PostgreSQL, YugabyteDB

--- Fused ranking (RRF of vector + graph proximity, 2 candidates) ---
[rrf 0.0333]  vec#0 (sim 0.750)  graph#0 (score 3.5)  yugabytedb.md#101: YugabyteDB is a distributed SQL database built by Yugabyte. It is Post...
[rrf 0.0328]  vec#1 (sim 0.140)  graph#1 (score 3.0)  graphrag.md#102: Graph RAG combines vector search with a knowledge graph. Vector search...

--- Pruned graph facts (kept 18 of 30) ---
  MAGE -[RELATED_TO]-> Apache AGE
  MAGE -[RELATED_TO]-> YugabyteDB
  Apache AGE -[RELATED_TO]-> MAGE
  YugabyteDB -[RELATED_TO]-> MAGE
  MAGE -[RELATED_TO]-> The
  PostgreSQL -[RELATED_TO]-> Yugabyte
  PostgreSQL -[RELATED_TO]-> YSQL API
  YugabyteDB -[RELATED_TO]-> SQL
  YugabyteDB -[RELATED_TO]-> Graph RAG
  YugabyteDB -[RELATED_TO]-> The
  YugabyteDB -[RELATED_TO]-> YSQL API
  Graph RAG -[RELATED_TO]-> YugabyteDB
  The -[RELATED_TO]-> MAGE
  The -[RELATED_TO]-> YugabyteDB
  YSQL API -[RELATED_TO]-> PostgreSQL
  YSQL API -[RELATED_TO]-> YugabyteDB
  Yugabyte -[RELATED_TO]-> PostgreSQL
  SQL -[RELATED_TO]-> YugabyteDB

--- Fused context for the LLM ---
Chunks:
- YugabyteDB is a distributed SQL database built by Yugabyte. It is PostgreSQL compatible and runs the YSQL API on port 5433. YugabyteDB supports the pgvector extension for similarity search. The 2026.1 release line adds MAGE, a graph engine compatible with Apache AGE. MAGE lets YugabyteDB store entities and relationships as a property graph.
- Graph RAG combines vector search with a knowledge graph. Vector search retrieves chunks semantically similar to a query. The knowledge graph adds multi-hop traversal over entities and relationships. Hybrid Graph RAG fuses both signals to give a language model richer context. Meko uses Graph RAG over YugabyteDB with pgvector and MAGE.
Graph facts:
- MAGE -[RELATED_TO]-> Apache AGE
- MAGE -[RELATED_TO]-> YugabyteDB
- Apache AGE -[RELATED_TO]-> MAGE
- YugabyteDB -[RELATED_TO]-> MAGE
- MAGE -[RELATED_TO]-> The
- PostgreSQL -[RELATED_TO]-> Yugabyte
- PostgreSQL -[RELATED_TO]-> YSQL API
- YugabyteDB -[RELATED_TO]-> SQL
- YugabyteDB -[RELATED_TO]-> Graph RAG
- YugabyteDB -[RELATED_TO]-> The
- YugabyteDB -[RELATED_TO]-> YSQL API
- Graph RAG -[RELATED_TO]-> YugabyteDB
- The -[RELATED_TO]-> MAGE
- The -[RELATED_TO]-> YugabyteDB
- YSQL API -[RELATED_TO]-> PostgreSQL
- YSQL API -[RELATED_TO]-> YugabyteDB
- Yugabyte -[RELATED_TO]-> PostgreSQL
- SQL -[RELATED_TO]-> YugabyteDB

--- LLM answer ---
## MAGE and Its Relationship to YugabyteDB via Apache AGE

### What is MAGE?
**MAGE** is a **graph engine** introduced in the YugabyteDB **2026.1 release line**. It is compatible with **Apache AGE** and enables YugabyteDB to **store entities and relationships as a property graph**.

### How is Apache AGE Related to YugabyteDB?
The relationship is **indirect, through MAGE**:

1. **MAGE is compatible with Apache AGE** — it was built to align with the Apache AGE graph engine standard.
2. **MAGE is part of YugabyteDB** — it was added to YugabyteDB in the 2026.1 release line.

This means **Apache AGE is related to YugabyteDB through MAGE** as the connecting technology.

> This is also reflected in the graph facts: `Apache AGE -[RELATED_TO]-> MAGE` and `MAGE -[RELATED_TO]-> YugabyteDB`.
```

> Notes
> - Re-ranking only changes the *order* when the graph signal disagrees with
>   vector similarity; with this two-chunk corpus the vector top hit is also the
>   graph top hit, so the value shows up most clearly in the **pruned fact set**
>   (18 of 30 kept, anchor-relevant facts surfaced first) rather than a chunk
>   reshuffle. On larger corpora the fusion routinely promotes a
>   lower-vector-ranked chunk that is closer to the query entities.
> - Offline (no AWS creds) the heuristic entity extractor only finds capitalized
>   phrases, so a lowercase question may resolve **no anchors** and the pipeline
>   degrades gracefully to pure vector order — by design.
> - Cloud-mode anchor lists vary slightly run-to-run because question-entity
>   extraction uses Claude (non-deterministic).

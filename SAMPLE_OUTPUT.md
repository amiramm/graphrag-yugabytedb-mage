# Sample run — Hybrid Graph RAG on YugabyteDB 2026.1.1
# (released `yugabytedb/yugabyte:2026.1.1.1-b2`; Amazon Bedrock: Titan Text
#  Embeddings V2 + Claude Sonnet 4.6)

The query step over-fetches vector candidates, re-ranks them with a
query-anchored graph-proximity signal via Reciprocal Rank Fusion (RRF), and
prunes the graph facts to the query-relevant subgraph (capped to a budget)
instead of dumping the entire one-hop neighbourhood.

```
$ python src/ingest.py
Ingested 2 chunks, 29 node-merges, 28 edge-merges.

$ python src/query.py "What is MAGE and how is Apache AGE related to YugabyteDB?"

=== Question: What is MAGE and how is Apache AGE related to YugabyteDB?

--- Query anchors (entities found in the graph) ---
  MAGE, Apache AGE, YugabyteDB

--- Fused ranking (RRF of vector + graph proximity, 2 candidates) ---
[rrf 0.0333]  vec#0 (sim 0.750)  graph#0 (score 5.0)  yugabytedb.md#1: YugabyteDB is a distributed SQL database built by Yugabyte. It is Post...
[rrf 0.0328]  vec#1 (sim 0.140)  graph#1 (score 3.0)  graphrag.md#2: Graph RAG combines vector search with a knowledge graph. Vector search...

--- Pruned graph facts (kept 18 of 56) ---
  MAGE -[COMPATIBLE_WITH]-> Apache AGE
  Apache AGE -[COMPATIBLE_WITH]-> MAGE
  MAGE -[LETS_STORE]-> Property Graph
  MAGE -[USES]-> Meko
  MAGE -[IS_A]-> Graph Engine
  MAGE -[ADDS]-> 2026.1 Release Line
  YugabyteDB -[IS_A]-> Distributed SQL Database
  YugabyteDB -[RUNS]-> YSQL API
  YugabyteDB -[COMPATIBLE_WITH]-> PostgreSQL
  YugabyteDB -[BUILT_BY]-> Yugabyte
  YugabyteDB -[DEPLOYED_OVER]-> Graph RAG
  YugabyteDB -[USES]-> Meko
  YugabyteDB -[SUPPORTS]-> Pgvector Extension
  PostgreSQL -[COMPATIBLE_WITH]-> YugabyteDB
  2026.1 Release Line -[ADDS]-> MAGE
  Graph Engine -[IS_A]-> MAGE
  Pgvector Extension -[SUPPORTS]-> YugabyteDB
  Property Graph -[LETS_STORE]-> MAGE

--- Fused context for the LLM ---
Chunks:
- YugabyteDB is a distributed SQL database built by Yugabyte. It is PostgreSQL compatible and runs the YSQL API on port 5433. YugabyteDB supports the pgvector extension for similarity search. The 2026.1 release line adds MAGE, a graph engine compatible with Apache AGE. MAGE lets YugabyteDB store entities and relationships as a property graph.
- Graph RAG combines vector search with a knowledge graph. Vector search retrieves chunks semantically similar to a query. The knowledge graph adds multi-hop traversal over entities and relationships. Hybrid Graph RAG fuses both signals to give a language model richer context. Meko uses Graph RAG over YugabyteDB with pgvector and MAGE.
Graph facts:
- MAGE -[COMPATIBLE_WITH]-> Apache AGE
- Apache AGE -[COMPATIBLE_WITH]-> MAGE
- MAGE -[LETS_STORE]-> Property Graph
- MAGE -[USES]-> Meko
- MAGE -[IS_A]-> Graph Engine
- MAGE -[ADDS]-> 2026.1 Release Line
- YugabyteDB -[IS_A]-> Distributed SQL Database
- YugabyteDB -[RUNS]-> YSQL API
- YugabyteDB -[COMPATIBLE_WITH]-> PostgreSQL
- YugabyteDB -[BUILT_BY]-> Yugabyte
- YugabyteDB -[DEPLOYED_OVER]-> Graph RAG
- YugabyteDB -[USES]-> Meko
- YugabyteDB -[SUPPORTS]-> Pgvector Extension
- PostgreSQL -[COMPATIBLE_WITH]-> YugabyteDB
- 2026.1 Release Line -[ADDS]-> MAGE
- Graph Engine -[IS_A]-> MAGE
- Pgvector Extension -[SUPPORTS]-> YugabyteDB
- Property Graph -[LETS_STORE]-> MAGE

--- LLM answer ---
## Answer

### What is MAGE?

Based on the context, **MAGE** is a **graph engine** added in the **2026.1 release line** of YugabyteDB. It is compatible with **Apache AGE** and allows YugabyteDB to **store entities and relationships as a property graph**.

---

### How is Apache AGE related to YugabyteDB?

The context does **not describe a direct relationship** between Apache AGE and YugabyteDB. The connection is **indirect**:

- YugabyteDB (via its 2026.1 release) **includes MAGE**
- MAGE is **compatible with Apache AGE**

So Apache AGE is related to YugabyteDB only through MAGE as an intermediary — there is no direct relationship stated between Apache AGE and YugabyteDB in the provided context.
```

> Notes
> - Re-ranking only changes the *order* when the graph signal disagrees with
>   vector similarity; with this two-chunk corpus the vector top hit is also the
>   graph top hit, so the value shows up most clearly in the **pruned fact set**
>   (18 of 56 kept, anchor-relevant facts surfaced first) rather than a chunk
>   reshuffle. On larger corpora the fusion routinely promotes a
>   lower-vector-ranked chunk that is closer to the query entities.
> - Offline (no AWS creds) the heuristic entity extractor only finds capitalized
>   phrases, so a lowercase question may resolve **no anchors** and the pipeline
>   degrades gracefully to pure vector order — by design. Offline the same
>   corpus yields fewer, coarser triples (15 node-merges / 17 edge-merges vs.
>   29 / 28 in cloud mode).
> - Cloud-mode anchor lists, predicate names, and total fact counts vary
>   run-to-run because triple extraction uses Claude (non-deterministic).

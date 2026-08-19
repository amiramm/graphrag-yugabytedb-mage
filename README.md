# Hybrid Graph RAG on YugabyteDB (2026.1.1) with pgvector + MAGE

> ✅ **Validated end-to-end on released YugabyteDB `2026.1.1.1-b2`** (official
> multi-arch image, `PostgreSQL 15.12-YB-2026.1.1.1-b0`, `mage` 1.6.0,
> `vector` 0.8.0-yb-1.0) — schema, ingest, and hybrid retrieval all run
> unmodified in both offline and Amazon Bedrock modes.
>
> ⚠️ **One caveat before publishing this as a general blog:** the GA graph
> engine *requires* per-tenant properties named `meko_datapack_id`,
> `meko_user_id`, and `meko_agent_id` on every vertex and edge. This was
> originally assumed to be Meko-fork-only, but it ships in GA — a stock
> release rejects `MERGE (n:Entity {name:"x"})` with
> `missing required tenant property "meko_datapack_id"`. The Cypher here is
> therefore correct as written, but the `meko_*` naming is awkward to explain
> in public YugabyteDB material. See "Tenant properties" below.

A small, **runnable** demo of *hybrid Graph RAG* on a single distributed SQL
database. It combines two retrievers over the same YugabyteDB instance:

| Signal | Engine | What it gives you |
|--------|--------|-------------------|
| Semantic | **pgvector** (`vector` extension, `ybhnsw` index) | chunks similar in meaning to the query |
| Relational | **MAGE** (Apache AGE-compatible graph engine) | multi-hop entity/relationship facts |

The two stores cross-reference each other: every graph `Entity` node carries the
`chunk_id` it was extracted from, so a vector hit can pull in graph context and
a graph walk can point back to source chunks. Fusing both is what gives a
language model a richer, more connected context than vector search alone.

> Why one database? Vector search and the knowledge graph live in the **same**
> YugabyteDB cluster — no separate graph database, no second system to operate,
> sync, or secure. YugabyteDB 2026.1.1 ships both `pgvector` and `MAGE`.

## Architecture

```
            ┌──────────────────────── YugabyteDB (YSQL :5433) ────────────────────────┐
ingest ───▶ │  doc_chunks(content, embedding vector(1024))   ◀── pgvector ybhnsw idx   │
            │        │ chunk_id                                                         │
            │        ▼                                                                  │
            │  kg graph:  (:Entity {name, last_chunk})-[:REL]->(:Entity)  ◀── MAGE      │
            └───────────────────────────────────────────────────────────────────────────┘
query ───▶  A) vector over-fetch (candidates) ─┐
            B) graph proximity to the          ├─▶ RRF re-rank ─▶ prune facts ─▶ context for the LLM
               question's entities ────────────┘
```

The graph doesn't just expand — it **re-ranks** the vector candidates. We
over-fetch chunks, score each by how close its entities sit to the entities in
the *question*, fuse the two rankings with Reciprocal Rank Fusion (RRF), and
keep only the query-relevant graph facts (capped to a budget) — instead of
stuffing the whole one-hop neighbourhood into the context. This mirrors how
community Graph RAG systems work (Neo4j hybrid retrieval, Microsoft GraphRAG
"local search", FalkorDB).

## Prerequisites

- Docker (tested with Colima on Apple Silicon — **native arm64**, see note
  below). Nothing to build: compose pulls the official
  `yugabytedb/yugabyte:2026.1.1.1-b2` multi-arch image.
- Python 3.11+
- *Optional:* AWS credentials with Amazon Bedrock access (in a region where
  `amazon.titan-embed-text-v2:0` and a Claude model are enabled, e.g.
  `us-east-1`). With them, the demo uses Titan V2 embeddings + Claude for entity
  extraction; **without** them, it falls back to a deterministic hash embedder
  and a heuristic extractor, so the full vector + graph + fusion pipeline still
  runs offline. Configure with `AWS_REGION`, `BEDROCK_EMBED_MODEL`,
  `BEDROCK_LLM_MODEL` (see `src/common.py`).

## Quick start

```bash
# 1. Start YugabyteDB (vector + MAGE) and apply the schema
docker compose up -d               # pulls the official 2026.1.1 image
# pin a different build:  YB_IMAGE=yugabytedb/yugabyte:2026.1.1.0-b91 docker compose up -d

# 2. Install the Python deps
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 3. Ingest the sample corpus (or pass your own .md/.txt files)
python src/ingest.py

# 4. Ask a question — see vector hits, graph expansion, fused context, and an LLM answer
python src/query.py "how does yugabytedb do graph rag?"
```

## How it works

- **`sql/00_schema.sql`** — enables `vector` + `mage`, creates `doc_chunks`
  with an `ybhnsw` cosine index, and creates the `knowledge_graph` graph with
  `Entity` / `RELATED_TO` labels.
- **`src/ingest.py`** — chunks each doc, embeds + inserts it, extracts triples,
  and `MERGE`s entities/relationships into the graph (tagging nodes with the
  source `chunk_id`).
- **`src/query.py`** — the hybrid retriever. Over-fetches pgvector candidates,
  extracts the question's entities and anchors them in the graph, scores each
  candidate by graph proximity to those anchors, fuses the vector and graph
  rankings with **RRF**, prunes the graph facts to the query-relevant subgraph
  (budget-capped), prints a ranked/scored trace, and sends the fused context to
  Bedrock Claude for a grounded answer (`--no-llm` skips the LLM). The
  `retrieve(question) -> RankedContext` function is importable for use in your
  own generation pipeline.

### MAGE specifics on YugabyteDB 2026.1.1

This is worth knowing if you adapt the cypher:

- MAGE lives under the **`mag_catalog`** schema (not `ag_catalog`). Call
  `create_graph` / `create_vlabel` / `create_elabel` **unqualified** with
  `mag_catalog` on the `search_path` — schema-qualifying them, or wrapping in
  an explicit `BEGIN/COMMIT`, raises *"Commit separate ddl txn called when not
  in a separate DDL transaction"*.
- **Tenant properties are required — including on GA.** MAGE enforces
  multi-tenancy in the engine: every vertex *and* edge must carry
  `meko_datapack_id`, `meko_user_id`, `meko_agent_id` (see `tenant_props()` in
  `src/common.py`), or the statement fails with
  `missing required tenant property "meko_datapack_id"`. Verified against
  released `2026.1.1.1-b2`, so this is **not** a Meko-fork behaviour and
  `tenant_props()` cannot be dropped. The names are hard-coded in the compiled
  `mage.so`; there is no gflag or GUC to turn the requirement off — notably
  `SET mage.enable_containment = off` (a MAGE GUC, on by default) does **not**
  lift it. For a single-tenant demo, fixed values are fine.
- Only edge labels declared via `create_elabel` resolve, so all edges use the
  single `RELATED_TO` label and keep the real predicate as a property.

## A note on Apple Silicon

YugabyteDB must run **natively**. Under QEMU x86-64 emulation the `yb-master`
shared-memory allocator fails with `mmap: Cannot allocate memory (system error
12)` regardless of how much RAM the VM has — so an emulated `amd64` image is not
a workable fallback.

Good news on 2026.1.1: the official `yugabytedb/yugabyte` tags are **multi-arch**
and include native `arm64`, so Docker resolves the right architecture and there
is nothing to build. (This demo originally built a native `aarch64` image from a
release tarball because the pre-GA build published only `amd64`;
`db/Dockerfile` is retained for that case — see `db/README.md`.)

## Layout

```
docker-compose.yml     db (official 2026.1.1 image) + one-shot schema init
db/Dockerfile          optional: build from a release tarball (pre-GA builds)
sql/00_schema.sql      extensions, vector table + index, graph
src/common.py          DB connection, embeddings, entity extraction
src/ingest.py          chunk → embed → insert → extract → graph MERGE
src/query.py           hybrid retrieval: vector + graph fused
```

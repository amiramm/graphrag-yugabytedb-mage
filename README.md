# Hybrid Graph RAG on YugabyteDB (2026.1) with pgvector + MAGE

> ⚠️ **Status: demo-only, not yet publishable.** This runs against the
> **Meko-customized** MAGE build of YugabyteDB 2026.1, whose graph engine
> *requires* per-tenant properties (`meko_datapack_id`, `meko_user_id`,
> `meko_agent_id`) on every vertex and edge — these are **not** part of
> stock/GA MAGE. The demo is suitable for showing at DSS; before publishing as
> a general blog, re-verify the Cypher against a non-Meko MAGE build (the
> tenant props should then be unnecessary). See "Tenant properties" below.

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
> sync, or secure. YugabyteDB 2026.1 ships both `pgvector` and `MAGE`.

## Architecture

```
            ┌──────────────────────── YugabyteDB (YSQL :5433) ────────────────────────┐
ingest ───▶ │  doc_chunks(content, embedding vector(1024))   ◀── pgvector ybhnsw idx   │
            │        │ chunk_id                                                         │
            │        ▼                                                                  │
            │  kg graph:  (:Entity {name, last_chunk})-[:REL]->(:Entity)  ◀── MAGE      │
            └───────────────────────────────────────────────────────────────────────────┘
query ───▶  A) vector top-k  ─┐
                              ├─▶  fuse  ─▶  context for the LLM
            B) graph 1-hop  ──┘
```

## Prerequisites

- Docker (tested with Colima on Apple Silicon — **native arm64**, see note below)
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
docker compose up -d --build        # or: docker-compose up -d --build

# 2. Install the Python deps
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 3. Ingest the sample corpus (or pass your own .md/.txt files)
python src/ingest.py

# 4. Ask a question — see vector hits, graph expansion, and the fused context
python src/query.py "how does yugabytedb do graph rag?"
```

## How it works

- **`sql/00_schema.sql`** — enables `vector` + `mage`, creates `doc_chunks`
  with an `ybhnsw` cosine index, and creates the `knowledge_graph` graph with
  `Entity` / `RELATED_TO` labels.
- **`src/ingest.py`** — chunks each doc, embeds + inserts it, extracts triples,
  and `MERGE`s entities/relationships into the graph (tagging nodes with the
  source `chunk_id`).
- **`src/query.py`** — embeds the question, runs pgvector top-k, collects the
  entities in those chunks, traverses one hop in MAGE, and prints the fused
  context an LLM would consume.

### MAGE specifics on YugabyteDB 2026.1

This is worth knowing if you adapt the cypher:

- MAGE lives under the **`mag_catalog`** schema (not `ag_catalog`). Call
  `create_graph` / `create_vlabel` / `create_elabel` **unqualified** with
  `mag_catalog` on the `search_path` — schema-qualifying them, or wrapping in
  an explicit `BEGIN/COMMIT`, raises *"Commit separate ddl txn called when not
  in a separate DDL transaction"*.
- **Tenant properties (Meko build only).** This build enforces multi-tenancy
  in the engine: every vertex *and* edge must carry `meko_datapack_id`,
  `meko_user_id`, `meko_agent_id` (see `tenant_props()` in `src/common.py`).
  These names are hard-coded in the compiled `mage.so` — there is no gflag to
  disable the requirement. They are **specific to the Meko fork**; a stock/GA
  MAGE build is not expected to require them, so on a non-Meko build you can
  drop `tenant_props()` from the cypher entirely.
- Only edge labels declared via `create_elabel` resolve, so all edges use the
  single `RELATED_TO` label and keep the real predicate as a property.

## A note on Apple Silicon

YugabyteDB 2026.1 must run **natively**. The published `amd64` image crashes
under QEMU x86-64 emulation — the `yb-master` shared-memory allocator fails with
`mmap: Cannot allocate memory (system error 12)` regardless of how much RAM the
VM has. This demo therefore builds from a native `aarch64` AlmaLinux 8 release
tarball (`db/Dockerfile`), which runs at full speed.

## Layout

```
db/Dockerfile          native-arch YugabyteDB image (vector + MAGE)
docker-compose.yml     db + one-shot schema init
sql/00_schema.sql      extensions, vector table + index, graph
src/common.py          DB connection, embeddings, entity extraction
src/ingest.py          chunk → embed → insert → extract → graph MERGE
src/query.py           hybrid retrieval: vector + graph fused
```

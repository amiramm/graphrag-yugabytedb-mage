# Hybrid Graph RAG on YugabyteDB (2026.1.1) with pgvector + MAGE

> **MAGE is a Tech Preview feature.** MAGE ships in YugabyteDB 2026.1.1, but as
> a Tech Preview: you turn it on with a flag, and its behavior can change in
> later releases. In this preview, the graph engine is tailored to the Meko use
> case, so it requires three tenant properties on every vertex and edge. This
> demo supplies them for you, so the code here runs as-is. As MAGE matures to
> Early Access and then GA, YugabyteDB plans to generalize the engine so these
> properties are no longer required. To learn what this means for Cypher you
> write yourself, see [Tenant properties](#tenant-properties).
>
> **Tested with:** YugabyteDB `2026.1.1.1-b2` (official multi-arch image,
> `PostgreSQL 15.12-YB-2026.1.1.1-b0`, `mage` 1.6.0, `vector` 0.8.0-yb-1.0).
> The schema, the ingest step, and the hybrid retriever all run unchanged, both
> offline and with Amazon Bedrock.

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

```text
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
- Python 3.9 or later (tested on 3.9, 3.12, and 3.14)
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
python3 -m venv .venv && . .venv/bin/activate
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

### Work with MAGE in Tech Preview

MAGE is a Tech Preview feature in YugabyteDB 2026.1.1, so you switch it on with
the `ysql_yb_enable_mage` flag on both the master and the tserver (see
`docker-compose.yml`). Without the flag, the extension isn't there at all:

```output
ERROR:  extension "mage" is not available
```

A few behaviors differ from what you may expect from Apache AGE. Keep them in
mind when you adapt the Cypher in this demo:

- MAGE objects live in the **`mag_catalog`** schema, where Apache AGE uses
  `ag_catalog`. Put `mag_catalog` on the `search_path` and call `create_graph`,
  `create_vlabel`, and `create_elabel` without a schema prefix. If you prefix
  the call, or wrap it in `BEGIN`/`COMMIT`, it fails with *"Commit separate ddl
  txn called when not in a separate DDL transaction"*.
- MAGE creates an edge label the first time you use it, so `create_elabel` is
  optional. This demo declares one label, `RELATED_TO`, and stores the real
  predicate (such as `BUILT_BY`) as a property on the edge. That keeps the
  traversal queries simple; use as many labels as suit your data.
- Build a relationship in a single `MERGE` statement, together with the nodes it
  connects, the way `src/ingest.py` does. If you `MATCH` two nodes first and then
  `MERGE` an edge between them, the statement fails with `graph_oid and label_id
  must not be null`. `MATCH` followed by `CREATE` works if you know the edge
  doesn't exist yet.

#### Tenant properties

MAGE handles multi-tenancy inside the engine. Every vertex and every edge must
carry three properties:

- `meko_datapack_id` — must be a UUID
- `meko_user_id` — must be a UUID
- `meko_agent_id` — any string

Leave one out and the statement fails:

```output
ERROR:  missing required tenant property "meko_datapack_id"
```

Pass something that isn't a UUID and it fails too:

```output
ERROR:  invalid value for tenant property "meko_datapack_id"
DETAIL:  invalid input syntax for type uuid: "d"
```

This demo sets the three properties in `tenant_props()` (see `src/common.py`)
and adds them to every `MERGE`, so you don't have to. A single set of fixed
values is all a single-tenant demo needs. In a multi-tenant application, you
vary the values per request, which is how Meko keeps each tenant's graph
separate.

Two things to know if you write your own Cypher against this preview:

- You can't turn the requirement off. The property names are built into the
  extension, and no flag or setting removes them. In particular,
  `SET mage.enable_containment = off` does not.
- The names are shaped by the Meko use case, which MAGE is tailored to during
  Tech Preview. Expect them to change as the feature matures: the plan is to
  generalize tenancy in Early Access and GA, so graphs that don't need
  multi-tenancy won't carry these properties at all. Keep your tenant values in
  one helper, as this demo does, and you'll have one place to update.

## Run on Apple Silicon

Run YugabyteDB natively on Apple Silicon. Don't run an `amd64` image under QEMU
x86-64 emulation: `yb-master` fails to start with `mmap: Cannot allocate memory
(system error 12)`, however much memory you give the virtual machine.

You get a native image by default. The official `yugabytedb/yugabyte` tags for
2026.1.1 are multi-arch and include `arm64`, so Docker pulls the build that
matches your machine and there is nothing for you to compile. If you ever need
a version that isn't published yet, you can build an image from a release
tarball instead — see [db/README.md](db/README.md).

## Layout

```text
docker-compose.yml     db (official 2026.1.1 image) + one-shot schema init
db/Dockerfile          optional: build an image from a release tarball
sql/00_schema.sql      extensions, vector table + index, graph
src/common.py          DB connection, embeddings, entity extraction
src/ingest.py          chunk → embed → insert → extract → graph MERGE
src/query.py           hybrid retrieval: vector + graph fused
```

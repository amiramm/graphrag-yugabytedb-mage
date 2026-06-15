"""Ingest documents into the hybrid store.

For each chunk we:
  1. embed it and INSERT into doc_chunks (the vector side), and
  2. extract entity/relationship triples and MERGE them into the `kg` graph
     (the MAGE side), tagging every node with the chunk_id it came from so the
     two stores cross-reference each other.

Usage:  python src/ingest.py docs/*.md
        (with no args, ingests a small built-in sample corpus)
"""
from __future__ import annotations

import sys

from common import GRAPH_NAME, connect, embed, extract_triples, tenant_props, vec_literal

CHUNK_CHARS = 600

SAMPLE_DOCS = {
    "yugabytedb.md": """YugabyteDB is a distributed SQL database built by Yugabyte.
It is PostgreSQL compatible and runs the YSQL API on port 5433.
YugabyteDB supports the pgvector extension for similarity search.
The 2026.1 release line adds MAGE, a graph engine compatible with Apache AGE.
MAGE lets YugabyteDB store entities and relationships as a property graph.
""",
    "graphrag.md": """Graph RAG combines vector search with a knowledge graph.
Vector search retrieves chunks semantically similar to a query.
The knowledge graph adds multi-hop traversal over entities and relationships.
Hybrid Graph RAG fuses both signals to give a language model richer context.
Meko uses Graph RAG over YugabyteDB with pgvector and MAGE.
""",
}


def chunk(text: str) -> list[str]:
    words, out, buf = text.split(), [], ""
    for w in words:
        if len(buf) + len(w) + 1 > CHUNK_CHARS:
            out.append(buf.strip())
            buf = ""
        buf += " " + w
    if buf.strip():
        out.append(buf.strip())
    return out


def upsert_node(cur, name: str, chunk_id: int) -> None:
    """MERGE an Entity node by name, tagged with tenant props + source chunk.

    The tenant props are part of the MERGE key (this MAGE build requires them
    on every vertex); last_chunk is the vector<->graph back-reference.
    """
    cur.execute(
        f"SELECT * FROM cypher('{GRAPH_NAME}', $q$ "
        f'MERGE (e:Entity {{name: "{_esc(name)}", {tenant_props()}}}) '
        f"SET e.last_chunk = {int(chunk_id)} "
        "RETURN e.name $q$) AS (name agtype);"
    )


def upsert_edge(cur, subj: str, pred: str, obj: str) -> None:
    """MERGE a relationship between two entities.

    All edges use the single pre-created RELATED_TO label (MAGE only resolves
    edge labels that were declared with create_elabel); the human-readable
    predicate is kept as the `predicate` property. The edge also carries the
    required tenant props.
    """
    tp = tenant_props()
    # Single combined MERGE (the pattern mem0's MAGE store uses): MERGE both
    # endpoints and the edge in one statement. Splitting into MATCH ... MERGE
    # can leave the edge's graph_oid/label_id unresolved on this MAGE build.
    cur.execute(
        f"SELECT * FROM cypher('{GRAPH_NAME}', $q$ "
        f'MERGE (a:Entity {{name: "{_esc(subj)}", {tp}}}) '
        f'MERGE (b:Entity {{name: "{_esc(obj)}", {tp}}}) '
        f'MERGE (a)-[r:RELATED_TO {{predicate: "{_esc(_rel_type(pred))}", {tp}}}]->(b) '
        "RETURN type(r) $q$) AS (t agtype);"
    )


def _esc(s: str) -> str:
    return s.replace('"', '\\"')


def _rel_type(pred: str) -> str:
    import re

    t = re.sub(r"[^A-Za-z0-9]+", "_", pred.strip()).strip("_").upper()
    return t or "RELATED_TO"


def main(paths: list[str]) -> None:
    docs: dict[str, str] = {}
    if paths:
        for p in paths:
            with open(p, encoding="utf-8") as fh:
                docs[p] = fh.read()
    else:
        docs = SAMPLE_DOCS
        print("No paths given; ingesting built-in sample corpus.")

    conn = connect()
    n_chunks = n_nodes = n_edges = 0
    with conn.cursor() as cur:
        for doc_id, text in docs.items():
            # Idempotent re-ingest: drop any prior chunks for this doc so reruns
            # don't accumulate duplicate vector rows. (Graph nodes MERGE by
            # name, so they dedupe naturally.)
            cur.execute("DELETE FROM doc_chunks WHERE doc_id = %s;", (doc_id,))
            for i, ch in enumerate(chunk(text)):
                cur.execute(
                    "INSERT INTO doc_chunks (doc_id, chunk_no, content, embedding) "
                    "VALUES (%s, %s, %s, %s) RETURNING chunk_id;",
                    (doc_id, i, ch, vec_literal(embed(ch))),
                )
                chunk_id = cur.fetchone()[0]
                n_chunks += 1

                triples = extract_triples(ch)
                names = {t["subject"] for t in triples} | {t["object"] for t in triples}
                for name in names:
                    upsert_node(cur, name, chunk_id)
                    n_nodes += 1
                for t in triples:
                    upsert_edge(cur, t["subject"], t["predicate"], t["object"])
                    n_edges += 1

    print(f"Ingested {n_chunks} chunks, {n_nodes} node-merges, {n_edges} edge-merges.")


if __name__ == "__main__":
    main(sys.argv[1:])

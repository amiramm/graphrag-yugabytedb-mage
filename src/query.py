"""Hybrid Graph RAG retrieval.

Given a question we run two retrievers over the same YugabyteDB database and
fuse them:

  A. VECTOR  - cosine-nearest doc_chunks via the pgvector ybhnsw index.
  B. GRAPH   - starting from entities that appear in the top vector hits,
               traverse the MAGE `kg` graph one hop out to pull in related
               entities (the multi-hop signal vector search alone misses).

The fused context (chunks + graph facts) is what you would hand to an LLM.
This script prints it so the retrieval is fully inspectable.

Usage:  python src/query.py "how does yugabytedb do graph rag?"
"""
from __future__ import annotations

import sys

from common import GRAPH_NAME, connect, embed, vec_literal

TOP_K = 3


def vector_search(cur, q_embedding: list[float], k: int = TOP_K):
    cur.execute(
        "SELECT chunk_id, doc_id, content, "
        "       1 - (embedding <=> %s) AS cosine_sim "
        "FROM doc_chunks "
        "ORDER BY embedding <=> %s "
        "LIMIT %s;",
        (vec_literal(q_embedding), vec_literal(q_embedding), k),
    )
    return cur.fetchall()


def entities_for_chunk(cur, chunk_id: int) -> list[str]:
    """Graph nodes tagged with this chunk_id (the vector<->graph link)."""
    cur.execute(
        f"SELECT * FROM cypher('{GRAPH_NAME}', $q$ "
        f"MATCH (e:Entity) WHERE e.last_chunk = {int(chunk_id)} "
        "RETURN e.name $q$) AS (name agtype);"
    )
    return [_unquote(r[0]) for r in cur.fetchall()]


def neighbors(cur, name: str) -> list[tuple[str, str]]:
    """One-hop neighbours of an entity: (relationship_type, neighbour_name)."""
    cur.execute(
        f"SELECT * FROM cypher('{GRAPH_NAME}', $q$ "
        f'MATCH (a:Entity {{name: "{name}"}})-[r:RELATED_TO]-(b:Entity) '
        "RETURN r.predicate, b.name $q$) AS (rel agtype, nbr agtype);"
    )
    return [(_unquote(r[0]), _unquote(r[1])) for r in cur.fetchall()]


def _unquote(agtype_val) -> str:
    s = str(agtype_val)
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def main(question: str) -> None:
    conn = connect()
    with conn.cursor() as cur:
        q_emb = embed(question)

        # --- A. vector retrieval ---------------------------------------
        hits = vector_search(cur, q_emb)
        print(f"\n=== Question: {question}\n")
        print("--- Vector hits (pgvector) ---")
        seed_entities: list[str] = []
        for chunk_id, doc_id, content, sim in hits:
            print(f"[{sim:.3f}] {doc_id}#{chunk_id}: {content[:90]}...")
            seed_entities += entities_for_chunk(cur, chunk_id)

        # --- B. graph expansion ----------------------------------------
        seen = set()
        seed_entities = [e for e in seed_entities if not (e in seen or seen.add(e))]
        print("\n--- Graph expansion (MAGE one-hop) ---")
        graph_facts: list[str] = []
        for ent in seed_entities:
            for rel, nbr in neighbors(cur, ent):
                fact = f"{ent} -[{rel}]-> {nbr}"
                if fact not in graph_facts:
                    graph_facts.append(fact)
                    print("  " + fact)
        if not graph_facts:
            print("  (no graph neighbours found)")

        # --- C. fused context (what an LLM would receive) --------------
        print("\n--- Fused context for the LLM ---")
        print("Chunks:")
        for _, doc_id, content, _ in hits:
            print(f"  - {content.strip()}")
        print("Graph facts:")
        for f in graph_facts:
            print(f"  - {f}")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "how does yugabytedb do graph rag?"
    main(q)

"""Hybrid Graph RAG retrieval and answer generation.

Given a question we run two retrievers over the same YugabyteDB database and
*fuse* them so the graph actually re-ranks the vector hits instead of just
dumping its whole neighbourhood:

  A. VECTOR  - over-fetch the cosine-nearest doc_chunks via the pgvector
               ybhnsw index (a wide candidate set, not the final answer).
  B. GRAPH   - extract entities from the *question*, anchor them in the MAGE
               `knowledge_graph`, and score each candidate chunk by how close
               its entities sit to those anchors (overlap + 1-hop adjacency).
  C. FUSE    - Reciprocal Rank Fusion (RRF) of the vector-rank list and the
               graph-proximity-rank list picks the final chunks.
  D. PRUNE   - keep only the facts touching the anchors / winning chunks,
               capped to a budget, so the LLM context is the relevant
               subgraph rather than the full one-hop dump.

This mirrors how community Graph RAG systems work (Neo4j hybrid retrieval,
Microsoft GraphRAG "local search", FalkorDB): over-fetch, re-rank with the
graph signal, prune to the query-relevant subgraph.

`retrieve(question)` returns a structured `RankedContext` that a generation
step can consume directly; the CLI prints a ranked, scored trace and (unless
--no-llm or no AWS creds) hands the fused context to Bedrock Claude.

Usage:  python src/query.py "how does yugabytedb do graph rag?"
        python src/query.py --no-llm "how does yugabytedb do graph rag?"
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from common import (
    GRAPH_NAME,
    answer_with_context,
    connect,
    embed,
    query_entities,
    vec_literal,
)

# Over-fetch a wide candidate set, then let fusion pick the survivors. The gap
# between CANDIDATE_K and FINAL_K is what gives the graph signal room to
# re-order chunks (a low vector hit can be promoted, a high one demoted).
CANDIDATE_K = 10
FINAL_K = 4

# RRF constant (standard 60): dampens the influence of absolute rank position
# so neither retriever's head dominates. score = sum 1/(RRF_K + rank).
RRF_K = 60

# Graph-proximity weights: a chunk entity that *is* a query anchor counts more
# than one merely adjacent to an anchor (the 1-hop decay term).
ANCHOR_WEIGHT = 1.0
HOP_WEIGHT = 0.5

# Budget cap on facts handed to the LLM — the whole point is to stop stuffing
# the context window with the entire neighbourhood.
MAX_FACTS = 18


@dataclass
class Chunk:
    chunk_id: int
    doc_id: str
    content: str
    cosine_sim: float
    vector_rank: int
    entities: list[str] = field(default_factory=list)
    graph_score: float = 0.0
    graph_rank: int | None = None
    rrf_score: float = 0.0


@dataclass
class RankedContext:
    """Everything a generation step needs, plus the trace for inspection."""

    question: str
    anchors: list[str]          # query entities resolved in the graph
    chunks: list[Chunk]         # final, fusion-ranked (top FINAL_K)
    facts: list[str]            # pruned, query-relevant graph facts
    candidates: int             # how many vector candidates were considered
    facts_total: int            # candidate facts before the budget cap
    facts_kept: int             # facts that survived pruning


# --------------------------------------------------------------------------
# Retrievers
# --------------------------------------------------------------------------
def vector_search(cur, q_embedding: list[float], k: int = CANDIDATE_K):
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
    """Graph nodes tagged with this chunk_id (the vector<->graph link).

    Note: a node's `last_chunk` holds only the *latest* chunk it was seen in
    (MERGE semantics during ingest), so an entity spanning several chunks links
    to one. The query-anchored signal below doesn't depend on this being exact
    — it scores by entity *name* membership in the anchor/neighbour sets.
    """
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
        f'MATCH (a:Entity {{name: "{_esc(name)}"}})-[r]-(b:Entity) '
        "RETURN r.predicate, b.name $q$) AS (rel agtype, nbr agtype);"
    )
    return [(_unquote(r[0]), _unquote(r[1])) for r in cur.fetchall()]


def resolve_anchors(cur, names: list[str]) -> list[str]:
    """Resolve question entities to canonical node names that exist in the graph.

    Case-insensitive so "yugabytedb" in a question matches the stored
    "YugabyteDB" node. Returns the canonical names (deduped, order-preserving).
    """
    seen: set[str] = set()
    anchors: list[str] = []
    for name in names:
        cur.execute(
            f"SELECT * FROM cypher('{GRAPH_NAME}', $q$ "
            f'MATCH (e:Entity) WHERE toLower(e.name) = "{_esc(name.lower())}" '
            "RETURN e.name $q$) AS (name agtype);"
        )
        for row in cur.fetchall():
            canon = _unquote(row[0])
            if canon not in seen:
                seen.add(canon)
                anchors.append(canon)
    return anchors


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------
def _graph_proximity(chunk_entities: set[str], anchors: set[str], anchor_nbrs: set[str]) -> float:
    """Score a chunk's entities by closeness to the query anchors."""
    direct = len(chunk_entities & anchors)
    adjacent = len(chunk_entities & anchor_nbrs - anchors)
    return ANCHOR_WEIGHT * direct + HOP_WEIGHT * adjacent


def _rrf(*ranks: int | None) -> float:
    """Reciprocal Rank Fusion: sum 1/(RRF_K + rank) over the lists a chunk is in."""
    return sum(1.0 / (RRF_K + r) for r in ranks if r is not None)


def retrieve(question: str) -> RankedContext:
    """Run the hybrid pipeline and return a fusion-ranked, pruned context.

    This is the importable entry point a generation step calls.
    """
    conn = connect()
    with conn.cursor() as cur:
        q_emb = embed(question)

        # --- A. over-fetch vector candidates ---------------------------
        candidates: list[Chunk] = []
        for rank, (chunk_id, doc_id, content, sim) in enumerate(vector_search(cur, q_emb)):
            c = Chunk(chunk_id, doc_id, content, float(sim), rank)
            c.entities = entities_for_chunk(cur, chunk_id)
            candidates.append(c)

        # --- B. anchor the question in the graph, score proximity ------
        anchors = resolve_anchors(cur, query_entities(question))
        anchor_set = set(anchors)
        # Cache one-hop neighbours of every anchor (also drives fact pruning).
        anchor_nbr_edges: dict[str, list[tuple[str, str]]] = {a: neighbors(cur, a) for a in anchors}
        anchor_nbrs = {nbr for edges in anchor_nbr_edges.values() for _, nbr in edges}

        for c in candidates:
            c.graph_score = _graph_proximity(set(c.entities), anchor_set, anchor_nbrs)

        # graph rank: only chunks with a positive signal are "in" the graph list
        graph_ranked = sorted(
            [c for c in candidates if c.graph_score > 0],
            key=lambda c: c.graph_score,
            reverse=True,
        )
        for gr, c in enumerate(graph_ranked):
            c.graph_rank = gr

        # --- C. RRF fusion → final chunk order -------------------------
        for c in candidates:
            c.rrf_score = _rrf(c.vector_rank, c.graph_rank)
        ranked = sorted(candidates, key=lambda c: c.rrf_score, reverse=True)[:FINAL_K]

        # --- D. prune facts to the query-relevant subgraph -------------
        facts, facts_total = _prune_facts(cur, anchors, anchor_nbr_edges, ranked)

    return RankedContext(
        question=question,
        anchors=anchors,
        chunks=ranked,
        facts=facts,
        candidates=len(candidates),
        facts_total=facts_total,
        facts_kept=len(facts),
    )


def _prune_facts(cur, anchors, anchor_nbr_edges, ranked_chunks) -> tuple[list[str], int]:
    """Keep facts touching the anchors / winning chunks, capped to MAX_FACTS.

    Candidate facts come from (a) the anchors' one-hop edges (already fetched)
    and (b) the winning chunks' entities. Each fact is scored so anchor-touching
    edges and edges that *bridge* an anchor to a winning-chunk entity rank above
    incidental ones; we then take the top MAX_FACTS.
    """
    anchor_set = set(anchors)
    chunk_entities = {e for c in ranked_chunks for e in c.entities}

    # subject -> (predicate, object); dedupe with a directed key.
    scored: dict[tuple[str, str, str], float] = {}

    def consider(subj: str, rel: str, obj: str) -> None:
        a, b = subj in anchor_set, obj in anchor_set
        ca, cb = subj in chunk_entities, obj in chunk_entities
        # Skip facts that don't touch anything relevant.
        if not (a or b or ca or cb):
            return
        score = 0.0
        score += ANCHOR_WEIGHT * (a + b)            # touches an anchor
        score += HOP_WEIGHT * (ca + cb)             # touches a winning chunk
        # Bridge bonus: anchor on one end, winning-chunk entity on the other.
        if (a and cb) or (b and ca):
            score += 1.0
        scored[(subj, rel, obj)] = max(scored.get((subj, rel, obj), 0.0), score)

    # (a) anchors' cached edges (neighbors() returns undirected -[r]- pairs).
    for anchor, edges in anchor_nbr_edges.items():
        for rel, nbr in edges:
            consider(anchor, rel, nbr)

    # (b) edges incident to the winning chunks' entities (not already covered).
    for ent in chunk_entities:
        for rel, nbr in neighbors(cur, ent):
            consider(ent, rel, nbr)

    ordered = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    kept = [f"{s} -[{r}]-> {o}" for (s, r, o), _ in ordered[:MAX_FACTS]]
    return kept, len(scored)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _unquote(agtype_val) -> str:
    s = str(agtype_val)
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def _esc(s: str) -> str:
    return s.replace('"', '\\"')


def build_context(ctx: RankedContext) -> str:
    """Format the fused retrieval context passed to the LLM."""
    lines = ["Chunks:"]
    for c in ctx.chunks:
        lines.append(f"- {c.content.strip()}")
    lines.append("Graph facts:")
    for fact in ctx.facts:
        lines.append(f"- {fact}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(question: str, *, use_llm: bool = True) -> None:
    ctx = retrieve(question)

    print(f"\n=== Question: {question}\n")
    print(f"--- Query anchors (entities found in the graph) ---")
    print("  " + (", ".join(ctx.anchors) if ctx.anchors else "(none — falling back to vector order)"))

    print(f"\n--- Fused ranking (RRF of vector + graph proximity, {ctx.candidates} candidates) ---")
    for c in ctx.chunks:
        gr = "-" if c.graph_rank is None else str(c.graph_rank)
        print(
            f"[rrf {c.rrf_score:.4f}]  vec#{c.vector_rank} (sim {c.cosine_sim:.3f})  "
            f"graph#{gr} (score {c.graph_score:.1f})  {c.doc_id}#{c.chunk_id}: "
            f"{c.content[:70].strip()}..."
        )

    print(f"\n--- Pruned graph facts (kept {ctx.facts_kept} of {ctx.facts_total}) ---")
    for fact in ctx.facts:
        print("  " + fact)
    if not ctx.facts:
        print("  (no relevant graph facts)")

    print("\n--- Fused context for the LLM ---")
    print(build_context(ctx))

    if not use_llm:
        return

    print("\n--- LLM answer ---")
    answer = answer_with_context(question, build_context(ctx))
    if answer is None:
        print("(skipped: Bedrock unavailable — set AWS credentials to generate an answer)")
    else:
        print(answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid Graph RAG query over YugabyteDB.")
    parser.add_argument("question", nargs="?", default="how does yugabytedb do graph rag?")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="print retrieval context only; do not call the LLM",
    )
    args = parser.parse_args()
    main(args.question, use_llm=not args.no_llm)

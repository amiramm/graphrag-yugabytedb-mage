"""Shared helpers: DB connection, embeddings, and LLM entity extraction.

The demo runs in two modes:

* **Cloud mode** (default when AWS creds resolve): Amazon Bedrock provides
  Titan V2 embeddings and a Claude model for entity/relationship extraction.
* **Offline mode** (no creds): a deterministic hash embedder + a regex-ish
  heuristic extractor stand in, so the *plumbing* (vector search + MAGE
  traversal + fusion) is still fully exercisable without network access.

Both paths write to the same YugabyteDB schema, so the retrieval code is
identical regardless of mode.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct

import psycopg

EMBED_DIM = 1024
GRAPH_NAME = "knowledge_graph"
BEDROCK_EMBED_MODEL = os.environ.get("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
BEDROCK_LLM_MODEL = os.environ.get(
    "BEDROCK_LLM_MODEL", "us.anthropic.claude-sonnet-4-6-20250930-v1:0"
)

# YugabyteDB 2026.1's MAGE build enforces multi-tenancy in the engine: every
# graph vertex and edge MUST carry these three string properties or cypher
# CREATE/MERGE raises "missing required tenant property". There is no session
# GUC for them — they are inlined into each cypher clause. For a single-tenant
# demo we use fixed values; a real multi-tenant app varies them per request.
TENANT_DATAPACK_ID = os.environ.get("MEKO_DATAPACK_ID", "00000000-0000-0000-0000-000000000001")
TENANT_USER_ID = os.environ.get("MEKO_USER_ID", "00000000-0000-0000-0000-000000000002")
TENANT_AGENT_ID = os.environ.get("MEKO_AGENT_ID", "graphrag-demo")


def tenant_props() -> str:
    """Cypher property fragment that satisfies MAGE's tenant requirement.

    Returns e.g. `meko_datapack_id:"...", meko_user_id:"...", meko_agent_id:"..."`
    to be spliced into a node/edge property map.
    """
    return (
        f'meko_datapack_id:"{TENANT_DATAPACK_ID}", '
        f'meko_user_id:"{TENANT_USER_ID}", '
        f'meko_agent_id:"{TENANT_AGENT_ID}"'
    )


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def connect() -> psycopg.Connection:
    """Open a YugabyteDB (YSQL) connection and put MAGE on the search_path."""
    dsn = os.environ.get(
        "YB_DSN",
        "host=127.0.0.1 port=5433 dbname=yugabyte user=yugabyte password=yugabyte",
    )
    conn = psycopg.connect(dsn, autocommit=True)
    with conn.cursor() as cur:
        # MAGE objects live in mag_catalog; cypher() must resolve there.
        cur.execute('SET search_path = mag_catalog, "$user", public;')
    return conn


def vec_literal(vec: list[float]) -> str:
    """Render a Python list as a pgvector literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# --------------------------------------------------------------------------
# Bedrock client (lazy; only created if creds are available)
# --------------------------------------------------------------------------
_bedrock = None
_bedrock_tried = False


def _bedrock_client():
    global _bedrock, _bedrock_tried
    if _bedrock_tried:
        return _bedrock
    _bedrock_tried = True
    try:
        import boto3

        sess = boto3.Session()
        if sess.get_credentials() is None:
            return None
        region = os.environ.get("AWS_REGION") or sess.region_name or "us-east-1"
        _bedrock = sess.client("bedrock-runtime", region_name=region)
    except Exception:
        _bedrock = None
    return _bedrock


# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------
def _hash_embed(text: str) -> list[float]:
    """Deterministic offline embedding: hash tokens into a fixed-width vector."""
    vec = [0.0] * EMBED_DIM
    for tok in text.lower().split():
        h = hashlib.sha256(tok.encode()).digest()
        # spread each token across a few dimensions
        for i in range(4):
            idx = struct.unpack_from(">I", h, i * 4)[0] % EMBED_DIM
            sign = 1.0 if (h[16 + i] & 1) else -1.0
            vec[idx] += sign
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


def embed(text: str) -> list[float]:
    bc = _bedrock_client()
    if bc is None:
        return _hash_embed(text)
    resp = bc.invoke_model(
        modelId=BEDROCK_EMBED_MODEL,
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIM, "normalize": True}),
    )
    return json.loads(resp["body"].read())["embedding"]


# --------------------------------------------------------------------------
# Entity / relationship extraction
# --------------------------------------------------------------------------
EXTRACT_PROMPT = """Extract entities and relationships from the text as JSON.
Return ONLY a JSON object: {"triples": [{"subject": "...", "predicate": "...", "object": "..."}]}.
Use short canonical entity names (Title Case). Text:

%s"""


def extract_triples(text: str) -> list[dict[str, str]]:
    bc = _bedrock_client()
    if bc is None:
        return _heuristic_triples(text)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": EXTRACT_PROMPT % text}],
    }
    try:
        resp = bc.invoke_model(modelId=BEDROCK_LLM_MODEL, body=json.dumps(body))
        txt = json.loads(resp["body"].read())["content"][0]["text"]
        start, end = txt.find("{"), txt.rfind("}")
        data = json.loads(txt[start : end + 1])
        return [t for t in data.get("triples", []) if t.get("subject") and t.get("object")]
    except Exception:
        return _heuristic_triples(text)


def _heuristic_triples(text: str) -> list[dict[str, str]]:
    """Very small fallback: link capitalized phrases that co-occur in a line."""
    import re

    triples: list[dict[str, str]] = []
    for line in text.splitlines():
        ents = re.findall(r"[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*", line)
        ents = [e for e in ents if len(e) > 2]
        for i in range(len(ents) - 1):
            triples.append({"subject": ents[i], "predicate": "RELATED_TO", "object": ents[i + 1]})
    return triples

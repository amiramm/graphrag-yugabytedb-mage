# Sample run — Hybrid Graph RAG on YugabyteDB 2026.1
# (Amazon Bedrock: Titan Text Embeddings V2 + Claude Sonnet 4.6)

```
$ python src/ingest.py
Ingested 2 chunks, 29 node-merges, 28 edge-merges.

$ python src/query.py "how does yugabytedb do graph rag?"

=== Question: how does yugabytedb do graph rag?

--- Vector hits (pgvector) ---
[0.547] yugabytedb.md#501: YugabyteDB is a distributed SQL database built by Yugabyte. It is PostgreSQL compatible an...
[0.497] graphrag.md#502: Graph RAG combines vector search with a knowledge graph. Vector search retrieves chunks se...

--- Graph expansion (MAGE one-hop) ---
  2026.1 Release Line -[ADDS]-> MAGE
  Similarity Search -[USED_FOR]-> Pgvector Extension
  Distributed SQL Database -[IS_A]-> YugabyteDB
  Yugabyte -[BUILT_BY]-> YugabyteDB
  Apache AGE -[COMPATIBLE_WITH]-> MAGE
  YSQL API -[RUNS]-> YugabyteDB
  YSQL API -[RUNS_ON_PORT]-> 5433
  Pgvector Extension -[SUPPORTS]-> YugabyteDB
  Pgvector Extension -[USED_FOR]-> Similarity Search
  Graph Engine -[IS_A]-> MAGE
  Property Graph -[LETS_STORE]-> MAGE
  Property Graph -[CONTAINS]-> Entities
  Property Graph -[CONTAINS]-> Relationships
  PostgreSQL -[COMPATIBLE_WITH]-> YugabyteDB
  5433 -[RUNS_ON_PORT]-> YSQL API
  Knowledge Graph -[ADDS]-> Multi-Hop Traversal
  Knowledge Graph -[COMBINES]-> Graph RAG
  Knowledge Graph -[FUSES]-> Hybrid Graph RAG
  Pgvector -[USES]-> Meko
  Chunks -[SEMANTICALLY_SIMILAR_TO]-> Query
  Chunks -[RETRIEVES]-> Vector Search
  Meko -[USES]-> Graph RAG
  Meko -[USES]-> MAGE
  Meko -[USES]-> YugabyteDB
  Meko -[USES]-> Pgvector
  Relationships -[CONTAINS]-> Property Graph
  Relationships -[OVER]-> Multi-Hop Traversal
  Vector Search -[COMBINES]-> Graph RAG
  Vector Search -[FUSES]-> Hybrid Graph RAG
  Vector Search -[RETRIEVES]-> Chunks
  YugabyteDB -[SUPPORTS]-> Pgvector Extension
  YugabyteDB -[IS_A]-> Distributed SQL Database
  YugabyteDB -[USES]-> Meko
  YugabyteDB -[RUNS_OVER]-> Graph RAG
  YugabyteDB -[RUNS]-> YSQL API
  YugabyteDB -[COMPATIBLE_WITH]-> PostgreSQL
  YugabyteDB -[BUILT_BY]-> Yugabyte
  Language Model -[GIVES_RICHER_CONTEXT_TO]-> Hybrid Graph RAG
  Query -[SEMANTICALLY_SIMILAR_TO]-> Chunks
  MAGE -[ADDS]-> 2026.1 Release Line
  MAGE -[LETS_STORE]-> Property Graph
  MAGE -[USES]-> Meko
  MAGE -[IS_A]-> Graph Engine
  MAGE -[COMPATIBLE_WITH]-> Apache AGE
  Graph RAG -[USES]-> Meko
  Graph RAG -[COMBINES]-> Vector Search
  Graph RAG -[RUNS_OVER]-> YugabyteDB
  Graph RAG -[COMBINES]-> Knowledge Graph
  Multi-Hop Traversal -[OVER]-> Entities
  Multi-Hop Traversal -[ADDS]-> Knowledge Graph
  Multi-Hop Traversal -[OVER]-> Relationships
  Entities -[OVER]-> Multi-Hop Traversal
  Entities -[CONTAINS]-> Property Graph
  Hybrid Graph RAG -[GIVES_RICHER_CONTEXT_TO]-> Language Model
  Hybrid Graph RAG -[FUSES]-> Vector Search
  Hybrid Graph RAG -[FUSES]-> Knowledge Graph

--- Fused context for the LLM ---
Chunks:
  - YugabyteDB is a distributed SQL database built by Yugabyte. It is PostgreSQL compatible and runs the YSQL API on port 5433. YugabyteDB supports the pgvector extension for similarity search. The 2026.1 release line adds MAGE, a graph engine compatible with Apache AGE. MAGE lets YugabyteDB store entities and relationships as a property graph.
  - Graph RAG combines vector search with a knowledge graph. Vector search retrieves chunks semantically similar to a query. The knowledge graph adds multi-hop traversal over entities and relationships. Hybrid Graph RAG fuses both signals to give a language model richer context. Meko uses Graph RAG over YugabyteDB with pgvector and MAGE.
Graph facts:
  - 2026.1 Release Line -[ADDS]-> MAGE
  - Similarity Search -[USED_FOR]-> Pgvector Extension
  - Distributed SQL Database -[IS_A]-> YugabyteDB
  - Yugabyte -[BUILT_BY]-> YugabyteDB
  - Apache AGE -[COMPATIBLE_WITH]-> MAGE
  - YSQL API -[RUNS]-> YugabyteDB
  - YSQL API -[RUNS_ON_PORT]-> 5433
  - Pgvector Extension -[SUPPORTS]-> YugabyteDB
  - Pgvector Extension -[USED_FOR]-> Similarity Search
  - Graph Engine -[IS_A]-> MAGE
  - Property Graph -[LETS_STORE]-> MAGE
  - Property Graph -[CONTAINS]-> Entities
  - Property Graph -[CONTAINS]-> Relationships
  - PostgreSQL -[COMPATIBLE_WITH]-> YugabyteDB
  - 5433 -[RUNS_ON_PORT]-> YSQL API
  - Knowledge Graph -[ADDS]-> Multi-Hop Traversal
  - Knowledge Graph -[COMBINES]-> Graph RAG
  - Knowledge Graph -[FUSES]-> Hybrid Graph RAG
  - Pgvector -[USES]-> Meko
  - Chunks -[SEMANTICALLY_SIMILAR_TO]-> Query
  - Chunks -[RETRIEVES]-> Vector Search
  - Meko -[USES]-> Graph RAG
  - Meko -[USES]-> MAGE
  - Meko -[USES]-> YugabyteDB
  - Meko -[USES]-> Pgvector
  - Relationships -[CONTAINS]-> Property Graph
  - Relationships -[OVER]-> Multi-Hop Traversal
  - Vector Search -[COMBINES]-> Graph RAG
  - Vector Search -[FUSES]-> Hybrid Graph RAG
  - Vector Search -[RETRIEVES]-> Chunks
  - YugabyteDB -[SUPPORTS]-> Pgvector Extension
  - YugabyteDB -[IS_A]-> Distributed SQL Database
  - YugabyteDB -[USES]-> Meko
  - YugabyteDB -[RUNS_OVER]-> Graph RAG
  - YugabyteDB -[RUNS]-> YSQL API
  - YugabyteDB -[COMPATIBLE_WITH]-> PostgreSQL
  - YugabyteDB -[BUILT_BY]-> Yugabyte
  - Language Model -[GIVES_RICHER_CONTEXT_TO]-> Hybrid Graph RAG
  - Query -[SEMANTICALLY_SIMILAR_TO]-> Chunks
  - MAGE -[ADDS]-> 2026.1 Release Line
  - MAGE -[LETS_STORE]-> Property Graph
  - MAGE -[USES]-> Meko
  - MAGE -[IS_A]-> Graph Engine
  - MAGE -[COMPATIBLE_WITH]-> Apache AGE
  - Graph RAG -[USES]-> Meko
  - Graph RAG -[COMBINES]-> Vector Search
  - Graph RAG -[RUNS_OVER]-> YugabyteDB
  - Graph RAG -[COMBINES]-> Knowledge Graph
  - Multi-Hop Traversal -[OVER]-> Entities
  - Multi-Hop Traversal -[ADDS]-> Knowledge Graph
  - Multi-Hop Traversal -[OVER]-> Relationships
  - Entities -[OVER]-> Multi-Hop Traversal
  - Entities -[CONTAINS]-> Property Graph
  - Hybrid Graph RAG -[GIVES_RICHER_CONTEXT_TO]-> Language Model
  - Hybrid Graph RAG -[FUSES]-> Vector Search
  - Hybrid Graph RAG -[FUSES]-> Knowledge Graph
```

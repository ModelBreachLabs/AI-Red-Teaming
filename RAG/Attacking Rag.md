# RAG Attack Surface 

**Unlike traditional applications, external data is not just stored — it directly influences model reasoning at inference time.**

The main RAG-specific attack surfaces are:

- Document ingestion: Untrusted, outdated, or malicious documents can enter the system if validation is weak.
- Embedding generation: Text is converted into numerical vectors, making intent and safety harder to inspect manually.
- Similarity-based retrieval: Documents are selected by semantic relevance, not correctness, trust, or safety.
- Context injection: Retrieved documents are injected directly into the model’s context window before generation.

**Retrieval abuse** is a RAG-specific attack technique in which unintended or malicious documents influence model output via retrieval.

- **Passive poisoning:** Malicious content is ingested once and left in the knowledge base. The attacker waits for normal queries to retrieve it.
- **Active manipulation:** Content is deliberately crafted to rank highly for common or sensitive queries.

### Context Manipulation 

- In RAG systems, retrieved documents are injected into the model’s context window before generation.

## Training Data Poisoning



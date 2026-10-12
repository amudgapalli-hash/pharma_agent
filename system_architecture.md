[PubMed / PDF Data Source] 
         │
         ▼
 1. Document Ingestion Pipeline ──► Text Processing & Chunking
         │
         ▼
 2. Structured Data Extraction Agent ──► JSON Schema Validation (Ollama + Pydantic)
         │
         ▼
 3. Protocol Drafting Agent ──► Generates Medical Write-up (FDA E6(R2) Guidelines)

 ********************************
 LangGraph Enterprise Workflow Architecture
 The framework relies on a state-machine architecture. Instead of a linear pipeline, LangGraph routes control based on evaluation flags, allowing the FDA Critic to reject the document and dynamically loop back to the Medical Writer until it meets strict verification criteria.
 
  [ Batch PDF Directory ]
                 │ (Asynchronous Ingestion)
                 ▼
       [ Vector DB (Qdrant) ]
                 │
                 ▼
  ┌─────────► [ Node 1: Writer Agent ]
  │                  │
  │                  ▼
  │           [ Node 2: FDA Critic Agent ]
  │                  │
  │                  ├─── [ Rejected: Fails Criteria ] ──┐
  └─── Loop Back ────┘                                   │
                                                         ▼
                                              [ Node 3: Final Output ]
# Pharma Agent - Architecture & Implementation Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Component Breakdown](#component-breakdown)
5. [Workflow & Data Flow](#workflow--data-flow)
6. [LangGraph State Machine](#langgraph-state-machine)
7. [API Endpoints](#api-endpoints)
8. [Database Schema](#database-schema)
9. [Security Architecture](#security-architecture)
10. [Deployment & Scalability](#deployment--scalability)
11. [Production Considerations](#production-considerations)

---

## Project Overview

**Pharma Agent** is an enterprise-grade, containerized multi-agent system for automated pharmaceutical compliance analysis and medical writing. It leverages LangGraph for state-machine orchestration, Retrieval-Augmented Generation (RAG) for document processing, and FDA E6(R2) compliance criteria enforcement.

### Key Features
- **Multi-Agent Orchestration**: Writer → Critic → Compliance Loop
- **RAG-Powered**: Integrates PubMed/PDF ingestion with vector embeddings
- **FDA Compliance Enforcement**: Automated critic agent validates outputs against regulatory standards
- **Role-Based Access Control (RBAC)**: Team-scoped data visibility
- **On-Premise Data Governance**: All data remains within enterprise boundary (localhost)
- **Containerized Stack**: Docker Compose orchestration with 5 integrated services

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                              │
│            Streamlit Web Dashboard (Port 8501)               │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP Requests + Bearer Token
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  API LAYER (Port 8000)                       │
│    FastAPI Backend with JWT Authentication                  │
│    • /token - Authentication                                │
│    • /compliance/audits - Retrieve team-scoped data         │
│    • LangGraph Agent Router                                 │
└──┬──────────────┬────────────────┬──────────────┬───────────┘
   │              │                │              │
   ▼              ▼                ▼              ▼
┌────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐
│ PostgreSQL │ │   Qdrant   │ │  Ollama  │ │ LangGraph    │
│ Database   │ │ Vector DB  │ │  Local   │ │ Workflows    │
│ (Port 5432)│ │(Port 6333) │ │  LLM     │ │ (State Graph)│
│            │ │            │ │(Port     │ │              │
│ Metadata & │ │ Embeddings │ │ 11434)  │ │ Agent Nodes: │
│ Audits     │ │ & Docs     │ │         │ │ • Retrieve   │
│            │ │            │ │         │ │ • Writer     │
└────────────┘ └────────────┘ └─────────┘ │ • Critic     │
                                          │ • Route      │
                                          └──────────────┘
```

### Container Architecture

```
Docker Compose Network: sci_network (bridge)
├── fastapi_backend (Port 8000)
│   ├── Depends on: postgres_db, qdrant_vector
│   ├── Environment: JWT_SECRET, POSTGRES_URL, QDRANT_URL, OLLAMA_URL
│   └── Volumes: None (stateless)
│
├── streamlit_dashboard (Port 8501)
│   ├── Depends on: fastapi_backend
│   ├── Environment: API_URL (http://fastapi_backend:8000)
│   └── Volumes: None (stateless)
│
├── postgres_db (Port 5432)
│   ├── Image: postgres:15-alpine
│   ├── Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
│   └── Volumes: postgres_data (persistent)
│
├── qdrant_vector (Port 6333-6334)
│   ├── Image: qdrant/qdrant:latest
│   ├── Environment: None
│   └── Volumes: qdrant_data (persistent)
│
└── ollama_llm (Port 11434)
    ├── Image: ollama/ollama:latest
    ├── Environment: None (GPU deployment optional)
    └── Volumes: ollama_data (persistent)
```

---

## Technology Stack

### Backend Framework
| Component | Version | Purpose |
|-----------|---------|---------|
| **FastAPI** | ≥0.100.0 | REST API framework with automatic OpenAPI docs |
| **Uvicorn** | ≥0.22.0 | ASGI server for FastAPI |
| **Pydantic** | ≥2.0 | Data validation & serialization |
| **python-jose** | ≥3.3.0 | JWT token creation/validation |
| **passlib[bcrypt]** | ≥1.7.4 | Password hashing (bcrypt) |

### Frontend Framework
| Component | Version | Purpose |
|-----------|---------|---------|
| **Streamlit** | latest | Interactive web dashboard |
| **Pandas** | (via streamlit) | DataFrames for audit display |
| **Requests** | (via python) | HTTP client for API communication |

### AI/ML Orchestration
| Component | Role | Function |
|-----------|------|----------|
| **LangGraph** | Workflow Engine | State-machine orchestration for multi-agent workflows |
| **Ollama** | Local LLM | On-premise language model execution |
| **Qdrant** | Vector Database | Semantic search & RAG embeddings |
| **LangChain** | (via agent.py) | Document loaders & text splitters |

### Infrastructure
| Component | Image | Role |
|-----------|-------|------|
| **PostgreSQL** | postgres:15-alpine | Relational DB for audit metadata |
| **Qdrant** | qdrant/qdrant:latest | Vector store for embeddings |
| **Docker Compose** | v3.8 spec | Multi-container orchestration |
| **Docker Network** | bridge (sci_network) | Service-to-service communication |

---

## Component Breakdown

### 1. FastAPI Backend (`app/main.py`)

**Purpose**: Secure REST API with JWT authentication and compliance data endpoints.

**Key Classes & Functions**:

#### Models (Pydantic)
```python
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    team: str
```

#### Core Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `login()` | `POST /token` | Authenticates user, returns JWT bearer token |
| `get_audits()` | `GET /compliance/audits` | Returns team-scoped compliance audit data |
| `create_access_token()` | Internal | Encodes JWT with 60-min expiry |
| `get_current_user()` | Dependency | Validates & extracts User from bearer token |

#### Authentication Flow

```
Client Credentials (username, password)
         │
         ▼
POST /token
         │
         ▼
Lookup in USER_DB → bcrypt.verify() → JWT encode
         │
         ▼
{ access_token, token_type: "bearer" }
         │
         ▼
Client stores in session state
         │
         ▼
Authorization: Bearer <token>
```

#### Authorization Model
- **RBAC Scoping**: Each user belongs to a `team` (BioGenomics, QuantumChem)
- **Token Claims**: JWT payload contains `{"sub": username, "team": team_name}`
- **Endpoint Access**: `/compliance/audits` filters results by `current_user.team`

**Database (Mock):**
```python
USER_DB = {
    "dr_smith": {"hashed_password": bcrypt(...), "team": "BioGenomics"},
    "dr_jones": {"hashed_password": bcrypt(...), "team": "QuantumChem"}
}

COMPLIANCE_DATA = [
    {"id": 1, "team": "BioGenomics", "metric": "Data Privacy", "score": 92, ...},
    # ... scoped to team
]
```

---

### 2. Streamlit Dashboard (`app/app.py`)

**Purpose**: Interactive web UI for login, authentication, and compliance metric visualization.

**UI Components**:

#### Layout
```
┌─ Sidebar (Left Panel)
│  ├─ "Team Authentication" (if not logged in)
│  │  ├─ Username input
│  │  ├─ Password input
│  │  └─ Login button
│  │
│  └─ Session Status (if logged in)
│     ├─ "Authenticated session active"
│     └─ Logout button
│
└─ Main Panel (Right Panel)
   ├─ Title: "🔬 Scientific Compliance Dashboard"
   ├─ Subheader: "📊 Compliance Metrics for Team: <TEAM_NAME>"
   ├─ KPI Cards:
   │  ├─ Total Audits Run: <count>
   │  ├─ Average Score: <%.1f>%
   │  └─ Passed Audits: <count>
   ├─ Charts:
   │  ├─ Bar Chart: Performance by Metric
   │  └─ Table: Raw Audit Log
```

#### Session State Management
```python
st.session_state = {
    "token": None or "<JWT>",
    "team": None or "<team_name>"
}
```

#### Data Fetch Flow
```
User Login
    │
    ▼
POST /token → Store token in st.session_state
    │
    ▼
Authorization Header: Bearer <token>
    │
    ▼
GET /compliance/audits
    │
    ▼
Response: { team, audits: [...] }
    │
    ▼
DataFrame → Streamlit Components (metrics, charts, tables)
```

---

### 3. LangGraph Agent Orchestration (`src/agent.py`)

**Purpose**: Multi-agent state machine for medical writing workflow with FDA compliance validation.

**State Definition:**
```python
class AgentState(TypedDict, total=False):
    compliant: bool
    # ... additional state fields
```

**Agent Nodes** (to be implemented):

| Node | Input | Process | Output |
|------|-------|---------|--------|
| **RetrieveContext** | AgentState | Query Qdrant for relevant documents | Updated state with context |
| **MedicalWriter** | State + context | Generate medical draft via Ollama | State + draft_content |
| **FDACritic** | State + draft | Validate against compliance criteria | State + compliant: bool |

**Workflow Graph:**

```
START
  │
  ▼
RetrieveContext
  │
  ▼
MedicalWriter
  │
  ▼
FDACritic
  │
  ├─ [compliant=true] ──→ END
  │
  └─ [compliant=false] ──→ MedicalWriter (loop back)
```

**Conditional Routing:**
```python
def evaluate_compliance_route(state: AgentState) -> str:
    return "pass" if state.get("compliant", False) else "fail"
```

**LangGraph Configuration** (`langgraph.json`):
```json
{
  "dependencies": ["."],
  "graphs": {
    "pharma_agent": "./src/agent.py:graph"
  },
  "env": ".env"
}
```

---

## Workflow & Data Flow

### End-to-End Request Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER LOGIN (Streamlit Frontend)                                  │
│    Input: username, password                                        │
│    Action: POST /token to FastAPI                                  │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. AUTHENTICATION (FastAPI Backend)                                 │
│    • Lookup user in USER_DB                                        │
│    • Verify bcrypt hash                                            │
│    • Generate JWT with 60-min expiry                              │
│    • Return: { access_token, token_type }                         │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. STORE SESSION (Streamlit State)                                  │
│    st.session_state.token = <JWT>                                  │
│    st.session_state.team = <extracted from JWT>                   │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. FETCH COMPLIANCE DATA (Streamlit → FastAPI)                      │
│    Action: GET /compliance/audits                                  │
│    Headers: Authorization: Bearer <JWT>                            │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. VALIDATE & FILTER (FastAPI)                                     │
│    • Decode JWT, extract team                                      │
│    • Filter COMPLIANCE_DATA by team == JWT.team                   │
│    • Return: { team, audits: [...] }                             │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. RENDER DASHBOARD (Streamlit)                                    │
│    • Create DataFrame from audits                                  │
│    • Display KPI metrics                                           │
│    • Render bar chart (Performance by Metric)                     │
│    • Display audit log table                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Medical Compliance Processing Flow (Future Implementation)

```
┌─ PDF/Document Input
│
├─ 1. Document Ingestion (LangChain UnstructuredDirectoryLoader)
│    └─ Ingest from ./pdf_vault
│
├─ 2. Text Processing & Chunking (RecursiveCharacterTextSplitter)
│    └─ chunk_size: 1000, chunk_overlap: 150
│
├─ 3. Vectorization & Storage (Qdrant)
│    └─ Store embeddings + metadata
│
├─ 4. LangGraph Orchestration
│    ├─ RetrieveContext: Query Qdrant for relevant chunks
│    ├─ MedicalWriter: Generate draft via Ollama
│    ├─ FDACritic: Validate against ICH E6(R2) criteria
│    └─ Loop until compliant=true
│
└─ Compliance Artifact Output (JSON + audit trail)
```

---

## LangGraph State Machine

### Detailed Workflow Definition

**State Variables:**
```python
AgentState = {
    "compliant": bool,  # FDA compliance status
    "context": str,     # Retrieved document chunks
    "draft": str,       # Medical writing output
    "feedback": str,    # Critic's feedback
    "iteration": int    # Loop counter (prevents infinite loops)
}
```

**Node Implementations:**

#### Node 1: RetrieveContext
```
Input:  PDF query or topic
Action: Query Qdrant vector DB for top-k similar documents
Output: state["context"] = concatenated chunks
```

#### Node 2: MedicalWriter
```
Input:  state["context"]
Action: Prompt Ollama with medical writing template
        Template: "Based on context, draft FDA E6(R2) compliant write-up"
Output: state["draft"] = generated medical document
```

#### Node 3: FDACritic
```
Input:  state["draft"]
Action: Validate using predefined compliance rules:
        - Required sections present?
        - References properly cited?
        - Safety data adequate?
        - Statistical analysis present?
Output: state["compliant"] = true|false
        state["feedback"] = critique reason
```

**Routing Logic:**
```
After FDACritic:
├─ IF compliant == true
│  └─ Route: END (success)
└─ IF compliant == false
   ├─ IF iteration < 3
   │  └─ Route: MedicalWriter (retry with feedback)
   └─ ELSE
      └─ Route: END (manual review required)
```

---

## API Endpoints

### Authentication

#### `POST /token`
**Description:** User login, returns JWT bearer token

**Request:**
```
Content-Type: application/x-www-form-urlencoded

username=<username>&password=<password>
```

**Response (Success - 200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Response (Failure - 400):**
```json
{
  "detail": "Incorrect username or password"
}
```

### Compliance Data

#### `GET /compliance/audits`
**Description:** Retrieve team-scoped compliance audit data

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (Success - 200):**
```json
{
  "team": "BioGenomics",
  "audits": [
    {
      "id": 1,
      "team": "BioGenomics",
      "metric": "Data Privacy",
      "score": 92,
      "status": "Passed",
      "date": "2026-10-01"
    },
    {
      "id": 2,
      "team": "BioGenomics",
      "metric": "Lab Safety",
      "score": 88,
      "status": "Passed",
      "date": "2026-10-03"
    }
  ]
}
```

**Response (Unauthorized - 401):**
```json
{
  "detail": "Could not validate credentials"
}
```

---

## Database Schema

### PostgreSQL (postgres_db)

**Current Schema (Mock - In-Memory)**

#### users_table
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  team VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Sample Data:**
```
id | username  | team          | created_at
1  | dr_smith  | BioGenomics   | 2024-01-01
2  | dr_jones  | QuantumChem   | 2024-01-01
```

#### compliance_audits_table
```sql
CREATE TABLE compliance_audits (
  id SERIAL PRIMARY KEY,
  team VARCHAR(255) NOT NULL,
  metric VARCHAR(255) NOT NULL,
  score INT NOT NULL (0-100),
  status VARCHAR(50) NOT NULL (Passed/Failed),
  date DATE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (team) REFERENCES users_table(team)
);
```

**Sample Data:**
```
id | team       | metric                | score | status  | date
1  | BioGenomics| Data Privacy          | 92    | Passed  | 2026-10-01
2  | BioGenomics| Lab Safety            | 88    | Passed  | 2026-10-03
3  | QuantumChem| Compute Governance    | 65    | Failed  | 2026-10-05
4  | QuantumChem| Chemical Disposal     | 95    | Passed  | 2026-10-06
```

### Qdrant Vector Database (qdrant_vector)

**Purpose:** Store document embeddings and metadata for RAG

**Collection Schema:**
```
Collection: pharma_documents
├─ Vectors: 1536-dim (OpenAI embedding size)
├─ Metadata:
│  ├─ source_file: str (PDF filename)
│  ├─ chunk_index: int
│  ├─ page_number: int
│  ├─ text_snippet: str (first 500 chars)
│  └─ ingestion_date: timestamp
└─ Indexed: source_file, ingestion_date
```

---

## Security Architecture

### Authentication Layer

**JWT Token Structure:**
```
Header:   { "alg": "HS256", "typ": "JWT" }
Payload:  { "sub": "dr_smith", "team": "BioGenomics", "exp": <timestamp> }
Signature: HMAC-SHA256(header + payload, SECRET_KEY)
```

**Token Flow:**
```
1. Client sends credentials to /token
2. Server validates against USER_DB (bcrypt)
3. Server encodes JWT (claims: username, team, 60-min expiry)
4. Client stores token in session
5. Client includes token in Authorization header for subsequent requests
6. Server validates token signature and expiry on each request
7. Server extracts team from token, filters data by team
```

### Data Isolation (RBAC)

**Team-Scoped Access:**
```python
# Example: dr_smith (BioGenomics team) cannot see QuantumChem data
user_team = jwt.decode(token)["team"]  # "BioGenomics"
audits = COMPLIANCE_DATA.filter(team == user_team)  # Only BioGenomics records
```

### Secrets Management

**Environment Variables (docker-compose.yml):**
```
JWT_SECRET=super-secret-scientific-key-12345 (IN-MEMORY ONLY, REPLACE IN PROD)
POSTGRES_PASSWORD=sci_pass (EXAMPLE, USE VAULT/SECRETS MANAGER)
QDRANT_API_KEY=<if using cloud Qdrant>
OLLAMA_URL=http://ollama_llm:11434 (internal service endpoint)
```

### On-Premise Data Governance

- **No external data transit**: All data remains within docker container network (`sci_network`)
- **Local LLM execution**: Ollama runs locally, no cloud API calls
- **Vector embeddings**: Stored in containerized Qdrant, not third-party services
- **HIPAA/GDPR compliance**: Suitable for regulated environments when secrets are properly managed

---

## Deployment & Scalability

### Local Development Deployment

```bash
# 1. Clone and navigate
git clone <repo>
cd pharma_agent

# 2. Set up environment
cp .env.example .env
# Edit .env with production credentials

# 3. Launch stack
docker compose up --pull always -d

# 4. Access services
# Frontend:  http://localhost:8501
# API:       http://localhost:8000
# API Docs:  http://localhost:8000/docs
```

### Service Readiness

**Dependencies:**
```
streamlit_dashboard → fastapi_backend → postgres_db ✓
                                     → qdrant_vector ✓
fastapi_backend → ollama_llm (optional for now)
```

**Health Checks (Recommended):**
```
# Postgres
curl http://localhost:5432  (can add SELECT 1 query)

# Qdrant
curl http://localhost:6333/health

# Ollama
curl http://localhost:11434/api/tags

# FastAPI
curl http://localhost:8000/docs

# Streamlit
curl http://localhost:8501
```

### Scaling Considerations

#### Horizontal Scaling (Multi-Instance)
```
Load Balancer (Nginx)
├─ fastapi_backend instance 1
├─ fastapi_backend instance 2
└─ fastapi_backend instance 3
     ↓ (shared connection pool)
   PostgreSQL (primary) + Replicas
   Qdrant Cluster (distributed)
```

#### Vertical Scaling (More Powerful Hardware)
```
Current: docker-compose on single host
Future: Kubernetes cluster with:
  • Deployment replicas: fastapi_backend (3)
  • StatefulSet: postgres_db, qdrant_vector (persistence)
  • ConfigMap: environment variables
  • Secret: sensitive credentials
  • HPA: auto-scale based on CPU/memory
```

#### Document Processing at Scale

**Production Blueprint (from prod_blueprint.md):**

1. **Distributed Ingestion:**
   ```python
   from langchain_community.document_loaders import UnstructuredDirectoryLoader
   loader = UnstructuredDirectoryLoader("./pdf_vault", mode="elements", strategy="fast")
   ```

2. **Semantic Chunking:**
   ```python
   from langchain_text_splitters import RecursiveCharacterTextSplitter
   splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
   ```

3. **Enterprise Vector Cluster:**
   ```python
   qdrant_client = QdrantClient(
       url="http://enterprise-qdrant-cluster:6333",
       api_key=os.getenv("QDRANT_API_KEY")
   )
   ```

4. **Batch Processing Pipeline:**
   - Job Queue: Celery/RQ for async task scheduling
   - Worker Pool: Multiple instances processing PDFs in parallel
   - Results: Store in PostgreSQL + Qdrant

---

## Production Considerations

### Pre-Production Checklist

#### Secrets & Configuration
- [ ] Replace `JWT_SECRET` with cryptographically secure value (256-bit minimum)
- [ ] Use AWS Secrets Manager / HashiCorp Vault for credential management
- [ ] Enable TLS/HTTPS for all external endpoints
- [ ] Implement API rate limiting (FastAPI middleware)
- [ ] Enable CORS with explicit allowlist

#### Database & Persistence
- [ ] Set up PostgreSQL automated backups (daily, retention: 30 days)
- [ ] Enable PostgreSQL replication for HA
- [ ] Configure Qdrant persistent storage on external volumes
- [ ] Implement database connection pooling (pgBouncer)
- [ ] Add database monitoring (slow queries, replication lag)

#### Monitoring & Logging
- [ ] Implement centralized logging (ELK stack, Splunk, or CloudWatch)
- [ ] Add application metrics export (Prometheus)
- [ ] Set up container health checks
- [ ] Configure alerts for service degradation
- [ ] Enable audit logs for compliance (user actions, data access)

#### Security Hardening
- [ ] Run containers as non-root user
- [ ] Use network policies to restrict inter-service communication
- [ ] Enable image scanning for vulnerabilities (Trivy, Snyk)
- [ ] Implement secret rotation policies
- [ ] Set resource limits (CPU, memory) per container

#### Compliance & Audit
- [ ] Maintain audit trail of all compliance artifacts generated
- [ ] Document data retention policies (medical records: min 3-7 years)
- [ ] Implement role-based access control (RBAC) expansion (admin, reviewer, reader)
- [ ] Enable cryptographic signing of compliance documents
- [ ] Establish SOC 2 / HIPAA compliance framework

#### Disaster Recovery
- [ ] Define RTO (Recovery Time Objective) and RPO (Recovery Point Objective)
- [ ] Test backup restoration procedures monthly
- [ ] Implement multi-region failover (if applicable)
- [ ] Document runbooks for common incidents
- [ ] Maintain off-site backup copies

### Performance Optimization

#### Caching Strategy
- Cache Qdrant vector search results (Redis)
- Cache FDA compliance rules (in-memory)
- Implement browser caching for Streamlit assets

#### Database Indexing
- Add indexes on frequently queried columns:
  ```sql
  CREATE INDEX idx_compliance_team ON compliance_audits(team);
  CREATE INDEX idx_compliance_date ON compliance_audits(date);
  ```

#### API Optimization
- Enable gzip compression in FastAPI
- Implement pagination for large audit datasets
- Use connection pooling for database connections

---

## Migration Path

### Phase 1: Current State (MVP)
- In-memory user database
- Mock compliance data
- LangGraph infrastructure (blueprint ready)
- Docker Compose orchestration

### Phase 2: Enhanced Backend
- Real PostgreSQL schema implementation
- Document ingestion pipeline (PDFs → Qdrant)
- Full LangGraph workflow implementation
- Prometheus metrics export

### Phase 3: Production Hardening
- Vault-based secrets management
- Multi-replica PostgreSQL
- Distributed Qdrant cluster
- Kubernetes deployment manifests

### Phase 4: Enterprise Scale
- Multi-tenant architecture
- Advanced RBAC (admin, reviewer, auditor)
- Batch processing with Celery
- Audit trail analytics dashboard

---

## Conclusion

Pharma Agent is architected as a modular, containerized, multi-agent system for pharmaceutical compliance automation. Its layered design (Frontend → API → AI Agents → Data Layer) allows for independent scaling, testing, and evolution. The use of LangGraph enables sophisticated agentic workflows with built-in compliance enforcement, while Docker Compose provides production-ready orchestration out of the box.

**Key Strengths:**
- On-premise data governance (HIPAA/GDPR ready)
- Fault-tolerant microservices architecture
- LangGraph for deterministic agent routing
- Team-based RBAC for regulatory compliance
- Clear upgrade path to Kubernetes and multi-region deployments

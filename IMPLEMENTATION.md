# Pharma Agent - Implementation Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Environment Setup](#environment-setup)
4. [Backend Implementation Details](#backend-implementation-details)
5. [Frontend Implementation Details](#frontend-implementation-details)
6. [LangGraph Agent Implementation](#langgraph-agent-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Common Tasks & Troubleshooting](#common-tasks--troubleshooting)
9. [Development Workflow](#development-workflow)

---

## Getting Started

### Prerequisites
- Docker 20.10+ and Docker Compose 1.29+
- Python 3.11+ (for local development)
- Git
- Text editor or IDE (VS Code, PyCharm)

### Quick Start

```bash
# 1. Clone repository
git clone <repo-url>
cd pharma_agent

# 2. Create environment file
cp .env.example .env

# 3. Build and start containers
docker compose up --pull always -d

# 4. Verify services
docker compose ps

# 5. Access dashboard
# Frontend:  http://localhost:8501
# API:       http://localhost:8000/docs
# API Root:  http://localhost:8000
```

### Verification Checklist

```bash
# Check all containers are running
docker compose ps
# Expected: 5 running containers (fastapi_backend, streamlit_dashboard, 
#           postgres_db, qdrant_vector, ollama_llm)

# Test FastAPI backend
curl http://localhost:8000/docs

# Test PostgreSQL connection
docker exec pharma_agent-postgres_db-1 psql -U sci_user -d compliance_db -c "SELECT 1"

# Test Qdrant
curl http://localhost:6333/health

# Test Ollama
curl http://localhost:11434/api/tags

# View backend logs
docker compose logs fastapi_backend -f

# View frontend logs
docker compose logs streamlit_dashboard -f
```

---

## Project Structure

```
pharma_agent/
├── app/
│   ├── main.py                      # FastAPI backend with JWT auth
│   └── app.py                       # Streamlit frontend dashboard
├── src/
│   └── agent.py                     # LangGraph state machine
├── agents/                          # Future: Agent implementations
├── .langgraph_api/                  # LangGraph API config
├── Dockerfile.fastapi               # Backend container definition
├── Dockerfile.streamlit             # Frontend container definition
├── docker-compose.yml               # Multi-service orchestration
├── requirements.txt                 # Python dependencies
├── langgraph.json                   # LangGraph configuration
├── .env                             # Environment variables
├── .env.example                     # Template for .env
├── ARCHITECTURE.md                  # System architecture documentation
├── IMPLEMENTATION.md                # This file
├── system_architecture.md           # Visual architecture diagrams
├── prod_blueprint.md                # Production scaling blueprint
└── value_and_impact_metrics.md      # Impact analysis

Key Files Explained:
├── app/main.py
│   • FastAPI application factory
│   • OAuth2 + JWT authentication
│   • User database (USER_DB)
│   • Compliance data (COMPLIANCE_DATA)
│   • Secured endpoints
│
├── app/app.py
│   • Streamlit page layout
│   • Session state management
│   • Authentication UI
│   • Dashboard components
│
├── src/agent.py
│   • LangGraph workflow definition
│   • AgentState TypedDict
│   • Agent nodes (retrieve, write, criticize)
│   • Conditional routing logic
│
├── Dockerfile.fastapi
│   • Multi-stage build (future optimization)
│   • Python 3.11-slim base
│   • COPY app code
│   • Expose port 8000
│
└── docker-compose.yml
    • 5-service orchestration
    • Network configuration (sci_network)
    • Volume management
    • Environment variables
```

---

## Environment Setup

### `.env` File Configuration

**Location:** Repository root

**Template:**
```bash
# JWT Configuration
JWT_SECRET=super-secret-scientific-key-12345

# PostgreSQL Configuration
POSTGRES_USER=sci_user
POSTGRES_PASSWORD=sci_pass
POSTGRES_DB=compliance_db
POSTGRES_URL=postgresql://sci_user:sci_pass@postgres_db:5432/compliance_db

# Qdrant Configuration
QDRANT_URL=http://qdrant_vector:6333
QDRANT_API_KEY=         # Optional, for cloud deployment

# Ollama Configuration
OLLAMA_URL=http://ollama_llm:11434

# FastAPI Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Streamlit Configuration
STREAMLIT_PORT=8501
STREAMLIT_SERVER_MAXUPLOADSIZE=200

# LangGraph Configuration
LANGGRAPH_API_URL=http://fastapi_backend:8000
```

### Production `.env` Changes

```bash
# BEFORE (Development)
JWT_SECRET=super-secret-scientific-key-12345
POSTGRES_PASSWORD=sci_pass

# AFTER (Production - Use Secrets Manager)
JWT_SECRET=$(aws secretsmanager get-secret-value --secret-id pharma/jwt-secret --query SecretString --output text)
POSTGRES_PASSWORD=$(aws secretsmanager get-secret-value --secret-id pharma/db-password --query SecretString --output text)

# Enable HTTPS/TLS
API_SCHEME=https
STREAMLIT_SERVER_SSL_CERTFILE=/path/to/cert.pem
STREAMLIT_SERVER_SSL_KEYFILE=/path/to/key.pem
```

---

## Backend Implementation Details

### FastAPI Application Structure (`app/main.py`)

#### 1. Imports & Configuration

```python
import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from passlib.context import CryptContext
```

**Key Libraries:**
- `fastapi`: Web framework
- `python-jose`: JWT encoding/decoding
- `passlib`: Password hashing (bcrypt)
- `pydantic`: Data validation

#### 2. Security Configuration

```python
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-scientific-key-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Bcrypt password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
```

**Security Notes:**
- `SECRET_KEY`: 256-bit minimum in production
- `ALGORITHM`: HS256 (symmetric) for internal use. For distributed systems, use RS256 (asymmetric)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 60 minutes balances security vs UX
- `bcrypt`: Naturally slow (resistant to brute force)

#### 3. Data Models

```python
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds

class User(BaseModel):
    username: str
    team: str
    is_admin: bool = False  # Future RBAC expansion
```

#### 4. Authentication Endpoints

**POST /token**
```python
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2-compatible token endpoint for user login.
    
    Expected form data:
    - username: str
    - password: str
    - scope: str (optional, for future use)
    - grant_type: str (default: "password")
    - client_id: str (optional)
    - client_secret: str (optional)
    """
    user = USER_DB.get(form_data.username)
    
    # Validate user exists and password matches
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    access_token = create_access_token(
        data={"sub": user["username"], "team": user["team"]}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
```

**Key Security Features:**
- Uses OAuth2 PasswordRequestForm (standardized)
- Returns 401 for invalid credentials (not 403 or 404)
- Generic error message (doesn't reveal user existence)
- JWT includes only essential claims (sub, team)

#### 5. Dependency Injection for Authorization

```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Dependency that validates JWT and returns current user.
    Use as: async def endpoint(current_user: User = Depends(get_current_user))
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT with secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        team: str = payload.get("team")
        
        if username is None or team is None:
            raise credentials_exception
        
        return User(username=username, team=team)
    
    except JWTError:
        # Handles: invalid signature, expired token, malformed JWT
        raise credentials_exception
```

**Flow:**
```
Request with Authorization: Bearer <token>
         │
         ▼
FastAPI extracts token from Authorization header via oauth2_scheme
         │
         ▼
get_current_user() decodes JWT with SECRET_KEY
         │
         ├─ Valid & not expired → User object ✓
         │
         └─ Invalid or expired → 401 Unauthorized ✗
```

#### 6. Protected Data Endpoints

```python
@app.get("/compliance/audits")
async def get_audits(current_user: User = Depends(get_current_user)):
    """
    Retrieve compliance audits scoped to the current user's team.
    
    Security:
    - Only returns audits where team == current_user.team
    - Prevents cross-team data leakage
    """
    team_audits = [
        audit for audit in COMPLIANCE_DATA 
        if audit["team"] == current_user.team
    ]
    
    return {
        "team": current_user.team,
        "audits": team_audits
    }
```

### Adding New Endpoints

**Template:**
```python
@app.post("/api/v1/compliance/submit")
async def submit_compliance_report(
    report: ComplianceReportSchema,
    current_user: User = Depends(get_current_user)
):
    """
    Submit a new compliance report for the current user's team.
    """
    # Validate request
    if not report.metric:
        raise HTTPException(status_code=400, detail="Metric required")
    
    # Process
    new_audit = {
        "id": len(COMPLIANCE_DATA) + 1,
        "team": current_user.team,
        "metric": report.metric,
        "score": report.score,
        "status": "Passed" if report.score >= 80 else "Failed",
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    COMPLIANCE_DATA.append(new_audit)
    
    # Return
    return new_audit
```

---

## Frontend Implementation Details

### Streamlit Application Structure (`app/app.py`)

#### 1. Page Configuration

```python
st.set_page_config(
    page_title="Scientific Compliance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("🔬 Scientific Compliance Dashboard")
```

**Configuration Options:**
- `page_title`: Browser tab title
- `layout`: "centered" (default) or "wide"
- `initial_sidebar_state`: "auto" (default), "expanded", or "collapsed"

#### 2. Session State Initialization

```python
# Initialize session state variables if not present
if "token" not in st.session_state:
    st.session_state.token = None
if "team" not in st.session_state:
    st.session_state.team = None
if "username" not in st.session_state:
    st.session_state.username = None
```

**Why Session State?**
- Streamlit reruns entire script on every interaction
- Session state persists across reruns within same browser session
- Prevents losing authentication token on button clicks

#### 3. Conditional UI: Authentication Block

```python
if not st.session_state.token:
    # NOT AUTHENTICATED - Show login form
    st.sidebar.subheader("🔐 Team Authentication")
    
    col1, col2 = st.sidebar.columns([1, 1])
    with col1:
        username = st.text_input("Username", key="login_username")
    with col2:
        password = st.text_input("Password", type="password", key="login_password")
    
    if st.sidebar.button("Login", use_container_width=True):
        try:
            # POST to FastAPI /token endpoint
            response = requests.post(
                f"{API_URL}/token",
                data={"username": username, "password": password},
                timeout=5
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Store in session state
                st.session_state.token = token_data["access_token"]
                st.session_state.username = username
                
                # Trigger rerun to show authenticated UI
                st.success("✓ Successfully logged in!")
                st.rerun()
            else:
                st.sidebar.error("✗ Invalid credentials")
        
        except requests.exceptions.ConnectionError:
            st.sidebar.error("✗ Backend API unreachable")
        except requests.exceptions.Timeout:
            st.sidebar.error("✗ Request timeout")

else:
    # AUTHENTICATED - Show session status and logout
    st.sidebar.success(f"✓ Authenticated: {st.session_state.username}")
    
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.token = None
        st.session_state.team = None
        st.session_state.username = None
        st.rerun()
```

#### 4. Protected Dashboard Content

```python
if st.session_state.token:
    # User is authenticated - Fetch and display data
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/compliance/audits",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.team = data["team"]
            audits = data["audits"]
            
            # Display header
            st.subheader(f"📊 Compliance Metrics for Team: **{st.session_state.team}**")
            
            # Display KPI metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="Total Audits Run",
                    value=len(audits),
                    delta=None
                )
            with col2:
                avg_score = pd.Series([a["score"] for a in audits]).mean()
                st.metric(
                    label="Average Score",
                    value=f"{avg_score:.1f}%",
                    delta=None
                )
            with col3:
                passed_count = len([a for a in audits if a["status"] == "Passed"])
                st.metric(
                    label="Passed Audits",
                    value=passed_count,
                    delta=None
                )
            
            # Display charts and tables
            st.write("---")
            chart_col, table_col = st.columns([2, 1])
            
            with chart_col:
                st.markdown("### Performance By Metric")
                df = pd.DataFrame(audits)
                st.bar_chart(
                    data=df.set_index("metric")["score"],
                    use_container_width=True
                )
            
            with table_col:
                st.markdown("### Raw Audit Log")
                display_df = df[["date", "metric", "score", "status"]]
                st.dataframe(display_df, use_container_width=True)
        
        elif response.status_code == 401:
            st.error("Session expired. Please re-authenticate.")
            st.session_state.token = None
            st.rerun()
        else:
            st.error(f"Error: {response.status_code}")
    
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")

else:
    # User is not authenticated - Show prompt
    st.warning("🔒 Please enter your scientific credentials in the sidebar to view compliance data.")
```

### Streamlit Advanced Features

#### Caching for Performance
```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_audit_data(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_URL}/compliance/audits", headers=headers)
    return response.json()
```

#### Custom Styling
```python
# Add custom CSS for branding
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    h1 { color: #1f77b4; }
</style>
""", unsafe_allow_html=True)
```

#### Error Handling with Retry
```python
from time import sleep

def fetch_with_retry(url: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            return response
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

---

## LangGraph Agent Implementation

### Agent State Definition

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict, total=False):
    """
    State object passed through LangGraph nodes.
    Mutable fields accumulate; immutable fields are replaced.
    """
    # Input
    query: str
    documents: list[str]
    
    # Processing
    context: str
    draft: str
    feedback: str
    
    # Output
    compliant: bool
    iteration: int
    messages: Annotated[list[BaseMessage], operator.add]
```

### Node Implementations

#### Node 1: Document Retrieval

```python
from langchain_community.vectorstores import Qdrant
from langchain_embeddings.ollama import OllamaEmbeddings

def retrieve_context_node(state: AgentState) -> AgentState:
    """
    Query vector store for relevant documents.
    """
    # Initialize vector store client
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    
    vectorstore = Qdrant(
        client=qdrant_client,
        collection_name="pharma_documents",
        embeddings=embeddings
    )
    
    # Retrieve top-k relevant documents
    docs = vectorstore.similarity_search(
        query=state["query"],
        k=5
    )
    
    # Format retrieved context
    context = "\n\n".join([
        f"[{i+1}] {doc.metadata.get('source', 'Unknown Source')}\n{doc.page_content}"
        for i, doc in enumerate(docs)
    ])
    
    return {
        **state,
        "context": context
    }
```

#### Node 2: Medical Writer

```python
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate

def medical_writer_node(state: AgentState) -> AgentState:
    """
    Generate medical compliance document.
    """
    # Initialize LLM
    llm = Ollama(
        model="mistral",
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        temperature=0.3  # Low temperature for consistency
    )
    
    # Define medical writing prompt
    prompt_template = PromptTemplate(
        input_variables=["context", "feedback"],
        template="""You are a medical writer specializing in FDA compliance documentation.
        
Context from medical literature:
{context}

{feedback_section}

Generate a compliance document following ICH E6(R2) guidelines:
1. Introduction (2-3 sentences)
2. Clinical Rationale (3-4 sentences)
3. Safety Considerations (3-4 sentences)
4. Regulatory Alignment (2-3 sentences)
5. Conclusion (1-2 sentences)

Ensure all claims are supported by provided context.
"""
    )
    
    # Build feedback section if iterating
    feedback_section = ""
    if state.get("iteration", 0) > 0 and state.get("feedback"):
        feedback_section = f"Previous Feedback:\n{state['feedback']}\nPlease address these concerns."
    
    # Generate draft
    prompt = prompt_template.format(
        context=state["context"],
        feedback_section=feedback_section
    )
    
    draft = llm.invoke(prompt)
    
    return {
        **state,
        "draft": draft,
        "iteration": state.get("iteration", 0) + 1
    }
```

#### Node 3: FDA Compliance Critic

```python
def fda_critic_node(state: AgentState) -> AgentState:
    """
    Evaluate draft against compliance criteria.
    """
    # Define compliance rules
    compliance_rules = {
        "has_introduction": "Introduction section present",
        "has_clinical_rationale": "Clinical rationale explained",
        "has_safety_section": "Safety considerations addressed",
        "has_regulatory_reference": "Regulatory framework mentioned",
        "has_conclusion": "Conclusion provided",
        "supported_by_evidence": "Claims supported by context",
    }
    
    draft = state["draft"]
    
    # Validate compliance
    feedback = []
    compliant = True
    
    if "Introduction" not in draft:
        feedback.append("Missing: Introduction section")
        compliant = False
    
    if "Safety" not in draft:
        feedback.append("Missing: Safety considerations section")
        compliant = False
    
    if "Conclusion" not in draft:
        feedback.append("Missing: Conclusion")
        compliant = False
    
    # Check for unsupported claims
    if "[1]" not in draft:  # Citation check
        feedback.append("Warning: No citations found in document")
        compliant = False
    
    feedback_text = "\n".join(feedback) if feedback else "✓ All compliance checks passed"
    
    return {
        **state,
        "compliant": compliant,
        "feedback": feedback_text
    }
```

### Graph Construction

```python
def create_workflow() -> StateGraph:
    """Build and return compiled workflow graph."""
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("RetrieveContext", retrieve_context_node)
    workflow.add_node("MedicalWriter", medical_writer_node)
    workflow.add_node("FDACritic", fda_critic_node)
    
    # Add edges
    workflow.add_edge(START, "RetrieveContext")
    workflow.add_edge("RetrieveContext", "MedicalWriter")
    workflow.add_edge("MedicalWriter", "FDACritic")
    
    # Conditional routing
    def evaluate_compliance(state: AgentState) -> str:
        """Route based on compliance status."""
        if state.get("compliant", False):
            return "end"  # Compliance achieved
        elif state.get("iteration", 0) >= 3:
            return "end"  # Max iterations reached
        else:
            return "retry"  # Loop back
    
    workflow.add_conditional_edges(
        "FDACritic",
        evaluate_compliance,
        {
            "end": END,
            "retry": "MedicalWriter"
        }
    )
    
    return workflow.compile()

# Export compiled graph
graph = create_workflow()
```

### Running the Agent

```python
# In a FastAPI endpoint
@app.post("/api/v1/generate-compliance-document")
async def generate_document(
    query: str,
    current_user: User = Depends(get_current_user)
):
    """Trigger the multi-agent workflow."""
    
    # Initialize state
    initial_state = {
        "query": query,
        "context": "",
        "draft": "",
        "feedback": "",
        "compliant": False,
        "iteration": 0,
    }
    
    # Execute workflow
    output = graph.invoke(initial_state)
    
    # Return results
    return {
        "status": "passed" if output["compliant"] else "needs_review",
        "iterations": output["iteration"],
        "document": output["draft"],
        "feedback": output["feedback"]
    }
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_auth.py
import pytest
from app.main import create_access_token, pwd_context, get_current_user

def test_password_hashing():
    """Test bcrypt password hashing."""
    password = "test_password_123"
    hashed = pwd_context.hash(password)
    
    assert pwd_context.verify(password, hashed)
    assert not pwd_context.verify("wrong_password", hashed)

def test_jwt_creation():
    """Test JWT token creation and validation."""
    data = {"sub": "test_user", "team": "TestTeam"}
    token = create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 parts

def test_jwt_expired():
    """Test expired token handling."""
    # Create token with 0 expiry
    from datetime import timedelta, datetime
    data = {"sub": "test", "exp": datetime.utcnow() - timedelta(seconds=1)}
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    
    with pytest.raises(JWTError):
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

### Integration Tests

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    """Test successful login."""
    response = client.post(
        "/token",
        data={"username": "dr_smith", "password": "password123"}
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_invalid_credentials():
    """Test login with wrong password."""
    response = client.post(
        "/token",
        data={"username": "dr_smith", "password": "wrong_password"}
    )
    
    assert response.status_code == 400
    assert "Incorrect" in response.json()["detail"]

def test_audits_unauthorized():
    """Test unauthorized access to protected endpoint."""
    response = client.get("/compliance/audits")
    
    assert response.status_code == 403  # or 401 depending on implementation

def test_audits_authorized():
    """Test authorized access to audits."""
    # Login first
    login_resp = client.post(
        "/token",
        data={"username": "dr_smith", "password": "password123"}
    )
    token = login_resp.json()["access_token"]
    
    # Access protected endpoint
    response = client.get(
        "/compliance/audits",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["team"] == "BioGenomics"
    assert len(data["audits"]) > 0
```

### E2E Tests (Selenium/Playwright)

```python
# tests/test_e2e.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def test_login_and_view_dashboard():
    """Test full user login and dashboard viewing flow."""
    
    driver = webdriver.Chrome()
    driver.get("http://localhost:8501")
    
    # Find login fields
    username_field = driver.find_element(By.ID, "login_username")
    password_field = driver.find_element(By.ID, "login_password")
    login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
    
    # Fill and submit
    username_field.send_keys("dr_smith")
    password_field.send_keys("password123")
    login_button.click()
    
    # Wait for dashboard
    wait = WebDriverWait(driver, 10)
    dashboard = wait.until(
        lambda d: d.find_element(By.XPATH, "//h2[contains(text(), 'Compliance Metrics')]")
    )
    
    assert dashboard is not None
    driver.quit()
```

---

## Common Tasks & Troubleshooting

### Task 1: Add a New User

**Step 1: Update USER_DB in `app/main.py`**
```python
USER_DB = {
    "dr_smith": {
        "username": "dr_smith",
        "hashed_password": pwd_context.hash("password123"),
        "team": "BioGenomics",
    },
    "dr_johnson": {  # NEW USER
        "username": "dr_johnson",
        "hashed_password": pwd_context.hash("secure_password_456"),
        "team": "QuantumChem",
    }
}
```

**Step 2: Restart backend**
```bash
docker compose restart fastapi_backend
```

**Step 3: Test login**
```bash
curl -X POST http://localhost:8000/token \
  -d "username=dr_johnson&password=secure_password_456"
```

### Task 2: Add New Compliance Data

**Option A: Update COMPLIANCE_DATA in `app/main.py`**
```python
COMPLIANCE_DATA = [
    # ... existing audits ...
    {
        "id": 5,
        "team": "BioGenomics",
        "metric": "Clinical Trial Management",
        "score": 94,
        "status": "Passed",
        "date": "2026-10-10"
    }
]
```

**Option B: Create API endpoint to add audits**
```python
@app.post("/compliance/audits")
async def create_audit(
    audit: AuditSchema,
    current_user: User = Depends(get_current_user)
):
    """Create new compliance audit for current user's team."""
    new_audit = {
        "id": max(a["id"] for a in COMPLIANCE_DATA) + 1,
        "team": current_user.team,
        **audit.dict()
    }
    COMPLIANCE_DATA.append(new_audit)
    return new_audit
```

### Task 3: Change JWT Expiration

**In `app/main.py`:**
```python
# Current: 60 minutes
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Change to: 24 hours
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60

# Restart backend
```

### Troubleshooting: "Invalid credentials"

**Checklist:**
1. Verify user exists in USER_DB
   ```bash
   docker exec pharma_agent-fastapi_backend-1 python -c "from app.main import USER_DB; print(list(USER_DB.keys()))"
   ```

2. Verify password is correct
   ```bash
   docker exec pharma_agent-fastapi_backend-1 python -c "
   from app.main import USER_DB, pwd_context
   user = USER_DB['dr_smith']
   print('Match:', pwd_context.verify('password123', user['hashed_password']))
   "
   ```

3. Check API logs
   ```bash
   docker compose logs fastapi_backend -f
   ```

### Troubleshooting: "Backend unreachable"

**Checklist:**
1. Verify fastapi_backend container is running
   ```bash
   docker compose ps | grep fastapi_backend
   ```

2. Check if port 8000 is accessible
   ```bash
   curl http://localhost:8000/docs
   ```

3. Check container logs for startup errors
   ```bash
   docker compose logs fastapi_backend
   ```

4. Verify network connectivity
   ```bash
   docker exec pharma_agent-streamlit_dashboard-1 curl http://fastapi_backend:8000/docs
   ```

### Troubleshooting: "Database connection error"

**Checklist:**
1. Verify PostgreSQL container is running
   ```bash
   docker compose ps | grep postgres_db
   ```

2. Test database connection
   ```bash
   docker exec pharma_agent-postgres_db-1 psql -U sci_user -d compliance_db -c "SELECT 1"
   ```

3. Check environment variables in FastAPI container
   ```bash
   docker exec pharma_agent-fastapi_backend-1 env | grep POSTGRES
   ```

---

## Development Workflow

### Local Development Without Docker

**Prerequisites:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Run services locally:**
```bash
# Terminal 1: FastAPI
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Streamlit
streamlit run app/app.py --server.port 8501

# Terminal 3: PostgreSQL (using Docker)
docker run -d \
  -e POSTGRES_USER=sci_user \
  -e POSTGRES_PASSWORD=sci_pass \
  -e POSTGRES_DB=compliance_db \
  -p 5432:5432 \
  postgres:15-alpine
```

### Hot Reloading in Docker

**Current Setup:**
```dockerfile
# Dockerfile.fastapi
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
```

**With volume mounts for hot reload:**
```yaml
# docker-compose.yml
services:
  fastapi_backend:
    volumes:
      - ./app:/app/app  # Mount source code
      - ./src:/app/src
```

**Restart to apply changes:**
```bash
docker compose up -d  # Changes picked up via --reload
```

### Debugging in VSCode

**Launch Configuration (`.vscode/launch.json`):**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

**Run with debugging:**
```
F5 (Start Debugging)
```

---

## Conclusion

This implementation guide provides step-by-step instructions for:
- Understanding each component's role
- Adding new features (users, endpoints, agents)
- Debugging common issues
- Running tests
- Setting up local development

For production deployment, refer to the ARCHITECTURE.md document's "Production Considerations" section.

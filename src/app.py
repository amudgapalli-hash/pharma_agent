"""Pharmaceutical Multi-Agent Pipeline with Security Guard Rails
Provides automated medical text generation with FDA/HIPAA compliance checking,
PHI detection, and comprehensive audit logging.
"""

import os
import datetime
import logging
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langgraph.graph import StateGraph, START, END

from app.security import InputValidator, PHIDetector, RateLimiter, generate_request_id

# =====================================================================
# LOGGING CONFIGURATION
# =====================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(max_requests=50, window_seconds=60)

# =====================================================================
# 1. POSTGRESQL RELATIONAL DATABASE AUDIT LOG CONFIGURATION
# =====================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pharma_audit_trail.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CriticAuditLog(Base):
    __tablename__ = "critic_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    request_id = Column(String(32), index=True)  # Track requests
    query_topic = Column(String(255), index=True)
    iteration_number = Column(Integer)
    is_fda_compliant = Column(Boolean)
    is_hipaa_compliant = Column(Boolean)
    phi_leaks_found = Column(JSON)
    raw_critique_json = Column(JSON)
    evaluated_draft_text = Column(Text)

Base.metadata.create_all(bind=engine)

# =====================================================================
# 2. ENHANCED FDA & HIPAA COMPLIANCE SCHEMA (Pydantic)
# =====================================================================
class EnhancedFDACritique(BaseModel):
    is_fda_compliant: bool = Field(description="True if text matches FDA E6(R2) guidance.")
    is_hipaa_compliant: bool = Field(description="False if Safe Harbor PHI elements exist.")
    phi_leaks_identified: List[str] = Field(description="List of detected PHI.")
    missing_regulatory_elements: List[str] = Field(description="Gaps in regulatory requirements.")
    revisions_required: str = Field(description="Revision guidelines for Medical Writer.")

# =====================================================================
# 3. LANGGRAPH AGENT STATE & DEFINITION
# =====================================================================
class AgentState(TypedDict):
    research_query: str
    retrieved_context: str
    generated_draft: str
    critic_feedback: Dict[str, Any]
    iteration_count: int

llm_writer = ChatOllama(model="llama3", base_url="http://localhost:11434", temperature=0.3)
llm_critic = ChatOllama(model="llama3", base_url="http://localhost:11434", temperature=0.0)

def medical_writer_node(state: AgentState) -> Dict[str, Any]:
    print(f"📝 [Graph] Medical Writer executing loop iteration: {state.get('iteration_count', 0) + 1}")
    feedback_str = "None (Initial Draft)"
    if state.get("critic_feedback"):
        feedback_str = f"FAILED PREVIOUS CRITIQUE: {state['critic_feedback']['revisions_required']}"
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Clinical Protocol Writer. Output objective regulatory data. "
                   "IMPORTANT: You must preserve data anonymity. NEVER use patient names or specific dates."),
        ("user", "Draft clinical protocol text for: {query}.\n\nContext:\n{context}\n\nFeedback:\n{feedback}")
    ])
    writer_chain = prompt | llm_writer | StrOutputParser()
    draft = writer_chain.invoke({
        "query": state["research_query"],
        "context": state["retrieved_context"] or "Focus on molecule safety boundaries.",
        "feedback": feedback_str
    })
    return {"generated_draft": draft, "iteration_count": state.get("iteration_count", 0) + 1}

def fda_hipaa_critic_node(state: AgentState) -> Dict[str, Any]:
    print("⚖️ [Graph] FDA & HIPAA Critic checking draft restrictions...")
    parser = JsonOutputParser(pydantic_object=EnhancedFDACritique)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Regulatory Compliance Officer. Scan for PHI leaks and FDA alignment. "
                   "Output JSON:\n{format_instructions}"),
        ("user", "Evaluate this draft for compliance:\n\n{draft}")
    ]).partial(format_instructions=parser.get_format_instructions())
    
    critic_chain = prompt | llm_critic | parser
    feedback = critic_chain.invoke({"draft": state["generated_draft"]})
    
    return {"critic_feedback": feedback}

def evaluate_route(state: AgentState) -> Literal["pass", "fail"]:
    feedback = state["critic_feedback"]
    if state.get("iteration_count", 0) >= 3:
        return "pass"
    if feedback.get("is_fda_compliant") and feedback.get("is_hipaa_compliant"):
        return "pass"
    return "fail"

# Building Graph Logic
workflow = StateGraph(AgentState)
workflow.add_node("MedicalWriter", medical_writer_node)
workflow.add_node("FDACritic", fda_hipaa_critic_node)
workflow.add_edge(START, "MedicalWriter")
workflow.add_edge("MedicalWriter", "FDACritic")
workflow.add_conditional_edges("FDACritic", evaluate_route, {"pass": END, "fail": "MedicalWriter"})
graph_application = workflow.compile()

# =====================================================================
# 4. FASTAPI APPLICATION WITH SECURITY MIDDLEWARE
# =====================================================================
app = FastAPI(
    title="Pharmaceutical Multi-Agent Automation Pipeline",
    description="Enterprise API with HIPAA security, PHI detection, and audit logging."
)

# Security: CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def add_request_logging(request: Request, call_next):
    """Add request ID and logging."""
    request_id = generate_request_id()
    request.state.request_id = request_id
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# =====================================================================
# 5. PYDANTIC SCHEMAS
# =====================================================================
class PipelineRequest(BaseModel):
    research_query: str = Field(
        ...,
        example="Draft Section 2.1 protocol for JAK inhibitor molecule TX-404.",
        max_length=5000
    )

class PipelineResponse(BaseModel):
    status: str
    final_draft: str
    total_iterations: int
    compliance_summary: Dict[str, Any]

# =====================================================================
# 6. API ENDPOINTS
# =====================================================================

@app.post("/api/v1/generate-protocol", response_model=PipelineResponse)
async def process_pipeline_endpoint(request: Request, payload: PipelineRequest):
    """
    Generate compliant medical protocol with PHI detection and FDA/HIPAA checks.
    
    Security features:
    - Rate limiting per IP
    - Input validation (SQL injection, XSS prevention)
    - PHI detection and logging
    - Request tracing with unique ID
    - Comprehensive audit logging
    """
    request_id = request.state.request_id
    client_ip = request.client.host
    
    # Rate limiting
    if not rate_limiter.is_allowed(f"protocol_{client_ip}"):
        logger.warning(f"[{request_id}] Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "60", "X-Request-ID": request_id},
        )
    
    # Input validation
    try:
        query = InputValidator.validate_string(
            payload.research_query,
            max_length=5000,
            field_name="research_query"
        )
    except ValueError as e:
        logger.warning(f"[{request_id}] Input validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # PHI detection (informational)
    phi_is_compliant, detected_phi = PHIDetector.scan_for_phi_violations(query, allow_detected_phi=True)
    if detected_phi:
        logger.warning(f"[{request_id}] PHI detected in query: {list(detected_phi.keys())}")
    
    try:
        logger.info(f"[{request_id}] Starting pipeline: {query[:80]}...")
        
        initial_state: AgentState = {
            "research_query": query,
            "retrieved_context": "",
            "generated_draft": "",
            "critic_feedback": {},
            "iteration_count": 0
        }
        
        result = graph_application.invoke(initial_state)
        
        # Log PHI in generated draft
        draft_phi_compliant, draft_phi = PHIDetector.scan_for_phi_violations(
            result["generated_draft"],
            allow_detected_phi=True
        )
        
        # Record audit
        db = SessionLocal()
        try:
            audit_entry = CriticAuditLog(
                request_id=request_id,
                query_topic=query[:255],
                iteration_number=result["iteration_count"],
                is_fda_compliant=result["critic_feedback"].get("is_fda_compliant", False),
                is_hipaa_compliant=result["critic_feedback"].get("is_hipaa_compliant", False),
                phi_leaks_found=draft_phi,
                raw_critique_json=result["critic_feedback"],
                evaluated_draft_text=result["generated_draft"][:2000]  # Truncate for storage
            )
            db.add(audit_entry)
            db.commit()
            logger.info(f"[{request_id}] Audit logged successfully")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to log audit: {str(e)}")
            db.rollback()
        finally:
            db.close()
        
        logger.info(f"[{request_id}] Pipeline completed in {result['iteration_count']} iterations")
        
        return PipelineResponse(
            status="Success",
            final_draft=result["generated_draft"],
            total_iterations=result["iteration_count"],
            compliance_summary=result["critic_feedback"]
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Pipeline execution failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}",
            headers={"X-Request-ID": request_id},
        )

@app.get("/api/v1/audit-trail")
async def get_audit_trail(request: Request, limit: int = 10):
    """
    Retrieve audit trail entries.
    
    Security features:
    - Rate limiting
    - Parameter validation
    - Request tracing
    """
    request_id = request.state.request_id
    
    # Rate limiting
    if not rate_limiter.is_allowed(f"audit_{request.client.host}"):
        logger.warning(f"[{request_id}] Rate limit exceeded for audit trail")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "60"},
        )
    
    # Validate limit
    limit = max(1, min(limit, 100))
    
    db = SessionLocal()
    try:
        logs = db.query(CriticAuditLog).order_by(CriticAuditLog.timestamp.desc())
        results = logs.limit(limit).all()
        logger.info(f"[{request_id}] Retrieved {len(results)} audit entries")
        
        return [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "request_id": log.request_id,
                "query": log.query_topic[:100],
                "iteration": log.iteration_number,
                "fda_compliant": log.is_fda_compliant,
                "hipaa_compliant": log.is_hipaa_compliant,
                "phi_leaks": log.phi_leaks_found,
            } for log in results
        ]
    except Exception as e:
        logger.error(f"[{request_id}] Error retrieving audit trail: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving audit trail",
            headers={"X-Request-ID": request_id},
        )
    finally:
        db.close()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

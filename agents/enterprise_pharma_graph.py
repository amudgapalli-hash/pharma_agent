import os
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# LangChain & Ollama core components
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

# LangGraph state management
from langgraph.graph import StateGraph, START, END

# Vector Database (Using Local Qdrant Memory Client for Mock Integration)
try:
    from langchain_qdrant import Qdrant  # type: ignore[import-not-found]
except ImportError:  # Fallback for environments using the community integration
    try:
        from langchain_community.vectorstores import Qdrant  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "Qdrant integration is unavailable. Install langchain-qdrant or "
            "langchain-community to use this module."
        ) from exc

from qdrant_client import QdrantClient

# =====================================================================
# 1. ENTERPRISE DATA MODELING & STATES
# =====================================================================

class FDACritique(BaseModel):
    is_compliant: bool = Field(description="True if the text fully adheres to FDA E6(R2) / ICH guidelines, False otherwise.")
    missing_elements: List[str] = Field(description="Specific missing components, regulatory data, or unbacked clinical assumptions.")
    revisions_required: str = Field(description="Clear directives for the writer agent on how to adjust text for compliance.")

class AgentState(TypedDict):
    """Maintains the continuous state passing through the LangGraph workflow."""
    research_query: str
    retrieved_context: str
    generated_draft: str
    critic_feedback: Dict[str, Any]
    iteration_count: int

# =====================================================================
# 2. LOCAL AGENT AND VECTOR DB CONFIGURATION
# =====================================================================
# Ollama models optimized for local enterprise deployment
llm_writer = ChatOllama(model="llama3", base_url="http://localhost:11434", temperature=0.3)
llm_critic = ChatOllama(model="llama3", base_url="http://localhost:11434", temperature=0.0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# Initialize an in-memory high performance Vector DB client
qdrant_client = QdrantClient(":memory:")
vector_store = Qdrant(client=qdrant_client, collection_name="pharma_literature", embeddings=embeddings)

def seed_enterprise_knowledge_base():
    """
    Blueprint function mimicking batch ingestion.
    In production, replace with directory loops using UnstructuredPDFLoader:
    >>> from langchain_community.document_loaders import UnstructuredPDFLoader
    >>> loader = UnstructuredPDFLoader("path/to/fda_guidelines.pdf")
    """
    mock_literature = [
        "FDA E6(R2) Guidelines stipulate that all clinical rationales must declare primary indications, pre-clinical safety signal markers, and explicit adverse events monitoring steps.",
        "Clinical trials evaluating therapeutic TX-404 must account for transient elevations in hepatic transaminases and establish rigorous baseline testing parameters for target cohorts."
    ]
    vector_store.add_texts(mock_literature)

# Initialize vector collection
seed_enterprise_knowledge_base()

# =====================================================================
# 3. GRAPH NODE ACTIONS
# =====================================================================

def retrieve_context_node(state: AgentState) -> Dict[str, Any]:
    """Queries the localized database to inject target data parameters."""
    print("🔍 [Node: Retriever] Fetching relevant regulatory and clinical guidelines...")
    docs = vector_store.similarity_search(state["research_query"], k=2)
    combined_context = "\n".join([doc.page_content for doc in docs])
    return {"retrieved_context": combined_context}

def medical_writer_node(state: AgentState) -> Dict[str, Any]:
    """Generates or revises the pharmaceutical protocol based on critique feedback."""
    print("📝 [Node: Medical Writer] Processing literature context and drafting section...")
    
    feedback_str = "None (Initial Draft)"
    if state.get("critic_feedback"):
        feedback_str = f"FAILED PREVIOUS REVIEW: {state['critic_feedback']['revisions_required']}"
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Clinical Protocol Writer. Synthesize technical raw text into formal "
                   "Section 2.1 Background & Rationale writeups. Maintain strict medical objectivity."),
        ("user", "Draft clinical protocol text for: {query}.\n\n"
                 "Utilize this RAG Reference Material:\n{context}\n\n"
                 "Address this compliance feedback:\n{feedback}")
    ])
    
    writer_chain = prompt | llm_writer | StrOutputParser()
    draft = writer_chain.invoke({
        "query": state["research_query"],
        "context": state["retrieved_context"],
        "feedback": feedback_str
    })
    return {"generated_draft": draft, "iteration_count": state.get("iteration_count", 0) + 1}

def fda_critic_node(state: AgentState) -> Dict[str, Any]:
    """Evaluates the text against target protocols using structured JSON formatting."""
    print("⚖️ [Node: FDA Critic] Reviewing generated draft against FDA validation rules...")
    parser = JsonOutputParser(pydantic_object=FDACritique)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an FDA Regulatory Compliance Officer verifying clinical application drafts against "
                   "ICH E6(R2) and FDA safety oversight models. Be pedantic, uncompromising, and objective. "
                   "Output strictly a JSON document matching the template schema:\n{format_instructions}"),
        ("user", "Assess this proposed text section:\n\n{draft}")
    ]).partial(format_instructions=parser.get_format_instructions())
    
    critic_chain = prompt | llm_critic | parser
    feedback = critic_chain.invoke({"draft": state["generated_draft"]})
    return {"critic_feedback": feedback}

# =====================================================================
# 4. CONDITIONAL ROUTING LOGIC
# =====================================================================

def evaluate_compliance_route(state: AgentState) -> Literal["pass", "fail"]:
    """Directs flow down to completion or forces an iteration correction loop."""
    feedback = state["critic_feedback"]
    
    # Circuit breaker setup to protect against endless loops
    if state.get("iteration_count", 0) >= 3:
        print("⚠️ [Router] Maximum optimization loops reached. Forcing export.")
        return "pass"
        
    if feedback.get("is_compliant") is True:
        print("🎉 [Router] Draft passed FDA Compliance Check cleanly.")
        return "pass"
    else:
        print(f"❌ [Router] Draft rejected by FDA Critic. Required revisions: {feedback.get('missing_elements')}")
        return "fail"

# =====================================================================
# 5. COMPILING THE GRAPH CONFIGURATION
# =====================================================================

workflow = StateGraph(AgentState)

# Append functional operational nodes
workflow.add_node("RetrieveContext", retrieve_context_node)
workflow.add_node("MedicalWriter", medical_writer_node)
workflow.add_node("FDACritic", fda_critic_node)

# Map edge connections
workflow.add_edge(START, "RetrieveContext")
workflow.add_edge("RetrieveContext", "MedicalWriter")
workflow.add_edge("MedicalWriter", "FDACritic")

# Inject the dynamic loop-back routing evaluation
workflow.add_conditional_edges(
    "FDACritic",
    evaluate_compliance_route,
    {
        "pass": END,
        "fail": "MedicalWriter"
    }
)

# Compile into structural executable runtime
app = workflow.compile()

# =====================================================================
# 6. RUN SYSTEM EXECUTION
# =====================================================================
if __name__ == "__main__":
    initial_input = {
        "research_query": "Draft Section 2.1 protocol for JAK inhibitor molecule TX-404 handling joint erosion.",
        "iteration_count": 0
    }
    
    final_state = app.invoke(initial_input)
    
    print("\n FINAL GRAPH OUTPUT GENERATION:")
    print("=" * 80)
    print(final_state["generated_draft"])
    print("=" * 80)

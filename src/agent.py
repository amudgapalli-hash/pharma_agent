# src/agent.py
from langgraph.graph import StateGraph, START, END
from typing import TypedDict
import os
from dotenv import load_dotenv

load_dotenv()   

class AgentState(TypedDict, total=False):
    compliant: bool

# ... (Your state definitions, nodes, and routing logic) ...

def retrieve_context_node(state: AgentState) -> AgentState:
    """Retrieve supporting context for the medical writer."""
    return state

def medical_writer_node(state: AgentState) -> AgentState:
    """Draft medical content from the retrieved context."""
    return state

def fda_critic_node(state: AgentState) -> AgentState:
    """Evaluate the medical draft for compliance."""
    return state

def evaluate_compliance_route(state: AgentState) -> str:
    """Route according to the FDA critic's compliance result."""
    return "pass" if state.get("compliant", False) else "fail"

workflow = StateGraph(AgentState)

# Add nodes and edges
workflow.add_node("RetrieveContext", retrieve_context_node)
workflow.add_node("MedicalWriter", medical_writer_node)
workflow.add_node("FDACritic", fda_critic_node)

workflow.add_edge(START, "RetrieveContext")
workflow.add_edge("RetrieveContext", "MedicalWriter")
workflow.add_edge("MedicalWriter", "FDACritic")

workflow.add_conditional_edges(
    "FDACritic",
    evaluate_compliance_route,
    {"pass": END, "fail": "MedicalWriter"}
)

# Top-level compiled variable referenced by langgraph.json
graph = workflow.compile()
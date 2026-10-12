import json
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

# =====================================================================
# 1. DEFINE STRUCTURED DATA SCHEMAS (Data Ingestion & Extraction)
# =====================================================================
class ClinicalTrialData(BaseModel):
    drug_name: str = Field(description="Name of the therapeutic molecule or drug candidate.")
    sample_size: int = Field(description="Total number of patients or participants enrolled in the study.")
    primary_indication: str = Field(description="The primary disease or condition targeted by the trial.")
    efficacy_metrics: str = Field(description="Key findings, p-values, or statistical success metrics.")
    adverse_events: List[str] = Field(description="List of documented side effects or safety signals.")
    dosage_regimen: str = Field(description="The dosage amount, frequency, and route of administration.")

# =====================================================================
# 2. INITIALIZE AGENT INFRASTRUCTURE (Local Ollama Endpoint)
# =====================================================================
# We use a low temperature (0.0) to strictly enforce factual data extraction
local_llm = ChatOllama(
    model="llama3", 
    base_url="http://localhost:11434",
    temperature=0.0
)

# =====================================================================
# 3. AGENT DEFINITIONS
# =====================================================================

def run_extraction_agent(raw_literature_text: str) -> ClinicalTrialData:
    """Agent 1: Ingests unformatted biomedical text and maps it to a strict schema."""
    parser = JsonOutputParser(pydantic_object=ClinicalTrialData)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Clinical Data Extraction Agent. Extrapolate critical insights from raw clinical papers. "
                   "Format your output strictly as a JSON object matching this schema:\n{format_instructions}"),
        ("user", "Extract data from the following medical text:\n\n{text}")
    ]).partial(format_instructions=parser.get_format_instructions())
    
    extraction_chain = prompt | local_llm | parser
    extracted_json = extraction_chain.invoke({"text": raw_literature_text})
    return ClinicalTrialData(**extracted_json)


def run_protocol_drafting_agent(extracted_data: ClinicalTrialData) -> str:
    """Agent 2: Acts as a Principal Medical Writer to synthesize data into FDA-ready text."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Principal Medical Writer specializing in regulatory affairs and FDA clinical protocol design. "
                   "Generate highly technical, objective, and precise trial literature synthesis based on structured data payloads."),
        ("user", "Draft the 'Section 2.1: Background and Clinical Rationale' for a new Phase II Clinical Protocol. "
                 "Incorporate the following extracted trial data into a professional prose narrative: \n\n{data_payload}")
    ])
    
    drafting_chain = prompt | local_llm | StrOutputParser()
    return drafting_chain.invoke({"data_payload": extracted_data.model_dump_json(indent=2)})

# =====================================================================
# 4. END-TO-END AUTOMATION EXECUTION
# =====================================================================
if __name__ == "__main__":
    # Mocking raw unformatted text retrieved from a PubMed query
    raw_pubmed_article = """
    In a recent multicenter study of the novel JAK inhibitor, Tofacit-X (coded as TX-404), researchers evaluated 
    its footprint in treating moderate-to-severe Rheumatoid Arthritis. The trial randomized 342 adult subjects. 
    Administered orally at 10mg twice daily, TX-404 demonstrated an ACR50 response rate of 58.4% at Week 12 (p < 0.001) 
    compared to the placebo control arm. The primary therapeutic focus remained on suppressing joint erosion. 
    Safety data indicated mild-to-moderate treatment-emergent complications, predominantly nausea, transient elevations 
    in hepatic transaminases, and low-grade upper respiratory tract infections. No cases of deep vein thrombosis were recorded.
    """
    
    print("🚀 Step 1: Initiating Literature Extraction Agent...")
    structured_findings = run_extraction_agent(raw_pubmed_article)
    print("\n✅ Extraction Complete. Validated Payload Structured:")
    print(json.dumps(structured_findings.model_dump(), indent=4))
    
    print("\n🚀 Step 2: Handoff to Protocol Drafting Agent...")
    protocol_section = run_protocol_drafting_agent(structured_findings)
    
    print("\n📝 Generated Protocol Blueprint Section:")
    print("-" * 80)
    print(protocol_section)
    print("-" * 80)

import os
import json
import yaml
import base64
from typing import Dict, TypedDict, Any
from dotenv import load_dotenv

# --- Azure OpenAI Setup ---
load_dotenv()
os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_API_KEY", "")
os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_ENDPOINT", "")
os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_API_VERSION", "2024-06-01")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# --- Memory Initialization ---
LOGICAL_MEMORY_FILE = "logical_memory.yaml"
if not os.path.exists(LOGICAL_MEMORY_FILE):
    with open(LOGICAL_MEMORY_FILE, 'w', encoding='utf-8') as f:
        yaml.dump({"learned_rules": {}}, f)

with open(LOGICAL_MEMORY_FILE, 'r', encoding='utf-8') as f:
    logical_memory = yaml.safe_load(f) or {"learned_rules": {}}

def save_logical_memory():
    with open(LOGICAL_MEMORY_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(logical_memory, f, sort_keys=False)

def encode_image(image_path: str) -> str:
    if not image_path or not os.path.exists(image_path): return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- PHASE 1: DATA PREP (Column-Centric Engine) ---
def flatten_graphql_response(api_key, json_filepath):
    """Pivots GraphQL JSONs into Token-Efficient Column Arrays."""
    if "PreferenceData" in api_key or "Config" in api_key: return "[Ignored: UI Configuration API - No Business Logic]"
    if not os.path.exists(json_filepath): return f"[Error: Dump file not found at {json_filepath}]"
    
    with open(json_filepath, 'r', encoding='utf-8') as f:
        try: full_dump = json.load(f)
        except: return "[Error: Invalid JSON]"

    req_data = full_dump.get("request", {})
    resp_data = full_dump.get("response", {})

    try: measure_headers = req_data.get("variables", {}).get("query", {}).get("aggregatedMeasures", [])
    except: measure_headers = []

    def find_edges(node):
        if isinstance(node, dict):
            if "edges" in node: return node["edges"]
            for k, v in node.items():
                res = find_edges(v)
                if res: return res
        elif isinstance(node, list):
            for item in node:
                res = find_edges(item)
                if res: return res
        return None

    edges = find_edges(resp_data)
    if not edges: return "[No grid 'edges' data found in this payload]"

    columns = {"Dimensions (Rows)": []}
    for header in measure_headers: columns[header] = []

    for edge in edges:
        node = edge.get("node", {})
        dims = node.get("dimensionMembers", [])
        dim_names = [str(d.get("name", "Unknown")) for d in dims if d.get("name")]
        row_title = " | ".join(dim_names) if dim_names else "Total/Aggregate"
        columns["Dimensions (Rows)"].append(row_title)
        
        measures = node.get("measureValues", [])
        for i, val in enumerate(measures):
            clean_val = round(val, 2) if isinstance(val, float) else val
            if i < len(measure_headers): columns[measure_headers[i]].append(clean_val)
            else:
                col_key = f"Unknown_Measure_{i}"
                if col_key not in columns: columns[col_key] = []
                columns[col_key].append(clean_val)

    output_lines = ["Grid Data (Column-Centric View):"]
    for col_name, values in columns.items():
        if values: output_lines.append(f"  - Column [{col_name}]: {values}")

    return "\n".join(output_lines)

def get_latest_regression_evidence():
    """Finds the most recent regression run folder and loads its evidence file."""
    runs_dir = "Regression_Runs"
    if not os.path.exists(runs_dir):
        print(f"❌ Error: '{runs_dir}' folder not found.")
        return None
        
    runs = sorted([d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))], reverse=True)
    if not runs:
        print("❌ Error: No regression runs found.")
        return None
        
    latest_run = runs[0]
    evidence_path = os.path.join(runs_dir, latest_run, "regression_evidence.yaml")
    
    if not os.path.exists(evidence_path):
        print(f"❌ Error: 'regression_evidence.yaml' not found in {latest_run}.")
        return None
        
    print(f"📂 Loading Evidence from Latest Run: {latest_run}")
    return evidence_path

def build_test_case_payloads():
    evidence_path = get_latest_regression_evidence()
    if not evidence_path: return []

    with open(evidence_path, "r", encoding="utf-8") as f: 
        evidence_kb = yaml.safe_load(f)

    test_cases = evidence_kb.get("test_cases", [])
    if not test_cases:
        print("⚠️ No test cases found in the evidence file.")
        return []

    print("\n" + "="*80)
    print("🧠 PHASE 1: CONTEXT FUSION NODE (DATA PREP)")
    print("="*80)

    llm_payloads = []

    for test in test_cases:
        test_name = test.get("test_name", "Unknown Test")
        print(f"  └── Compiling Case File: {test_name}")
        timeline_context = []

        for idx, snap in enumerate(test.get("snapshots", [])):
            step_num = idx + 1
            human_note = snap.get("human_note", "")
            image_path = snap.get("image_path", "No image")
            apis = snap.get("apis_triggered", [])

            step_context = {
                "step_number": step_num,
                "human_constraint": human_note,
                "image_attached": image_path,
                "api_data": {}
            }

            if apis:
                for api in apis:
                    api_key = api.get("api_key")
                    file_path = api.get("file")
                    # Truncate & Pivot the JSON!
                    step_context["api_data"][api_key] = flatten_graphql_response(api_key, file_path)

            timeline_context.append(step_context)

        llm_payloads.append({"test_name": test_name, "storyboard": timeline_context})
        
    return llm_payloads

# --- PHASE 2 & 3: LANGGRAPH LOGICAL AGENT ---

class LogicalState(TypedDict):
    test_name: str
    storyboard: list
    evaluation: dict

def evaluator_node(state: LogicalState):
    print(f"\n🧠 [Evaluator Node] Analyzing Logical Test Case: '{state['test_name']}'...")
    
    llm = AzureChatOpenAI(
        azure_deployment=AZURE_DEPLOYMENT_NAME,
        temperature=0.1, # Low temp for strict logical reasoning
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    # Inject Agent Memory Fine-Tuning
    memory_rule = logical_memory["learned_rules"].get(state['test_name'], "")
    memory_prompt = f"\n\nCRITICAL PAST HUMAN CORRECTION FOR THIS TEST: {memory_rule}\nYou MUST strictly obey this rule when evaluating." if memory_rule else ""

    system_prompt = SystemMessage(content=(
        "You are a Principal QA Architect validating complex business logic for an enterprise web application. "
        "You will be given a chronological storyboard of an automated UI test. Each step contains an image, a human constraint/rule, and optionally, backend API data. "
        "Evaluate the storyboard sequentially. Does the final visual state AND the mathematical API data prove the human's constraints were met? "
        "Use mathematical reasoning when verifying grid data against filters or sorting rules. "
        f"{memory_prompt}\n\n"
        "Output ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "chain_of_thought": "Step-by-step reasoning evaluating visual and mathematical evidence.",\n'
        '  "status": "PASS" | "FAIL",\n'
        '  "bug_description": "If FAIL, explicitly state why the logic was violated. If PASS, return None."\n'
        "}"
    ))

    content_payload = [{"type": "text", "text": f"Evaluating Storyboard for: {state['test_name']}\n"}]
    
    for step in state['storyboard']:
        text_chunk = f"\n--- STEP {step['step_number']} ---\nHuman Rule/Constraint: {step['human_constraint']}\n"
        if step['api_data']:
            text_chunk += "Backend API Data Dumped during this step:\n"
            for k, v in step['api_data'].items():
                if "Ignored" not in v:
                    text_chunk += f"API [{k}]:\n{v}\n"
        
        content_payload.append({"type": "text", "text": text_chunk})
        
        b64_img = encode_image(step['image_attached'])
        if b64_img:
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}", "detail": "high"}})

    user_prompt = HumanMessage(content=content_payload)

    try:
        response = llm.invoke([system_prompt, user_prompt])
        raw_json = response.content.strip()
        if raw_json.startswith("```json"): raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"): raw_json = raw_json[3:-3].strip()
        result = json.loads(raw_json)
        
        print(f"  └── 🕵️‍♂️ Reasoning: {result.get('chain_of_thought')}")
        print(f"  └── ⚖️ Initial Verdict: {result.get('status')}")
        return {"evaluation": result}
    except Exception as e:
        print(f"  └── ⚠️ LLM Error: {e}")
        return {"evaluation": {"status": "FAIL", "bug_description": f"LLM parsing error: {e}"}}

def hitl_triage_node(state: LogicalState):
    print(f"\n" + "!"*70)
    print(f"🚨 LOGICAL BUG DETECTED IN: '{state['test_name']}'")
    print(f"   Reasoning: {state['evaluation'].get('bug_description')}")
    print("!"*70)
    
    print("   [Opening storyboard images for your review...]")
    for step in state['storyboard']:
        try:
            if os.path.exists(step['image_attached']):
                os.startfile(step['image_attached'])
                import time; time.sleep(0.3)
        except: pass
    
    while True:
        choice = input("\n   👉 Is this a REAL logical bug? (y = Confirmed, n = False Positive, s = Skip): ").strip().lower()
        if choice in ['y', 'n', 's']: break
    
    if choice == 'y':
        print("   └── 🐞 Bug Confirmed! Logging to report.")
        state['evaluation']['final_status'] = "CONFIRMED_BUG"
        
    elif choice == 'n':
        print("   └── 🔧 FALSE POSITIVE. Let's fine-tune the agent's logic.")
        correction = input("       Explain the correct business logic so the Agent learns: \n       > ")
        
        logical_memory["learned_rules"][state['test_name']] = correction
        save_logical_memory()
        
        state['evaluation']['status'] = "PASS"
        state['evaluation']['final_status'] = "FALSE_POSITIVE_RESOLVED"
        state['evaluation']['bug_description'] = f"Overridden by human: {correction}"
        print("   └── 🧠 Logical Memory Updated!")
        
    return {"evaluation": state['evaluation']}

# --- Routing Logic ---
def route_evaluation(state: LogicalState):
    if state['evaluation'].get('status') == "FAIL":
        return "hitl_triage"
    return END

# --- Build & Execute Graph ---
def run_logical_agent():
    print("\n" + "="*80)
    print("🚀 INITIALIZING PHASE 1: DATA FUSION & EVIDENCE RETRIEVAL")
    payloads = build_test_case_payloads()
    
    if not payloads:
        return

    # Build LangGraph
    workflow = StateGraph(LogicalState)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("hitl_triage", hitl_triage_node)
    
    workflow.add_edge(START, "evaluator")
    workflow.add_conditional_edges("evaluator", route_evaluation)
    workflow.add_edge("hitl_triage", END)
    
    app = workflow.compile()

    print("\n" + "="*80)
    print("🧠 EXECUTING PHASE 2 & 3: LOGICAL EVALUATION & HITL TRIAGE")
    print("="*80)

    results_report = []

    for payload in payloads:
        initial_state = {
            "test_name": payload['test_name'],
            "storyboard": payload['storyboard'],
            "evaluation": {}
        }
        
        final_state = app.invoke(initial_state)
        
        results_report.append({
            "test_name": payload['test_name'],
            "status": final_state['evaluation'].get('status'),
            "details": final_state['evaluation'].get('bug_description')
        })

    print("\n" + "="*80)
    print("📊 FINAL LOGICAL TEST REPORT")
    print("="*80)
    for res in results_report:
        icon = "✅" if res['status'] == "PASS" else "❌"
        print(f"{icon} {res['test_name']}")
        if res['status'] != "PASS":
            print(f"   └── {res['details']}")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_logical_agent()

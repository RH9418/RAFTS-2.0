import os
import base64
import json
import yaml
import time
from datetime import datetime
from typing import Dict, TypedDict, Any, List
from dotenv import load_dotenv

try:
    import pandas as pd
except ImportError:
    print("❌ Missing required libraries for Excel export. Please run: pip install pandas openpyxl")
    exit(1)

# --- Load Environment Variables ---
load_dotenv()
os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_API_KEY", "")
os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_ENDPOINT", "")
os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_API_VERSION", "2024-06-01")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# --- Dynamic Agent Memory Initialization ---
AGENT_MEMORY_FILE = ""
agent_memory = {}

def init_agent_memory(kb_filename):
    global AGENT_MEMORY_FILE, agent_memory
    # Create a unique memory file for this specific knowledge base
    base_name = os.path.basename(kb_filename).replace(".yaml", "")
    AGENT_MEMORY_FILE = f"agent_memory_{base_name}.yaml"
    
    if not os.path.exists(AGENT_MEMORY_FILE):
        with open(AGENT_MEMORY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump({"learned_rules": {}}, f)
            
    with open(AGENT_MEMORY_FILE, 'r', encoding='utf-8') as f:
        agent_memory = yaml.safe_load(f) or {"learned_rules": {}}
        
    print(f"  🧠 Loaded Agent Memory: {AGENT_MEMORY_FILE}")

def save_agent_memory():
    global AGENT_MEMORY_FILE, agent_memory
    with open(AGENT_MEMORY_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(agent_memory, f, sort_keys=False)

def encode_image(image_path: str) -> str:
    if not image_path or not os.path.exists(image_path): return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- 1. Define the LangGraph State ---
class AgentState(TypedDict):
    chunk_id: str
    steps: List[dict]
    start_image_path: str
    end_image_path: str
    code_chunk_text: str
    enriched_images: dict
    predicted_outcome: str      
    confidence_score: float
    confusing_step_id: str
    loop_count: int
    verification_status: str
    bug_description: str
    micro_debug_result: str

# --- 2. The Semantic Segmenter (Text Only) ---
def segment_steps(steps: List[dict]) -> List[List[dict]]:
    if not steps: return []
    if len(steps) <= 3: return [steps] 
    
    print("  🧠 [Semantic Segmenter] Analyzing code to build semantic chunks...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.0, model_kwargs={"response_format": {"type": "json_object"}})
    
    steps_text = "\n".join([f"StepID [{s['step_id']}]: {s['raw_code']}" for s in steps])
    
    system_prompt = SystemMessage(content=(
        "You are an AI Test Architect. Group the following sequential automation steps into semantic chunks. "
        "A chunk represents a single logical user goal (e.g., 'Applying a filter', 'Sorting a grid'). "
        "Chunks should ideally be 4 to 8 steps long. Break chunks AFTER state-committing actions (clicks/navigates). "
        "Output ONLY JSON in this format: { \"chunks\": [ [\"1_1\", \"1_2\"], [\"1_3\"] ] }\n"
        "Ensure the strings in the arrays perfectly match the StepID."
    ))
    
    try:
        response = llm.invoke([system_prompt, HumanMessage(content=steps_text)])
        raw_json = response.content.strip()
        if raw_json.startswith("```json"): raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"): raw_json = raw_json[3:-3].strip()
        
        parsed = json.loads(raw_json)
        chunk_ids = parsed.get("chunks", [])
        
        step_map = {str(s['step_id']).strip(): s for s in steps}
        final_chunks = []
        for id_list in chunk_ids:
            chunk = []
            for i in id_list:
                clean_i = str(i).replace("Step", "").replace("ID", "").replace("[", "").replace("]", "").strip()
                if clean_i in step_map:
                    chunk.append(step_map[clean_i])
            if chunk: final_chunks.append(chunk)
            
        print(f"    └── Successfully mapped into {len(final_chunks)} semantic chunks.")
        return final_chunks
    except Exception as e:
        print(f"  ⚠️ Segmentation failed, falling back to heuristic chunks. Error: {e}")
        return [steps[i:i + 5] for i in range(0, len(steps), 5)]

# --- 3. The LangGraph Nodes ---
def predictor_node(state: AgentState):
    print(f"  [Node: Predictor] Simulating Code Chunk (Confidence Loop: {state['loop_count']})...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.1, model_kwargs={"response_format": {"type": "json_object"}})
    
    content_payload = [{"type": "text", "text": f"Simulate this code sequentially:\n{state['code_chunk_text']}"}]
    
    b64_start = encode_image(state["start_image_path"])
    if b64_start:
        content_payload.append({"type": "text", "text": "Starting UI State:"})
        content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_start}", "detail": "high"}})
    
    if state["enriched_images"]:
        content_payload.append({"type": "text", "text": "ENRICHED CONTEXT: Here are the exact elements interacted with for the steps you found confusing:"})
        for s_id, path in state["enriched_images"].items():
            b64_intent = encode_image(path)
            if b64_intent:
                content_payload.append({"type": "text", "text": f"Crosshair for Step {s_id}:"})
                content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_intent}", "detail": "high"}})
    
    learned_context = ""
    for step in state["steps"]:
        rule = agent_memory["learned_rules"].get(step['raw_code'])
        if rule: learned_context += f"\n- Rule for `{step['raw_code']}`: {rule}"
    
    system_prompt = SystemMessage(content=(
        "You are an expert UI/UX Test Automation Architect. "
        "You receive a Start Image and a sequential block of Playwright code. "
        "Predict what the final UI state will look like AFTER all code executes. "
        "If a specific line of code has an unreadable/wild CSS locator that makes you guess, return a low confidence score and set 'confusing_step_id' to that step. "
        f"HUMAN OVERRIDES TO APPLY STRICTLY: {learned_context}\n\n"
        "Output JSON:\n"
        "{\n"
        '  "predicted_outcome": "Step-by-step logic, ending with a description of the final state.",\n'
        '  "confidence_score": 0.0 to 1.0,\n'
        '  "confusing_step_id": "step_id_here" (or null if confident >= 0.85)\n'
        "}"
    ))
    try:
        response = llm.invoke([system_prompt, HumanMessage(content=content_payload)])
        raw_json = response.content.strip()
        if raw_json.startswith("```json"): raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"): raw_json = raw_json[3:-3].strip()
        
        result = json.loads(raw_json)
        state['predicted_outcome'] = result.get("predicted_outcome", "")
        state['confidence_score'] = result.get("confidence_score", 1.0)
        state['confusing_step_id'] = result.get("confusing_step_id")
        
        print(f"    └── Confidence: {state['confidence_score']:.2f}")
        return state
    except Exception as e:
        print(f"    └── ⚠️ LLM Error: {e}")
        state['predicted_outcome'] = "Error predicting state."
        state['confidence_score'] = 1.0 
        return state

def enricher_node(state: AgentState):
    target_id = state['confusing_step_id']
    target_id = str(target_id).replace("Step", "").replace("ID", "").replace("[", "").replace("]", "").strip()
    
    print(f"  [Node: Enricher] Agent requested clarification on Step {target_id}. Fetching Crosshair Image...")
    
    target_step = next((s for s in state['steps'] if str(s['step_id']).strip() == target_id), None)
    if target_step and target_step.get("baseline_images", {}).get("intent"):
        state['enriched_images'][target_id] = target_step["baseline_images"]["intent"]
    else:
        print(f"    └── ⚠️ Crosshair image not found for {target_id}. Forcing verification.")
        state['confidence_score'] = 1.0
        
    state['loop_count'] += 1
    return state

def verifier_node(state: AgentState):
    print(f"  [Node: Verifier] Validating Final Chunk Output...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.0, model_kwargs={"response_format": {"type": "json_object"}})
    
    b64_end = encode_image(state["end_image_path"])
    if not b64_end: 
        state['verification_status'] = "FAIL"
        state['bug_description'] = "End image not found."
        return state

    system_prompt = SystemMessage(content=(
        "You are a strict QA Inspector. You are analyzing the 'End' screenshot of a UI code chunk. "
        "Does the visual state match the 'Expected Outcome' exactly? "
        "Output JSON:\n"
        "{\n"
        '  "status": "PASS" or "FAIL",\n'
        '  "description": "Brief explanation"\n'
        "}"
    ))

    user_prompt = HumanMessage(content=[
        {"type": "text", "text": f"Expected Outcome:\n{state['predicted_outcome']}"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_end}", "detail": "high"}}
    ])

    try:
        response = llm.invoke([system_prompt, user_prompt])
        raw_json = response.content.strip()
        if raw_json.startswith("```json"): raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"): raw_json = raw_json[3:-3].strip()
        
        result = json.loads(raw_json)
        state['verification_status'] = result.get("status", "FAIL")
        state['bug_description'] = result.get("description", "")
        print(f"    └── Verdict: {state['verification_status']}")
        return state
    except Exception as e:
        state['verification_status'] = "FAIL"
        state['bug_description'] = f"Verification Error: {e}"
        return state

def micro_debug_node(state: AgentState):
    print(f"  [Node: Micro-Debug] Chunk failed. Replaying timeline frame-by-frame to isolate bug...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.1, model_kwargs={"response_format": {"type": "json_object"}})
    
    content_payload = [{"type": "text", "text": "The chunk execution failed to reach the expected final state. Here is the frame-by-frame replay. Identify EXACTLY which step caused the UI to break or stop responding."}]
    
    for step in state['steps']:
        content_payload.append({"type": "text", "text": f"\nExecuting Step {step['step_id']}: `{step['raw_code']}`"})
        
        intent_b64 = encode_image(step.get("baseline_images", {}).get("intent"))
        if intent_b64:
            content_payload.append({"type": "text", "text": "Element Clicked (Crosshair):"})
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{intent_b64}", "detail": "high"}})
            
        after_b64 = encode_image(step.get("baseline_images", {}).get("after"))
        if after_b64:
            content_payload.append({"type": "text", "text": "Resulting UI State:"})
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_b64}", "detail": "high"}})

    system_prompt = SystemMessage(content=(
        "You are an investigative QA Agent. Review the timeline of actions and images. "
        "Find the exact step where the UI failed to respond properly. "
        "Output JSON:\n"
        "{\n"
        '  "failed_step_id": "The exact step_id that broke",\n'
        '  "root_cause": "Detailed explanation of what failed."\n'
        "}"
    ))

    try:
        response = llm.invoke([system_prompt, HumanMessage(content=content_payload)])
        raw_json = response.content.strip()
        if raw_json.startswith("```json"): raw_json = raw_json[7:-3].strip()
        elif raw_json.startswith("```"): raw_json = raw_json[3:-3].strip()
        
        result = json.loads(raw_json)
        state['micro_debug_result'] = f"Failed at Step {result.get('failed_step_id')}: {result.get('root_cause')}"
        print(f"    └── Isolated Bug: {state['micro_debug_result']}")
        return state
    except Exception:
        state['micro_debug_result'] = "Could not isolate bug via micro-debug."
        return state

# --- 4. Define Routing Logic ---
def route_prediction(state: AgentState):
    if state['confidence_score'] < 0.85 and state.get('confusing_step_id') and state['loop_count'] < 2:
        return "enricher"
    return "verifier"

def route_verification(state: AgentState):
    if state['verification_status'] == "FAIL":
        return "micro_debug"
    return END

# --- 5. Build Graph ---
def build_agent_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("predictor", predictor_node)
    workflow.add_node("enricher", enricher_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("micro_debug", micro_debug_node)
    
    workflow.add_edge(START, "predictor")
    workflow.add_conditional_edges("predictor", route_prediction)
    workflow.add_edge("enricher", "predictor")
    workflow.add_conditional_edges("verifier", route_verification)
    workflow.add_edge("micro_debug", END)
    
    return workflow.compile()

# --- 6. Orchestrator ---
def main():
    print("\n" + "="*70)
    print("🤖 NAIVE AGENT V2: SEMANTIC CHUNKING & MACRO-MICRO DEBUGGING")
    print("="*70)
    
    # 🔴 DYNAMIC YAML INPUT
    default_kb = "workflow_kb.yaml"
    kb_path = input(f"Enter target Knowledge Base YAML\n(Press [ENTER] for default: {default_kb}):\n> ").strip()
    if not kb_path:
        kb_path = default_kb
    if not kb_path.endswith(".yaml"):
        kb_path += ".yaml"

    if not os.path.exists(kb_path):
        print(f"\n❌ Error: '{kb_path}' not found.")
        return

    # Initialize dynamic memory based on the specific KB
    init_agent_memory(kb_path)

    with open(kb_path, "r", encoding="utf-8") as f: 
        kb = yaml.safe_load(f)
        
    agent_graph = build_agent_graph()
    
    # 🔴 SET UP EXCEL REPORTING
    RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORT_DIR = "Naive_Agent_Reports"
    os.makedirs(REPORT_DIR, exist_ok=True)
    base_name = os.path.basename(kb_path).replace(".yaml", "")
    excel_report_path = os.path.join(REPORT_DIR, f"{base_name}_Report_{RUN_TIMESTAMP}.xlsx")
    
    excel_rows = []
    total_chunks = 0
    total_bugs = 0

    for section in kb.get("sections", []):
        section_name = section.get('section_name', 'Unknown')
        print(f"\n📁 Processing Section: {section_name}")
        
        valid_steps = [s for s in section.get("steps", []) if s.get("baseline_images", {}).get("before")]
        chunks = segment_steps(valid_steps)

        for chunk_idx, chunk_steps in enumerate(chunks):
            chunk_id = f"{section_name}_Chunk_{chunk_idx+1}"
            code_text = "\n".join([f"Step {s['step_id']}: {s['raw_code']}" for s in chunk_steps])
            
            print(f"\n  📦 Running {chunk_id} ({len(chunk_steps)} Actions)")
            
            initial_state = {
                "chunk_id": chunk_id,
                "steps": chunk_steps,
                "start_image_path": chunk_steps[0]["baseline_images"]["before"],
                "end_image_path": chunk_steps[-1]["baseline_images"]["after"],
                "code_chunk_text": code_text,
                "enriched_images": {},
                "predicted_outcome": "",
                "confidence_score": 1.0,
                "confusing_step_id": None,
                "loop_count": 0,
                "verification_status": "",
                "bug_description": "",
                "micro_debug_result": ""
            }

            final_state = agent_graph.invoke(initial_state)
            human_triage = "N/A"
            final_pass_fail = "PASS" if final_state["verification_status"] == "PASS" else "FAIL"

            if final_state["verification_status"] == "FAIL":
                print("\n" + "!"*60)
                print(f"🚨 BUG DETECTED IN CHUNK")
                print(f"   Micro-Debug Isolation: {final_state['micro_debug_result']}")
                
                try:
                    os.startfile(final_state["start_image_path"])
                    time.sleep(0.3)
                    os.startfile(final_state["end_image_path"])
                except: pass
                
                while True:
                    choice = input("\n   👉 Is this a REAL bug? (y = Confirmed, n = False Positive, s = Skip): ").strip().lower()
                    if choice in ['y', 'n', 's']: break
                    
                human_triage = choice
                if choice == 'y':
                    print("   └── 🐞 Bug Confirmed! Logging.")
                    total_bugs += 1
                elif choice == 'n':
                    correction = input("   └── 🔧 What SHOULD the Agent have expected? \n       > ")
                    agent_memory["learned_rules"][chunk_steps[-1]['raw_code']] = correction
                    save_agent_memory()
                    print("   └── 🧠 Agent Memory Updated.")
                    final_pass_fail = "PASS"  # Overridden by human

            # 🔴 PREPARE EXCEL ROW
            total_chunks += 1
            
            # Extract formatted screenshots for the Excel file
            screenshots_arr = []
            for s in chunk_steps:
                imgs = s.get("baseline_images", {})
                screenshots_arr.append(f"Step {s['step_id']}:\nBefore: {imgs.get('before')}\nIntent: {imgs.get('intent')}\nAfter: {imgs.get('after')}\n")
            
            observed_combined = final_state.get("bug_description", "")
            if final_state.get("micro_debug_result"):
                observed_combined += f"\n\nMicro-Debug:\n{final_state.get('micro_debug_result')}"

            excel_rows.append({
                "Test Case ID": chunk_id,
                "Section": section_name,
                "Test Steps": code_text,
                "Expected Result": final_state.get("predicted_outcome", ""),
                "Observed Result": observed_combined,
                "Screenshots": "\n".join(screenshots_arr),
                "Pass/Fail": final_pass_fail
            })
            
            # 🔴 INCREMENTAL EXCEL SAVE
            df = pd.DataFrame(excel_rows)
            df.to_excel(excel_report_path, index=False)

    print("\n" + "="*70)
    print("🏁 SEMANTIC WORKFLOW COMPLETE")
    print(f"   Semantic Chunks Evaluated: {total_chunks}")
    print(f"   Confirmed Bugs Found: {total_bugs}")
    print(f"   Excel Report Saved To: {excel_report_path}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

import os
import base64
import json
import yaml
import time
from datetime import datetime
from typing import Dict, TypedDict, Any, List
from dotenv import load_dotenv

VERBOSE_DEBUG_MODE = True

try:
    import pandas as pd
except ImportError:
    print("❌ Missing required libraries. Please run: pip install pandas openpyxl")
    exit(1)

try:
    import cv2
    import numpy as np
except ImportError:
    print("❌ Missing Computer Vision libraries. Please run: pip install opencv-python numpy")
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

# --- Dynamic Memory & Epistemic Ontology Initialization ---
EPISTEMIC_MEMORY_FILE = ""
ONTOLOGY_FILE = ""
epistemic_memory = {}
domain_ontology = {}

REPORT_DIR = "Epistemic_Agent_Reports"
DIFF_DIR = os.path.join(REPORT_DIR, "CV_Diffs")
os.makedirs(DIFF_DIR, exist_ok=True)

def init_memories(kb_filename):
    global EPISTEMIC_MEMORY_FILE, ONTOLOGY_FILE, epistemic_memory, domain_ontology
    base_name = os.path.basename(kb_filename).replace(".yaml", "")
    
    EPISTEMIC_MEMORY_FILE = f"epistemic_memory_{base_name}.yaml"
    ONTOLOGY_FILE = f"domain_ontology_{base_name}.yaml"
    
    if not os.path.exists(EPISTEMIC_MEMORY_FILE):
        with open(EPISTEMIC_MEMORY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump({"learned_rules": {}, "cached_chunks": {}, "global_rules": []}, f)
    with open(EPISTEMIC_MEMORY_FILE, 'r', encoding='utf-8') as f:
        epistemic_memory = yaml.safe_load(f) or {"learned_rules": {}, "cached_chunks": {}, "global_rules": []}
        
    if not os.path.exists(ONTOLOGY_FILE):
        with open(ONTOLOGY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump({"entities": {}, "hierarchies": {}, "business_logic": []}, f)
    with open(ONTOLOGY_FILE, 'r', encoding='utf-8') as f:
        domain_ontology = yaml.safe_load(f) or {"entities": {}, "hierarchies": {}, "business_logic": []}

    print(f"  🧠 Loaded Epistemic Memory & Domain Ontology for: {base_name}")

def save_memories():
    global EPISTEMIC_MEMORY_FILE, ONTOLOGY_FILE, epistemic_memory, domain_ontology
    with open(EPISTEMIC_MEMORY_FILE, 'w', encoding='utf-8') as f: 
        yaml.dump(epistemic_memory, f, sort_keys=False)
    with open(ONTOLOGY_FILE, 'w', encoding='utf-8') as f: 
        yaml.dump(domain_ontology, f, sort_keys=False)

def encode_image(image_path: str) -> str:
    if not image_path or not os.path.exists(image_path): return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- COMPUTER VISION DIFF ENGINE ---
def create_cv_diff_image(before_path, after_path, step_id):
    if not before_path or not after_path or not os.path.exists(before_path) or not os.path.exists(after_path): return after_path 
    out_path = os.path.join(DIFF_DIR, f"diff_{step_id}_{int(time.time())}.png")
    img1 = cv2.imread(before_path)
    img2 = cv2.imread(after_path)
    if img1 is None or img2 is None: return after_path
    
    g1 = cv2.GaussianBlur(cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY), (11, 11), 0)
    g2 = cv2.GaussianBlur(cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), (11, 11), 0)
    diff = cv2.absdiff(g1, g2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    kernel = np.ones((5,5), np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=3)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    result = img2.copy()
    drawn = False
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 20 and h > 20: 
            cv2.rectangle(result, (x, y), (x+w, y+h), (0, 0, 255), 4)
            drawn = True
    if drawn:
        cv2.imwrite(out_path, result)
        return out_path
    return after_path

# --- PILLAR 1: OPAQUE LOCATOR HEURISTIC ---
def is_opaque_locator(code_str: str) -> bool:
    """Returns True if the code lacks semantic selectors (like get_by_text, get_by_role)."""
    semantic_keywords = ["get_by_text", "get_by_role", "get_by_label", "get_by_placeholder"]
    if not any(k in code_str for k in semantic_keywords): return True
    if "nth-child" in code_str or ".locator(" in code_str: return True
    return False

# --- 1. Define the LangGraph State ---
class AgentState(TypedDict):
    chunk_id: str
    steps: List[dict]
    chunk_signature: str
    start_image_path: str
    end_image_path: str
    code_chunk_text: str
    enriched_images: dict
    ui_graph: dict              
    traceability_matrix: dict   
    verification_plan: list     
    confidence_score: float
    confusing_step_id: str
    loop_count: int
    is_cached: bool
    verification_status: str
    bug_description: str
    micro_debug_result: str

def segment_steps(steps: List[dict]) -> List[List[dict]]:
    if not steps: return []
    if len(steps) <= 3: return [steps] 
    
    print("  🧠 [Semantic Segmenter] Analyzing code to build semantic chunks...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.0, model_kwargs={"response_format": {"type": "json_object"}})
    steps_text = "\n".join([f"StepID [{s['step_id']}]: {s['raw_code']}" for s in steps])
    
    system_prompt = SystemMessage(content=(
        "You are an AI Test Architect. Group sequential automation steps into semantic chunks. "
        "A chunk represents a single logical user goal (e.g., 'Applying a filter'). "
        "Chunks should ideally be 4 to 8 steps long. Break chunks AFTER state-committing actions (clicks/navigates). "
        "Output JSON: { \"chunks\": [ [\"1_1\", \"1_2\"], [\"1_3\"] ] }"
    ))
    try:
        response = llm.invoke([system_prompt, HumanMessage(content=steps_text)])
        raw_json = response.content.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_json)
        
        step_map = {str(s['step_id']).strip(): s for s in steps}
        final_chunks = []
        for id_list in parsed.get("chunks", []):
            chunk = []
            for i in id_list:
                clean_i = str(i).replace("Step", "").replace("ID", "").replace("[", "").replace("]", "").strip()
                if clean_i in step_map: chunk.append(step_map[clean_i])
            if chunk: final_chunks.append(chunk)
        return final_chunks
    except:
        return [steps[i:i + 5] for i in range(0, len(steps), 5)]

# --- 3. The LangGraph Nodes ---
def predictor_node(state: AgentState):
    if state['is_cached']:
        print(f"  [Node: Predictor] ⚡ Cache Hit! Loading V-DOM and Traceability Matrix.")
        return state

    print(f"  [Node: Predictor] Building Virtual DOM & Verification Plan (Loop: {state['loop_count']})...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.1, model_kwargs={"response_format": {"type": "json_object"}})
    
    ontology_text = json.dumps(domain_ontology, indent=2)
    
    content_payload = [
        {"type": "text", "text": f"Current V-DOM State:\n{json.dumps(state.get('ui_graph', {}), indent=2)}"},
        {"type": "text", "text": f"Code Chunk to simulate:\n{state['code_chunk_text']}"}
    ]
    
    b64_start = encode_image(state["start_image_path"])
    if b64_start:
        content_payload.append({"type": "text", "text": "Starting UI State:"})
        content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_start}", "detail": "high"}})

    if state["enriched_images"]:
        for s_id, path in state["enriched_images"].items():
            b64_intent = encode_image(path)
            if b64_intent:
                content_payload.append({"type": "text", "text": f"Crosshair showing exact location clicked for Step {s_id}:"})
                content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_intent}", "detail": "high"}})

    learned_context = "\n".join([f"- GLOBAL RULE: {rule}" for rule in epistemic_memory.get("global_rules", [])])
    for step in state["steps"]:
        rule = epistemic_memory["learned_rules"].get(step['raw_code'])
        if rule: learned_context += f"\n- Rule for `{step['raw_code']}`: {rule}"
    
    system_prompt = SystemMessage(content=(
        "You are an Epistemic UI Automation Architect. Update the V-DOM (Virtual DOM) based on the code provided.\n"
        f"APP DOMAIN KNOWLEDGE (Use this to understand opaque entities):\n{ontology_text}\n\n"
        "CRITICAL RULE FOR TRACEABILITY: You must map EVERY single step_id to a checkpoint in the 'traceability_matrix'. "
        "If a step modifies an element that gets closed/hidden by a later step, its checkpoint MUST be the step_id right before the parent closes! "
        "If the element remains visible, its checkpoint is 'END'. Every checkpoint ID in the matrix must exist in the 'verification_plan'.\n\n"
        f"HUMAN OVERRIDES & GUIDELINES: {learned_context}\n\n"
        "Output JSON Schema:\n"
        "{\n"
        '  "ui_graph": {"Updated_VDOM_Here": {}},\n'
        '  "traceability_matrix": {"1_1": "1_3", "1_2": "1_3", "1_3": "END"},\n'
        '  "confidence_score": 0.0 to 1.0,\n'
        '  "confusing_step_id": "1_2" (or null),\n'
        '  "verification_plan": [\n'
        '     {"step_id_checkpoint": "1_3", "what_to_verify": "Verify Checkboxes 1_1 and 1_2 are CHECKED"},\n'
        '     {"step_id_checkpoint": "END", "what_to_verify": "Verify Sidebar 1_3 is CLOSED"}\n'
        '  ]\n'
        "}"
    ))

    try:
        response = llm.invoke([system_prompt, HumanMessage(content=content_payload)])
        raw_json = response.content.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw_json)
        
        state['ui_graph'] = result.get("ui_graph", state['ui_graph'])
        state['traceability_matrix'] = result.get("traceability_matrix", {})
        state['confidence_score'] = result.get("confidence_score", 1.0)
        state['confusing_step_id'] = result.get("confusing_step_id")
        state['verification_plan'] = result.get("verification_plan", [])
        
        print(f"    └── Confidence: {state['confidence_score']:.2f}")
        if VERBOSE_DEBUG_MODE:
            print(f"    [VERBOSE] Predictor Traceability:\n{json.dumps(state['traceability_matrix'], indent=2)}")
            
        return state
    except Exception as e:
        print(f"    └── ⚠️ LLM Error: {e}")
        state['confidence_score'] = 1.0 
        state['verification_plan'] = [{"step_id_checkpoint": "END", "what_to_verify": "Verify chunk completed successfully."}]
        return state

def enricher_node(state: AgentState):
    target_id = str(state['confusing_step_id']).replace("Step", "").replace("ID", "").replace("[", "").replace("]", "").strip()
    print(f"  [Node: Enricher] Agent requested clarification on Step {target_id}. Fetching Crosshair Image...")
    
    target_step = next((s for s in state['steps'] if str(s['step_id']).strip() == target_id), None)
    if target_step and target_step.get("baseline_images", {}).get("intent"):
        state['enriched_images'][target_id] = target_step["baseline_images"]["intent"]
    else:
        state['confidence_score'] = 1.0
    state['loop_count'] += 1
    return state

def verifier_node(state: AgentState):
    print(f"  [Node: Verifier] Executing {len(state['verification_plan'])} Atomic CV-Checkpoints...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.0, model_kwargs={"response_format": {"type": "json_object"}})
    
    all_verdicts = []
    chunk_failed = False
    fail_reasons = []

    image_map = {str(s['step_id']): {"before": s.get("baseline_images", {}).get("before"), "after": s.get("baseline_images", {}).get("after")} for s in state['steps']}
    
    for task in state['verification_plan']:
        step_val = str(task.get("step_id_checkpoint"))
        before_path = state["start_image_path"] 
        
        if step_val == "END": after_path = state["end_image_path"]
        else: after_path = image_map.get(step_val, {}).get("after")

        if not after_path: continue

        diff_path = create_cv_diff_image(before_path, after_path, step_val)
        
        print(f"    └── CV-Checking Frame [{step_val}]: {task.get('what_to_verify')}")
        b64_img = encode_image(diff_path)

        system_prompt = SystemMessage(content=(
            "You are a strict QA Inspector. You receive ONE image and ONE specific task. "
            "IMPORTANT: Look closely at the RED BOX drawn on the image. This highlights EXACTLY what changed in the UI since the chunk began. "
            "Does the visual state inside or around the RED BOX match the task exactly? "
            "Output JSON: { \"status\": \"PASS\" or \"FAIL\", \"description\": \"Brief explanation\" }"
        ))
        
        try:
            response = llm.invoke([system_prompt, HumanMessage(content=[
                {"type": "text", "text": f"Task: {task.get('what_to_verify')}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}", "detail": "high"}}
            ])])
            raw_json = response.content.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(raw_json)
            
            status = result.get("status", "FAIL")
            all_verdicts.append(f"[{status}] {task.get('what_to_verify')} - {result.get('description')}")
            if status == "FAIL":
                chunk_failed = True
                fail_reasons.append(result.get('description', 'Unknown Error'))
                
        except Exception as e:
            chunk_failed = True
            fail_reasons.append(f"Verification Error: {e}")

    state['verification_status'] = "FAIL" if chunk_failed else "PASS"
    state['bug_description'] = "\n".join(all_verdicts)
    return state

def micro_debug_node(state: AgentState):
    print(f"  [Node: Micro-Debug] Chunk failed. Replaying timeline to isolate bug...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.1, model_kwargs={"response_format": {"type": "json_object"}})
    
    content_payload = [{"type": "text", "text": "The chunk execution failed. Here is the frame-by-frame replay."}]
    for step in state['steps']:
        content_payload.append({"type": "text", "text": f"\nExecuting Step {step['step_id']}: `{step['raw_code']}`"})
        intent_b64 = encode_image(step.get("baseline_images", {}).get("intent"))
        if intent_b64:
            content_payload.append({"type": "text", "text": "Element Clicked:"})
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{intent_b64}", "detail": "high"}})
        after_b64 = encode_image(step.get("baseline_images", {}).get("after"))
        if after_b64:
            content_payload.append({"type": "text", "text": "Resulting UI State:"})
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_b64}", "detail": "high"}})

    system_prompt = SystemMessage(content=(
        "You are an investigative QA Agent reviewing a supposedly failed test. "
        "CRITICAL RULE: If the code executed perfectly and the UI behaved correctly, the previous agent hallucinated the failure. "
        "If it is a false positive, output 'failed_step_id': 'NONE'.\n"
        "Output JSON: { \"failed_step_id\": \"step_id or NONE\", \"root_cause\": \"Detailed explanation.\" }"
    ))

    try:
        response = llm.invoke([system_prompt, HumanMessage(content=content_payload)])
        raw_json = response.content.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw_json)
        state['micro_debug_result'] = f"Failed at Step {result.get('failed_step_id')}: {result.get('root_cause')}"
        print(f"    └── Isolated Bug: {state['micro_debug_result']}")
    except Exception:
        state['micro_debug_result'] = "Could not isolate bug via micro-debug."
    return state

def route_prediction(state: AgentState):
    if state['confidence_score'] < 0.85 and state.get('confusing_step_id') and state['loop_count'] < 2:
        return "enricher"
    
    if not state['is_cached'] and state['confidence_score'] >= 0.85:
        epistemic_memory["cached_chunks"][state['chunk_signature']] = {
            "ui_graph": state.get('ui_graph', {}),
            "traceability_matrix": state.get('traceability_matrix', {}),
            "verification_plan": state.get('verification_plan', [])
        }
        save_memories()  # 🔴 FIXED BUG HERE
        
    return "verifier"

def route_verification(state: AgentState):
    if state['verification_status'] == "FAIL":
        return "micro_debug"
    return END

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

# --- PILLAR 3: THE EPISTEMIC ENGINE ---
def extract_domain_knowledge(code_text: str, ui_graph: dict):
    print("  🧠 [Epistemic Engine] Extracting business logic for Ontology...")
    llm = AzureChatOpenAI(azure_deployment=AZURE_DEPLOYMENT_NAME, temperature=0.1, model_kwargs={"response_format": {"type": "json_object"}})
    
    system_prompt = SystemMessage(content=(
        "You are an Epistemic Knowledge Extractor. Analyze the code and the resulting V-DOM. "
        "Extract new, generalized facts about the application's domain taxonomy (e.g. 'League is a child of Global Filters'). "
        "Output JSON: { \"new_facts\": [\"Fact 1\", \"Fact 2\"] }"
    ))
    
    try:
        response = llm.invoke([system_prompt, HumanMessage(content=f"Code:\n{code_text}\n\nV-DOM:\n{json.dumps(ui_graph)}")])
        raw = response.content.strip().replace("```json", "").replace("```", "").strip()
        facts = json.loads(raw).get("new_facts", [])
        
        added_new = False
        for fact in facts:
            if fact not in domain_ontology["business_logic"]:
                domain_ontology["business_logic"].append(fact)
                print(f"    └── 💡 Discovered: {fact}")
                added_new = True
                
        if added_new:
            save_memories()
    except Exception as e:
        pass


def main():
    print("\n" + "="*70)
    print("🤖 EPISTEMIC AGENT (LAYER 5): ONTOLOGY, TRACEABILITY & CV-DIFFS")
    print("="*70)
    
    default_kb = "workflow_kb.yaml"
    kb_path = input(f"Enter target Knowledge Base YAML\n(Press [ENTER] for default: {default_kb}):\n> ").strip()
    if not kb_path: kb_path = default_kb
    if not kb_path.endswith(".yaml"): kb_path += ".yaml"

    if not os.path.exists(kb_path):
        print(f"\n❌ Error: '{kb_path}' not found.")
        return

    init_memories(kb_path)

    with open(kb_path, "r", encoding="utf-8") as f: kb = yaml.safe_load(f)
    agent_graph = build_agent_graph()
    
    RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(REPORT_DIR, exist_ok=True)
    base_name = os.path.basename(kb_path).replace(".yaml", "")
    excel_report_path = os.path.join(REPORT_DIR, f"Epistemic_{base_name}_Report_{RUN_TIMESTAMP}.xlsx")
    
    excel_rows = []
    total_chunks, total_bugs = 0, 0
    ongoing_ui_graph = {}

    for section in kb.get("sections", []):
        section_name = section.get('section_name', 'Unknown')
        print(f"\n📁 Processing Section: {section_name}")
        
        valid_steps = [s for s in section.get("steps", []) if s.get("baseline_images", {}).get("before")]
        chunks = segment_steps(valid_steps)

        for chunk_idx, chunk_steps in enumerate(chunks):
            chunk_id = f"{section_name}_Chunk_{chunk_idx+1}"
            code_text = "\n".join([f"Step {s['step_id']}: {s['raw_code']}" for s in chunk_steps])
            chunk_signature = "|".join([s['raw_code'] for s in chunk_steps])
            
            print(f"\n  📦 Running {chunk_id} ({len(chunk_steps)} Actions)")
            
            # PILLAR 1: PRE-FETCH CROSSHAIRS FOR OPAQUE LOCATORS
            enriched_images = {}
            for s in chunk_steps:
                if is_opaque_locator(s['raw_code']) and s.get("baseline_images", {}).get("intent"):
                    enriched_images[str(s['step_id'])] = s["baseline_images"]["intent"]
                    if VERBOSE_DEBUG_MODE:
                        print(f"    └── 👁️ Opaque locator detected on Step {s['step_id']}. Pre-fetching visual anchor.")
            
            is_cached = False
            verification_plan = []
            if chunk_signature in epistemic_memory.get("cached_chunks", {}):
                is_cached = True
                cached_data = epistemic_memory["cached_chunks"][chunk_signature]
                ongoing_ui_graph = cached_data.get("ui_graph", ongoing_ui_graph)
                verification_plan = cached_data.get("verification_plan", [])
            
            initial_state = {
                "chunk_id": chunk_id,
                "steps": chunk_steps,
                "chunk_signature": chunk_signature,
                "start_image_path": chunk_steps[0]["baseline_images"]["before"],
                "end_image_path": chunk_steps[-1]["baseline_images"]["after"],
                "code_chunk_text": code_text,
                "enriched_images": enriched_images, 
                "ui_graph": ongoing_ui_graph, 
                "traceability_matrix": {},
                "verification_plan": verification_plan,
                "confidence_score": 1.0,
                "confusing_step_id": None,
                "loop_count": 0,
                "is_cached": is_cached,
                "verification_status": "",
                "bug_description": "",
                "micro_debug_result": ""
            }

            final_state = agent_graph.invoke(initial_state)
            ongoing_ui_graph = final_state.get('ui_graph', ongoing_ui_graph)

            human_triage = "N/A"
            final_pass_fail = "PASS" if final_state["verification_status"] == "PASS" else "FAIL"

            if final_state["verification_status"] == "PASS" and not is_cached:
                extract_domain_knowledge(code_text, ongoing_ui_graph)

            if final_state["verification_status"] == "FAIL":
                if "Failed at Step NONE" in final_state.get('micro_debug_result', ''):
                    print("\n   ✨ [Auto-Resolve] Micro-Debug confirmed Agent 2 hallucinated. Auto-passing chunk.")
                    final_pass_fail = "PASS"
                    if not is_cached: extract_domain_knowledge(code_text, ongoing_ui_graph)
                else:
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
                        print("\n   [Rule Builder]")
                        scope = input("   Apply this rule to:\n   (1) This specific chunk only.\n   (2) Globally across the entire app.\n   > ").strip()
                        correction = input("   What SHOULD the Agent have expected? \n   > ")
                        if scope == '2':
                            epistemic_memory["global_rules"].append(correction)
                            print("   └── 🌍 Global App Rule Added.")
                        else:
                            epistemic_memory["learned_rules"][chunk_steps[-1]['raw_code']] = correction
                            print("   └── 📍 Chunk-Specific Rule Added.")
                            
                        epistemic_memory["cached_chunks"].pop(chunk_signature, None)
                        save_memories() # 🔴 FIXED BUG HERE
                        final_pass_fail = "PASS" 

            total_chunks += 1
            
            screenshots_arr = []
            for s in chunk_steps:
                imgs = s.get("baseline_images", {})
                screenshots_arr.append(f"Step {s['step_id']}:\nBefore: {imgs.get('before')}\nIntent: {imgs.get('intent')}\nAfter: {imgs.get('after')}\n")
            
            observed_combined = final_state.get("bug_description", "")
            if final_state.get("micro_debug_result"):
                observed_combined += f"\n\nMicro-Debug:\n{final_state.get('micro_debug_result')}"
            expected_text = "\n".join([f"- {task['what_to_verify']}" for task in final_state.get("verification_plan", [])])

            excel_rows.append({
                "Test Case ID": chunk_id,
                "Section": section_name,
                "Test Steps": code_text,
                "Expected Result": expected_text,
                "Observed Result": observed_combined,
                "Screenshots": "\n".join(screenshots_arr),
                "Pass/Fail": final_pass_fail
            })
            
            df = pd.DataFrame(excel_rows)
            df.to_excel(excel_report_path, index=False)

    print("\n" + "="*70)
    print("🏁 EPISTEMIC WORKFLOW COMPLETE")
    print(f"   Semantic Chunks Evaluated: {total_chunks}")
    print(f"   Confirmed Bugs Found: {total_bugs}")
    print(f"   Excel Report Saved To: {excel_report_path}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

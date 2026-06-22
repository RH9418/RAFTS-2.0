import os
import re
import yaml

# --- The Purely Mechanical Injection Block ---
INJECTION_BLOCK = r"""
import os
import sys
import time
import yaml
import atexit
import contextlib
from datetime import datetime
import json

# --- Execution Tracking & Reporting ---
_successful_actions = []
_failed_actions = []

# 🔴 DYNAMIC DIRECTORY FOR EVERY RUN
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
IMAGE_DIR = f"Mechanical_Images/Run_{RUN_TIMESTAMP}"
os.makedirs(IMAGE_DIR, exist_ok=True)

def _generate_execution_report():
    report_dir = "Execution_Reports"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"Mechanical_Execution_{RUN_TIMESTAMP}.txt")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Mechanical Execution Report\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total Successful Actions: {len(_successful_actions)}\n")
        f.write(f"Total Failed/Healed Actions: {len(_failed_actions)}\n\n")
        
        f.write("--- ❌ FAILED ACTIONS (Required Healing/Manual) ---\n")
        if _failed_actions:
            for fa in _failed_actions: f.write(f"- {fa}\n")
        else:
            f.write("None! 100% of actions succeeded automatically.\n")
            
        f.write("\n--- ✅ SUCCESSFUL ACTIONS ---\n")
        for sa in _successful_actions: f.write(f"- {sa}\n")
            
    print(f"\n📊 Execution Report saved to: {report_path}\n")

atexit.register(_generate_execution_report)

# --- TELEMETRY & NETWORK TRACKING ---
captured_graphql_apis = []
active_api_calls = 0

def handle_request(request):
    global active_api_calls
    if request.resource_type in ["fetch", "xhr"]:
        active_api_calls += 1

def handle_request_done(request):
    global active_api_calls
    if request.resource_type in ["fetch", "xhr"]:
        active_api_calls = max(0, active_api_calls - 1)

def get_composite_key(req_data):
    op_name = req_data.get("operationName", "unknown_op")
    try:
        dim_levels = req_data.get("variables", {}).get("query", {}).get("dimensionLevels")
        if dim_levels:
            dim_str = "-".join(str(d) for d in dim_levels) if isinstance(dim_levels, list) else str(dim_levels)
            return f"{op_name}_[{dim_str}]"
    except: pass
    return op_name

def handle_response(response):
    try:
        if response.request.method == "POST":
            post_text = response.request.post_data
            if post_text and '"operationName"' in post_text:
                req_data = json.loads(post_text)
                keys = []
                if isinstance(req_data, dict) and "operationName" in req_data:
                    keys.append((get_composite_key(req_data), req_data))
                elif isinstance(req_data, list):
                    for item in req_data:
                        if isinstance(item, dict) and "operationName" in item:
                            keys.append((get_composite_key(item), item))
                if keys:
                    try:
                        resp_json = response.json()
                        for k, req in keys:
                            captured_graphql_apis.append({
                                "api_key": k,
                                "request": req,
                                "response": resp_json
                            })
                    except: pass
    except: pass

# --- STABILITY ENGINE ---
WAIT_FOR_STABILITY_JS = '''
() => new Promise(resolve => {
    let checkCount = 0;
    const check = () => {
        checkCount++;
        const loaders = document.querySelectorAll('.ag-overlay-loading-wrapper, .spinner, .loading, [aria-busy="true"], .skeleton');
        let isVisible = false;
        for (let i = 0; i < loaders.length; i++) {
            const l = loaders[i];
            const style = window.getComputedStyle(l);
            if (l.offsetWidth > 0 && l.offsetHeight > 0 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                isVisible = true; break;
            }
        }
        if (isVisible && checkCount < 100) { setTimeout(check, 100); return; }
        resolve();
    };
    check(); // Instantly check because network is already idle
})
'''

def wait_for_stability(page):
    global active_api_calls
    page.wait_for_timeout(250)
    wait_cycles = 0
    while active_api_calls > 0 and wait_cycles < 300: 
        page.wait_for_timeout(100)
        wait_cycles += 1
    try: page.evaluate(WAIT_FOR_STABILITY_JS)
    except: pass
    page.wait_for_timeout(400)

# --- WIDGETS ---
DRAW_CROSSHAIR_JS = '''
([x, y]) => {
    const div = document.createElement('div'); div.id = 'agent-intent-crosshair';
    div.style.cssText = `position:fixed; left:${x-25}px; top:${y-25}px; width:50px; height:50px; border:4px solid #00FF00; border-radius:50%; z-index:2147483647; pointer-events:none; box-shadow: 0 0 15px #00FF00;`;
    const dot = document.createElement('div');
    dot.style.cssText = 'position:absolute; left:21px; top:21px; width:8px; height:8px; background-color:#FF0000; border-radius:50%;';
    div.appendChild(dot); document.body.appendChild(div);
}
'''
REMOVE_CROSSHAIR_JS = "() => { const e = document.getElementById('agent-intent-crosshair'); if(e) e.remove(); }"
MANUAL_CAPTURE_JS = '''
() => new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:2147483647; cursor:crosshair; background: rgba(255,0,0,0.15);';
    const msg = document.createElement('div');
    msg.innerText = "🎯 TARGET MODE: Click the correct element on the screen to auto-heal";
    msg.style.cssText = 'position:absolute; top:20px; left:50%; transform:translateX(-50%); background:black; color:white; padding:12px 24px; font-size:18px; font-weight:bold; border-radius:8px; pointer-events:none; box-shadow: 0 4px 10px rgba(0,0,0,0.5);';
    overlay.appendChild(msg); document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => {
        e.preventDefault(); e.stopPropagation(); overlay.remove(); resolve({x: e.clientX, y: e.clientY});
    }, {capture: true, once: true});
})
'''

# --- Python Helper Functions ---
@contextlib.contextmanager
def safe_download(page, timeout_ms=30000):
    class DummyEvent:
        @property
        def value(self):
            return None
    try:
        with page.expect_download(timeout=timeout_ms) as d: yield d
        _successful_actions.append("Download action completed")
    except Exception as e:
        _failed_actions.append("Download action failed/timed out")
        yield DummyEvent()

def update_yaml_knowledge_base(step_id, healed_coords=None):
    try:
        with open(TARGET_YAML_FILE, 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id and healed_coords:
                    s['healed_coords'] = healed_coords
                    s['execution_mode'] = 'HEALED_COORDINATES'
        with open(TARGET_YAML_FILE, 'w', encoding='utf-8') as f: yaml.dump(kb, f, default_flow_style=False, sort_keys=False)
    except: pass

def check_for_healed_coords(step_id):
    try:
        with open(TARGET_YAML_FILE, 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id and 'healed_coords' in s: return s['healed_coords']
    except: pass
    return None

def safe_action(page, locator, action_name, step_id, before_path, intent_path, after_path, *args, **kwargs):
    print(f"\n▶ Step {step_id}: {action_name}")
    
    before_path = os.path.join(IMAGE_DIR, os.path.basename(before_path))
    intent_path = os.path.join(IMAGE_DIR, os.path.basename(intent_path))
    after_path = os.path.join(IMAGE_DIR, os.path.basename(after_path))
    
    page.wait_for_timeout(50)
    page.screenshot(path=before_path)
    print(f"  └── 📸 Captured Before: {before_path}")
    
    # 🔴 NEW: ADVANCED ANGULAR DOMAIN EXTRACTION
    parent_context = "page_level"
    try:
        js_find_parent = '''el => {
            let current = el;
            let gridId = null;
            
            while (current && current !== document.body && current !== document.documentElement) {
                // Catch AG Grid's internal ID
                if (current.hasAttribute('grid-id')) {
                    gridId = current.getAttribute('grid-id');
                }
                
                // Catch Standard Test IDs
                if (current.hasAttribute('data-testid')) {
                    return `testid:${current.getAttribute('data-testid')}`;
                }
                
                // Catch Custom Angular Components (e.g. esp-grid-container)
                // We ignore 'ag-' because we want the business wrapper, not the generic vendor wrapper
                if (current.tagName && current.tagName.includes('-') && !current.tagName.toLowerCase().startsWith('ag-')) {
                    let ctx = current.tagName.toLowerCase();
                    if (gridId) ctx += `_gridId-${gridId}`;
                    return ctx;
                }
                
                // Catch hard IDs (ignoring generic auto-generated ones)
                if (current.id && current.id !== 'undefined' && !current.id.startsWith('ag-') && !current.id.startsWith('cdk-')) {
                    return `id:${current.id}`;
                }
                
                current = current.parentElement;
            }
            
            // Fallbacks
            if (gridId) return `ag_grid_id_${gridId}`;
            
            const rect = el.getBoundingClientRect();
            if (rect) {
                const qX = Math.floor(rect.left / (window.innerWidth / 2));
                const qY = Math.floor(rect.top / (window.innerHeight / 2));
                return `screen_quadrant_${qX}_${qY}`;
            }
            return 'page_level';
        }'''
        extracted_context = locator.first.evaluate(js_find_parent)
        if extracted_context:
            parent_context = extracted_context
            print(f"  └── 🧭 Component Scope Detected: {parent_context}")
    except:
        pass
        
    healed = check_for_healed_coords(step_id)
    target_x, target_y = None, None
    if healed: target_x, target_y = healed['x'], healed['y']
    else:
        try:
            locator.scroll_into_view_if_needed(timeout=500)
            box = locator.bounding_box()
            if box:
                target_x = box['x'] + (box['width'] / 2)
                target_y = box['y'] + (box['height'] / 2)
        except: pass

    if target_x is not None and target_y is not None:
        try:
            page.evaluate(DRAW_CROSSHAIR_JS, [target_x, target_y])
            page.wait_for_timeout(50) 
            page.screenshot(path=intent_path)
            print(f"  └── 🎯 Captured Intent: {intent_path}")
            page.evaluate(REMOVE_CROSSHAIR_JS)
        except: pass

    fallback_success = False
    
    if healed and action_name in ['click', 'dblclick', 'hover']:
        try:
            if action_name == 'click': page.mouse.click(target_x, target_y)
            elif action_name == 'dblclick': page.mouse.dblclick(target_x, target_y)
            elif action_name == 'hover': page.mouse.move(target_x, target_y)
            fallback_success = True
            print("  └── ✅ Healed Coordinate action executed.")
        except: pass
    else:
        try:
            if 'timeout' not in kwargs: kwargs['timeout'] = 3000
            getattr(locator, action_name)(*args, **kwargs)
            fallback_success = True
            print("  └── ✅ Native action succeeded.")
        except Exception as e:
            error_msg = str(e)
            print(f"  └── ⚠️ Native action failed: {error_msg.splitlines()[0][:80]}...")
            
            print("  └── Initiating Autonomous Fallbacks...")
            if "strict mode violation" in error_msg.lower() and not fallback_success:
                try: getattr(locator.first, action_name)(*args, **kwargs); fallback_success = True; print("  └── 🛠️ F1 Succeeded.")
                except: pass
            if not fallback_success and action_name in ['click', 'dblclick', 'check', 'uncheck', 'hover']:
                try: forced = kwargs.copy(); forced['force'] = True; getattr(locator, action_name)(*args, **forced); fallback_success = True; print("  └── 🛠️ F2 Succeeded.")
                except: pass
            if not fallback_success and action_name in ['click', 'check', 'uncheck']:
                try: 
                    if action_name == 'click': locator.evaluate("el => el.click()")
                    elif action_name == 'check': locator.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change')); }")
                    elif action_name == 'uncheck': locator.evaluate("el => { el.checked = false; el.dispatchEvent(new Event('change')); }")
                    fallback_success = True; print("  └── 🛠️ F3 Succeeded.")
                except: pass
            if not fallback_success and target_x is not None and action_name in ['click', 'dblclick', 'hover']:
                try: 
                    if action_name == 'click': page.mouse.click(target_x, target_y)
                    elif action_name == 'hover': page.mouse.move(target_x, target_y)
                    fallback_success = True; print("  └── 🛠️ F4 Succeeded.")
                except: pass
            if not fallback_success and "Timeout" in error_msg:
                try: 
                    page.evaluate("() => { document.querySelectorAll('.ag-body-viewport').forEach(v => { v.scrollTop+=300; setTimeout(()=>v.scrollTop-=300, 150); }); }")
                    time.sleep(0.5); getattr(locator, action_name)(*args, **kwargs); fallback_success = True; print("  └── 🛠️ F6 Succeeded.")
                except: pass

    if not fallback_success:
        print(f"  └── 🛑 ALL FALLBACKS FAILED. INJECTING TARGET MODE...")
        _failed_actions.append(f"Step {step_id}: {action_name}")
        coords = page.evaluate(MANUAL_CAPTURE_JS)
        if coords:
            update_yaml_knowledge_base(step_id, healed_coords=coords)
            try:
                page.evaluate(DRAW_CROSSHAIR_JS, [coords['x'], coords['y']])
                page.wait_for_timeout(100)
                page.screenshot(path=intent_path)
                page.evaluate(REMOVE_CROSSHAIR_JS)
                page.mouse.click(coords['x'], coords['y'])
                print("  └── ✅ Manual click executed and HEALED for future runs.")
            except: pass
    else:
        _successful_actions.append(f"Step {step_id}: {action_name}")

    wait_for_stability(page)
    page.screenshot(path=after_path)
    print(f"  └── 📸 Captured After:  {after_path}")
    
    # 🔴 RECORD NEW PATHS & COMPONENT CONTEXT IN YAML SO LAYER 4 CAN FIND THEM
    try:
        with open(TARGET_YAML_FILE, 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id:
                    s['baseline_images']['before'] = before_path
                    s['baseline_images']['intent'] = intent_path
                    s['baseline_images']['after'] = after_path
                    s['parent_context'] = parent_context # <--- INJECTED CONTEXT HERE
        with open(TARGET_YAML_FILE, 'w', encoding='utf-8') as f: yaml.dump(kb, f, default_flow_style=False, sort_keys=False)
    except: pass
"""

def main():
    print("\n" + "="*70)
    print("⚙️ BUILDING MECHANICAL RUNNER")
    print("="*70)
    
    # DYNAMIC INPUTS
    default_input = "clean_codegen.py"
    input_py = input(f"Enter the cleaned script to build\n(Press [ENTER] for default: {default_input}):\n> ").strip()
    if not input_py:
        input_py = default_input
    if not input_py.endswith(".py"):
        input_py += ".py"

    if not os.path.exists(input_py): 
        print(f"\n❌ Error: '{input_py}' not found in the current directory.")
        return

    # 🔴 DYNAMIC YAML SELECTION
    default_yaml = "workflow_kb.yaml"
    input_yaml = input(f"\nEnter the corresponding Knowledge Base YAML\n(Press [ENTER] for default: {default_yaml}):\n> ").strip()
    if not input_yaml:
        input_yaml = default_yaml
    if not input_yaml.endswith(".yaml"):
        input_yaml += ".yaml"

    if not os.path.exists(input_yaml): 
        print(f"\n❌ Error: '{input_yaml}' not found in the current directory.")
        return

    base_name = os.path.basename(input_py)
    if base_name.endswith('.py'): base_name = base_name[:-3]
    output_py = f"execute_mechanical_{base_name}.py"

    with open(input_yaml, "r", encoding="utf-8") as f: 
        kb = yaml.safe_load(f)
        
    steps_queue = [s for sec in kb.get('sections', []) for s in sec.get('steps', [])]
    with open(input_py, "r", encoding="utf-8") as f: 
        lines = f.readlines()
        
    new_lines = []
    header_injected = False
    
    print(f"\n⚙️ Building Layer 1 (Mechanical Execution) into '{output_py}'...")
    for line in lines:
        stripped = line.strip()
        
        if not header_injected and not stripped.startswith("import ") and not stripped.startswith("from "):
            # 🔴 INJECT DYNAMIC YAML TARGET INTO SCRIPT
            new_lines.append(f'TARGET_YAML_FILE = "{input_yaml}"\n')
            new_lines.append(INJECTION_BLOCK + "\n")
            header_injected = True

        if "page.expect_download()" in stripped:
            new_lines.append(line.replace("page.expect_download()", "safe_download(page)"))
            continue

        matched_step = next((s for s in steps_queue if s['raw_code'] in stripped), None)
        
        if "page.goto(" in stripped:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}page.on('response', handle_response)\n")
            new_lines.append(f"{indent}page.on('request', handle_request)\n")
            new_lines.append(f"{indent}page.on('requestfinished', handle_request_done)\n")
            new_lines.append(f"{indent}page.on('requestfailed', handle_request_done)\n")
            new_lines.append(line)
            continue

        if matched_step:
            steps_queue.remove(matched_step)
            indent = line[:len(line) - len(line.lstrip())]
            action = matched_step['action']
            match = re.match(rf"^(.*?)\.{action}\((.*?)\)$", matched_step['raw_code'])
            
            if match:
                loc, args = match.group(1), match.group(2)
                step_id = matched_step['step_id']
                imgs = matched_step['baseline_images']
                if args:
                    new_lines.append(f"{indent}safe_action(page, {loc}, '{action}', '{step_id}', '{imgs['before']}', '{imgs['intent']}', '{imgs['after']}', {args})\n")
                else:
                    new_lines.append(f"{indent}safe_action(page, {loc}, '{action}', '{step_id}', '{imgs['before']}', '{imgs['intent']}', '{imgs['after']}')\n")
            else: 
                new_lines.append(line)
        else: 
            new_lines.append(line)
            
            if "ACTION REQUIRED: Log in, pass MFA" in stripped:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}print('\\n✅ Initializing Stability Engine...')\n")
                new_lines.append(f"{indent}wait_for_stability(page)\n")

    with open(output_py, "w", encoding="utf-8") as f: 
        f.writelines(new_lines)
        
    print(f"✅ Layer 1 Executable saved: {output_py}\n")

if __name__ == "__main__":
    main()

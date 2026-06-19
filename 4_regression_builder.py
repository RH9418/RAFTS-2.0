import os
import yaml
import json
import re

# --- The Autonomous Snapshot Engine & Phase 4 Auto-Healer ---
INJECTION_BLOCK = r"""
import os
import sys
import time
import json
import yaml
import re
from datetime import datetime

# --- Regression Initialization ---
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = f"Regression_Runs/Run_{RUN_TIMESTAMP}"
SCREENSHOT_DIR = os.path.join(RUN_DIR, "Screenshots")
API_DUMP_DIR = os.path.join(RUN_DIR, "API_Dumps")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(API_DUMP_DIR, exist_ok=True)

regression_evidence = {
    "workflow_name": "Autonomous Regression Evidence",
    "run_timestamp": RUN_TIMESTAMP,
    "test_cases": []
}

# --- TELEMETRY & NETWORK TRACKING ---
captured_graphql_apis = []
active_api_calls = 0

def handle_request(request):
    global active_api_calls
    # Only track data requests (Fetch/XHR), ignore images, scripts, and CSS
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

# --- SPEED OPTIMIZED STABILITY ENGINE ---
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
    # 1. Buffer: Give Javascript 250ms to dispatch the fetch request after the click
    page.wait_for_timeout(250)
    
    # 2. NETWORK LOCK: Block execution until API responses arrive
    wait_cycles = 0
    while active_api_calls > 0 and wait_cycles < 300: # 30 second max timeout
        page.wait_for_timeout(100)
        wait_cycles += 1
        
    # 3. VISUAL LOCK: Network is done. Wait for the DOM to remove skeletons/spinners
    try: page.evaluate(WAIT_FOR_STABILITY_JS)
    except: pass
    
    # 4. DOM PAINT BUFFER: Give grids 400ms to physically render rows
    page.wait_for_timeout(400)


def take_automated_snapshot(page, test_name, snap_idx, boxes, scroll_x, scroll_y, human_note, target_action):
    print(f"\n  ⏳ [Auto-Capture] Waiting for Network & UI to stabilize for '{test_name}'...")
    wait_for_stability(page)
    
    # 🔴 RESTORE EXACT SCROLL POSITION
    try:
        page.evaluate(f"window.scrollTo({scroll_x}, {scroll_y})")
        page.wait_for_timeout(250) # Let the browser paint the scrolled view
    except: pass

    print(f"  📸 [Auto-Capture] Taking snapshot: {snap_idx}")
    
    # 🔴 ANTI-FLEXBOX ARMOR: Inject Divs instead of SVGs
    js_code = f'''
    () => {{
        const wrapper = document.createElement('div');
        wrapper.id = 'agent-auto-draw';
        wrapper.style.cssText = 'position:fixed !important; top:0 !important; left:0 !important; width:100vw !important; height:100vh !important; z-index:2147483645 !important; pointer-events:none !important; margin:0 !important; padding:0 !important; background:transparent !important; display:block !important;';
        document.body.appendChild(wrapper);
        
        const boxes = {json.dumps(boxes)};
        boxes.forEach(b => {{
            const box = document.createElement('div');
            box.style.cssText = `position:absolute !important; top:${{b.y}}px !important; left:${{b.x}}px !important; width:${{b.width || b.w}}px !important; height:${{b.height || b.h}}px !important; border:4px solid #ef4444 !important; background:rgba(234,179,8,0.2) !important; z-index:2147483646 !important; pointer-events:none !important; box-sizing:border-box !important; margin:0 !important; padding:0 !important; transform:none !important; display:block !important;`;
            wrapper.appendChild(box);
        }});
    }}
    '''
    page.evaluate(js_code)
    page.wait_for_timeout(200)
    
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', test_name)[:20]
    img_filename = f"{safe_name}_{RUN_TIMESTAMP}_{snap_idx}.png"
    img_path = os.path.join(SCREENSHOT_DIR, img_filename)
    page.screenshot(path=img_path)
    
    page.evaluate("() => { const w = document.getElementById('agent-auto-draw'); if(w) w.remove(); }")
    
    api_dumps = []
    for api in captured_graphql_apis:
        api_key = api['api_key']
        dump_filename = f"{safe_name}_{RUN_TIMESTAMP}_{snap_idx}_{api_key}.json"
        dump_path = os.path.join(API_DUMP_DIR, dump_filename)
        with open(dump_path, 'w', encoding='utf-8') as f: json.dump(api, f, indent=4)
        api_dumps.append({"api_key": api_key, "file": dump_path})
        
    captured_graphql_apis.clear()
    
    tc_entry = next((tc for tc in regression_evidence["test_cases"] if tc["test_name"] == test_name), None)
    if not tc_entry:
        tc_entry = {"test_name": test_name, "snapshots": []}
        regression_evidence["test_cases"].append(tc_entry)
        
    tc_entry["snapshots"].append({
        "target_action": target_action,
        "human_note": human_note,
        "image_path": img_path,
        "apis_triggered": api_dumps
    })
    
    evidence_path = os.path.join(RUN_DIR, "regression_evidence.yaml")
    with open(evidence_path, 'w', encoding='utf-8') as f: yaml.dump(regression_evidence, f, sort_keys=False)


# --- PHASE 4: HITL MECHANIC (MID-FLIGHT CODEGEN) & 6-TIER FALLBACKS ---
def patch_raw_codegen(old_code, new_code):
    script_path = "clean_codegen.py" 
    if not os.path.exists(script_path): return
    with open(script_path, 'r', encoding='utf-8') as f: lines = f.readlines()
    with open(script_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if old_code in line:
                indent = line[:len(line) - len(line.lstrip())]
                f.write(f"{indent}{new_code}\n")
            else:
                f.write(line)

def safe_regression_action(page, locator, action_name, original_code_str, *args, **kwargs):
    fallback_success = False
    try:
        if 'timeout' not in kwargs: kwargs['timeout'] = 3000
        getattr(locator, action_name)(*args, **kwargs)
        fallback_success = True
    except Exception as e:
        error_msg = str(e)
        print("\n" + "!"*70)
        print(f"🚨 SCRIPT BROKE: Could not execute `{original_code_str}`")
        print(f"   Reason: {error_msg.splitlines()[0][:80]}...")
        print("!"*70)
        print("  └── Initiating Autonomous Fallbacks...")
        
        if "strict mode violation" in error_msg.lower():
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
        if not fallback_success and action_name in ['click', 'dblclick']:
            try: 
                locator.evaluate("el => { let c = el.closest('.ag-cell, [role=\"gridcell\"], .ag-row'); if(c) c.click(); else el.parentElement.click(); }")
                fallback_success = True; print("  └── 🛠️ F5 Succeeded.")
            except: pass
        if not fallback_success and "Timeout" in error_msg:
            try: 
                page.evaluate("() => { document.querySelectorAll('.ag-body-viewport').forEach(v => { v.scrollTop+=300; setTimeout(()=>v.scrollTop-=300, 150); }); }")
                time.sleep(0.5); getattr(locator, action_name)(*args, **kwargs); fallback_success = True; print("  └── 🛠️ F6 Succeeded.")
            except: pass

    if not fallback_success:
        print(f"  └── 🛑 ALL FALLBACKS FAILED. INJECTING MID-FLIGHT REPAIR...")
        print("   [Opening Playwright Inspector...]")
        print("   1. Click 'Record' in the Inspector.")
        print("   2. Perform the correct action in the browser.")
        print("   3. Copy the NEW line of code from the Inspector.")
        
        page.pause()
        
        new_code = input("\n   👉 Paste the new Playwright code here (or 'skip'): ").strip()
        if new_code.lower() != 'skip' and new_code:
            try:
                exec(new_code, globals(), {'page': page})
                patch_raw_codegen(original_code_str, new_code)
                print("   └── 💾 clean_codegen.py permanently patched. Resuming test...")
            except Exception as ex:
                print(f"   └── ❌ Failed to execute pasted code: {ex}")
"""

def main():
    kb_path = "test_cases_kb.yaml"
    input_py = "clean_codegen.py"
    output_py = "execute_regression.py"

    if not os.path.exists(kb_path):
        print(f"❌ Error: '{kb_path}' not found.")
        return
    if not os.path.exists(input_py):
        print(f"❌ Error: '{input_py}' not found.")
        return

    with open(kb_path, "r", encoding="utf-8") as f:
        kb = yaml.safe_load(f)

    expected_snapshots = []
    for test in kb.get('test_cases', []):
        for i, snap in enumerate(test.get('snapshots', [])):
            expected_snapshots.append({
                "test_name": test["test_name"],
                "snap_idx": i + 1,
                "target_action": snap["target_action"].strip(),
                "bounding_boxes": snap.get("bounding_boxes", []),
                "scroll_x": snap.get("scroll_x", 0),
                "scroll_y": snap.get("scroll_y", 0),
                "human_note": snap.get("human_note", "")
            })

    print(f"\n⚙️ Building Autonomous Regression Runner '{output_py}'...")
    print(f"   └── Found {len(expected_snapshots)} Target Snapshots in KB queue.")

    with open(input_py, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    header_injected = False
    
    action_pattern = re.compile(r'^(\s*)(page.*?\.(?:click|fill|press|check|uncheck|hover|dblclick)\(.*?\))(.*)$')

    for line in lines:
        stripped = line.strip()

        if not header_injected and not stripped.startswith("import ") and not stripped.startswith("from ") and stripped != "":
            new_lines.append(INJECTION_BLOCK + "\n")
            header_injected = True

        # VIEWPORT LOCK
        if "browser.new_context(" in line and "viewport" not in line:
            new_lines.append(line.replace("browser.new_context(", "browser.new_context(viewport={'width': 1280, 'height': 800}, "))
            continue
            
        # NETWORK LISTENERS INJECTED CLEANLY
        if stripped.startswith("def test_"):
            new_lines.append(line)
            indent = "    "
            new_lines.append(f"{indent}page.on('response', handle_response)\n")
            new_lines.append(f"{indent}page.on('request', handle_request)\n")
            new_lines.append(f"{indent}page.on('requestfinished', handle_request_done)\n")
            new_lines.append(f"{indent}page.on('requestfailed', handle_request_done)\n")
            continue

        if "ACTION REQUIRED: Log in, pass MFA" in stripped:
            new_lines.append(line)
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}print('\\n✅ Initializing Stability Engine...')\n")
            new_lines.append(f"{indent}wait_for_stability(page)\n")
            continue

                # TO THIS:
        while expected_snapshots and stripped == expected_snapshots[0]["target_action"]:
            snap = expected_snapshots.pop(0)
            indent = line[:len(line) - len(line.lstrip())]
            
            t_name = json.dumps(snap["test_name"])
            s_idx = snap["snap_idx"]
            boxes = json.dumps(snap["bounding_boxes"])
            sx = snap["scroll_x"]
            sy = snap["scroll_y"]
            note = json.dumps(snap["human_note"])
            action = json.dumps(snap["target_action"])
            
            new_lines.append(f"{indent}take_automated_snapshot(page, test_name={t_name}, snap_idx={s_idx}, boxes={boxes}, scroll_x={sx}, scroll_y={sy}, human_note={note}, target_action={action})\n")


        # HITL MECHANIC & 6-TIER FALLBACK INJECTION
        match = action_pattern.search(line)
        if match:
            indent = match.group(1)
            action_code = match.group(2)
            remainder = match.group(3)
            
            # Extract locator and action type for fallback magic
            inner_match = re.match(r"^(.*?)\.(click|fill|press|check|uncheck|hover|dblclick)\((.*?)\)$", action_code)
            if inner_match:
                loc = inner_match.group(1)
                action_name = inner_match.group(2)
                args = inner_match.group(3)
                if args:
                    new_lines.append(f"{indent}safe_regression_action(page, {loc}, '{action_name}', {repr(action_code)}, {args}){remainder}\n")
                else:
                    new_lines.append(f"{indent}safe_regression_action(page, {loc}, '{action_name}', {repr(action_code)}){remainder}\n")
            else:
                new_lines.append(line)
            continue

        if "page.close()" in line:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}print('\\n✅ Autonomous Regression Run Complete.')\n")
            new_lines.append(f"{indent}print(f'   └── Evidence saved to: {{RUN_DIR}}/regression_evidence.yaml')\n")
            new_lines.append(line)
            continue

        new_lines.append(line)

    if expected_snapshots:
        print(f"\n⚠️ WARNING: Not all snapshots were matched in the code!")
        for s in expected_snapshots:
            print(f"     - '{s['target_action']}'")

    with open(output_py, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"\n✅ Regression Runner Saved: {output_py}")

if __name__ == "__main__":
    main()

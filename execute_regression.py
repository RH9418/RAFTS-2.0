import re

from playwright.sync_api import Page, expect






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

def test_example(page: Page) -> None:
    page.on('response', handle_response)
    page.on('request', handle_request)
    page.on('requestfinished', handle_request_done)
    page.on('requestfailed', handle_request_done)
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.bbu.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=4&tabIndex=1", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print('\n✅ Initializing Stability Engine...')
    wait_for_stability(page)
    print("="*60 + "\n")

    # ============================================================
    # SECTION: Global Filters
    # ============================================================
    safe_regression_action(page, page.locator(".zeb-filter"), 'click', 'page.locator(".zeb-filter").click()')
    safe_regression_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    safe_regression_action(page, page.get_by_text("Brand Level 4"), 'click', 'page.get_by_text("Brand Level 4").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_regression_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.get_by_text("Brand Level 4"), 'click', 'page.get_by_text("Brand Level 4").click()')
    safe_regression_action(page, page.get_by_text("Brand Level 3"), 'click', 'page.get_by_text("Brand Level 3").click()')
    safe_regression_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_regression_action(page, page.locator(".pointer.partial-selected"), 'click', 'page.locator(".pointer.partial-selected").click()')
    safe_regression_action(page, page.get_by_text("Brand Level 3"), 'click', 'page.get_by_text("Brand Level 3").click()')
    safe_regression_action(page, page.get_by_text("Attribute"), 'click', 'page.get_by_text("Attribute").click()')
    safe_regression_action(page, page.get_by_text("Product Level 4"), 'click', 'page.get_by_text("Product Level 4").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.get_by_text("Product Level 4"), 'click', 'page.get_by_text("Product Level 4").click()')
    safe_regression_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location"), 'click', 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location").click()')
    safe_regression_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    safe_regression_action(page, page.get_by_text("Sales Level 6"), 'click', 'page.get_by_text("Sales Level 6").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_regression_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer"), 'click', 'page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer").click()')
    safe_regression_action(page, page.get_by_text("Sales Level 6"), 'click', 'page.get_by_text("Sales Level 6").click()')
    safe_regression_action(page, page.get_by_text("Sales Level 5"), 'click', 'page.get_by_text("Sales Level 5").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.get_by_text("Sales Level 5"), 'click', 'page.get_by_text("Sales Level 5").click()')
    safe_regression_action(page, page.get_by_text("Sales Level 4"), 'click', 'page.get_by_text("Sales Level 4").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_regression_action(page, page.get_by_text("Sales Level 4"), 'click', 'page.get_by_text("Sales Level 4").click()')
    safe_regression_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer"), 'click', 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer").click()')
    safe_regression_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    safe_regression_action(page, page.get_by_text("Customer Level 4"), 'click', 'page.get_by_text("Customer Level 4").click()')
    safe_regression_action(page, page.get_by_text("Customer Level 4"), 'click', 'page.get_by_text("Customer Level 4").click()')
    safe_regression_action(page, page.locator(".pointer.zeb-check"), 'click', 'page.locator(".pointer.zeb-check").click()')
    safe_regression_action(page, page.get_by_role("button", name="Apply Filters"), 'click', 'page.get_by_role("button", name="Apply Filters").click()')
    safe_regression_action(page, page.locator(".pointer.custom-checkbox-unchecked"), 'click', 'page.locator(".pointer.custom-checkbox-unchecked").click()')
    safe_regression_action(page, page.get_by_role("button", name="Apply Filters"), 'click', 'page.get_by_role("button", name="Apply Filters").click()')
    safe_regression_action(page, page.locator(".filter-icon-wrapper"), 'click', 'page.locator(".filter-icon-wrapper").click()')

    # ============================================================
    # SECTION: Alert Types
    # ============================================================
    safe_regression_action(page, page.locator(".dropdown-caret").first, 'click', 'page.locator(".dropdown-caret").first.click()')
    safe_regression_action(page, page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1).click()')
    safe_regression_action(page, page.locator(".dropdown-caret").first, 'click', 'page.locator(".dropdown-caret").first.click()')
    safe_regression_action(page, page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1).click()')

    # ============================================================
    # SECTION: Alerts Sumary
    # ============================================================
    safe_regression_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')
    safe_regression_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', 'page.get_by_role("spinbutton", name="Filter Value").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("129406")', "129406")
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("-6.5")', "-6.5")
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("21")', "21")
    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_regression_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("7.2")', "7.2")
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10")', "10")
    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_regression_action(page, page.get_by_role("option", name="Less than or equal to"), 'click', 'page.get_by_role("option", name="Less than or equal to").click()')
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_regression_action(page, page.locator("div:nth-child(7) > .ag-column-select-column"), 'click', 'page.locator("div:nth-child(7) > .ag-column-select-column").click()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("380906")', "380906")
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("384298")', "384298")
    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    safe_regression_action(page, page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper"), 'check', 'page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper").check()')
    safe_regression_action(page, page.locator("#ag-2417-input"), 'check', 'page.locator("#ag-2417-input").check()')

    safe_regression_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("100")', "100")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("200")', "200")

    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("383")', "383")

    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.locator("a").filter(has_text="2"), 'click', 'page.locator("a").filter(has_text="2").click()')

    safe_regression_action(page, page.locator("a").filter(has_text="1"), 'click', 'page.locator("a").filter(has_text="1").click()')

    safe_regression_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')

    safe_regression_action(page, page.get_by_text("View 20 row(s)"), 'click', 'page.get_by_text("View 20 row(s)").click()')

    safe_regression_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')

    safe_regression_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()')

    safe_regression_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')

    safe_regression_action(page, page.locator(".pointer.zeb-adjustments"), 'click', 'page.locator(".pointer.zeb-adjustments").click()')

    safe_regression_action(page, page.get_by_text("Save Preference"), 'click', 'page.get_by_text("Save Preference").click()')

    with page.expect_download() as download_info:

        safe_regression_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', 'page.locator(".icon-color-toolbar-active.zeb-download-underline").click()')

    download = download_info.value

    safe_regression_action(page, page.locator(".pointer.zeb-adjustments"), 'click', 'page.locator(".pointer.zeb-adjustments").click()')

    safe_regression_action(page, page.get_by_text("Reset Preference"), 'click', 'page.get_by_text("Reset Preference").click()')

    safe_regression_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')

    take_automated_snapshot(page, test_name="Check Alerts Summary Grid", snap_idx=1, boxes=[{"x": 223, "y": 235, "width": 214, "height": 22}], scroll_x=0, scroll_y=292, human_note="Check that a Row has been Selected.", target_action="page.locator(\"span\").filter(has_text=\"WALMART STORES HQ\").first.click(button=\"right\")")
    take_automated_snapshot(page, test_name="Check Alerts Summary Grid", snap_idx=2, boxes=[{"x": 127, "y": 217, "width": 283, "height": 42}, {"x": 95, "y": 250, "width": 366, "height": 197}], scroll_x=0, scroll_y=908.7999877929688, human_note="Ensure Products Have been selected.", target_action="page.locator(\"span\").filter(has_text=\"WALMART STORES HQ\").first.click(button=\"right\")")
    take_automated_snapshot(page, test_name="Check Alerts Summary Grid", snap_idx=3, boxes=[{"x": 108, "y": 165, "width": 237, "height": 112}], scroll_x=0, scroll_y=1407.199951171875, human_note="Verify Time Filter is Applied.", target_action="page.locator(\"span\").filter(has_text=\"WALMART STORES HQ\").first.click(button=\"right\")")
    safe_regression_action(page, page.locator("span").filter(has_text="WALMART STORES HQ").first, 'click', 'page.locator("span").filter(has_text="WALMART STORES HQ").first.click(button="right")', button="right")

    safe_regression_action(page, page.get_by_text("Drill down"), 'click', 'page.get_by_text("Drill down").click()')

    safe_regression_action(page, page.locator("span").filter(has_text="WALMART").first, 'click', 'page.locator("span").filter(has_text="WALMART").first.click(button="right")', button="right")

    safe_regression_action(page, page.get_by_text("Drill up"), 'click', 'page.get_by_text("Drill up").click()')

    safe_regression_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')

    safe_regression_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')

    safe_regression_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")', "10000")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20")', "20")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20")', "20")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("1000")', "1000")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20000")', "20000")

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')

    safe_regression_action(page, page.get_by_text("Apply Reset Clear"), 'click', 'page.get_by_text("Apply Reset Clear").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("100000")', "100000")

    safe_regression_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')

    safe_regression_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("65000")', "65000")

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')

    safe_regression_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")', "10000")

    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')

    safe_regression_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()')

    safe_regression_action(page, page.locator("#ag-6860-input"), 'check', 'page.locator("#ag-6860-input").check()')

    safe_regression_action(page, page.locator("div:nth-child(12) > .ag-column-select-column"), 'click', 'page.locator("div:nth-child(12) > .ag-column-select-column").click()')

    safe_regression_action(page, page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')

    safe_regression_action(page, page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first, 'click', 'page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first.click()')

    safe_regression_action(page, page.locator(".checkbox-primary-color").first, 'check', 'page.locator(".checkbox-primary-color").first.check()')

    safe_regression_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")', button="right")

    safe_regression_action(page, page.get_by_text("Drill down"), 'click', 'page.get_by_text("Drill down").click()')

    safe_regression_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")', button="right")

    safe_regression_action(page, page.get_by_text("Drill up"), 'click', 'page.get_by_text("Drill up").click()')

    safe_regression_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')



    # ============================================================
    # SECTION: Weekly Summary Section
    # ============================================================


    safe_regression_action(page, page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')

    safe_regression_action(page, page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1).click()')

    safe_regression_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')

    safe_regression_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')

    safe_regression_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')

    safe_regression_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')

    safe_regression_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')

    safe_regression_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')

    safe_regression_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', 'page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(4) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(5) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(5) > .d-flex").click()')

    safe_regression_action(page, page.locator("div:nth-child(6) > .d-flex"), 'click', 'page.locator("div:nth-child(6) > .d-flex").click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', 'page.locator(".overflow-auto > div:nth-child(7)").click()')

    safe_regression_action(page, page.locator("div:nth-child(8) > .d-flex"), 'click', 'page.locator("div:nth-child(8) > .d-flex").click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first.click()')

    safe_regression_action(page, page.locator("div:nth-child(9) > .d-flex"), 'click', 'page.locator("div:nth-child(9) > .d-flex").click()')

    safe_regression_action(page, page.locator("div:nth-child(10) > .d-flex"), 'click', 'page.locator("div:nth-child(10) > .d-flex").click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')

    safe_regression_action(page, page.get_by_text("All").nth(3), 'click', 'page.get_by_text("All").nth(3).click()')

    safe_regression_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')

    safe_regression_action(page, page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')

    safe_regression_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')

    safe_regression_action(page, page.locator("svg").get_by_text("User Forecast Total"), 'click', 'page.locator("svg").get_by_text("User Forecast Total").click()')

    safe_regression_action(page, page.locator("svg").get_by_text("User Override Total"), 'click', 'page.locator("svg").get_by_text("User Override Total").click()')

    safe_regression_action(page, page.locator("svg").get_by_text("Aged Net Units"), 'click', 'page.locator("svg").get_by_text("Aged Net Units").click()')

    safe_regression_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', 'page.locator(".overflow-auto > div:nth-child(7)").click()')

    safe_regression_action(page, page.locator(".overflow-auto > div:nth-child(8)"), 'click', 'page.locator(".overflow-auto > div:nth-child(8)").click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')

    safe_regression_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')

    safe_regression_action(page, page.locator("path:nth-child(78)"), 'click', 'page.locator("path:nth-child(78)").click()')

    safe_regression_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')

    safe_regression_action(page, page.get_by_text("Save Preference"), 'click', 'page.get_by_text("Save Preference").click()')

    safe_regression_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')

    safe_regression_action(page, page.get_by_text("Reset Preference"), 'click', 'page.get_by_text("Reset Preference").click()')

    safe_regression_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div"), 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div").click()')

    # ============================================================
    # SECTION: Events Grid
    # ============================================================
    safe_regression_action(page, page.locator("div:nth-child(4) > span > .align-middle"), 'click', 'page.locator("div:nth-child(4) > span > .align-middle").click()')
    safe_regression_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content"), 'click', 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content").click()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', 'page.get_by_role("textbox", name="Filter Value").fill("Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")', "Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")
    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click(button="right")', button="right")
    safe_regression_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click()')
    safe_regression_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_regression_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', 'page.get_by_role("textbox", name="Filter Value").fill("TOR")', "TOR")
    safe_regression_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_regression_action(page, page.locator("a").nth(2), 'click', 'page.locator("a").nth(2).click()')
    safe_regression_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    safe_regression_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_regression_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    safe_regression_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_regression_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^View 20 row\\(s\\)$")).nth(1).click()')


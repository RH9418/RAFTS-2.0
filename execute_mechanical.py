import re

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

def _generate_execution_report():
    report_dir = "Execution_Reports"
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"Mechanical_Execution_{timestamp}.txt")
    
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
    # 1. Buffer: Give Javascript 250ms to dispatch the fetch request after the click
    page.wait_for_timeout(250)
    
    # 2. NETWORK LOCK: Block execution until API responses arrive
    wait_cycles = 0
    while active_api_calls > 0 and wait_cycles < 300: # 30 second max timeout
        page.wait_for_timeout(100)
        wait_cycles += 1
        
    # 3. VISUAL LOCK: Network is done. Now wait for the DOM to remove skeletons/spinners
    try: page.evaluate(WAIT_FOR_STABILITY_JS)
    except: pass
    
    # 4. DOM PAINT BUFFER: Give grids 400ms to physically render rows
    page.wait_for_timeout(400)


# --- WIDGETS ---
DRAW_CROSSHAIR_JS = '''
([x, y]) => {
    const div = document.createElement('div'); div.id = 'agent-intent-crosshair';
    div.style.cssText = `position:fixed; left:${x-25}px; top:${y-25}px; width:50px; height:50px; border:4px solid #00FF00; border-radius:50%; z-index:2147483647; pointer-events:none; box-shadow:0 0 15px #00FF00;`;
    const dot = document.createElement('div');
    dot.style.cssText = 'position:absolute; left:21px; top:21px; width:8px; height:8px; background-color:#FF0000; border-radius:50%;';
    div.appendChild(dot); document.body.appendChild(div);
}
'''

REMOVE_CROSSHAIR_JS = "() => { const e = document.getElementById('agent-intent-crosshair'); if(e) e.remove(); }"

MANUAL_CAPTURE_JS = '''
() => new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:2147483647; cursor:crosshair; background:rgba(255,0,0,0.15);';
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
        with open('workflow_kb.yaml', 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id and healed_coords:
                    s['healed_coords'] = healed_coords
                    s['execution_mode'] = 'HEALED_COORDINATES'
        with open('workflow_kb.yaml', 'w', encoding='utf-8') as f: yaml.dump(kb, f, default_flow_style=False, sort_keys=False)
    except: pass

def check_for_healed_coords(step_id):
    try:
        with open('workflow_kb.yaml', 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id and 'healed_coords' in s: return s['healed_coords']
    except: pass
    return None

def safe_action(page, locator, action_name, step_id, before_path, intent_path, after_path, *args, **kwargs):
    print(f"\n▶ Step {step_id}: {action_name}")
    os.makedirs(os.path.dirname(before_path), exist_ok=True)
    
    page.wait_for_timeout(50)
    page.screenshot(path=before_path)
    
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
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 3000
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

    # 🔴 THE MAGIC: Wait for network to resolve BEFORE snapping the After image!
    wait_for_stability(page)
    page.screenshot(path=after_path)
    print(f"  └── 📸 Captured After:  {after_path}")


from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    page.on('response', handle_response)
    page.on('request', handle_request)
    page.on('requestfinished', handle_request_done)
    page.on('requestfailed', handle_request_done)
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
    safe_action(page, page.locator(".zeb-filter"), 'click', '1_1', 'baselines/step_1_1_before.png', 'baselines/step_1_1_intent.png', 'baselines/step_1_1_after.png')
    safe_action(page, page.get_by_text("Hierarchy"), 'click', '1_2', 'baselines/step_1_2_before.png', 'baselines/step_1_2_intent.png', 'baselines/step_1_2_after.png')
    safe_action(page, page.get_by_text("Brand Level 4"), 'click', '1_3', 'baselines/step_1_3_before.png', 'baselines/step_1_3_intent.png', 'baselines/step_1_3_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', '1_4', 'baselines/step_1_4_before.png', 'baselines/step_1_4_intent.png', 'baselines/step_1_4_after.png')
    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '1_5', 'baselines/step_1_5_before.png', 'baselines/step_1_5_intent.png', 'baselines/step_1_5_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_6', 'baselines/step_1_6_before.png', 'baselines/step_1_6_intent.png', 'baselines/step_1_6_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_7', 'baselines/step_1_7_before.png', 'baselines/step_1_7_intent.png', 'baselines/step_1_7_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_8', 'baselines/step_1_8_before.png', 'baselines/step_1_8_intent.png', 'baselines/step_1_8_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_9', 'baselines/step_1_9_before.png', 'baselines/step_1_9_intent.png', 'baselines/step_1_9_after.png')
    safe_action(page, page.get_by_text("Brand Level 4"), 'click', '1_10', 'baselines/step_1_10_before.png', 'baselines/step_1_10_intent.png', 'baselines/step_1_10_after.png')
    safe_action(page, page.get_by_text("Brand Level 3"), 'click', '1_11', 'baselines/step_1_11_before.png', 'baselines/step_1_11_intent.png', 'baselines/step_1_11_after.png')
    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '1_12', 'baselines/step_1_12_before.png', 'baselines/step_1_12_intent.png', 'baselines/step_1_12_after.png')
    safe_action(page, page.locator(".pointer.partial-selected"), 'click', '1_13', 'baselines/step_1_13_before.png', 'baselines/step_1_13_intent.png', 'baselines/step_1_13_after.png')
    safe_action(page, page.get_by_text("Brand Level 3"), 'click', '1_14', 'baselines/step_1_14_before.png', 'baselines/step_1_14_intent.png', 'baselines/step_1_14_after.png')
    safe_action(page, page.get_by_text("Attribute"), 'click', '1_15', 'baselines/step_1_15_before.png', 'baselines/step_1_15_intent.png', 'baselines/step_1_15_after.png')
    safe_action(page, page.get_by_text("Product Level 4"), 'click', '1_16', 'baselines/step_1_16_before.png', 'baselines/step_1_16_intent.png', 'baselines/step_1_16_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', '1_17', 'baselines/step_1_17_before.png', 'baselines/step_1_17_intent.png', 'baselines/step_1_17_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_18', 'baselines/step_1_18_before.png', 'baselines/step_1_18_intent.png', 'baselines/step_1_18_after.png')
    safe_action(page, page.get_by_text("Product Level 4"), 'click', '1_19', 'baselines/step_1_19_before.png', 'baselines/step_1_19_intent.png', 'baselines/step_1_19_after.png')
    safe_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location"), 'click', '1_20', 'baselines/step_1_20_before.png', 'baselines/step_1_20_intent.png', 'baselines/step_1_20_after.png')
    safe_action(page, page.get_by_text("Hierarchy"), 'click', '1_21', 'baselines/step_1_21_before.png', 'baselines/step_1_21_intent.png', 'baselines/step_1_21_after.png')
    safe_action(page, page.get_by_text("Sales Level 6"), 'click', '1_22', 'baselines/step_1_22_before.png', 'baselines/step_1_22_intent.png', 'baselines/step_1_22_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', '1_23', 'baselines/step_1_23_before.png', 'baselines/step_1_23_intent.png', 'baselines/step_1_23_after.png')
    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '1_24', 'baselines/step_1_24_before.png', 'baselines/step_1_24_intent.png', 'baselines/step_1_24_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_25', 'baselines/step_1_25_before.png', 'baselines/step_1_25_intent.png', 'baselines/step_1_25_after.png')
    safe_action(page, page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer"), 'click', '1_26', 'baselines/step_1_26_before.png', 'baselines/step_1_26_intent.png', 'baselines/step_1_26_after.png')
    safe_action(page, page.get_by_text("Sales Level 6"), 'click', '1_27', 'baselines/step_1_27_before.png', 'baselines/step_1_27_intent.png', 'baselines/step_1_27_after.png')
    safe_action(page, page.get_by_text("Sales Level 5"), 'click', '1_28', 'baselines/step_1_28_before.png', 'baselines/step_1_28_intent.png', 'baselines/step_1_28_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_29', 'baselines/step_1_29_before.png', 'baselines/step_1_29_intent.png', 'baselines/step_1_29_after.png')
    safe_action(page, page.get_by_text("Sales Level 5"), 'click', '1_30', 'baselines/step_1_30_before.png', 'baselines/step_1_30_intent.png', 'baselines/step_1_30_after.png')
    safe_action(page, page.get_by_text("Sales Level 4"), 'click', '1_31', 'baselines/step_1_31_before.png', 'baselines/step_1_31_intent.png', 'baselines/step_1_31_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', '1_32', 'baselines/step_1_32_before.png', 'baselines/step_1_32_intent.png', 'baselines/step_1_32_after.png')
    safe_action(page, page.get_by_text("Sales Level 4"), 'click', '1_33', 'baselines/step_1_33_before.png', 'baselines/step_1_33_intent.png', 'baselines/step_1_33_after.png')
    safe_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer"), 'click', '1_34', 'baselines/step_1_34_before.png', 'baselines/step_1_34_intent.png', 'baselines/step_1_34_after.png')
    safe_action(page, page.get_by_text("Hierarchy"), 'click', '1_35', 'baselines/step_1_35_before.png', 'baselines/step_1_35_intent.png', 'baselines/step_1_35_after.png')
    safe_action(page, page.get_by_text("Customer Level 4"), 'click', '1_36', 'baselines/step_1_36_before.png', 'baselines/step_1_36_intent.png', 'baselines/step_1_36_after.png')
    safe_action(page, page.get_by_text("Customer Level 4"), 'click', '1_37', 'baselines/step_1_37_before.png', 'baselines/step_1_37_intent.png', 'baselines/step_1_37_after.png')
    safe_action(page, page.locator(".pointer.zeb-check"), 'click', '1_38', 'baselines/step_1_38_before.png', 'baselines/step_1_38_intent.png', 'baselines/step_1_38_after.png')
    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '1_39', 'baselines/step_1_39_before.png', 'baselines/step_1_39_intent.png', 'baselines/step_1_39_after.png')
    safe_action(page, page.locator(".pointer.custom-checkbox-unchecked"), 'click', '1_40', 'baselines/step_1_40_before.png', 'baselines/step_1_40_intent.png', 'baselines/step_1_40_after.png')
    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '1_41', 'baselines/step_1_41_before.png', 'baselines/step_1_41_intent.png', 'baselines/step_1_41_after.png')
    safe_action(page, page.locator(".filter-icon-wrapper"), 'click', '1_42', 'baselines/step_1_42_before.png', 'baselines/step_1_42_intent.png', 'baselines/step_1_42_after.png')

    # ============================================================
    # SECTION: Alert Types
    # ============================================================
    safe_action(page, page.locator(".dropdown-caret").first, 'click', '2_1', 'baselines/step_2_1_before.png', 'baselines/step_2_1_intent.png', 'baselines/step_2_1_after.png')
    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1), 'click', '2_2', 'baselines/step_2_2_before.png', 'baselines/step_2_2_intent.png', 'baselines/step_2_2_after.png')
    safe_action(page, page.locator(".dropdown-caret").first, 'click', '2_3', 'baselines/step_2_3_before.png', 'baselines/step_2_3_intent.png', 'baselines/step_2_3_after.png')
    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1), 'click', '2_4', 'baselines/step_2_4_before.png', 'baselines/step_2_4_intent.png', 'baselines/step_2_4_after.png')

    # ============================================================
    # SECTION: Alerts Sumary
    # ============================================================
    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_1', 'baselines/step_3_1_before.png', 'baselines/step_3_1_intent.png', 'baselines/step_3_1_after.png')
    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '3_2', 'baselines/step_3_2_before.png', 'baselines/step_3_2_intent.png', 'baselines/step_3_2_after.png')
    safe_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_3', 'baselines/step_3_3_before.png', 'baselines/step_3_3_intent.png', 'baselines/step_3_3_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_4', 'baselines/step_3_4_before.png', 'baselines/step_3_4_intent.png', 'baselines/step_3_4_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', '3_5', 'baselines/step_3_5_before.png', 'baselines/step_3_5_intent.png', 'baselines/step_3_5_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_6', 'baselines/step_3_6_before.png', 'baselines/step_3_6_intent.png', 'baselines/step_3_6_after.png', "129406")
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_7', 'baselines/step_3_7_before.png', 'baselines/step_3_7_intent.png', 'baselines/step_3_7_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_8', 'baselines/step_3_8_before.png', 'baselines/step_3_8_intent.png', 'baselines/step_3_8_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_9', 'baselines/step_3_9_before.png', 'baselines/step_3_9_intent.png', 'baselines/step_3_9_after.png')
    safe_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_10', 'baselines/step_3_10_before.png', 'baselines/step_3_10_intent.png', 'baselines/step_3_10_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_11', 'baselines/step_3_11_before.png', 'baselines/step_3_11_intent.png', 'baselines/step_3_11_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_12', 'baselines/step_3_12_before.png', 'baselines/step_3_12_intent.png', 'baselines/step_3_12_after.png', "-6.5")
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_13', 'baselines/step_3_13_before.png', 'baselines/step_3_13_intent.png', 'baselines/step_3_13_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_14', 'baselines/step_3_14_before.png', 'baselines/step_3_14_intent.png', 'baselines/step_3_14_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_15', 'baselines/step_3_15_before.png', 'baselines/step_3_15_intent.png', 'baselines/step_3_15_after.png')
    safe_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_16', 'baselines/step_3_16_before.png', 'baselines/step_3_16_intent.png', 'baselines/step_3_16_after.png')
    safe_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_17', 'baselines/step_3_17_before.png', 'baselines/step_3_17_intent.png', 'baselines/step_3_17_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_18', 'baselines/step_3_18_before.png', 'baselines/step_3_18_intent.png', 'baselines/step_3_18_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_19', 'baselines/step_3_19_before.png', 'baselines/step_3_19_intent.png', 'baselines/step_3_19_after.png', "21")
    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_20', 'baselines/step_3_20_before.png', 'baselines/step_3_20_intent.png', 'baselines/step_3_20_after.png')
    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_21', 'baselines/step_3_21_before.png', 'baselines/step_3_21_intent.png', 'baselines/step_3_21_after.png')
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_22', 'baselines/step_3_22_before.png', 'baselines/step_3_22_intent.png', 'baselines/step_3_22_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_23', 'baselines/step_3_23_before.png', 'baselines/step_3_23_intent.png', 'baselines/step_3_23_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_24', 'baselines/step_3_24_before.png', 'baselines/step_3_24_intent.png', 'baselines/step_3_24_after.png')
    safe_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_25', 'baselines/step_3_25_before.png', 'baselines/step_3_25_intent.png', 'baselines/step_3_25_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_26', 'baselines/step_3_26_before.png', 'baselines/step_3_26_intent.png', 'baselines/step_3_26_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_27', 'baselines/step_3_27_before.png', 'baselines/step_3_27_intent.png', 'baselines/step_3_27_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_28', 'baselines/step_3_28_before.png', 'baselines/step_3_28_intent.png', 'baselines/step_3_28_after.png', "7.2")
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_29', 'baselines/step_3_29_before.png', 'baselines/step_3_29_intent.png', 'baselines/step_3_29_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_30', 'baselines/step_3_30_before.png', 'baselines/step_3_30_intent.png', 'baselines/step_3_30_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_31', 'baselines/step_3_31_before.png', 'baselines/step_3_31_intent.png', 'baselines/step_3_31_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_32', 'baselines/step_3_32_before.png', 'baselines/step_3_32_intent.png', 'baselines/step_3_32_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_33', 'baselines/step_3_33_before.png', 'baselines/step_3_33_intent.png', 'baselines/step_3_33_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_34', 'baselines/step_3_34_before.png', 'baselines/step_3_34_intent.png', 'baselines/step_3_34_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_35', 'baselines/step_3_35_before.png', 'baselines/step_3_35_intent.png', 'baselines/step_3_35_after.png', "10")
    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_36', 'baselines/step_3_36_before.png', 'baselines/step_3_36_intent.png', 'baselines/step_3_36_after.png')
    safe_action(page, page.get_by_role("option", name="Less than or equal to"), 'click', '3_37', 'baselines/step_3_37_before.png', 'baselines/step_3_37_intent.png', 'baselines/step_3_37_after.png')
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_38', 'baselines/step_3_38_before.png', 'baselines/step_3_38_intent.png', 'baselines/step_3_38_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_39', 'baselines/step_3_39_before.png', 'baselines/step_3_39_intent.png', 'baselines/step_3_39_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_40', 'baselines/step_3_40_before.png', 'baselines/step_3_40_intent.png', 'baselines/step_3_40_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_41', 'baselines/step_3_41_before.png', 'baselines/step_3_41_intent.png', 'baselines/step_3_41_after.png')
    safe_action(page, page.locator("div:nth-child(7) > .ag-column-select-column"), 'click', '3_42', 'baselines/step_3_42_before.png', 'baselines/step_3_42_intent.png', 'baselines/step_3_42_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_43', 'baselines/step_3_43_before.png', 'baselines/step_3_43_intent.png', 'baselines/step_3_43_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_44', 'baselines/step_3_44_before.png', 'baselines/step_3_44_intent.png', 'baselines/step_3_44_after.png', "380906")
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_45', 'baselines/step_3_45_before.png', 'baselines/step_3_45_intent.png', 'baselines/step_3_45_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_46', 'baselines/step_3_46_before.png', 'baselines/step_3_46_intent.png', 'baselines/step_3_46_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_47', 'baselines/step_3_47_before.png', 'baselines/step_3_47_intent.png', 'baselines/step_3_47_after.png')
    safe_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_48', 'baselines/step_3_48_before.png', 'baselines/step_3_48_intent.png', 'baselines/step_3_48_after.png')
    safe_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_49', 'baselines/step_3_49_before.png', 'baselines/step_3_49_intent.png', 'baselines/step_3_49_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_50', 'baselines/step_3_50_before.png', 'baselines/step_3_50_intent.png', 'baselines/step_3_50_after.png')
    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_51', 'baselines/step_3_51_before.png', 'baselines/step_3_51_intent.png', 'baselines/step_3_51_after.png', "384298")
    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_52', 'baselines/step_3_52_before.png', 'baselines/step_3_52_intent.png', 'baselines/step_3_52_after.png')
    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_53', 'baselines/step_3_53_before.png', 'baselines/step_3_53_intent.png', 'baselines/step_3_53_after.png')
    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_54', 'baselines/step_3_54_before.png', 'baselines/step_3_54_intent.png', 'baselines/step_3_54_after.png')
    safe_action(page, page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper"), 'check', '3_55', 'baselines/step_3_55_before.png', 'baselines/step_3_55_intent.png', 'baselines/step_3_55_after.png')
    safe_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_134', 'baselines/step_3_134_before.png', 'baselines/step_3_134_intent.png', 'baselines/step_3_134_after.png')

    page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    safe_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_154', 'baselines/step_3_154_before.png', 'baselines/step_3_154_intent.png', 'baselines/step_3_154_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_59', 'baselines/step_3_59_before.png', 'baselines/step_3_59_intent.png', 'baselines/step_3_59_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_60', 'baselines/step_3_60_before.png', 'baselines/step_3_60_intent.png', 'baselines/step_3_60_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_61', 'baselines/step_3_61_before.png', 'baselines/step_3_61_intent.png', 'baselines/step_3_61_after.png', "100")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_62', 'baselines/step_3_62_before.png', 'baselines/step_3_62_intent.png', 'baselines/step_3_62_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_63', 'baselines/step_3_63_before.png', 'baselines/step_3_63_intent.png', 'baselines/step_3_63_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_64', 'baselines/step_3_64_before.png', 'baselines/step_3_64_intent.png', 'baselines/step_3_64_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_65', 'baselines/step_3_65_before.png', 'baselines/step_3_65_intent.png', 'baselines/step_3_65_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_66', 'baselines/step_3_66_before.png', 'baselines/step_3_66_intent.png', 'baselines/step_3_66_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_67', 'baselines/step_3_67_before.png', 'baselines/step_3_67_intent.png', 'baselines/step_3_67_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_68', 'baselines/step_3_68_before.png', 'baselines/step_3_68_intent.png', 'baselines/step_3_68_after.png', "200")

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_69', 'baselines/step_3_69_before.png', 'baselines/step_3_69_intent.png', 'baselines/step_3_69_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_70', 'baselines/step_3_70_before.png', 'baselines/step_3_70_intent.png', 'baselines/step_3_70_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_71', 'baselines/step_3_71_before.png', 'baselines/step_3_71_intent.png', 'baselines/step_3_71_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_72', 'baselines/step_3_72_before.png', 'baselines/step_3_72_intent.png', 'baselines/step_3_72_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_73', 'baselines/step_3_73_before.png', 'baselines/step_3_73_intent.png', 'baselines/step_3_73_after.png', "383")

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_74', 'baselines/step_3_74_before.png', 'baselines/step_3_74_intent.png', 'baselines/step_3_74_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_75', 'baselines/step_3_75_before.png', 'baselines/step_3_75_intent.png', 'baselines/step_3_75_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '3_76', 'baselines/step_3_76_before.png', 'baselines/step_3_76_intent.png', 'baselines/step_3_76_after.png')

    safe_action(page, page.locator("a").filter(has_text="2"), 'click', '3_77', 'baselines/step_3_77_before.png', 'baselines/step_3_77_intent.png', 'baselines/step_3_77_after.png')

    safe_action(page, page.locator("a").filter(has_text="1"), 'click', '3_78', 'baselines/step_3_78_before.png', 'baselines/step_3_78_intent.png', 'baselines/step_3_78_after.png')

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '3_79', 'baselines/step_3_79_before.png', 'baselines/step_3_79_intent.png', 'baselines/step_3_79_after.png')

    safe_action(page, page.get_by_text("View 20 row(s)"), 'click', '3_80', 'baselines/step_3_80_before.png', 'baselines/step_3_80_intent.png', 'baselines/step_3_80_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_81', 'baselines/step_3_81_before.png', 'baselines/step_3_81_intent.png', 'baselines/step_3_81_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '3_82', 'baselines/step_3_82_before.png', 'baselines/step_3_82_intent.png', 'baselines/step_3_82_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_83', 'baselines/step_3_83_before.png', 'baselines/step_3_83_intent.png', 'baselines/step_3_83_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '3_84', 'baselines/step_3_84_before.png', 'baselines/step_3_84_intent.png', 'baselines/step_3_84_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '3_85', 'baselines/step_3_85_before.png', 'baselines/step_3_85_intent.png', 'baselines/step_3_85_after.png')

    with safe_download(page) as download_info:

        safe_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', '3_86', 'baselines/step_3_86_before.png', 'baselines/step_3_86_intent.png', 'baselines/step_3_86_after.png')

    download = download_info.value

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '3_87', 'baselines/step_3_87_before.png', 'baselines/step_3_87_intent.png', 'baselines/step_3_87_after.png')

    safe_action(page, page.get_by_text("Reset Preference"), 'click', '3_88', 'baselines/step_3_88_before.png', 'baselines/step_3_88_intent.png', 'baselines/step_3_88_after.png')

    safe_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', '3_89', 'baselines/step_3_89_before.png', 'baselines/step_3_89_intent.png', 'baselines/step_3_89_after.png')

    safe_action(page, page.locator("span").filter(has_text="WALMART STORES HQ").first, 'click', '3_90', 'baselines/step_3_90_before.png', 'baselines/step_3_90_intent.png', 'baselines/step_3_90_after.png', button="right")

    safe_action(page, page.get_by_text("Drill down"), 'click', '3_91', 'baselines/step_3_91_before.png', 'baselines/step_3_91_intent.png', 'baselines/step_3_91_after.png')

    safe_action(page, page.locator("span").filter(has_text="WALMART").first, 'click', '3_92', 'baselines/step_3_92_before.png', 'baselines/step_3_92_intent.png', 'baselines/step_3_92_after.png', button="right")

    safe_action(page, page.get_by_text("Drill up"), 'click', '3_93', 'baselines/step_3_93_before.png', 'baselines/step_3_93_intent.png', 'baselines/step_3_93_after.png')

    safe_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', '3_94', 'baselines/step_3_94_before.png', 'baselines/step_3_94_intent.png', 'baselines/step_3_94_after.png')

    safe_action(page, page.get_by_role("button", name="columns").nth(1), 'click', '3_95', 'baselines/step_3_95_before.png', 'baselines/step_3_95_intent.png', 'baselines/step_3_95_after.png')

    safe_action(page, page.get_by_role("button", name="columns").nth(1), 'click', '3_96', 'baselines/step_3_96_before.png', 'baselines/step_3_96_intent.png', 'baselines/step_3_96_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_97', 'baselines/step_3_97_before.png', 'baselines/step_3_97_intent.png', 'baselines/step_3_97_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_98', 'baselines/step_3_98_before.png', 'baselines/step_3_98_intent.png', 'baselines/step_3_98_after.png', "10000")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_99', 'baselines/step_3_99_before.png', 'baselines/step_3_99_intent.png', 'baselines/step_3_99_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_100', 'baselines/step_3_100_before.png', 'baselines/step_3_100_intent.png', 'baselines/step_3_100_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_101', 'baselines/step_3_101_before.png', 'baselines/step_3_101_intent.png', 'baselines/step_3_101_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_102', 'baselines/step_3_102_before.png', 'baselines/step_3_102_intent.png', 'baselines/step_3_102_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_103', 'baselines/step_3_103_before.png', 'baselines/step_3_103_intent.png', 'baselines/step_3_103_after.png', "20")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_104', 'baselines/step_3_104_before.png', 'baselines/step_3_104_intent.png', 'baselines/step_3_104_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_105', 'baselines/step_3_105_before.png', 'baselines/step_3_105_intent.png', 'baselines/step_3_105_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_106', 'baselines/step_3_106_before.png', 'baselines/step_3_106_intent.png', 'baselines/step_3_106_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_107', 'baselines/step_3_107_before.png', 'baselines/step_3_107_intent.png', 'baselines/step_3_107_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_108', 'baselines/step_3_108_before.png', 'baselines/step_3_108_intent.png', 'baselines/step_3_108_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_109', 'baselines/step_3_109_before.png', 'baselines/step_3_109_intent.png', 'baselines/step_3_109_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_110', 'baselines/step_3_110_before.png', 'baselines/step_3_110_intent.png', 'baselines/step_3_110_after.png', "20")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_111', 'baselines/step_3_111_before.png', 'baselines/step_3_111_intent.png', 'baselines/step_3_111_after.png')

    safe_action(page, page.get_by_text("Greater than or equal to"), 'click', '3_112', 'baselines/step_3_112_before.png', 'baselines/step_3_112_intent.png', 'baselines/step_3_112_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_113', 'baselines/step_3_113_before.png', 'baselines/step_3_113_intent.png', 'baselines/step_3_113_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_114', 'baselines/step_3_114_before.png', 'baselines/step_3_114_intent.png', 'baselines/step_3_114_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_115', 'baselines/step_3_115_before.png', 'baselines/step_3_115_intent.png', 'baselines/step_3_115_after.png')

    safe_action(page, page.get_by_role("button", name="columns").nth(1), 'click', '3_116', 'baselines/step_3_116_before.png', 'baselines/step_3_116_intent.png', 'baselines/step_3_116_after.png')

    safe_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_117', 'baselines/step_3_117_before.png', 'baselines/step_3_117_intent.png', 'baselines/step_3_117_after.png')

    safe_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_118', 'baselines/step_3_118_before.png', 'baselines/step_3_118_intent.png', 'baselines/step_3_118_after.png')

    safe_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_119', 'baselines/step_3_119_before.png', 'baselines/step_3_119_intent.png', 'baselines/step_3_119_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_120', 'baselines/step_3_120_before.png', 'baselines/step_3_120_intent.png', 'baselines/step_3_120_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_121', 'baselines/step_3_121_before.png', 'baselines/step_3_121_intent.png', 'baselines/step_3_121_after.png', "1000")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_122', 'baselines/step_3_122_before.png', 'baselines/step_3_122_intent.png', 'baselines/step_3_122_after.png')

    safe_action(page, page.get_by_text("Greater than or equal to"), 'click', '3_123', 'baselines/step_3_123_before.png', 'baselines/step_3_123_intent.png', 'baselines/step_3_123_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_124', 'baselines/step_3_124_before.png', 'baselines/step_3_124_intent.png', 'baselines/step_3_124_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_125', 'baselines/step_3_125_before.png', 'baselines/step_3_125_intent.png', 'baselines/step_3_125_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_126', 'baselines/step_3_126_before.png', 'baselines/step_3_126_intent.png', 'baselines/step_3_126_after.png')

    safe_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_127', 'baselines/step_3_127_before.png', 'baselines/step_3_127_intent.png', 'baselines/step_3_127_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_128', 'baselines/step_3_128_before.png', 'baselines/step_3_128_intent.png', 'baselines/step_3_128_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_129', 'baselines/step_3_129_before.png', 'baselines/step_3_129_intent.png', 'baselines/step_3_129_after.png', "20000")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_130', 'baselines/step_3_130_before.png', 'baselines/step_3_130_intent.png', 'baselines/step_3_130_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '3_131', 'baselines/step_3_131_before.png', 'baselines/step_3_131_intent.png', 'baselines/step_3_131_after.png')

    safe_action(page, page.get_by_text("Apply Reset Clear"), 'click', '3_132', 'baselines/step_3_132_before.png', 'baselines/step_3_132_intent.png', 'baselines/step_3_132_after.png')

    safe_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_133', 'baselines/step_3_133_before.png', 'baselines/step_3_133_intent.png', 'baselines/step_3_133_after.png')

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    safe_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_135', 'baselines/step_3_135_before.png', 'baselines/step_3_135_intent.png', 'baselines/step_3_135_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_136', 'baselines/step_3_136_before.png', 'baselines/step_3_136_intent.png', 'baselines/step_3_136_after.png', "100000")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_137', 'baselines/step_3_137_before.png', 'baselines/step_3_137_intent.png', 'baselines/step_3_137_after.png')

    safe_action(page, page.get_by_text("Greater than or equal to"), 'click', '3_138', 'baselines/step_3_138_before.png', 'baselines/step_3_138_intent.png', 'baselines/step_3_138_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_139', 'baselines/step_3_139_before.png', 'baselines/step_3_139_intent.png', 'baselines/step_3_139_after.png')

    safe_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_140', 'baselines/step_3_140_before.png', 'baselines/step_3_140_intent.png', 'baselines/step_3_140_after.png')

    safe_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_141', 'baselines/step_3_141_before.png', 'baselines/step_3_141_intent.png', 'baselines/step_3_141_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_142', 'baselines/step_3_142_before.png', 'baselines/step_3_142_intent.png', 'baselines/step_3_142_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_143', 'baselines/step_3_143_before.png', 'baselines/step_3_143_intent.png', 'baselines/step_3_143_after.png', "65000")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_144', 'baselines/step_3_144_before.png', 'baselines/step_3_144_intent.png', 'baselines/step_3_144_after.png')

    safe_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_145', 'baselines/step_3_145_before.png', 'baselines/step_3_145_intent.png', 'baselines/step_3_145_after.png')

    safe_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_146', 'baselines/step_3_146_before.png', 'baselines/step_3_146_intent.png', 'baselines/step_3_146_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '3_147', 'baselines/step_3_147_before.png', 'baselines/step_3_147_intent.png', 'baselines/step_3_147_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_148', 'baselines/step_3_148_before.png', 'baselines/step_3_148_intent.png', 'baselines/step_3_148_after.png', "10000")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_149', 'baselines/step_3_149_before.png', 'baselines/step_3_149_intent.png', 'baselines/step_3_149_after.png')

    safe_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_150', 'baselines/step_3_150_before.png', 'baselines/step_3_150_intent.png', 'baselines/step_3_150_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '3_151', 'baselines/step_3_151_before.png', 'baselines/step_3_151_intent.png', 'baselines/step_3_151_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_152', 'baselines/step_3_152_before.png', 'baselines/step_3_152_intent.png', 'baselines/step_3_152_after.png')

    safe_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '3_153', 'baselines/step_3_153_before.png', 'baselines/step_3_153_intent.png', 'baselines/step_3_153_after.png')

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").uncheck()

    page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()

    safe_action(page, page.locator("div:nth-child(12) > .ag-column-select-column"), 'click', '3_157', 'baselines/step_3_157_before.png', 'baselines/step_3_157_intent.png', 'baselines/step_3_157_after.png')

    safe_action(page, page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', '3_158', 'baselines/step_3_158_before.png', 'baselines/step_3_158_intent.png', 'baselines/step_3_158_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first, 'click', '3_159', 'baselines/step_3_159_before.png', 'baselines/step_3_159_intent.png', 'baselines/step_3_159_after.png')

    safe_action(page, page.locator(".checkbox-primary-color").first, 'check', '3_160', 'baselines/step_3_160_before.png', 'baselines/step_3_160_intent.png', 'baselines/step_3_160_after.png')

    safe_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', '3_161', 'baselines/step_3_161_before.png', 'baselines/step_3_161_intent.png', 'baselines/step_3_161_after.png', button="right")

    safe_action(page, page.get_by_text("Drill down"), 'click', '3_162', 'baselines/step_3_162_before.png', 'baselines/step_3_162_intent.png', 'baselines/step_3_162_after.png')

    safe_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', '3_163', 'baselines/step_3_163_before.png', 'baselines/step_3_163_intent.png', 'baselines/step_3_163_after.png', button="right")

    safe_action(page, page.get_by_text("Drill up"), 'click', '3_164', 'baselines/step_3_164_before.png', 'baselines/step_3_164_intent.png', 'baselines/step_3_164_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_165', 'baselines/step_3_165_before.png', 'baselines/step_3_165_intent.png', 'baselines/step_3_165_after.png')



    # ============================================================
    # SECTION: Weekly Summary Section
    # ============================================================


    safe_action(page, page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_1', 'baselines/step_4_1_before.png', 'baselines/step_4_1_intent.png', 'baselines/step_4_1_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1), 'click', '4_2', 'baselines/step_4_2_before.png', 'baselines/step_4_2_intent.png', 'baselines/step_4_2_after.png')

    safe_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', '4_3', 'baselines/step_4_3_before.png', 'baselines/step_4_3_intent.png', 'baselines/step_4_3_after.png')

    safe_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', '4_4', 'baselines/step_4_4_before.png', 'baselines/step_4_4_intent.png', 'baselines/step_4_4_after.png')

    safe_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', '4_5', 'baselines/step_4_5_before.png', 'baselines/step_4_5_intent.png', 'baselines/step_4_5_after.png')

    safe_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', '4_6', 'baselines/step_4_6_before.png', 'baselines/step_4_6_intent.png', 'baselines/step_4_6_after.png')

    safe_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', '4_7', 'baselines/step_4_7_before.png', 'baselines/step_4_7_intent.png', 'baselines/step_4_7_after.png')

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_8', 'baselines/step_4_8_before.png', 'baselines/step_4_8_intent.png', 'baselines/step_4_8_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '4_9', 'baselines/step_4_9_before.png', 'baselines/step_4_9_intent.png', 'baselines/step_4_9_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '4_10', 'baselines/step_4_10_before.png', 'baselines/step_4_10_intent.png', 'baselines/step_4_10_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '4_11', 'baselines/step_4_11_before.png', 'baselines/step_4_11_intent.png', 'baselines/step_4_11_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '4_12', 'baselines/step_4_12_before.png', 'baselines/step_4_12_intent.png', 'baselines/step_4_12_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(4) > .d-flex"), 'click', '4_13', 'baselines/step_4_13_before.png', 'baselines/step_4_13_intent.png', 'baselines/step_4_13_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(5) > .d-flex"), 'click', '4_14', 'baselines/step_4_14_before.png', 'baselines/step_4_14_intent.png', 'baselines/step_4_14_after.png')

    safe_action(page, page.locator("div:nth-child(6) > .d-flex"), 'click', '4_15', 'baselines/step_4_15_before.png', 'baselines/step_4_15_intent.png', 'baselines/step_4_15_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', '4_16', 'baselines/step_4_16_before.png', 'baselines/step_4_16_intent.png', 'baselines/step_4_16_after.png')

    safe_action(page, page.locator("div:nth-child(8) > .d-flex"), 'click', '4_17', 'baselines/step_4_17_before.png', 'baselines/step_4_17_intent.png', 'baselines/step_4_17_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first, 'click', '4_18', 'baselines/step_4_18_before.png', 'baselines/step_4_18_intent.png', 'baselines/step_4_18_after.png')

    safe_action(page, page.locator("div:nth-child(9) > .d-flex"), 'click', '4_19', 'baselines/step_4_19_before.png', 'baselines/step_4_19_intent.png', 'baselines/step_4_19_after.png')

    safe_action(page, page.locator("div:nth-child(10) > .d-flex"), 'click', '4_20', 'baselines/step_4_20_before.png', 'baselines/step_4_20_intent.png', 'baselines/step_4_20_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '4_21', 'baselines/step_4_21_before.png', 'baselines/step_4_21_intent.png', 'baselines/step_4_21_after.png')

    safe_action(page, page.get_by_text("All").nth(3), 'click', '4_22', 'baselines/step_4_22_before.png', 'baselines/step_4_22_intent.png', 'baselines/step_4_22_after.png')

    safe_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', '4_23', 'baselines/step_4_23_before.png', 'baselines/step_4_23_intent.png', 'baselines/step_4_23_after.png')

    safe_action(page, page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_24', 'baselines/step_4_24_before.png', 'baselines/step_4_24_intent.png', 'baselines/step_4_24_after.png')

    safe_action(page, page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_25', 'baselines/step_4_25_before.png', 'baselines/step_4_25_intent.png', 'baselines/step_4_25_after.png')

    safe_action(page, page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_26', 'baselines/step_4_26_before.png', 'baselines/step_4_26_intent.png', 'baselines/step_4_26_after.png')

    safe_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', '4_27', 'baselines/step_4_27_before.png', 'baselines/step_4_27_intent.png', 'baselines/step_4_27_after.png')

    safe_action(page, page.locator("svg").get_by_text("User Forecast Total"), 'click', '4_28', 'baselines/step_4_28_before.png', 'baselines/step_4_28_intent.png', 'baselines/step_4_28_after.png')

    safe_action(page, page.locator("svg").get_by_text("User Override Total"), 'click', '4_29', 'baselines/step_4_29_before.png', 'baselines/step_4_29_intent.png', 'baselines/step_4_29_after.png')

    safe_action(page, page.locator("svg").get_by_text("Aged Net Units"), 'click', '4_30', 'baselines/step_4_30_before.png', 'baselines/step_4_30_intent.png', 'baselines/step_4_30_after.png')

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_31', 'baselines/step_4_31_before.png', 'baselines/step_4_31_intent.png', 'baselines/step_4_31_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_32', 'baselines/step_4_32_before.png', 'baselines/step_4_32_intent.png', 'baselines/step_4_32_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_33', 'baselines/step_4_33_before.png', 'baselines/step_4_33_intent.png', 'baselines/step_4_33_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_34', 'baselines/step_4_34_before.png', 'baselines/step_4_34_intent.png', 'baselines/step_4_34_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_35', 'baselines/step_4_35_before.png', 'baselines/step_4_35_intent.png', 'baselines/step_4_35_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', '4_36', 'baselines/step_4_36_before.png', 'baselines/step_4_36_intent.png', 'baselines/step_4_36_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(8)"), 'click', '4_37', 'baselines/step_4_37_before.png', 'baselines/step_4_37_intent.png', 'baselines/step_4_37_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_38', 'baselines/step_4_38_before.png', 'baselines/step_4_38_intent.png', 'baselines/step_4_38_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', '4_39', 'baselines/step_4_39_before.png', 'baselines/step_4_39_intent.png', 'baselines/step_4_39_after.png')

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_40', 'baselines/step_4_40_before.png', 'baselines/step_4_40_intent.png', 'baselines/step_4_40_after.png')

    safe_action(page, page.locator("path:nth-child(78)"), 'click', '4_41', 'baselines/step_4_41_before.png', 'baselines/step_4_41_intent.png', 'baselines/step_4_41_after.png')

    safe_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', '4_42', 'baselines/step_4_42_before.png', 'baselines/step_4_42_intent.png', 'baselines/step_4_42_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '4_43', 'baselines/step_4_43_before.png', 'baselines/step_4_43_intent.png', 'baselines/step_4_43_after.png')

    safe_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', '4_44', 'baselines/step_4_44_before.png', 'baselines/step_4_44_intent.png', 'baselines/step_4_44_after.png')

    safe_action(page, page.get_by_text("Reset Preference"), 'click', '4_45', 'baselines/step_4_45_before.png', 'baselines/step_4_45_intent.png', 'baselines/step_4_45_after.png')

    safe_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div"), 'click', '4_46', 'baselines/step_4_46_before.png', 'baselines/step_4_46_intent.png', 'baselines/step_4_46_after.png')

    # ============================================================
    # SECTION: Events Grid
    # ============================================================
    safe_action(page, page.locator("div:nth-child(4) > span > .align-middle"), 'click', '5_1', 'baselines/step_5_1_before.png', 'baselines/step_5_1_intent.png', 'baselines/step_5_1_after.png')
    safe_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content"), 'click', '5_2', 'baselines/step_5_2_before.png', 'baselines/step_5_2_intent.png', 'baselines/step_5_2_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '5_3', 'baselines/step_5_3_before.png', 'baselines/step_5_3_intent.png', 'baselines/step_5_3_after.png')
    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '5_4', 'baselines/step_5_4_before.png', 'baselines/step_5_4_intent.png', 'baselines/step_5_4_after.png', "Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")
    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '5_5', 'baselines/step_5_5_before.png', 'baselines/step_5_5_intent.png', 'baselines/step_5_5_after.png')
    safe_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', '5_6', 'baselines/step_5_6_before.png', 'baselines/step_5_6_intent.png', 'baselines/step_5_6_after.png', button="right")
    safe_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', '5_7', 'baselines/step_5_7_before.png', 'baselines/step_5_7_intent.png', 'baselines/step_5_7_after.png')
    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '5_8', 'baselines/step_5_8_before.png', 'baselines/step_5_8_intent.png', 'baselines/step_5_8_after.png')
    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '5_9', 'baselines/step_5_9_before.png', 'baselines/step_5_9_intent.png', 'baselines/step_5_9_after.png', "TOR")
    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '5_10', 'baselines/step_5_10_before.png', 'baselines/step_5_10_intent.png', 'baselines/step_5_10_after.png')
    safe_action(page, page.locator("a").nth(2), 'click', '5_11', 'baselines/step_5_11_before.png', 'baselines/step_5_11_intent.png', 'baselines/step_5_11_after.png')
    safe_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', '5_12', 'baselines/step_5_12_before.png', 'baselines/step_5_12_intent.png', 'baselines/step_5_12_after.png')
    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '5_13', 'baselines/step_5_13_before.png', 'baselines/step_5_13_intent.png', 'baselines/step_5_13_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '5_14', 'baselines/step_5_14_before.png', 'baselines/step_5_14_intent.png', 'baselines/step_5_14_after.png')
    safe_action(page, page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '5_15', 'baselines/step_5_15_before.png', 'baselines/step_5_15_intent.png', 'baselines/step_5_15_after.png')
    safe_action(page, page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '5_16', 'baselines/step_5_16_before.png', 'baselines/step_5_16_intent.png', 'baselines/step_5_16_after.png')
    safe_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', '5_17', 'baselines/step_5_17_before.png', 'baselines/step_5_17_intent.png', 'baselines/step_5_17_after.png')
    safe_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '5_18', 'baselines/step_5_18_before.png', 'baselines/step_5_18_intent.png', 'baselines/step_5_18_after.png')
    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', '5_19', 'baselines/step_5_19_before.png', 'baselines/step_5_19_intent.png', 'baselines/step_5_19_after.png')


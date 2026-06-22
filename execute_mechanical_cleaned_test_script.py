import re
TARGET_YAML_FILE = "test_script_KB.yaml"

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
    # SECTION: Filter Section Test
    # ============================================================


    safe_action(page, page.locator(".ag-icon.ag-icon-filter").first, 'click', '1_1', 'baselines/step_1_1_before.png', 'baselines/step_1_1_intent.png', 'baselines/step_1_1_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '1_2', 'baselines/step_1_2_before.png', 'baselines/step_1_2_intent.png', 'baselines/step_1_2_after.png', "WALMART")

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '1_3', 'baselines/step_1_3_before.png', 'baselines/step_1_3_intent.png', 'baselines/step_1_3_after.png')

    safe_action(page, page.locator(".ag-icon.ag-icon-filter").first, 'click', '1_4', 'baselines/step_1_4_before.png', 'baselines/step_1_4_intent.png', 'baselines/step_1_4_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '1_5', 'baselines/step_1_5_before.png', 'baselines/step_1_5_intent.png', 'baselines/step_1_5_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_6', 'baselines/step_1_6_before.png', 'baselines/step_1_6_intent.png', 'baselines/step_1_6_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_7', 'baselines/step_1_7_before.png', 'baselines/step_1_7_intent.png', 'baselines/step_1_7_after.png', "10496")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '1_8', 'baselines/step_1_8_before.png', 'baselines/step_1_8_intent.png', 'baselines/step_1_8_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '1_9', 'baselines/step_1_9_before.png', 'baselines/step_1_9_intent.png', 'baselines/step_1_9_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '1_10', 'baselines/step_1_10_before.png', 'baselines/step_1_10_intent.png', 'baselines/step_1_10_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_11', 'baselines/step_1_11_before.png', 'baselines/step_1_11_intent.png', 'baselines/step_1_11_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '1_12', 'baselines/step_1_12_before.png', 'baselines/step_1_12_intent.png', 'baselines/step_1_12_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_13', 'baselines/step_1_13_before.png', 'baselines/step_1_13_intent.png', 'baselines/step_1_13_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_14', 'baselines/step_1_14_before.png', 'baselines/step_1_14_intent.png', 'baselines/step_1_14_after.png', "328.8")

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '1_15', 'baselines/step_1_15_before.png', 'baselines/step_1_15_intent.png', 'baselines/step_1_15_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_16', 'baselines/step_1_16_before.png', 'baselines/step_1_16_intent.png', 'baselines/step_1_16_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '1_17', 'baselines/step_1_17_before.png', 'baselines/step_1_17_intent.png', 'baselines/step_1_17_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_18', 'baselines/step_1_18_before.png', 'baselines/step_1_18_intent.png', 'baselines/step_1_18_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_19', 'baselines/step_1_19_before.png', 'baselines/step_1_19_intent.png', 'baselines/step_1_19_after.png', "373.7")

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '1_20', 'baselines/step_1_20_before.png', 'baselines/step_1_20_intent.png', 'baselines/step_1_20_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_21', 'baselines/step_1_21_before.png', 'baselines/step_1_21_intent.png', 'baselines/step_1_21_after.png')

    safe_action(page, page.get_by_role("button", name="Reset"), 'click', '1_22', 'baselines/step_1_22_before.png', 'baselines/step_1_22_intent.png', 'baselines/step_1_22_after.png')

    safe_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', '1_23', 'baselines/step_1_23_before.png', 'baselines/step_1_23_intent.png', 'baselines/step_1_23_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_24', 'baselines/step_1_24_before.png', 'baselines/step_1_24_intent.png', 'baselines/step_1_24_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_25', 'baselines/step_1_25_before.png', 'baselines/step_1_25_intent.png', 'baselines/step_1_25_after.png', "2840")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '1_26', 'baselines/step_1_26_before.png', 'baselines/step_1_26_intent.png', 'baselines/step_1_26_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_27', 'baselines/step_1_27_before.png', 'baselines/step_1_27_intent.png', 'baselines/step_1_27_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '1_28', 'baselines/step_1_28_before.png', 'baselines/step_1_28_intent.png', 'baselines/step_1_28_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_29', 'baselines/step_1_29_before.png', 'baselines/step_1_29_intent.png', 'baselines/step_1_29_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_30', 'baselines/step_1_30_before.png', 'baselines/step_1_30_intent.png', 'baselines/step_1_30_after.png', "110.1")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '1_31', 'baselines/step_1_31_before.png', 'baselines/step_1_31_intent.png', 'baselines/step_1_31_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_32', 'baselines/step_1_32_before.png', 'baselines/step_1_32_intent.png', 'baselines/step_1_32_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '1_33', 'baselines/step_1_33_before.png', 'baselines/step_1_33_intent.png', 'baselines/step_1_33_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', '1_34', 'baselines/step_1_34_before.png', 'baselines/step_1_34_intent.png', 'baselines/step_1_34_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '1_35', 'baselines/step_1_35_before.png', 'baselines/step_1_35_intent.png', 'baselines/step_1_35_after.png', "4")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '1_36', 'baselines/step_1_36_before.png', 'baselines/step_1_36_intent.png', 'baselines/step_1_36_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', '1_37', 'baselines/step_1_37_before.png', 'baselines/step_1_37_intent.png', 'baselines/step_1_37_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '1_38', 'baselines/step_1_38_before.png', 'baselines/step_1_38_intent.png', 'baselines/step_1_38_after.png')

    safe_action(page, page.locator(".checkbox-primary-color").first, 'check', '1_39', 'baselines/step_1_39_before.png', 'baselines/step_1_39_intent.png', 'baselines/step_1_39_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '1_40', 'baselines/step_1_40_before.png', 'baselines/step_1_40_intent.png', 'baselines/step_1_40_after.png')

    safe_action(page, page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '1_41', 'baselines/step_1_41_before.png', 'baselines/step_1_41_intent.png', 'baselines/step_1_41_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1), 'click', '1_42', 'baselines/step_1_42_before.png', 'baselines/step_1_42_intent.png', 'baselines/step_1_42_after.png')


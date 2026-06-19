import re
TARGET_YAML_FILE = "Game_Day_KB.yaml"

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
    
    # 🔴 MAP PATHS TO DYNAMIC RUN DIRECTORY
    before_path = os.path.join(IMAGE_DIR, os.path.basename(before_path))
    intent_path = os.path.join(IMAGE_DIR, os.path.basename(intent_path))
    after_path = os.path.join(IMAGE_DIR, os.path.basename(after_path))
    
    page.wait_for_timeout(50)
    page.screenshot(path=before_path)
    print(f"  └── 📸 Captured Before: {before_path}")
    
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
    
    # 🔴 RECORD NEW PATHS IN YAML SO LAYER 4 CAN FIND THEM
    try:
        with open(TARGET_YAML_FILE, 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id:
                    s['baseline_images']['before'] = before_path
                    s['baseline_images']['intent'] = intent_path
                    s['baseline_images']['after'] = after_path
        with open(TARGET_YAML_FILE, 'w', encoding='utf-8') as f: yaml.dump(kb, f, default_flow_style=False, sort_keys=False)
    except: pass


from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:
    # --- MFA & Login Wait Block ---
    page.on('response', handle_response)
    page.on('request', handle_request)
    page.on('requestfinished', handle_request_done)
    page.on('requestfailed', handle_request_done)
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=2", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print('\n✅ Initializing Stability Engine...')
    wait_for_stability(page)
    print("="*60 + "\n")



    # ============================================================
    # SECTION: Default Initialization
    # ============================================================
    safe_action(page, page.locator(".zeb-filter").first, 'click', '1_1', 'baselines/step_1_1_before.png', 'baselines/step_1_1_intent.png', 'baselines/step_1_1_after.png')

    safe_action(page, page.get_by_text("Hierarchy"), 'click', '1_2', 'baselines/step_1_2_before.png', 'baselines/step_1_2_intent.png', 'baselines/step_1_2_after.png')

    safe_action(page, page.get_by_text("League"), 'click', '1_3', 'baselines/step_1_3_before.png', 'baselines/step_1_3_intent.png', 'baselines/step_1_3_after.png')

    safe_action(page, page.get_by_role("radio", name="MLS"), 'check', '1_4', 'baselines/step_1_4_before.png', 'baselines/step_1_4_intent.png', 'baselines/step_1_4_after.png')

    safe_action(page, page.get_by_text("League"), 'click', '1_5', 'baselines/step_1_5_before.png', 'baselines/step_1_5_intent.png', 'baselines/step_1_5_after.png')

    safe_action(page, page.locator("#SideFilterproducthierarchyId").get_by_text("Team"), 'click', '1_6', 'baselines/step_1_6_before.png', 'baselines/step_1_6_intent.png', 'baselines/step_1_6_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first, 'click', '1_7', 'baselines/step_1_7_before.png', 'baselines/step_1_7_intent.png', 'baselines/step_1_7_after.png')

    safe_action(page, page.locator("#SideFilterproducthierarchyId").get_by_text("Team", exact=True), 'click', '1_8', 'baselines/step_1_8_before.png', 'baselines/step_1_8_intent.png', 'baselines/step_1_8_after.png')

    safe_action(page, page.get_by_text("Department"), 'click', '1_9', 'baselines/step_1_9_before.png', 'baselines/step_1_9_intent.png', 'baselines/step_1_9_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first, 'click', '1_10', 'baselines/step_1_10_before.png', 'baselines/step_1_10_intent.png', 'baselines/step_1_10_after.png')

    safe_action(page, page.get_by_text("Department"), 'click', '1_11', 'baselines/step_1_11_before.png', 'baselines/step_1_11_intent.png', 'baselines/step_1_11_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer"), 'click', '1_12', 'baselines/step_1_12_before.png', 'baselines/step_1_12_intent.png', 'baselines/step_1_12_after.png')

    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '1_13', 'baselines/step_1_13_before.png', 'baselines/step_1_13_intent.png', 'baselines/step_1_13_after.png')

    safe_action(page, page.locator(".zeb-filter").first, 'click', '1_14', 'baselines/step_1_14_before.png', 'baselines/step_1_14_intent.png', 'baselines/step_1_14_after.png')



    # ============================================================
    # SECTION: Forecast Filters
    # ============================================================


    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '2_1', 'baselines/step_2_1_before.png', 'baselines/step_2_1_intent.png', 'baselines/step_2_1_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '2_2', 'baselines/step_2_2_before.png', 'baselines/step_2_2_intent.png', 'baselines/step_2_2_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '2_3', 'baselines/step_2_3_before.png', 'baselines/step_2_3_intent.png', 'baselines/step_2_3_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '2_4', 'baselines/step_2_4_before.png', 'baselines/step_2_4_intent.png', 'baselines/step_2_4_after.png')

    safe_action(page, page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_5', 'baselines/step_2_5_before.png', 'baselines/step_2_5_intent.png', 'baselines/step_2_5_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '2_6', 'baselines/step_2_6_before.png', 'baselines/step_2_6_intent.png', 'baselines/step_2_6_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '2_7', 'baselines/step_2_7_before.png', 'baselines/step_2_7_intent.png', 'baselines/step_2_7_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '2_8', 'baselines/step_2_8_before.png', 'baselines/step_2_8_intent.png', 'baselines/step_2_8_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '2_9', 'baselines/step_2_9_before.png', 'baselines/step_2_9_intent.png', 'baselines/step_2_9_after.png')

    safe_action(page, page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_10', 'baselines/step_2_10_before.png', 'baselines/step_2_10_intent.png', 'baselines/step_2_10_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_11', 'baselines/step_2_11_before.png', 'baselines/step_2_11_intent.png', 'baselines/step_2_11_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '2_12', 'baselines/step_2_12_before.png', 'baselines/step_2_12_intent.png', 'baselines/step_2_12_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '2_13', 'baselines/step_2_13_before.png', 'baselines/step_2_13_intent.png', 'baselines/step_2_13_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '2_14', 'baselines/step_2_14_before.png', 'baselines/step_2_14_intent.png', 'baselines/step_2_14_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_15', 'baselines/step_2_15_before.png', 'baselines/step_2_15_intent.png', 'baselines/step_2_15_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '2_16', 'baselines/step_2_16_before.png', 'baselines/step_2_16_intent.png', 'baselines/step_2_16_after.png')



    # ============================================================
    # SECTION: Forecast Total Grid
    # ============================================================


    safe_action(page, page.locator(".pointer.chevron.zeb-chevron-right.m-r-12.collapsed"), 'click', '3_1', 'baselines/step_3_1_before.png', 'baselines/step_3_1_intent.png', 'baselines/step_3_1_after.png')

    safe_action(page, page.locator(".ag-body-horizontal-scroll-container").first, 'click', '3_2', 'baselines/step_3_2_before.png', 'baselines/step_3_2_intent.png', 'baselines/step_3_2_after.png')

    safe_action(page, page.locator("esp-card-component").filter(has_text="Forecast Total columns (0)").get_by_role("button"), 'click', '3_3', 'baselines/step_3_3_before.png', 'baselines/step_3_3_intent.png', 'baselines/step_3_3_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '3_4', 'baselines/step_3_4_before.png', 'baselines/step_3_4_intent.png', 'baselines/step_3_4_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Stat Unit Sales Fcst Column").get_by_label("Press SPACE to toggle"), 'check', '3_5', 'baselines/step_3_5_before.png', 'baselines/step_3_5_intent.png', 'baselines/step_3_5_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Stat Sales Fcst ($) Column").get_by_label("Press SPACE to toggle"), 'check', '3_6', 'baselines/step_3_6_before.png', 'baselines/step_3_6_intent.png', 'baselines/step_3_6_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Sales Fcst Adjusted ($) Column").get_by_label("Press SPACE to toggle"), 'check', '3_7', 'baselines/step_3_7_before.png', 'baselines/step_3_7_intent.png', 'baselines/step_3_7_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Actual Sales & ROY Fcst ($)").get_by_label("Press SPACE to toggle"), 'check', '3_8', 'baselines/step_3_8_before.png', 'baselines/step_3_8_intent.png', 'baselines/step_3_8_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Actual Sales ($) Column").get_by_label("Press SPACE to toggle"), 'check', '3_9', 'baselines/step_3_9_before.png', 'baselines/step_3_9_intent.png', 'baselines/step_3_9_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY Sales ($) Column").get_by_label("Press SPACE to toggle"), 'check', '3_10', 'baselines/step_3_10_before.png', 'baselines/step_3_10_intent.png', 'baselines/step_3_10_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Sales ($) Change vs LY Column").get_by_label("Press SPACE to toggle"), 'check', '3_11', 'baselines/step_3_11_before.png', 'baselines/step_3_11_intent.png', 'baselines/step_3_11_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LLY Sales ($) Column").get_by_label("Press SPACE to toggle"), 'check', '3_12', 'baselines/step_3_12_before.png', 'baselines/step_3_12_intent.png', 'baselines/step_3_12_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Sales ($) Change vs LLY Column").get_by_label("Press SPACE to toggle"), 'check', '3_13', 'baselines/step_3_13_before.png', 'baselines/step_3_13_intent.png', 'baselines/step_3_13_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Actual Sales & ROY Fcst Column").get_by_label("Press SPACE to toggle"), 'check', '3_14', 'baselines/step_3_14_before.png', 'baselines/step_3_14_intent.png', 'baselines/step_3_14_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Actual Sales Column").get_by_label("Press SPACE to toggle"), 'check', '3_15', 'baselines/step_3_15_before.png', 'baselines/step_3_15_intent.png', 'baselines/step_3_15_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY Sales Column").get_by_label("Press SPACE to toggle"), 'check', '3_16', 'baselines/step_3_16_before.png', 'baselines/step_3_16_intent.png', 'baselines/step_3_16_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Sales Change vs LY Column").get_by_label("Press SPACE to toggle"), 'check', '3_17', 'baselines/step_3_17_before.png', 'baselines/step_3_17_intent.png', 'baselines/step_3_17_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LLY Sales Column").get_by_label("Press SPACE to toggle"), 'check', '3_18', 'baselines/step_3_18_before.png', 'baselines/step_3_18_intent.png', 'baselines/step_3_18_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (hidden)"), 'check', '3_19', 'baselines/step_3_19_before.png', 'baselines/step_3_19_intent.png', 'baselines/step_3_19_after.png')

    safe_action(page, page.locator("esp-card-component").filter(has_text="Forecast Total columns (0)").get_by_role("button"), 'click', '3_20', 'baselines/step_3_20_before.png', 'baselines/step_3_20_intent.png', 'baselines/step_3_20_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments").first, 'click', '3_21', 'baselines/step_3_21_before.png', 'baselines/step_3_21_intent.png', 'baselines/step_3_21_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '3_22', 'baselines/step_3_22_before.png', 'baselines/step_3_22_intent.png', 'baselines/step_3_22_after.png')

    with safe_download(page) as download_info:

        safe_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline").first, 'click', '3_23', 'baselines/step_3_23_before.png', 'baselines/step_3_23_intent.png', 'baselines/step_3_23_after.png')

    download = download_info.value



    # ============================================================
    # SECTION: Daily Forecast Event Grid
    # ============================================================


    safe_action(page, page.locator("esp-card-component").filter(has_text="Daily Forecast by Event").get_by_role("button"), 'click', '4_1', 'baselines/step_4_1_before.png', 'baselines/step_4_1_intent.png', 'baselines/step_4_1_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '4_2', 'baselines/step_4_2_before.png', 'baselines/step_4_2_intent.png', 'baselines/step_4_2_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Game # Column").get_by_label("Press SPACE to toggle"), 'check', '4_3', 'baselines/step_4_3_before.png', 'baselines/step_4_3_intent.png', 'baselines/step_4_3_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_4', 'baselines/step_4_4_before.png', 'baselines/step_4_4_intent.png', 'baselines/step_4_4_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_5', 'baselines/step_4_5_before.png', 'baselines/step_4_5_intent.png', 'baselines/step_4_5_after.png', "1")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_6', 'baselines/step_4_6_before.png', 'baselines/step_4_6_intent.png', 'baselines/step_4_6_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_7', 'baselines/step_4_7_before.png', 'baselines/step_4_7_intent.png', 'baselines/step_4_7_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_8', 'baselines/step_4_8_before.png', 'baselines/step_4_8_intent.png', 'baselines/step_4_8_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Series # Column").get_by_label("Press SPACE to toggle"), 'check', '4_9', 'baselines/step_4_9_before.png', 'baselines/step_4_9_intent.png', 'baselines/step_4_9_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Season Type Column").get_by_label("Press SPACE to toggle"), 'check', '4_10', 'baselines/step_4_10_before.png', 'baselines/step_4_10_intent.png', 'baselines/step_4_10_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_11', 'baselines/step_4_11_before.png', 'baselines/step_4_11_intent.png', 'baselines/step_4_11_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '4_12', 'baselines/step_4_12_before.png', 'baselines/step_4_12_intent.png', 'baselines/step_4_12_after.png', "On Season")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_13', 'baselines/step_4_13_before.png', 'baselines/step_4_13_intent.png', 'baselines/step_4_13_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_14', 'baselines/step_4_14_before.png', 'baselines/step_4_14_intent.png', 'baselines/step_4_14_after.png')

    safe_action(page, page.locator("#ag-3446-input"), 'fill', '4_15', 'baselines/step_4_15_before.png', 'baselines/step_4_15_intent.png', 'baselines/step_4_15_after.png', "Regular")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_16', 'baselines/step_4_16_before.png', 'baselines/step_4_16_intent.png', 'baselines/step_4_16_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_17', 'baselines/step_4_17_before.png', 'baselines/step_4_17_intent.png', 'baselines/step_4_17_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_18', 'baselines/step_4_18_before.png', 'baselines/step_4_18_intent.png', 'baselines/step_4_18_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Result Column").get_by_label("Press SPACE to toggle"), 'check', '4_19', 'baselines/step_4_19_before.png', 'baselines/step_4_19_intent.png', 'baselines/step_4_19_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_20', 'baselines/step_4_20_before.png', 'baselines/step_4_20_intent.png', 'baselines/step_4_20_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '4_21', 'baselines/step_4_21_before.png', 'baselines/step_4_21_intent.png', 'baselines/step_4_21_after.png', "Win")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_22', 'baselines/step_4_22_before.png', 'baselines/step_4_22_intent.png', 'baselines/step_4_22_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_23', 'baselines/step_4_23_before.png', 'baselines/step_4_23_intent.png', 'baselines/step_4_23_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_24', 'baselines/step_4_24_before.png', 'baselines/step_4_24_intent.png', 'baselines/step_4_24_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Result Column").get_by_label("Press SPACE to toggle"), 'uncheck', '4_25', 'baselines/step_4_25_before.png', 'baselines/step_4_25_intent.png', 'baselines/step_4_25_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Date Column", exact=True).get_by_label("Press SPACE to toggle"), 'check', '4_26', 'baselines/step_4_26_before.png', 'baselines/step_4_26_intent.png', 'baselines/step_4_26_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Date Column", exact=True).get_by_label("Press SPACE to toggle"), 'uncheck', '4_27', 'baselines/step_4_27_before.png', 'baselines/step_4_27_intent.png', 'baselines/step_4_27_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Game/Non-Game Day Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '4_28', 'baselines/step_4_28_before.png', 'baselines/step_4_28_intent.png', 'baselines/step_4_28_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_29', 'baselines/step_4_29_before.png', 'baselines/step_4_29_intent.png', 'baselines/step_4_29_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '4_30', 'baselines/step_4_30_before.png', 'baselines/step_4_30_intent.png', 'baselines/step_4_30_after.png', "Game Day")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_31', 'baselines/step_4_31_before.png', 'baselines/step_4_31_intent.png', 'baselines/step_4_31_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_32', 'baselines/step_4_32_before.png', 'baselines/step_4_32_intent.png', 'baselines/step_4_32_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_33', 'baselines/step_4_33_before.png', 'baselines/step_4_33_intent.png', 'baselines/step_4_33_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Game/Non-Game Day Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_34', 'baselines/step_4_34_before.png', 'baselines/step_4_34_intent.png', 'baselines/step_4_34_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Month Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '4_35', 'baselines/step_4_35_before.png', 'baselines/step_4_35_intent.png', 'baselines/step_4_35_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_36', 'baselines/step_4_36_before.png', 'baselines/step_4_36_intent.png', 'baselines/step_4_36_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '4_37', 'baselines/step_4_37_before.png', 'baselines/step_4_37_intent.png', 'baselines/step_4_37_after.png', "March")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_38', 'baselines/step_4_38_before.png', 'baselines/step_4_38_intent.png', 'baselines/step_4_38_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_39', 'baselines/step_4_39_before.png', 'baselines/step_4_39_intent.png', 'baselines/step_4_39_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_40', 'baselines/step_4_40_before.png', 'baselines/step_4_40_intent.png', 'baselines/step_4_40_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Month Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_41', 'baselines/step_4_41_before.png', 'baselines/step_4_41_intent.png', 'baselines/step_4_41_after.png')

    safe_action(page, page.get_by_role("treeitem", name="DoW Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '4_42', 'baselines/step_4_42_before.png', 'baselines/step_4_42_intent.png', 'baselines/step_4_42_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_43', 'baselines/step_4_43_before.png', 'baselines/step_4_43_intent.png', 'baselines/step_4_43_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '4_44', 'baselines/step_4_44_before.png', 'baselines/step_4_44_intent.png', 'baselines/step_4_44_after.png', "Monday")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_45', 'baselines/step_4_45_before.png', 'baselines/step_4_45_intent.png', 'baselines/step_4_45_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_46', 'baselines/step_4_46_before.png', 'baselines/step_4_46_intent.png', 'baselines/step_4_46_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_47', 'baselines/step_4_47_before.png', 'baselines/step_4_47_intent.png', 'baselines/step_4_47_after.png')

    safe_action(page, page.get_by_role("treeitem", name="DoW Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_48', 'baselines/step_4_48_before.png', 'baselines/step_4_48_intent.png', 'baselines/step_4_48_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Opp Column", exact=True).get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '4_49', 'baselines/step_4_49_before.png', 'baselines/step_4_49_intent.png', 'baselines/step_4_49_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Opp Column", exact=True).get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_50', 'baselines/step_4_50_before.png', 'baselines/step_4_50_intent.png', 'baselines/step_4_50_after.png')

    safe_action(page, page.locator("#ag-3569-input"), 'check', '4_51', 'baselines/step_4_51_before.png', 'baselines/step_4_51_intent.png', 'baselines/step_4_51_after.png')

    safe_action(page, page.locator("#ag-3569-input"), 'uncheck', '4_52', 'baselines/step_4_52_before.png', 'baselines/step_4_52_intent.png', 'baselines/step_4_52_after.png')

    safe_action(page, page.locator("#ag-3571-input"), 'check', '4_53', 'baselines/step_4_53_before.png', 'baselines/step_4_53_intent.png', 'baselines/step_4_53_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_54', 'baselines/step_4_54_before.png', 'baselines/step_4_54_intent.png', 'baselines/step_4_54_after.png')

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down"), 'click', '4_55', 'baselines/step_4_55_before.png', 'baselines/step_4_55_intent.png', 'baselines/step_4_55_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '4_56', 'baselines/step_4_56_before.png', 'baselines/step_4_56_intent.png', 'baselines/step_4_56_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', '4_57', 'baselines/step_4_57_before.png', 'baselines/step_4_57_intent.png', 'baselines/step_4_57_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_58', 'baselines/step_4_58_before.png', 'baselines/step_4_58_intent.png', 'baselines/step_4_58_after.png', "25")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_59', 'baselines/step_4_59_before.png', 'baselines/step_4_59_intent.png', 'baselines/step_4_59_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_60', 'baselines/step_4_60_before.png', 'baselines/step_4_60_intent.png', 'baselines/step_4_60_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_61', 'baselines/step_4_61_before.png', 'baselines/step_4_61_intent.png', 'baselines/step_4_61_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Stat Unit Sales Fcst Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '4_62', 'baselines/step_4_62_before.png', 'baselines/step_4_62_intent.png', 'baselines/step_4_62_after.png')

    safe_action(page, page.locator("#ag-3573-input"), 'check', '4_63', 'baselines/step_4_63_before.png', 'baselines/step_4_63_intent.png', 'baselines/step_4_63_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_64', 'baselines/step_4_64_before.png', 'baselines/step_4_64_intent.png', 'baselines/step_4_64_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_65', 'baselines/step_4_65_before.png', 'baselines/step_4_65_intent.png', 'baselines/step_4_65_after.png', "100")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '4_66', 'baselines/step_4_66_before.png', 'baselines/step_4_66_intent.png', 'baselines/step_4_66_after.png')

    safe_action(page, page.get_by_role("option", name="Less than or equal to"), 'click', '4_67', 'baselines/step_4_67_before.png', 'baselines/step_4_67_intent.png', 'baselines/step_4_67_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_68', 'baselines/step_4_68_before.png', 'baselines/step_4_68_intent.png', 'baselines/step_4_68_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_69', 'baselines/step_4_69_before.png', 'baselines/step_4_69_intent.png', 'baselines/step_4_69_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_70', 'baselines/step_4_70_before.png', 'baselines/step_4_70_intent.png', 'baselines/step_4_70_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '4_71', 'baselines/step_4_71_before.png', 'baselines/step_4_71_intent.png', 'baselines/step_4_71_after.png')

    safe_action(page, page.locator("#ag-3575-input"), 'check', '4_72', 'baselines/step_4_72_before.png', 'baselines/step_4_72_intent.png', 'baselines/step_4_72_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_73', 'baselines/step_4_73_before.png', 'baselines/step_4_73_intent.png', 'baselines/step_4_73_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_74', 'baselines/step_4_74_before.png', 'baselines/step_4_74_intent.png', 'baselines/step_4_74_after.png', "1")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '4_75', 'baselines/step_4_75_before.png', 'baselines/step_4_75_intent.png', 'baselines/step_4_75_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '4_76', 'baselines/step_4_76_before.png', 'baselines/step_4_76_intent.png', 'baselines/step_4_76_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_77', 'baselines/step_4_77_before.png', 'baselines/step_4_77_intent.png', 'baselines/step_4_77_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_78', 'baselines/step_4_78_before.png', 'baselines/step_4_78_intent.png', 'baselines/step_4_78_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_79', 'baselines/step_4_79_before.png', 'baselines/step_4_79_intent.png', 'baselines/step_4_79_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '4_80', 'baselines/step_4_80_before.png', 'baselines/step_4_80_intent.png', 'baselines/step_4_80_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Initial Per Cap Stat Fcst").get_by_label("Press SPACE to toggle"), 'check', '4_81', 'baselines/step_4_81_before.png', 'baselines/step_4_81_intent.png', 'baselines/step_4_81_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_82', 'baselines/step_4_82_before.png', 'baselines/step_4_82_intent.png', 'baselines/step_4_82_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_83', 'baselines/step_4_83_before.png', 'baselines/step_4_83_intent.png', 'baselines/step_4_83_after.png', "10")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '4_84', 'baselines/step_4_84_before.png', 'baselines/step_4_84_intent.png', 'baselines/step_4_84_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '4_85', 'baselines/step_4_85_before.png', 'baselines/step_4_85_intent.png', 'baselines/step_4_85_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_86', 'baselines/step_4_86_before.png', 'baselines/step_4_86_intent.png', 'baselines/step_4_86_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_87', 'baselines/step_4_87_before.png', 'baselines/step_4_87_intent.png', 'baselines/step_4_87_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_88', 'baselines/step_4_88_before.png', 'baselines/step_4_88_intent.png', 'baselines/step_4_88_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '4_89', 'baselines/step_4_89_before.png', 'baselines/step_4_89_intent.png', 'baselines/step_4_89_after.png')

    safe_action(page, page.get_by_role("treeitem", name="GD Sales Fcst Override ($) Column", exact=True).get_by_label("Press SPACE to toggle"), 'check', '4_90', 'baselines/step_4_90_before.png', 'baselines/step_4_90_intent.png', 'baselines/step_4_90_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '4_91', 'baselines/step_4_91_before.png', 'baselines/step_4_91_intent.png', 'baselines/step_4_91_after.png')

    safe_action(page, page.locator("#ag-7836-input"), 'check', '4_92', 'baselines/step_4_92_before.png', 'baselines/step_4_92_intent.png', 'baselines/step_4_92_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '4_93', 'baselines/step_4_93_before.png', 'baselines/step_4_93_intent.png', 'baselines/step_4_93_after.png')

    safe_action(page, page.locator("#ag-7838-input"), 'check', '4_94', 'baselines/step_4_94_before.png', 'baselines/step_4_94_intent.png', 'baselines/step_4_94_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_95', 'baselines/step_4_95_before.png', 'baselines/step_4_95_intent.png', 'baselines/step_4_95_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_96', 'baselines/step_4_96_before.png', 'baselines/step_4_96_intent.png', 'baselines/step_4_96_after.png', "20")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '4_97', 'baselines/step_4_97_before.png', 'baselines/step_4_97_intent.png', 'baselines/step_4_97_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '4_98', 'baselines/step_4_98_before.png', 'baselines/step_4_98_intent.png', 'baselines/step_4_98_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_99', 'baselines/step_4_99_before.png', 'baselines/step_4_99_intent.png', 'baselines/step_4_99_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_100', 'baselines/step_4_100_before.png', 'baselines/step_4_100_intent.png', 'baselines/step_4_100_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_101', 'baselines/step_4_101_before.png', 'baselines/step_4_101_intent.png', 'baselines/step_4_101_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Season Type Column").get_by_label("Press SPACE to toggle"), 'uncheck', '4_102', 'baselines/step_4_102_before.png', 'baselines/step_4_102_intent.png', 'baselines/step_4_102_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '4_103', 'baselines/step_4_103_before.png', 'baselines/step_4_103_intent.png', 'baselines/step_4_103_after.png')

    safe_action(page, page.get_by_text("Daily Forecast by Event columns (0) TopBottom"), 'click', '4_104', 'baselines/step_4_104_before.png', 'baselines/step_4_104_intent.png', 'baselines/step_4_104_after.png')

    safe_action(page, page.locator("esp-card-component").filter(has_text="Daily Forecast by Event").get_by_role("button"), 'click', '4_105', 'baselines/step_4_105_before.png', 'baselines/step_4_105_intent.png', 'baselines/step_4_105_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_106', 'baselines/step_4_106_before.png', 'baselines/step_4_106_intent.png', 'baselines/step_4_106_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_107', 'baselines/step_4_107_before.png', 'baselines/step_4_107_intent.png', 'baselines/step_4_107_after.png', "2000")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '4_108', 'baselines/step_4_108_before.png', 'baselines/step_4_108_intent.png', 'baselines/step_4_108_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '4_109', 'baselines/step_4_109_before.png', 'baselines/step_4_109_intent.png', 'baselines/step_4_109_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_110', 'baselines/step_4_110_before.png', 'baselines/step_4_110_intent.png', 'baselines/step_4_110_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_111', 'baselines/step_4_111_before.png', 'baselines/step_4_111_intent.png', 'baselines/step_4_111_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_112', 'baselines/step_4_112_before.png', 'baselines/step_4_112_intent.png', 'baselines/step_4_112_after.png')

    safe_action(page, page.locator("div:nth-child(4) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', '4_113', 'baselines/step_4_113_before.png', 'baselines/step_4_113_intent.png', 'baselines/step_4_113_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '4_114', 'baselines/step_4_114_before.png', 'baselines/step_4_114_intent.png', 'baselines/step_4_114_after.png')

    with safe_download(page) as download1_info:

        safe_action(page, page.locator("div:nth-child(3) > #export-iconId > .icon-color-toolbar-active"), 'click', '4_115', 'baselines/step_4_115_before.png', 'baselines/step_4_115_intent.png', 'baselines/step_4_115_after.png')

    download1 = download1_info.value

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_116', 'baselines/step_4_116_before.png', 'baselines/step_4_116_intent.png', 'baselines/step_4_116_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^View 10 row\(s\)$")).nth(1), 'click', '4_117', 'baselines/step_4_117_before.png', 'baselines/step_4_117_intent.png', 'baselines/step_4_117_after.png')

    safe_action(page, page.locator("a").filter(has_text=re.compile(r"^2$")), 'click', '4_118', 'baselines/step_4_118_before.png', 'baselines/step_4_118_intent.png', 'baselines/step_4_118_after.png')

    safe_action(page, page.get_by_role("gridcell", name="D.C. UNITED").first, 'click', '4_119', 'baselines/step_4_119_before.png', 'baselines/step_4_119_intent.png', 'baselines/step_4_119_after.png', button="right")

    safe_action(page, page.get_by_label("Context Menu").get_by_text("Dept Penetration Pivots"), 'click', '4_120', 'baselines/step_4_120_before.png', 'baselines/step_4_120_intent.png', 'baselines/step_4_120_after.png')


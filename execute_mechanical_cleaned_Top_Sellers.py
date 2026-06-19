import re
TARGET_YAML_FILE = "Top_Sellers.yaml"

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
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=5", timeout=0)
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

    safe_action(page, page.locator("#SideFilterproducthierarchyId").get_by_text("League"), 'click', '1_3', 'baselines/step_1_3_before.png', 'baselines/step_1_3_intent.png', 'baselines/step_1_3_after.png')

    safe_action(page, page.get_by_role("radio", name="MLS"), 'check', '1_4', 'baselines/step_1_4_before.png', 'baselines/step_1_4_intent.png', 'baselines/step_1_4_after.png')

    safe_action(page, page.locator("#SideFilterproducthierarchyId").get_by_text("Team"), 'click', '1_5', 'baselines/step_1_5_before.png', 'baselines/step_1_5_intent.png', 'baselines/step_1_5_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first, 'click', '1_6', 'baselines/step_1_6_before.png', 'baselines/step_1_6_intent.png', 'baselines/step_1_6_after.png')

    safe_action(page, page.locator("#SideFilterproducthierarchyId").get_by_text("Team", exact=True), 'click', '1_7', 'baselines/step_1_7_before.png', 'baselines/step_1_7_intent.png', 'baselines/step_1_7_after.png')

    safe_action(page, page.get_by_text("Department"), 'click', '1_8', 'baselines/step_1_8_before.png', 'baselines/step_1_8_intent.png', 'baselines/step_1_8_after.png')

    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '1_9', 'baselines/step_1_9_before.png', 'baselines/step_1_9_intent.png', 'baselines/step_1_9_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '1_10', 'baselines/step_1_10_before.png', 'baselines/step_1_10_intent.png', 'baselines/step_1_10_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '1_11', 'baselines/step_1_11_before.png', 'baselines/step_1_11_intent.png', 'baselines/step_1_11_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '1_12', 'baselines/step_1_12_before.png', 'baselines/step_1_12_intent.png', 'baselines/step_1_12_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '1_13', 'baselines/step_1_13_before.png', 'baselines/step_1_13_intent.png', 'baselines/step_1_13_after.png')

    safe_action(page, page.get_by_text("Attribute"), 'click', '1_14', 'baselines/step_1_14_before.png', 'baselines/step_1_14_intent.png', 'baselines/step_1_14_after.png')

    safe_action(page, page.locator("#SideFilterproductattributeId").get_by_text("Product Line"), 'click', '1_15', 'baselines/step_1_15_before.png', 'baselines/step_1_15_intent.png', 'baselines/step_1_15_after.png')

    safe_action(page, page.get_by_text("Player"), 'click', '1_16', 'baselines/step_1_16_before.png', 'baselines/step_1_16_intent.png', 'baselines/step_1_16_after.png')

    safe_action(page, page.locator(".aggrigate-panel > .custom-checkbox-wrapper > .pointer"), 'click', '1_17', 'baselines/step_1_17_before.png', 'baselines/step_1_17_intent.png', 'baselines/step_1_17_after.png')

    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '1_18', 'baselines/step_1_18_before.png', 'baselines/step_1_18_intent.png', 'baselines/step_1_18_after.png')

    safe_action(page, page.locator(".zeb-filter").first, 'click', '1_19', 'baselines/step_1_19_before.png', 'baselines/step_1_19_intent.png', 'baselines/step_1_19_after.png')



    # ============================================================
    # SECTION: Top Seller Filters and Dropdowns
    # ============================================================


    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '2_1', 'baselines/step_2_1_before.png', 'baselines/step_2_1_intent.png', 'baselines/step_2_1_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '2_2', 'baselines/step_2_2_before.png', 'baselines/step_2_2_intent.png', 'baselines/step_2_2_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '2_3', 'baselines/step_2_3_before.png', 'baselines/step_2_3_intent.png', 'baselines/step_2_3_after.png')

    safe_action(page, page.locator("#location-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_4', 'baselines/step_2_4_before.png', 'baselines/step_2_4_intent.png', 'baselines/step_2_4_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_5', 'baselines/step_2_5_before.png', 'baselines/step_2_5_intent.png', 'baselines/step_2_5_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '2_6', 'baselines/step_2_6_before.png', 'baselines/step_2_6_intent.png', 'baselines/step_2_6_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '2_7', 'baselines/step_2_7_before.png', 'baselines/step_2_7_intent.png', 'baselines/step_2_7_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_8', 'baselines/step_2_8_before.png', 'baselines/step_2_8_intent.png', 'baselines/step_2_8_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '2_9', 'baselines/step_2_9_before.png', 'baselines/step_2_9_intent.png', 'baselines/step_2_9_after.png')

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_10', 'baselines/step_2_10_before.png', 'baselines/step_2_10_intent.png', 'baselines/step_2_10_after.png')

    safe_action(page, page.get_by_text("View 10 row(s)"), 'click', '2_11', 'baselines/step_2_11_before.png', 'baselines/step_2_11_intent.png', 'baselines/step_2_11_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '2_12', 'baselines/step_2_12_before.png', 'baselines/step_2_12_intent.png', 'baselines/step_2_12_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '2_13', 'baselines/step_2_13_before.png', 'baselines/step_2_13_intent.png', 'baselines/step_2_13_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '2_14', 'baselines/step_2_14_before.png', 'baselines/step_2_14_intent.png', 'baselines/step_2_14_after.png')

    safe_action(page, page.get_by_role("treeitem", name="League Column").get_by_label("Press SPACE to toggle"), 'check', '2_15', 'baselines/step_2_15_before.png', 'baselines/step_2_15_intent.png', 'baselines/step_2_15_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Department Column").get_by_label("Press SPACE to toggle"), 'check', '2_16', 'baselines/step_2_16_before.png', 'baselines/step_2_16_intent.png', 'baselines/step_2_16_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '2_17', 'baselines/step_2_17_before.png', 'baselines/step_2_17_intent.png', 'baselines/step_2_17_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '2_18', 'baselines/step_2_18_before.png', 'baselines/step_2_18_intent.png', 'baselines/step_2_18_after.png', "MENS")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_19', 'baselines/step_2_19_before.png', 'baselines/step_2_19_intent.png', 'baselines/step_2_19_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '2_20', 'baselines/step_2_20_before.png', 'baselines/step_2_20_intent.png', 'baselines/step_2_20_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_21', 'baselines/step_2_21_before.png', 'baselines/step_2_21_intent.png', 'baselines/step_2_21_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Department Column").get_by_label("Press SPACE to toggle"), 'uncheck', '2_22', 'baselines/step_2_22_before.png', 'baselines/step_2_22_intent.png', 'baselines/step_2_22_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Class Column").get_by_label("Press SPACE to toggle"), 'check', '2_23', 'baselines/step_2_23_before.png', 'baselines/step_2_23_intent.png', 'baselines/step_2_23_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '2_24', 'baselines/step_2_24_before.png', 'baselines/step_2_24_intent.png', 'baselines/step_2_24_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'press', '2_25', 'baselines/step_2_25_before.png', 'baselines/step_2_25_intent.png', 'baselines/step_2_25_after.png', "CapsLock")

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'press', '2_26', 'baselines/step_2_26_before.png', 'baselines/step_2_26_intent.png', 'baselines/step_2_26_after.png', "CapsLock")

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '2_27', 'baselines/step_2_27_before.png', 'baselines/step_2_27_intent.png', 'baselines/step_2_27_after.png', "SS TEES")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_28', 'baselines/step_2_28_before.png', 'baselines/step_2_28_intent.png', 'baselines/step_2_28_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '2_29', 'baselines/step_2_29_before.png', 'baselines/step_2_29_intent.png', 'baselines/step_2_29_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_30', 'baselines/step_2_30_before.png', 'baselines/step_2_30_intent.png', 'baselines/step_2_30_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Product Line Column").get_by_label("Press SPACE to toggle"), 'check', '2_31', 'baselines/step_2_31_before.png', 'baselines/step_2_31_intent.png', 'baselines/step_2_31_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_32', 'baselines/step_2_32_before.png', 'baselines/step_2_32_intent.png', 'baselines/step_2_32_after.png')

    safe_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', '2_33', 'baselines/step_2_33_before.png', 'baselines/step_2_33_intent.png', 'baselines/step_2_33_after.png', "CORE")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_34', 'baselines/step_2_34_before.png', 'baselines/step_2_34_intent.png', 'baselines/step_2_34_after.png')

    safe_action(page, page.get_by_role("option", name="Does not contain"), 'click', '2_35', 'baselines/step_2_35_before.png', 'baselines/step_2_35_intent.png', 'baselines/step_2_35_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_36', 'baselines/step_2_36_before.png', 'baselines/step_2_36_intent.png', 'baselines/step_2_36_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_37', 'baselines/step_2_37_before.png', 'baselines/step_2_37_intent.png', 'baselines/step_2_37_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_38', 'baselines/step_2_38_before.png', 'baselines/step_2_38_intent.png', 'baselines/step_2_38_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Product Line Column").get_by_label("Press SPACE to toggle"), 'uncheck', '2_39', 'baselines/step_2_39_before.png', 'baselines/step_2_39_intent.png', 'baselines/step_2_39_after.png')

    safe_action(page, page.get_by_role("treeitem", name="PID Column").get_by_label("Press SPACE to toggle"), 'check', '2_40', 'baselines/step_2_40_before.png', 'baselines/step_2_40_intent.png', 'baselines/step_2_40_after.png')

    safe_action(page, page.get_by_role("treeitem", name="PID Column").get_by_label("Press SPACE to toggle"), 'uncheck', '2_41', 'baselines/step_2_41_before.png', 'baselines/step_2_41_intent.png', 'baselines/step_2_41_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LW Retail Sales Column", exact=True).get_by_label("Press SPACE to toggle"), 'check', '2_42', 'baselines/step_2_42_before.png', 'baselines/step_2_42_intent.png', 'baselines/step_2_42_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LW Retail Sales Column", exact=True).get_by_label("Press SPACE to toggle"), 'uncheck', '2_43', 'baselines/step_2_43_before.png', 'baselines/step_2_43_intent.png', 'baselines/step_2_43_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY LW Retail Sales Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '2_44', 'baselines/step_2_44_before.png', 'baselines/step_2_44_intent.png', 'baselines/step_2_44_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_45', 'baselines/step_2_45_before.png', 'baselines/step_2_45_intent.png', 'baselines/step_2_45_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_46', 'baselines/step_2_46_before.png', 'baselines/step_2_46_intent.png', 'baselines/step_2_46_after.png', "10")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_47', 'baselines/step_2_47_before.png', 'baselines/step_2_47_intent.png', 'baselines/step_2_47_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '2_48', 'baselines/step_2_48_before.png', 'baselines/step_2_48_intent.png', 'baselines/step_2_48_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_49', 'baselines/step_2_49_before.png', 'baselines/step_2_49_intent.png', 'baselines/step_2_49_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_50', 'baselines/step_2_50_before.png', 'baselines/step_2_50_intent.png', 'baselines/step_2_50_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_51', 'baselines/step_2_51_before.png', 'baselines/step_2_51_intent.png', 'baselines/step_2_51_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY LW Retail Sales Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', '2_52', 'baselines/step_2_52_before.png', 'baselines/step_2_52_intent.png', 'baselines/step_2_52_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY to TY LW Retail % Var").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', '2_53', 'baselines/step_2_53_before.png', 'baselines/step_2_53_intent.png', 'baselines/step_2_53_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY to TY LW Retail % Var").get_by_label("Press SPACE to toggle visibility (hidden)"), 'uncheck', '2_54', 'baselines/step_2_54_before.png', 'baselines/step_2_54_intent.png', 'baselines/step_2_54_after.png')

    safe_action(page, page.locator("#ag-937-input"), 'check', '2_55', 'baselines/step_2_55_before.png', 'baselines/step_2_55_intent.png', 'baselines/step_2_55_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_56', 'baselines/step_2_56_before.png', 'baselines/step_2_56_intent.png', 'baselines/step_2_56_after.png')

    safe_action(page, page.get_by_role("treeitem", name="L2W Unit Sales Column", exact=True).get_by_label("Press SPACE to toggle"), 'check', '2_57', 'baselines/step_2_57_before.png', 'baselines/step_2_57_intent.png', 'baselines/step_2_57_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_58', 'baselines/step_2_58_before.png', 'baselines/step_2_58_intent.png', 'baselines/step_2_58_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY L2W Unit Sales Column").get_by_label("Press SPACE to toggle"), 'check', '2_59', 'baselines/step_2_59_before.png', 'baselines/step_2_59_intent.png', 'baselines/step_2_59_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY L2W Unit Sales Column").get_by_label("Press SPACE to toggle"), 'uncheck', '2_60', 'baselines/step_2_60_before.png', 'baselines/step_2_60_intent.png', 'baselines/step_2_60_after.png')

    safe_action(page, page.get_by_role("treeitem", name="LY L4W Unit Sales Column"), 'click', '2_61', 'baselines/step_2_61_before.png', 'baselines/step_2_61_intent.png', 'baselines/step_2_61_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_62', 'baselines/step_2_62_before.png', 'baselines/step_2_62_intent.png', 'baselines/step_2_62_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_63', 'baselines/step_2_63_before.png', 'baselines/step_2_63_intent.png', 'baselines/step_2_63_after.png', "20")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_64', 'baselines/step_2_64_before.png', 'baselines/step_2_64_intent.png', 'baselines/step_2_64_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '2_65', 'baselines/step_2_65_before.png', 'baselines/step_2_65_intent.png', 'baselines/step_2_65_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_66', 'baselines/step_2_66_before.png', 'baselines/step_2_66_intent.png', 'baselines/step_2_66_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_67', 'baselines/step_2_67_before.png', 'baselines/step_2_67_intent.png', 'baselines/step_2_67_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_68', 'baselines/step_2_68_before.png', 'baselines/step_2_68_intent.png', 'baselines/step_2_68_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_69', 'baselines/step_2_69_before.png', 'baselines/step_2_69_intent.png', 'baselines/step_2_69_after.png')

    safe_action(page, page.locator("#ag-955-input"), 'check', '2_70', 'baselines/step_2_70_before.png', 'baselines/step_2_70_intent.png', 'baselines/step_2_70_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_71', 'baselines/step_2_71_before.png', 'baselines/step_2_71_intent.png', 'baselines/step_2_71_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_72', 'baselines/step_2_72_before.png', 'baselines/step_2_72_intent.png', 'baselines/step_2_72_after.png', "200")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_73', 'baselines/step_2_73_before.png', 'baselines/step_2_73_intent.png', 'baselines/step_2_73_after.png')

    safe_action(page, page.get_by_role("option", name="Less than or equal to"), 'click', '2_74', 'baselines/step_2_74_before.png', 'baselines/step_2_74_intent.png', 'baselines/step_2_74_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_75', 'baselines/step_2_75_before.png', 'baselines/step_2_75_intent.png', 'baselines/step_2_75_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_76', 'baselines/step_2_76_before.png', 'baselines/step_2_76_intent.png', 'baselines/step_2_76_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_77', 'baselines/step_2_77_before.png', 'baselines/step_2_77_intent.png', 'baselines/step_2_77_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_78', 'baselines/step_2_78_before.png', 'baselines/step_2_78_intent.png', 'baselines/step_2_78_after.png')

    safe_action(page, page.get_by_role("treeitem", name="+ PIDS Column"), 'click', '2_79', 'baselines/step_2_79_before.png', 'baselines/step_2_79_intent.png', 'baselines/step_2_79_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_80', 'baselines/step_2_80_before.png', 'baselines/step_2_80_intent.png', 'baselines/step_2_80_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_81', 'baselines/step_2_81_before.png', 'baselines/step_2_81_intent.png', 'baselines/step_2_81_after.png', "1")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_82', 'baselines/step_2_82_before.png', 'baselines/step_2_82_intent.png', 'baselines/step_2_82_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_83', 'baselines/step_2_83_before.png', 'baselines/step_2_83_intent.png', 'baselines/step_2_83_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_84', 'baselines/step_2_84_before.png', 'baselines/step_2_84_intent.png', 'baselines/step_2_84_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_85', 'baselines/step_2_85_before.png', 'baselines/step_2_85_intent.png', 'baselines/step_2_85_after.png')

    safe_action(page, page.locator("#ag-1794-input"), 'check', '2_86', 'baselines/step_2_86_before.png', 'baselines/step_2_86_intent.png', 'baselines/step_2_86_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_87', 'baselines/step_2_87_before.png', 'baselines/step_2_87_intent.png', 'baselines/step_2_87_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_88', 'baselines/step_2_88_before.png', 'baselines/step_2_88_intent.png', 'baselines/step_2_88_after.png', "0")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_89', 'baselines/step_2_89_before.png', 'baselines/step_2_89_intent.png', 'baselines/step_2_89_after.png')

    safe_action(page, page.get_by_role("option", name="Does not equal"), 'click', '2_90', 'baselines/step_2_90_before.png', 'baselines/step_2_90_intent.png', 'baselines/step_2_90_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_91', 'baselines/step_2_91_before.png', 'baselines/step_2_91_intent.png', 'baselines/step_2_91_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_92', 'baselines/step_2_92_before.png', 'baselines/step_2_92_intent.png', 'baselines/step_2_92_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_93', 'baselines/step_2_93_before.png', 'baselines/step_2_93_intent.png', 'baselines/step_2_93_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_94', 'baselines/step_2_94_before.png', 'baselines/step_2_94_intent.png', 'baselines/step_2_94_after.png')

    safe_action(page, page.locator("#ag-2449-input"), 'check', '2_95', 'baselines/step_2_95_before.png', 'baselines/step_2_95_intent.png', 'baselines/step_2_95_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_96', 'baselines/step_2_96_before.png', 'baselines/step_2_96_intent.png', 'baselines/step_2_96_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_97', 'baselines/step_2_97_before.png', 'baselines/step_2_97_intent.png', 'baselines/step_2_97_after.png', "100")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_98', 'baselines/step_2_98_before.png', 'baselines/step_2_98_intent.png', 'baselines/step_2_98_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '2_99', 'baselines/step_2_99_before.png', 'baselines/step_2_99_intent.png', 'baselines/step_2_99_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_100', 'baselines/step_2_100_before.png', 'baselines/step_2_100_intent.png', 'baselines/step_2_100_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_101', 'baselines/step_2_101_before.png', 'baselines/step_2_101_intent.png', 'baselines/step_2_101_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_102', 'baselines/step_2_102_before.png', 'baselines/step_2_102_intent.png', 'baselines/step_2_102_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Press SPACE to toggle visibility (visible)"), 'uncheck', '2_103', 'baselines/step_2_103_before.png', 'baselines/step_2_103_intent.png', 'baselines/step_2_103_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Over/Under Column"), 'click', '2_104', 'baselines/step_2_104_before.png', 'baselines/step_2_104_intent.png', 'baselines/step_2_104_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_105', 'baselines/step_2_105_before.png', 'baselines/step_2_105_intent.png', 'baselines/step_2_105_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '2_106', 'baselines/step_2_106_before.png', 'baselines/step_2_106_intent.png', 'baselines/step_2_106_after.png', "75")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '2_107', 'baselines/step_2_107_before.png', 'baselines/step_2_107_intent.png', 'baselines/step_2_107_after.png')

    safe_action(page, page.get_by_role("option", name="Does not equal"), 'click', '2_108', 'baselines/step_2_108_before.png', 'baselines/step_2_108_intent.png', 'baselines/step_2_108_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '2_109', 'baselines/step_2_109_before.png', 'baselines/step_2_109_intent.png', 'baselines/step_2_109_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '2_110', 'baselines/step_2_110_before.png', 'baselines/step_2_110_intent.png', 'baselines/step_2_110_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '2_111', 'baselines/step_2_111_before.png', 'baselines/step_2_111_intent.png', 'baselines/step_2_111_after.png')

    safe_action(page, page.get_by_role("treeitem", name="In Stock % Column"), 'click', '2_112', 'baselines/step_2_112_before.png', 'baselines/step_2_112_intent.png', 'baselines/step_2_112_after.png')

    safe_action(page, page.get_by_role("treeitem", name="In Stock Weighted % Column"), 'click', '2_113', 'baselines/step_2_113_before.png', 'baselines/step_2_113_intent.png', 'baselines/step_2_113_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '2_114', 'baselines/step_2_114_before.png', 'baselines/step_2_114_intent.png', 'baselines/step_2_114_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '2_115', 'baselines/step_2_115_before.png', 'baselines/step_2_115_intent.png', 'baselines/step_2_115_after.png')

    safe_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', '2_116', 'baselines/step_2_116_before.png', 'baselines/step_2_116_intent.png', 'baselines/step_2_116_after.png')

    safe_action(page, page.locator("div").filter(has_text="Loading...").nth(5), 'click', '2_117', 'baselines/step_2_117_before.png', 'baselines/step_2_117_intent.png', 'baselines/step_2_117_after.png')

    safe_action(page, page.locator("a").filter(has_text="2"), 'click', '2_118', 'baselines/step_2_118_before.png', 'baselines/step_2_118_intent.png', 'baselines/step_2_118_after.png')

    safe_action(page, page.get_by_role("treegrid").get_by_text("League"), 'click', '2_119', 'baselines/step_2_119_before.png', 'baselines/step_2_119_intent.png', 'baselines/step_2_119_after.png')

    safe_action(page, page.get_by_text("Over/Under"), 'click', '2_120', 'baselines/step_2_120_before.png', 'baselines/step_2_120_intent.png', 'baselines/step_2_120_after.png')

    safe_action(page, page.get_by_text("In Stock %"), 'click', '2_121', 'baselines/step_2_121_before.png', 'baselines/step_2_121_intent.png', 'baselines/step_2_121_after.png')

    safe_action(page, page.get_by_text("Over/Under"), 'click', '2_122', 'baselines/step_2_122_before.png', 'baselines/step_2_122_intent.png', 'baselines/step_2_122_after.png')

    safe_action(page, page.locator("a").filter(has_text="3"), 'click', '2_123', 'baselines/step_2_123_before.png', 'baselines/step_2_123_intent.png', 'baselines/step_2_123_after.png')

    safe_action(page, page.locator("a").filter(has_text="..."), 'click', '2_124', 'baselines/step_2_124_before.png', 'baselines/step_2_124_intent.png', 'baselines/step_2_124_after.png')

    safe_action(page, page.get_by_role("tooltip", name="Go to").get_by_role("textbox"), 'click', '2_125', 'baselines/step_2_125_before.png', 'baselines/step_2_125_intent.png', 'baselines/step_2_125_after.png')

    safe_action(page, page.get_by_role("tooltip", name="Go to").get_by_role("textbox"), 'fill', '2_126', 'baselines/step_2_126_before.png', 'baselines/step_2_126_intent.png', 'baselines/step_2_126_after.png', "100")

    safe_action(page, page.get_by_role("tooltip", name="Go to").get_by_role("textbox"), 'press', '2_127', 'baselines/step_2_127_before.png', 'baselines/step_2_127_intent.png', 'baselines/step_2_127_after.png', "Enter")

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '2_128', 'baselines/step_2_128_before.png', 'baselines/step_2_128_intent.png', 'baselines/step_2_128_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', '2_129', 'baselines/step_2_129_before.png', 'baselines/step_2_129_intent.png', 'baselines/step_2_129_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '2_130', 'baselines/step_2_130_before.png', 'baselines/step_2_130_intent.png', 'baselines/step_2_130_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '2_131', 'baselines/step_2_131_before.png', 'baselines/step_2_131_intent.png', 'baselines/step_2_131_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '2_132', 'baselines/step_2_132_before.png', 'baselines/step_2_132_intent.png', 'baselines/step_2_132_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '2_133', 'baselines/step_2_133_before.png', 'baselines/step_2_133_intent.png', 'baselines/step_2_133_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '2_134', 'baselines/step_2_134_before.png', 'baselines/step_2_134_intent.png', 'baselines/step_2_134_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '2_135', 'baselines/step_2_135_before.png', 'baselines/step_2_135_intent.png', 'baselines/step_2_135_after.png')


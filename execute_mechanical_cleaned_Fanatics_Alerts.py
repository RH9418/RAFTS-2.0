import re
TARGET_YAML_FILE = "Fanatics_Alerts_KB.yaml"

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
    try: page.goto("https://stage.ftics.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=5&tabIndex=1", timeout=30000)
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



    # ============================================================
    # SECTION: Global Filters
    # ============================================================


    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Hierarchy$")).nth(2), 'click', '2_1', 'baselines/step_2_1_before.png', 'baselines/step_2_1_intent.png', 'baselines/step_2_1_after.png')

    safe_action(page, page.get_by_text("League"), 'click', '2_2', 'baselines/step_2_2_before.png', 'baselines/step_2_2_intent.png', 'baselines/step_2_2_after.png')

    safe_action(page, page.get_by_text("League"), 'click', '2_3', 'baselines/step_2_3_before.png', 'baselines/step_2_3_intent.png', 'baselines/step_2_3_after.png')

    safe_action(page, page.get_by_text("Team", exact=True), 'click', '2_4', 'baselines/step_2_4_before.png', 'baselines/step_2_4_intent.png', 'baselines/step_2_4_after.png')

    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '2_5', 'baselines/step_2_5_before.png', 'baselines/step_2_5_intent.png', 'baselines/step_2_5_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_6', 'baselines/step_2_6_before.png', 'baselines/step_2_6_intent.png', 'baselines/step_2_6_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_7', 'baselines/step_2_7_before.png', 'baselines/step_2_7_intent.png', 'baselines/step_2_7_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_8', 'baselines/step_2_8_before.png', 'baselines/step_2_8_intent.png', 'baselines/step_2_8_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_9', 'baselines/step_2_9_before.png', 'baselines/step_2_9_intent.png', 'baselines/step_2_9_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_10', 'baselines/step_2_10_before.png', 'baselines/step_2_10_intent.png', 'baselines/step_2_10_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first, 'click', '2_11', 'baselines/step_2_11_before.png', 'baselines/step_2_11_intent.png', 'baselines/step_2_11_after.png')

    safe_action(page, page.get_by_text("Team", exact=True), 'click', '2_12', 'baselines/step_2_12_before.png', 'baselines/step_2_12_intent.png', 'baselines/step_2_12_after.png')

    safe_action(page, page.get_by_text("Department"), 'click', '2_13', 'baselines/step_2_13_before.png', 'baselines/step_2_13_intent.png', 'baselines/step_2_13_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first, 'click', '2_14', 'baselines/step_2_14_before.png', 'baselines/step_2_14_intent.png', 'baselines/step_2_14_after.png')

    safe_action(page, page.get_by_text("Department"), 'click', '2_15', 'baselines/step_2_15_before.png', 'baselines/step_2_15_intent.png', 'baselines/step_2_15_after.png')

    safe_action(page, page.get_by_text("Class"), 'click', '2_16', 'baselines/step_2_16_before.png', 'baselines/step_2_16_intent.png', 'baselines/step_2_16_after.png')

    safe_action(page, page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first, 'click', '2_17', 'baselines/step_2_17_before.png', 'baselines/step_2_17_intent.png', 'baselines/step_2_17_after.png')

    safe_action(page, page.get_by_text("Class"), 'click', '2_18', 'baselines/step_2_18_before.png', 'baselines/step_2_18_intent.png', 'baselines/step_2_18_after.png')

    safe_action(page, page.get_by_text("Attribute"), 'click', '2_19', 'baselines/step_2_19_before.png', 'baselines/step_2_19_intent.png', 'baselines/step_2_19_after.png')

    safe_action(page, page.get_by_text("Product Line"), 'click', '2_20', 'baselines/step_2_20_before.png', 'baselines/step_2_20_intent.png', 'baselines/step_2_20_after.png')

    safe_action(page, page.get_by_text("Color", exact=True), 'click', '2_21', 'baselines/step_2_21_before.png', 'baselines/step_2_21_intent.png', 'baselines/step_2_21_after.png')

    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '2_22', 'baselines/step_2_22_before.png', 'baselines/step_2_22_intent.png', 'baselines/step_2_22_after.png')

    safe_action(page, page.locator(".pill-nav-btn.pointer"), 'click', '2_23', 'baselines/step_2_23_before.png', 'baselines/step_2_23_intent.png', 'baselines/step_2_23_after.png')

    safe_action(page, page.locator(".zeb-filter").first, 'click', '2_24', 'baselines/step_2_24_before.png', 'baselines/step_2_24_intent.png', 'baselines/step_2_24_after.png')

    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '2_25', 'baselines/step_2_25_before.png', 'baselines/step_2_25_intent.png', 'baselines/step_2_25_after.png')



    # ============================================================
    # SECTION: Alert and Season Types
    # ============================================================


    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '3_1', 'baselines/step_3_1_before.png', 'baselines/step_3_1_intent.png', 'baselines/step_3_1_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^All Alerts$")).nth(1), 'click', '3_2', 'baselines/step_3_2_before.png', 'baselines/step_3_2_intent.png', 'baselines/step_3_2_after.png')

    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '3_3', 'baselines/step_3_3_before.png', 'baselines/step_3_3_intent.png', 'baselines/step_3_3_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Over Stock$")).nth(1), 'click', '3_4', 'baselines/step_3_4_before.png', 'baselines/step_3_4_intent.png', 'baselines/step_3_4_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '3_5', 'baselines/step_3_5_before.png', 'baselines/step_3_5_intent.png', 'baselines/step_3_5_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '3_6', 'baselines/step_3_6_before.png', 'baselines/step_3_6_intent.png', 'baselines/step_3_6_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '3_7', 'baselines/step_3_7_before.png', 'baselines/step_3_7_intent.png', 'baselines/step_3_7_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '3_8', 'baselines/step_3_8_before.png', 'baselines/step_3_8_intent.png', 'baselines/step_3_8_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_9', 'baselines/step_3_9_before.png', 'baselines/step_3_9_intent.png', 'baselines/step_3_9_after.png')

    safe_action(page, page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '3_10', 'baselines/step_3_10_before.png', 'baselines/step_3_10_intent.png', 'baselines/step_3_10_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '3_11', 'baselines/step_3_11_before.png', 'baselines/step_3_11_intent.png', 'baselines/step_3_11_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_12', 'baselines/step_3_12_before.png', 'baselines/step_3_12_intent.png', 'baselines/step_3_12_after.png')

    safe_action(page, page.locator(".dropdown-caret.p-l-16").first, 'click', '3_13', 'baselines/step_3_13_before.png', 'baselines/step_3_13_intent.png', 'baselines/step_3_13_after.png')

    safe_action(page, page.get_by_text("All Alerts"), 'click', '3_14', 'baselines/step_3_14_before.png', 'baselines/step_3_14_intent.png', 'baselines/step_3_14_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_15', 'baselines/step_3_15_before.png', 'baselines/step_3_15_intent.png', 'baselines/step_3_15_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_16', 'baselines/step_3_16_before.png', 'baselines/step_3_16_intent.png', 'baselines/step_3_16_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '3_17', 'baselines/step_3_17_before.png', 'baselines/step_3_17_intent.png', 'baselines/step_3_17_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_18', 'baselines/step_3_18_before.png', 'baselines/step_3_18_intent.png', 'baselines/step_3_18_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_19', 'baselines/step_3_19_before.png', 'baselines/step_3_19_intent.png', 'baselines/step_3_19_after.png')

    safe_action(page, page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle"), 'check', '3_20', 'baselines/step_3_20_before.png', 'baselines/step_3_20_intent.png', 'baselines/step_3_20_after.png')

    safe_action(page, page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle"), 'check', '3_21', 'baselines/step_3_21_before.png', 'baselines/step_3_21_intent.png', 'baselines/step_3_21_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '3_22', 'baselines/step_3_22_before.png', 'baselines/step_3_22_intent.png', 'baselines/step_3_22_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_23', 'baselines/step_3_23_before.png', 'baselines/step_3_23_intent.png', 'baselines/step_3_23_after.png', "5")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_24', 'baselines/step_3_24_before.png', 'baselines/step_3_24_intent.png', 'baselines/step_3_24_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_25', 'baselines/step_3_25_before.png', 'baselines/step_3_25_intent.png', 'baselines/step_3_25_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_26', 'baselines/step_3_26_before.png', 'baselines/step_3_26_intent.png', 'baselines/step_3_26_after.png')

    safe_action(page, page.get_by_title("Filter").nth(2), 'click', '3_27', 'baselines/step_3_27_before.png', 'baselines/step_3_27_intent.png', 'baselines/step_3_27_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_28', 'baselines/step_3_28_before.png', 'baselines/step_3_28_intent.png', 'baselines/step_3_28_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle"), 'check', '3_29', 'baselines/step_3_29_before.png', 'baselines/step_3_29_intent.png', 'baselines/step_3_29_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '3_30', 'baselines/step_3_30_before.png', 'baselines/step_3_30_intent.png', 'baselines/step_3_30_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', '3_31', 'baselines/step_3_31_before.png', 'baselines/step_3_31_intent.png', 'baselines/step_3_31_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_32', 'baselines/step_3_32_before.png', 'baselines/step_3_32_intent.png', 'baselines/step_3_32_after.png', "4")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_33', 'baselines/step_3_33_before.png', 'baselines/step_3_33_intent.png', 'baselines/step_3_33_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_34', 'baselines/step_3_34_before.png', 'baselines/step_3_34_intent.png', 'baselines/step_3_34_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_35', 'baselines/step_3_35_before.png', 'baselines/step_3_35_intent.png', 'baselines/step_3_35_after.png')

    safe_action(page, page.get_by_title("Filter").nth(3), 'click', '3_36', 'baselines/step_3_36_before.png', 'baselines/step_3_36_intent.png', 'baselines/step_3_36_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_37', 'baselines/step_3_37_before.png', 'baselines/step_3_37_intent.png', 'baselines/step_3_37_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle"), 'check', '3_38', 'baselines/step_3_38_before.png', 'baselines/step_3_38_intent.png', 'baselines/step_3_38_after.png')

    safe_action(page, page.get_by_title("Filter").nth(4), 'click', '3_39', 'baselines/step_3_39_before.png', 'baselines/step_3_39_intent.png', 'baselines/step_3_39_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_40', 'baselines/step_3_40_before.png', 'baselines/step_3_40_intent.png', 'baselines/step_3_40_after.png', "50")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_41', 'baselines/step_3_41_before.png', 'baselines/step_3_41_intent.png', 'baselines/step_3_41_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_42', 'baselines/step_3_42_before.png', 'baselines/step_3_42_intent.png', 'baselines/step_3_42_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_43', 'baselines/step_3_43_before.png', 'baselines/step_3_43_intent.png', 'baselines/step_3_43_after.png')

    safe_action(page, page.get_by_title("Filter").nth(4), 'click', '3_44', 'baselines/step_3_44_before.png', 'baselines/step_3_44_intent.png', 'baselines/step_3_44_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_45', 'baselines/step_3_45_before.png', 'baselines/step_3_45_intent.png', 'baselines/step_3_45_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '3_46', 'baselines/step_3_46_before.png', 'baselines/step_3_46_intent.png', 'baselines/step_3_46_after.png')

    safe_action(page, page.get_by_role("button", name="columns"), 'click', '3_47', 'baselines/step_3_47_before.png', 'baselines/step_3_47_intent.png', 'baselines/step_3_47_after.png')

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '3_48', 'baselines/step_3_48_before.png', 'baselines/step_3_48_intent.png', 'baselines/step_3_48_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).nth(1), 'click', '3_49', 'baselines/step_3_49_before.png', 'baselines/step_3_49_intent.png', 'baselines/step_3_49_after.png')

    with safe_download(page) as download_info:

        safe_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', '3_50', 'baselines/step_3_50_before.png', 'baselines/step_3_50_intent.png', 'baselines/step_3_50_after.png')

    download = download_info.value

    safe_action(page, page.locator("a").filter(has_text="2"), 'click', '3_51', 'baselines/step_3_51_before.png', 'baselines/step_3_51_intent.png', 'baselines/step_3_51_after.png')

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '3_52', 'baselines/step_3_52_before.png', 'baselines/step_3_52_intent.png', 'baselines/step_3_52_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', '3_53', 'baselines/step_3_53_before.png', 'baselines/step_3_53_intent.png', 'baselines/step_3_53_after.png')

    safe_action(page, page.get_by_role("gridcell", name=" Baltimore Orioles|LICENSE FRAME COLOR CHROME|N/A|ORANGE").get_by_role("radio"), 'check', '3_54', 'baselines/step_3_54_before.png', 'baselines/step_3_54_intent.png', 'baselines/step_3_54_after.png')



    # ============================================================
    # SECTION: Locations 
    # ============================================================


    safe_action(page, page.get_by_text("Show All Locations"), 'click', '4_1', 'baselines/step_4_1_before.png', 'baselines/step_4_1_intent.png', 'baselines/step_4_1_after.png')

    safe_action(page, page.get_by_role("button", name="columns").nth(1), 'click', '4_2', 'baselines/step_4_2_before.png', 'baselines/step_4_2_intent.png', 'baselines/step_4_2_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '4_3', 'baselines/step_4_3_before.png', 'baselines/step_4_3_intent.png', 'baselines/step_4_3_after.png')

    safe_action(page, page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle"), 'check', '4_4', 'baselines/step_4_4_before.png', 'baselines/step_4_4_intent.png', 'baselines/step_4_4_after.png')

    safe_action(page, page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle"), 'check', '4_5', 'baselines/step_4_5_before.png', 'baselines/step_4_5_intent.png', 'baselines/step_4_5_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle"), 'check', '4_6', 'baselines/step_4_6_before.png', 'baselines/step_4_6_intent.png', 'baselines/step_4_6_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle"), 'check', '4_7', 'baselines/step_4_7_before.png', 'baselines/step_4_7_intent.png', 'baselines/step_4_7_after.png')

    safe_action(page, page.get_by_role("treeitem", name="Unrecoverable Lost Units").get_by_label("Press SPACE to toggle"), 'check', '4_8', 'baselines/step_4_8_before.png', 'baselines/step_4_8_intent.png', 'baselines/step_4_8_after.png')

    safe_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon"), 'click', '4_9', 'baselines/step_4_9_before.png', 'baselines/step_4_9_intent.png', 'baselines/step_4_9_after.png')

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '4_10', 'baselines/step_4_10_before.png', 'baselines/step_4_10_intent.png', 'baselines/step_4_10_after.png', "100")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '4_11', 'baselines/step_4_11_before.png', 'baselines/step_4_11_intent.png', 'baselines/step_4_11_after.png')

    safe_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon"), 'click', '4_12', 'baselines/step_4_12_before.png', 'baselines/step_4_12_intent.png', 'baselines/step_4_12_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '4_13', 'baselines/step_4_13_before.png', 'baselines/step_4_13_intent.png', 'baselines/step_4_13_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '4_14', 'baselines/step_4_14_before.png', 'baselines/step_4_14_intent.png', 'baselines/step_4_14_after.png')

    safe_action(page, page.get_by_role("button", name="columns").nth(1), 'click', '4_15', 'baselines/step_4_15_before.png', 'baselines/step_4_15_intent.png', 'baselines/step_4_15_after.png')

    safe_action(page, page.locator("div:nth-child(3) > div > .componentParentWrapper > esp-grid-container > esp-card-component > .card-container > .title > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div:nth-child(2) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', '4_16', 'baselines/step_4_16_before.png', 'baselines/step_4_16_intent.png', 'baselines/step_4_16_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '4_17', 'baselines/step_4_17_before.png', 'baselines/step_4_17_intent.png', 'baselines/step_4_17_after.png')

    safe_action(page, page.get_by_role("row", name="Location").get_by_role("checkbox"), 'check', '4_18', 'baselines/step_4_18_before.png', 'baselines/step_4_18_intent.png', 'baselines/step_4_18_after.png')

    safe_action(page, page.get_by_role("button", name="Apply").nth(1), 'click', '4_19', 'baselines/step_4_19_before.png', 'baselines/step_4_19_intent.png', 'baselines/step_4_19_after.png')



    # ============================================================
    # SECTION: Monthly Trends
    # ============================================================


    safe_action(page, page.locator("svg").get_by_text("Actual Sales & ROY Fcst ($)"), 'click', '5_1', 'baselines/step_5_1_before.png', 'baselines/step_5_1_intent.png', 'baselines/step_5_1_after.png')

    safe_action(page, page.locator("svg").get_by_text("Sales Fcst Adjusted ($)", exact=True), 'click', '5_2', 'baselines/step_5_2_before.png', 'baselines/step_5_2_intent.png', 'baselines/step_5_2_after.png')

    safe_action(page, page.get_by_text("GD Sales Fcst Adjusted ($)", exact=True), 'click', '5_3', 'baselines/step_5_3_before.png', 'baselines/step_5_3_intent.png', 'baselines/step_5_3_after.png')

    safe_action(page, page.get_by_text("Non GD Sales Fcst Adjusted ($)"), 'click', '5_4', 'baselines/step_5_4_before.png', 'baselines/step_5_4_intent.png', 'baselines/step_5_4_after.png')

    safe_action(page, page.locator("svg").get_by_text("TY Actual Sales ($)"), 'click', '5_5', 'baselines/step_5_5_before.png', 'baselines/step_5_5_intent.png', 'baselines/step_5_5_after.png')

    safe_action(page, page.locator("svg").get_by_text("System Sales Fcst ($)"), 'click', '5_6', 'baselines/step_5_6_before.png', 'baselines/step_5_6_intent.png', 'baselines/step_5_6_after.png')

    safe_action(page, page.get_by_text("GD Sales Fcst ($)", exact=True), 'click', '5_7', 'baselines/step_5_7_before.png', 'baselines/step_5_7_intent.png', 'baselines/step_5_7_after.png')

    safe_action(page, page.get_by_text("Non GD Sales Fcst ($)"), 'click', '5_8', 'baselines/step_5_8_before.png', 'baselines/step_5_8_intent.png', 'baselines/step_5_8_after.png')

    safe_action(page, page.locator("svg").get_by_text("% Change vs LLY"), 'click', '5_9', 'baselines/step_5_9_before.png', 'baselines/step_5_9_intent.png', 'baselines/step_5_9_after.png')

    safe_action(page, page.locator("svg").get_by_text("LLY Sales ($)"), 'click', '5_10', 'baselines/step_5_10_before.png', 'baselines/step_5_10_intent.png', 'baselines/step_5_10_after.png')

    safe_action(page, page.locator("svg").get_by_text("LY Sales ($)", exact=True), 'click', '5_11', 'baselines/step_5_11_before.png', 'baselines/step_5_11_intent.png', 'baselines/step_5_11_after.png')

    safe_action(page, page.locator("svg").get_by_text("% Change vs LY"), 'click', '5_12', 'baselines/step_5_12_before.png', 'baselines/step_5_12_intent.png', 'baselines/step_5_12_after.png')

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '5_13', 'baselines/step_5_13_before.png', 'baselines/step_5_13_intent.png', 'baselines/step_5_13_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '5_14', 'baselines/step_5_14_before.png', 'baselines/step_5_14_intent.png', 'baselines/step_5_14_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '5_15', 'baselines/step_5_15_before.png', 'baselines/step_5_15_intent.png', 'baselines/step_5_15_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '5_16', 'baselines/step_5_16_before.png', 'baselines/step_5_16_intent.png', 'baselines/step_5_16_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '5_17', 'baselines/step_5_17_before.png', 'baselines/step_5_17_intent.png', 'baselines/step_5_17_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '5_18', 'baselines/step_5_18_before.png', 'baselines/step_5_18_intent.png', 'baselines/step_5_18_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '5_19', 'baselines/step_5_19_before.png', 'baselines/step_5_19_intent.png', 'baselines/step_5_19_after.png')

    safe_action(page, page.locator("div:nth-child(6) > .d-flex").first, 'click', '5_20', 'baselines/step_5_20_before.png', 'baselines/step_5_20_intent.png', 'baselines/step_5_20_after.png')

    safe_action(page, page.locator("div:nth-child(6) > .d-flex").first, 'click', '5_21', 'baselines/step_5_21_before.png', 'baselines/step_5_21_intent.png', 'baselines/step_5_21_after.png')

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '5_22', 'baselines/step_5_22_before.png', 'baselines/step_5_22_intent.png', 'baselines/step_5_22_after.png')

    safe_action(page, page.locator("span:nth-child(7) > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").first, 'click', '5_23', 'baselines/step_5_23_before.png', 'baselines/step_5_23_intent.png', 'baselines/step_5_23_after.png')

    safe_action(page, page.get_by_text("Save Preference"), 'click', '5_24', 'baselines/step_5_24_before.png', 'baselines/step_5_24_intent.png', 'baselines/step_5_24_after.png')



    # ============================================================
    # SECTION: Monthly Summary
    # ============================================================


    safe_action(page, page.locator("i").nth(3), 'click', '6_1', 'baselines/step_6_1_before.png', 'baselines/step_6_1_intent.png', 'baselines/step_6_1_after.png')

    safe_action(page, page.locator(".ag-row-odd.ag-row-no-focus > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', '6_2', 'baselines/step_6_2_before.png', 'baselines/step_6_2_intent.png', 'baselines/step_6_2_after.png')

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '6_3', 'baselines/step_6_3_before.png', 'baselines/step_6_3_intent.png', 'baselines/step_6_3_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '6_4', 'baselines/step_6_4_before.png', 'baselines/step_6_4_intent.png', 'baselines/step_6_4_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '6_5', 'baselines/step_6_5_before.png', 'baselines/step_6_5_intent.png', 'baselines/step_6_5_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '6_6', 'baselines/step_6_6_before.png', 'baselines/step_6_6_intent.png', 'baselines/step_6_6_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '6_7', 'baselines/step_6_7_before.png', 'baselines/step_6_7_intent.png', 'baselines/step_6_7_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '6_8', 'baselines/step_6_8_before.png', 'baselines/step_6_8_intent.png', 'baselines/step_6_8_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(4) > .d-flex"), 'click', '6_9', 'baselines/step_6_9_before.png', 'baselines/step_6_9_intent.png', 'baselines/step_6_9_after.png')

    safe_action(page, page.locator("div:nth-child(5) > .d-flex"), 'click', '6_10', 'baselines/step_6_10_before.png', 'baselines/step_6_10_intent.png', 'baselines/step_6_10_after.png')

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '6_11', 'baselines/step_6_11_before.png', 'baselines/step_6_11_intent.png', 'baselines/step_6_11_after.png')

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '6_12', 'baselines/step_6_12_before.png', 'baselines/step_6_12_intent.png', 'baselines/step_6_12_after.png')

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '6_13', 'baselines/step_6_13_before.png', 'baselines/step_6_13_intent.png', 'baselines/step_6_13_after.png')

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100"), 'click', '6_14', 'baselines/step_6_14_before.png', 'baselines/step_6_14_intent.png', 'baselines/step_6_14_after.png')


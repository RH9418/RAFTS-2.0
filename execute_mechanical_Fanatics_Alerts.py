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

# 🔴 NEW: DYNAMIC DIRECTORY FOR EVERY RUN
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
    
    # 🔴 MAP PATHS TO DYNAMIC RUN DIRECTORY
    before_path = os.path.join(IMAGE_DIR, os.path.basename(before_path))
    intent_path = os.path.join(IMAGE_DIR, os.path.basename(intent_path))
    after_path = os.path.join(IMAGE_DIR, os.path.basename(after_path))
    
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
    
    # 🔴 RECORD NEW PATHS IN YAML SO LAYER 4 CAN FIND THEM
    try:
        with open('workflow_kb.yaml', 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id:
                    s['baseline_images']['before'] = before_path
                    s['baseline_images']['intent'] = intent_path
                    s['baseline_images']['after'] = after_path
        with open('workflow_kb.yaml', 'w', encoding='utf-8') as f: yaml.dump(kb, f, default_flow_style=False, sort_keys=False)
    except: pass


from playwright.sync_api import Page, expect





def test_example(page: Page) -> None:

    page.locator(".zeb-filter").first.click()

    page.get_by_role("textbox", name="e.g. Global Filters").click()

    page.get_by_role("textbox", name="e.g. Global Filters").fill("Global Filters")

    page.get_by_role("button", name="Add Section").click()

    page.locator("div").filter(has_text=re.compile(r"^Hierarchy$")).nth(2).click()

    page.get_by_text("League").click()

    page.get_by_text("League").click()

    page.get_by_text("Team", exact=True).click()

    safe_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', '1_5', 'baselines/step_1_5_before.png', 'baselines/step_1_5_intent.png', 'baselines/step_1_5_after.png')

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8.pointer.white-background-color > .pointer").first.click()

    page.get_by_text("Team", exact=True).click()

    page.get_by_text("Department").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Department").click()

    page.get_by_text("Class").click()

    page.locator(".custom-checkbox-wrapper.overflow-hidden.d-flex.justify-content-center.m-r-8 > .pointer").first.click()

    page.get_by_text("Class").click()

    safe_action(page, page.get_by_text("Attribute"), 'click', '1_15', 'baselines/step_1_15_before.png', 'baselines/step_1_15_intent.png', 'baselines/step_1_15_after.png')

    page.get_by_text("Product Line").click()

    page.get_by_text("Color", exact=True).click()

    safe_action(page, page.get_by_role("button", name="Apply Filters"), 'click', '1_39', 'baselines/step_1_39_before.png', 'baselines/step_1_39_intent.png', 'baselines/step_1_39_after.png')

    page.locator(".pill-nav-btn.pointer").click()

    page.locator(".zeb-filter").first.click()

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.get_by_role("textbox", name="e.g. Global Filters").click()

    page.get_by_role("textbox", name="e.g. Global Filters").fill("Alert and Season Types")

    page.get_by_role("button", name="Add Section").click()

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator("div").filter(has_text=re.compile(r"^All Alerts$")).nth(1).click()

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.locator("div").filter(has_text=re.compile(r"^Over Stock$")).nth(1).click()

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '4_9', 'baselines/step_4_9_before.png', 'baselines/step_4_9_intent.png', 'baselines/step_4_9_after.png')

    safe_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', '4_11', 'baselines/step_4_11_before.png', 'baselines/step_4_11_intent.png', 'baselines/step_4_11_after.png')

    safe_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', '4_10', 'baselines/step_4_10_before.png', 'baselines/step_4_10_intent.png', 'baselines/step_4_10_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_7', 'baselines/step_3_7_before.png', 'baselines/step_3_7_intent.png', 'baselines/step_3_7_after.png')

    page.locator("#seasontype-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    safe_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', '4_21', 'baselines/step_4_21_before.png', 'baselines/step_4_21_intent.png', 'baselines/step_4_21_after.png')

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_13', 'baselines/step_3_13_before.png', 'baselines/step_3_13_intent.png', 'baselines/step_3_13_after.png')

    page.locator(".dropdown-caret.p-l-16").first.click()

    page.get_by_text("All Alerts").click()

    safe_action(page, page.get_by_role("button", name="Apply"), 'click', '3_22', 'baselines/step_3_22_before.png', 'baselines/step_3_22_intent.png', 'baselines/step_3_22_after.png')

    page.get_by_role("button", name="columns").click()

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '3_2', 'baselines/step_3_2_before.png', 'baselines/step_3_2_intent.png', 'baselines/step_3_2_after.png')

    page.get_by_role("button", name="columns").click()

    page.get_by_role("button", name="columns").click()

    page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(2).click()

    page.get_by_role("spinbutton", name="Filter Value").fill("5")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_20', 'baselines/step_3_20_before.png', 'baselines/step_3_20_intent.png', 'baselines/step_3_20_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_21', 'baselines/step_3_21_before.png', 'baselines/step_3_21_intent.png', 'baselines/step_3_21_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_101', 'baselines/step_3_101_before.png', 'baselines/step_3_101_intent.png', 'baselines/step_3_101_after.png')

    page.get_by_title("Filter").nth(2).click()

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_108', 'baselines/step_3_108_before.png', 'baselines/step_3_108_intent.png', 'baselines/step_3_108_after.png')

    page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(3).click()

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', '3_5', 'baselines/step_3_5_before.png', 'baselines/step_3_5_intent.png', 'baselines/step_3_5_after.png')

    page.get_by_role("spinbutton", name="Filter Value").fill("4")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_36', 'baselines/step_3_36_before.png', 'baselines/step_3_36_intent.png', 'baselines/step_3_36_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_63', 'baselines/step_3_63_before.png', 'baselines/step_3_63_intent.png', 'baselines/step_3_63_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_106', 'baselines/step_3_106_before.png', 'baselines/step_3_106_intent.png', 'baselines/step_3_106_after.png')

    page.get_by_title("Filter").nth(3).click()

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_115', 'baselines/step_3_115_before.png', 'baselines/step_3_115_intent.png', 'baselines/step_3_115_after.png')

    page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle").check()

    page.get_by_title("Filter").nth(4).click()

    page.get_by_role("spinbutton", name="Filter Value").fill("50")

    safe_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', '3_62', 'baselines/step_3_62_before.png', 'baselines/step_3_62_intent.png', 'baselines/step_3_62_after.png')

    safe_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', '3_100', 'baselines/step_3_100_before.png', 'baselines/step_3_100_intent.png', 'baselines/step_3_100_after.png')

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_113', 'baselines/step_3_113_before.png', 'baselines/step_3_113_intent.png', 'baselines/step_3_113_after.png')

    page.get_by_title("Filter").nth(4).click()

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', '3_126', 'baselines/step_3_126_before.png', 'baselines/step_3_126_intent.png', 'baselines/step_3_126_after.png')

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', '3_82', 'baselines/step_3_82_before.png', 'baselines/step_3_82_intent.png', 'baselines/step_3_82_after.png')

    page.get_by_role("button", name="columns").click()

    safe_action(page, page.locator(".pointer.zeb-adjustments"), 'click', '3_84', 'baselines/step_3_84_before.png', 'baselines/step_3_84_intent.png', 'baselines/step_3_84_after.png')

    page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).nth(1).click()

    with safe_download(page) as download_info:

        safe_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', '3_86', 'baselines/step_3_86_before.png', 'baselines/step_3_86_intent.png', 'baselines/step_3_86_after.png')

    download = download_info.value

    safe_action(page, page.locator("a").filter(has_text="2"), 'click', '3_77', 'baselines/step_3_77_before.png', 'baselines/step_3_77_intent.png', 'baselines/step_3_77_after.png')

    safe_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '3_79', 'baselines/step_3_79_before.png', 'baselines/step_3_79_intent.png', 'baselines/step_3_79_after.png')

    safe_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', '5_19', 'baselines/step_5_19_before.png', 'baselines/step_5_19_intent.png', 'baselines/step_5_19_after.png')

    page.get_by_role("gridcell", name=" Baltimore Orioles|LICENSE FRAME COLOR CHROME|N/A|ORANGE").get_by_role("radio").check()

    page.get_by_role("textbox", name="e.g. Global Filters").click()

    page.get_by_role("textbox", name="e.g. Global Filters").fill("Locations ")

    page.get_by_role("button", name="Add Section").click()

    page.get_by_text("Show All Locations").click()

    page.get_by_role("button", name="columns").nth(1).click()

    safe_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', '5_13', 'baselines/step_5_13_before.png', 'baselines/step_5_13_intent.png', 'baselines/step_5_13_after.png')

    page.get_by_role("treeitem", name="First OOS Week Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="No OOS Weeks Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Est Lost Units Column").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Estimated Lost Sales ($)").get_by_label("Press SPACE to toggle").check()

    page.get_by_role("treeitem", name="Unrecoverable Lost Units").get_by_label("Press SPACE to toggle").check()

    page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .filter-icon").click()

    safe_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', '3_61', 'baselines/step_3_61_before.png', 'baselines/step_3_61_intent.png', 'baselines/step_3_61_after.png', "100")

    safe_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', '3_124', 'baselines/step_3_124_before.png', 'baselines/step_3_124_intent.png', 'baselines/step_3_124_after.png')

    page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .filter-icon").click()

    page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()

    page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()

    page.get_by_role("button", name="columns").nth(1).click()

    page.locator("div:nth-child(3) > div > .componentParentWrapper > esp-grid-container > esp-card-component > .card-container > .title > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div:nth-child(2) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()

    safe_action(page, page.get_by_text("Save Preference"), 'click', '3_85', 'baselines/step_3_85_before.png', 'baselines/step_3_85_intent.png', 'baselines/step_3_85_after.png')

    page.get_by_role("row", name="Location").get_by_role("checkbox").check()

    page.get_by_role("button", name="Apply").nth(1).click()

    page.get_by_role("textbox", name="e.g. Global Filters").click()

    page.get_by_role("textbox", name="e.g. Global Filters").fill("Monthly Trends")

    page.get_by_role("button", name="Add Section").click()

    page.locator("svg").get_by_text("Actual Sales & ROY Fcst ($)").click()

    page.locator("svg").get_by_text("Sales Fcst Adjusted ($)", exact=True).click()

    page.get_by_text("GD Sales Fcst Adjusted ($)", exact=True).click()

    page.get_by_text("Non GD Sales Fcst Adjusted ($)").click()

    page.locator("svg").get_by_text("TY Actual Sales ($)").click()

    page.locator("svg").get_by_text("System Sales Fcst ($)").click()

    page.get_by_text("GD Sales Fcst ($)", exact=True).click()

    page.get_by_text("Non GD Sales Fcst ($)").click()

    page.locator("svg").get_by_text("% Change vs LLY").click()

    page.locator("svg").get_by_text("LLY Sales ($)").click()

    page.locator("svg").get_by_text("LY Sales ($)", exact=True).click()

    page.locator("svg").get_by_text("% Change vs LY").click()

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_31', 'baselines/step_4_31_before.png', 'baselines/step_4_31_intent.png', 'baselines/step_4_31_after.png')

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    safe_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', '4_12', 'baselines/step_4_12_before.png', 'baselines/step_4_12_intent.png', 'baselines/step_4_12_after.png')

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator("div:nth-child(6) > .d-flex").first.click()

    page.locator("div:nth-child(6) > .d-flex").first.click()

    safe_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_40', 'baselines/step_4_40_before.png', 'baselines/step_4_40_intent.png', 'baselines/step_4_40_after.png')

    page.locator("span:nth-child(7) > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").first.click()

    safe_action(page, page.get_by_text("Save Preference"), 'click', '4_43', 'baselines/step_4_43_before.png', 'baselines/step_4_43_intent.png', 'baselines/step_4_43_after.png')

    page.get_by_role("textbox", name="e.g. Global Filters").click()

    page.get_by_role("textbox", name="e.g. Global Filters").fill("Monthly Summary")

    page.get_by_role("button", name="Add Section").click()

    page.locator("i").nth(3).click()

    page.locator(".ag-row-odd.ag-row-no-focus > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()

    safe_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', '4_8', 'baselines/step_4_8_before.png', 'baselines/step_4_8_intent.png', 'baselines/step_4_8_after.png')

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()

    page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()

    safe_action(page, page.locator(".overflow-auto > div:nth-child(4) > .d-flex"), 'click', '4_13', 'baselines/step_4_13_before.png', 'baselines/step_4_13_intent.png', 'baselines/step_4_13_after.png')

    page.locator("div:nth-child(5) > .d-flex").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()

    page.locator(".d-flex.flex-column.justify-content-center").first.click()

    page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100").click()


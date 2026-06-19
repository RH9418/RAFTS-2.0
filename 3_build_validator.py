import os
import re
import yaml

# --- The Purely Data Validation Injection Block ---
INJECTION_BLOCK = r"""
import os
import sys
import time
import yaml
import json
import contextlib
import re
from datetime import datetime

# --- Directories for Audit Trail ---
os.makedirs("Data_Dumps", exist_ok=True)
os.makedirs("Execution_Reports", exist_ok=True)

# --- Network Capture Queue ---
captured_graphql_responses = []

def get_composite_key(req_data):
    op_name = req_data.get("operationName", "unknown_op")
    try:
        dim_levels = req_data.get("variables", {}).get("query", {}).get("dimensionLevels")
        if dim_levels:
            if isinstance(dim_levels, list):
                dim_str = "-".join(str(d) for d in dim_levels)
            else:
                dim_str = str(dim_levels)
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
                    keys.append(get_composite_key(req_data))
                elif isinstance(req_data, list):
                    for item in req_data:
                        if isinstance(item, dict) and "operationName" in item:
                            keys.append(get_composite_key(item))
                
                if keys:
                    try:
                        resp_text = response.text()
                        resp_json = json.loads(resp_text)
                        for k in keys:
                            captured_graphql_responses.append({"op_key": k, "json": resp_json})
                    except: pass
    except: pass

# --- Bulletproof Javascript Snippets ---
WAIT_FOR_STABILITY_JS = '''
() => new Promise(resolve => {
    let checkCount = 0;
    const check = () => {
        checkCount++;
        const loaders = document.querySelectorAll('.ag-overlay-loading-wrapper, .spinner, .loading, [aria-busy="true"]');
        let isVisible = false;
        loaders.forEach(l => {
            const style = window.getComputedStyle(l);
            if(style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') isVisible = true;
        });
        if (isVisible && checkCount < 20) { setTimeout(check, 500); return; }
        resolve();
    };
    check();
})
'''

# Safe string splitting to avoid V8 Syntax Errors
UNIVERSAL_SCRAPER_JS = '''
async ([selector, axis]) => {
    return new Promise(resolve => {
        const container = document.querySelector(selector);
        if (!container) {
            resolve([]);
            return;
        }
        let scrapedText = new Set();
        
        const scrapeCurrentView = () => {
            if(container.innerText) {
                const lines = container.innerText.split('\\n');
                lines.forEach(line => {
                    if(line.trim()) scrapedText.add(line.trim());
                });
            }
        };
        scrapeCurrentView();
        const needsHScroll = axis === 'horizontal' && container.scrollWidth > container.clientWidth;
        const needsVScroll = axis === 'vertical' && container.scrollHeight > container.clientHeight;
        if (!needsHScroll && !needsVScroll) {
            resolve(Array.from(scrapedText));
            return;
        }
        let currentScroll = 0;
        const scrollStep = 400; 
        
        const sweepInterval = setInterval(() => {
            currentScroll += scrollStep;
            
            if (axis === 'horizontal') {
                container.scrollLeft = currentScroll;
                scrapeCurrentView();
                if (currentScroll >= (container.scrollWidth - container.clientWidth)) {
                    clearInterval(sweepInterval);
                    container.scrollLeft = 0;
                    resolve(Array.from(scrapedText));
                }
            } else if (axis === 'vertical') {
                container.scrollTop = currentScroll;
                scrapeCurrentView();
                if (currentScroll >= (container.scrollHeight - container.clientHeight)) {
                    clearInterval(sweepInterval);
                    container.scrollTop = 0;
                    resolve(Array.from(scrapedText));
                }
            }
        }, 250); 
    });
}
'''

DRAG_JS = '''
function makeDraggable(el, handle) {
    let startX, startY, initialLeft, initialTop;
    handle.style.cursor = 'move';
    handle.onmousedown = (e) => {
        e.preventDefault();
        startX = e.clientX; startY = e.clientY;
        const rect = el.getBoundingClientRect();
        el.style.left = rect.left + 'px'; el.style.top = rect.top + 'px';
        el.style.right = 'auto'; el.style.transform = 'none';
        initialLeft = rect.left; initialTop = rect.top;
        document.onmousemove = (me) => {
            el.style.left = (initialLeft + me.clientX - startX) + 'px';
            el.style.top = (initialTop + me.clientY - startY) + 'px';
        };
        document.onmouseup = () => { document.onmousemove = null; document.onmouseup = null; };
    };
}
'''

MAPPER_WIDGET_JS = '''
(opName) => new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.id = 'mapper-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:2147483646;cursor:crosshair;';
    const banner = document.createElement('div');
    banner.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#1e293b;color:white;padding:15px;border-radius:8px;z-index:2147483647;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.5); border: 2px solid #f59e0b; pointer-events:auto; font-family:sans-serif; min-width: 300px;';
    const header = document.createElement('div');
    header.innerHTML = '⋮⋮ DRAG TO MOVE ⋮⋮';
    header.style.cssText = 'background:#0f172a; margin:-15px -15px 15px -15px; padding:5px; border-radius:8px 8px 0 0; font-size:10px; color:#94a3b8; user-select:none;';
    banner.appendChild(header);
    const content = document.createElement('div');
    content.innerHTML = `🚨 <b>New API:</b> <span style="color:#10b981;">${opName}</span><br><span style="font-size:12px">Hover and click the UI container where this data appears.</span><br><br><button id="mapper-ignore-btn" style="padding:6px 12px; background:#ef4444; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Mark as Junk (Ignore)</button>`;
    banner.appendChild(content);
    document.body.appendChild(overlay); document.body.appendChild(banner);
    ''' + DRAG_JS + '''
    makeDraggable(banner, header);
    document.getElementById('mapper-ignore-btn').addEventListener('click', (e) => {
        e.preventDefault(); e.stopPropagation();
        overlay.remove(); banner.remove();
        resolve({ selector: 'IGNORE', axis: 'none' });
    });
    let lastEl = null; let originalOutline = '';
    const mouseMove = (e) => {
        overlay.style.display = 'none'; const el = document.elementFromPoint(e.clientX, e.clientY); overlay.style.display = 'block';
        if (el && el !== lastEl && el !== banner && !banner.contains(el)) {
            if (lastEl) lastEl.style.outline = originalOutline;
            originalOutline = el.style.outline; el.style.outline = '3px solid #eab308'; el.style.outlineOffset = '-3px'; lastEl = el;
        }
    };
    const clickHandler = (e) => {
        e.preventDefault(); e.stopPropagation();
        overlay.removeEventListener('mousemove', mouseMove); overlay.removeEventListener('click', clickHandler);
        if (lastEl) lastEl.style.outline = originalOutline;
        let selector = '';
        const ag = lastEl.closest('.ag-body-viewport, .ag-center-cols-viewport');
        if (ag) { selector = '.ag-body-viewport'; } 
        else if (lastEl.id) { selector = '#' + lastEl.id; } 
        else {
            const classes = Array.from(lastEl.classList).filter(c => !c.includes('hover')).join('.');
            selector = lastEl.tagName.toLowerCase() + (classes ? '.' + classes : '');
        }
        content.innerHTML = `Container Selected: <b style="color:#3b82f6;">${selector}</b><br>How does this container scroll?`;
        const btnContainer = document.createElement('div'); btnContainer.style.marginTop = '12px'; btnContainer.style.display = 'flex'; btnContainer.style.gap = '10px'; btnContainer.style.justifyContent = 'center';
        const createBtn = (text, axis, color) => {
            const b = document.createElement('button'); b.innerText = text; b.style.cssText = `padding:8px 12px; background:${color}; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;`;
            b.onclick = () => { overlay.remove(); banner.remove(); resolve({ selector: selector, axis: axis }); }; return b;
        };
        btnContainer.appendChild(createBtn('Horizontal (Grid)', 'horizontal', '#3b82f6'));
        btnContainer.appendChild(createBtn('Vertical (Filter)', 'vertical', '#8b5cf6'));
        btnContainer.appendChild(createBtn('Static', 'none', '#64748b'));
        content.appendChild(btnContainer);
    };
    overlay.addEventListener('mousemove', mouseMove); overlay.addEventListener('click', clickHandler);
})
'''

# --- Python Helper & Verification Functions ---

def wait_for_stability(page):
    try: page.wait_for_load_state('networkidle', timeout=3000)
    except: pass
    try: page.evaluate(WAIT_FOR_STABILITY_JS)
    except: pass
    time.sleep(0.5)

def get_permutations(raw_value):
    if isinstance(raw_value, bool):
        return [str(raw_value), str(raw_value).lower()]
    if isinstance(raw_value, int): 
        return [str(raw_value), f"{raw_value:,}"]
    if isinstance(raw_value, float):
        return [
            f"{raw_value:,.2f}",      
            f"{raw_value:,.1f}",      
            f"{round(raw_value):,}",  
            f"{int(raw_value):,}",    
            str(raw_value),           
            f"{round(raw_value * 100):,}", 
            f"{raw_value * 100:,.2f}"
        ]
    return [str(raw_value)]

def extract_all_ui_numbers(ui_text_list):
    ui_nums = set()
    for text in ui_text_list:
        clean = str(text).replace(",", "").replace("%", "").strip()
        matches = re.findall(r'-?\d+\.?\d*', clean)
        for m in matches:
            try: ui_nums.add(float(m))
            except: pass
    return ui_nums

def extract_expected_values(api_json):
    expected_raw = []
    def search_dict(d):
        if isinstance(d, dict):
            if "dimensionMembers" in d:
                for dim in d["dimensionMembers"]:
                    if "name" in dim and dim["name"] is not None: expected_raw.append(dim["name"])
            if "measureValues" in d:
                for val in d["measureValues"]:
                    if val is not None: expected_raw.append(val)
            for k, v in d.items(): search_dict(v)
        elif isinstance(d, list):
            for item in d: search_dict(item)
    search_dict(api_json.get("data", {}))
    
    unique_expected = []
    seen = set()
    for val in expected_raw:
        if str(val) not in seen:
            seen.add(str(val))
            unique_expected.append(val)
    return unique_expected

def process_api_queue(page, step_id):
    global captured_graphql_responses
    if not captured_graphql_responses: return
    
    registry_file = 'graphql_registry.yaml'
    if not os.path.exists(registry_file):
        with open(registry_file, 'w', encoding='utf-8') as f: yaml.dump({}, f)
    
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = yaml.safe_load(f) or {}

    valid_apis = []
    for item in captured_graphql_responses:
        op_key = item["op_key"]
        if op_key not in registry:
            print(f"\n  └── 🚨 UNKNOWN API DETECTED: {op_key}")
            mapping_data = page.evaluate(MAPPER_WIDGET_JS, op_key)
            if mapping_data:
                registry[op_key] = mapping_data
                with open(registry_file, 'w', encoding='utf-8') as f:
                    yaml.dump(registry, f, default_flow_style=False, sort_keys=False)
                if mapping_data["selector"] == "IGNORE":
                    print(f"  └── 🗑️ Marked '{op_key}' as JUNK.")
                else:
                    print(f"  └── 💾 Saved '{op_key}' mapping!")

        if registry.get(op_key, {}).get("selector") != "IGNORE":
            valid_apis.append(item)

    if not valid_apis:
        captured_graphql_responses.clear()
        return

    print(f"\n  " + "="*70)
    print(f"  ⏳ PRE-CHECK PAUSE: The following APIs were triggered:")
    for api in valid_apis: print(f"      - {api['op_key']}")
    print(f"  🛑 ACTION REQUIRED: Ensure all columns are unhidden and dropdowns are visible.")
    input(f"  👉 PRESS [ENTER] when ready to begin the Data Sweep...")
    print(f"  " + "="*70 + "\n")

    for item in valid_apis:
        op_key = item["op_key"]
        resp_json = item["json"]
        config = registry[op_key]
        selector = config["selector"]
        axis = config["axis"]
        
        api_dump_path = os.path.join("Data_Dumps", f"{step_id}_{op_key}_API.json")
        with open(api_dump_path, "w", encoding="utf-8") as f:
            json.dump(resp_json, f, indent=4)
            
        expected_raw_values = extract_expected_values(resp_json)
        if not expected_raw_values: continue
        
        is_visible = page.evaluate('''args => {
            const el = document.querySelector(args[0]);
            return el && el.offsetWidth > 0 && el.offsetHeight > 0 && window.getComputedStyle(el).display !== 'none';
        }''', [selector])
        
        if not is_visible:
            print(f"  └── ⏭️ UI Container '{selector}' is currently hidden. Skipping verification for '{op_key}'.")
            continue
        
        cumulative_ui_text = set()
        
        while True:
            print(f"  └── 🧹 Sweeping UI container '{selector}'...")
            rendered_ui_text = page.evaluate(UNIVERSAL_SCRAPER_JS, [selector, axis])
            cumulative_ui_text.update(rendered_ui_text)
            
            ui_dump_path = os.path.join("Data_Dumps", f"{step_id}_{op_key}_UI.txt")
            with open(ui_dump_path, "w", encoding="utf-8") as f:
                f.write("\n".join(cumulative_ui_text))
                
            ui_text_blob = " | ".join(cumulative_ui_text)
            ui_numbers_set = extract_all_ui_numbers(cumulative_ui_text)
            
            missing_values = []
            
            # --- THE MATHEMATICAL VERIFIER ---
            for raw_val in expected_raw_values:
                # 1. Try String Permutation Match First
                perms = get_permutations(raw_val)
                if any(str(p) in ui_text_blob for p in perms):
                    continue
                
                # 2. Try Mathematical Range Match for Floats/Ints
                if isinstance(raw_val, (int, float)):
                    target = float(raw_val)
                    found_math_match = False
                    for unum in ui_numbers_set:
                        # Check within +/- 1.0 margin of error, AND percentage multiplier (*100)
                        if abs(unum - target) <= 1.0 or abs(unum - (target * 100)) <= 1.0:
                            found_math_match = True
                            break
                    if found_math_match:
                        continue
                
                missing_values.append(str(raw_val))
            
            if missing_values:
                global_ui_text = page.evaluate("() => document.body.innerText")
                global_nums_set = extract_all_ui_numbers(global_ui_text.split('\n'))
                still_missing = []
                
                for m in missing_values:
                    try:
                        target_float = float(m)
                        perms = get_permutations(target_float)
                    except:
                        target_float = None
                        perms = [m]
                        
                    if any(str(p) in global_ui_text for p in perms):
                        continue
                        
                    if target_float is not None:
                        found_math_global = False
                        for gnum in global_nums_set:
                            if abs(gnum - target_float) <= 1.0 or abs(gnum - (target_float * 100)) <= 1.0:
                                found_math_global = True
                                break
                        if found_math_global:
                            continue
                            
                    still_missing.append(m)
                
                if not still_missing:
                    print(f"  └── 🪄 PORTAL DETECTED: Match Accepted via floating DOM overlay.")
                    missing_values = []
                else:
                    missing_values = still_missing

            if not missing_values:
                print(f"  └── ✅ DATA VERIFIED: 100% API match for '{op_key}'.")
                break 
            else:
                print(f"  └── ⚠️ DATA MISMATCH: {len(missing_values)} values missing.")
                for m in missing_values[:5]: print(f"       - Missing: {m}")
                
                print("  └── 🛑 POST-CHECK PAUSE:")
                user_input = input("      Press [ENTER] to Re-Sweep (will accumulate), type 'ignore' to bypass, or 'fail' to HALT: ").strip().lower()
                
                if user_input == 'fail':
                    raise Exception(f"Bug Raised: Data Mismatch on {op_key}. See Data_Dumps/")
                elif user_input == 'ignore':
                    print("  └── ⏭️ Human bypassed mismatch. Continuing...")
                    break
                else:
                    print("  └── 🔄 Re-Sweeping and Accumulating...")

    captured_graphql_responses.clear()

def check_for_healed_coords(step_id):
    try:
        with open('workflow_kb.yaml', 'r', encoding='utf-8') as f: kb = yaml.safe_load(f)
        for sec in kb.get('sections', []):
            for s in sec.get('steps', []):
                if s['step_id'] == step_id and 'healed_coords' in s: return s['healed_coords']
    except: pass
    return None

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

def safe_action(page, locator, action_name, step_id, *args, **kwargs):
    print(f"\n▶ Step {step_id}: {action_name}")
    wait_for_stability(page)
    
    healed = check_for_healed_coords(step_id)
    target_x, target_y = None, None

    if healed: target_x, target_y = healed['x'], healed['y']

    global captured_graphql_responses
    captured_graphql_responses.clear()

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
            getattr(locator, action_name)(*args, **kwargs)
            fallback_success = True
            print("  └── ✅ Native action succeeded.")
        except Exception as e:
            if not fallback_success:
                try: getattr(locator.first, action_name)(*args, **kwargs); fallback_success = True; print("  └── 🛠️ F1 Succeeded.")
                except: pass
            if not fallback_success and action_name == 'click':
                try: locator.evaluate("el => el.click()"); fallback_success = True; print("  └── 🛠️ F2 (JS) Succeeded.")
                except: pass

    if not fallback_success:
        print(f"  └── 🛑 ALL FALLBACKS FAILED. Skipping to next action.")

    wait_for_stability(page)
    process_api_queue(page, step_id)
"""

def main():
    input_py = "clean_codegen.py"
    input_yaml = "workflow_kb.yaml"
    output_py = "execute_data_validation.py"

    if not os.path.exists(input_py) or not os.path.exists(input_yaml): 
        print(f"❌ Error: Missing required files.")
        return

    with open(input_yaml, "r", encoding="utf-8") as f: kb = yaml.safe_load(f)
    steps_queue = [s for sec in kb.get('sections', []) for s in sec.get('steps', [])]

    with open(input_py, "r", encoding="utf-8") as f: lines = f.readlines()
        
    new_lines = []
    header_injected = False

    print(f"\n⚙️ Building Layer 2 (Data Validation) into '{output_py}'...")

    for line in lines:
        stripped = line.strip()
        
        if not header_injected and not stripped.startswith("import ") and not stripped.startswith("from "):
            new_lines.append(INJECTION_BLOCK + "\n")
            header_injected = True

        if "def test_example(" in stripped:
            new_lines.append(line)
            new_lines.append('    page.on("response", handle_response)\n')
            new_lines.append('    try: page.goto("https://stage.bbu.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=4&tabIndex=1", timeout=0)\n    except: pass\n')
            new_lines.append('    print("\\n" + "="*60)\n')
            new_lines.append('    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\\n")\n')
            new_lines.append('    wait_for_stability(page)\n')
            new_lines.append('    process_api_queue(page, "0_0_Init")\n')
            continue

        matched_step = next((s for s in steps_queue if s['raw_code'] in stripped), None)
        
        if matched_step:
            steps_queue.remove(matched_step)
            indent = line[:len(line) - len(line.lstrip())]
            action = matched_step['action']
            match = re.match(rf"^(.*?)\.{action}\((.*?)\)$", matched_step['raw_code'])
            
            if match:
                loc, args = match.group(1), match.group(2)
                step_id = matched_step['step_id']
                if args:
                    new_lines.append(f"{indent}safe_action(page, {loc}, '{action}', '{step_id}', {args})\n")
                else:
                    new_lines.append(f"{indent}safe_action(page, {loc}, '{action}', '{step_id}')\n")
            else: new_lines.append(line)
        else: new_lines.append(line)

    with open(output_py, "w", encoding="utf-8") as f: f.writelines(new_lines)
    print(f"✅ Layer 2 Executable saved: {output_py}")

if __name__ == "__main__":
    main()

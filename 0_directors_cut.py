import os
import re

INJECTION_BLOCK = r"""
import os
import sys
import time
import json
import yaml
import re
from datetime import datetime

# --- Architecture Initialization ---
os.makedirs("Screenshots", exist_ok=True)
os.makedirs("API_Dumps", exist_ok=True)
os.makedirs("Data_Dumps", exist_ok=True)

test_case_kb = {
    "workflow_name": "Logical Test Case Definitions",
    "test_cases": []
}

def init_kb():
    if not os.path.exists('test_cases_kb.yaml'):
        with open('test_cases_kb.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(test_case_kb, f, sort_keys=False)

# --- Telemetry & Memory ---
captured_graphql_apis = []
command_queue = []
current_test_case = None
snapshot_counter = 1

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

def handle_js_event(source, event_str):
    event = json.loads(event_str)
    command_queue.append(event)

# --- Fallback Target Mode Javascript ---
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

# --- Javascript Annotator Widget (Spatial, Temporal & SCROLL Anchors) ---
ANNOTATOR_WIDGET_JS = '''
(() => {
    window.setNextAction = (code) => {
        const el = document.getElementById('next-action-text');
        if(el) el.value = code;
        const btn = document.getElementById('execute-next-btn');
        if(btn) {
            btn.innerHTML = "<b>[Alt+N]</b> Execute Next Action";
            btn.style.background = "#8b5cf6";
            btn.disabled = false;
        }
    };
    window.waitForEnd = () => new Promise(resolve => {
        const txt = document.getElementById('next-action-text');
        if(txt) txt.value = "🏁 Script Complete!";
        const btn = document.getElementById('execute-next-btn');
        if(btn) {
            btn.innerText = "💾 Save & Close Browser";
            btn.style.background = "#10b981";
            btn.disabled = false;
            btn.onclick = () => resolve();
        } else { resolve(); }
    });
    function injectWidget() {
        if (document.getElementById('agent-annotator-widget')) return;
        
        let isRecordingTest = false;
        let currentTestName = "";
        let drawnBoxes = []; 
        const widget = document.createElement('div');
        widget.id = 'agent-annotator-widget';
        widget.onmousedown = (e) => { 
            if(e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); }
            e.stopPropagation(); 
        };
        widget.style.cssText = 'position:fixed; top:20px; right:20px; z-index:2147483647; background:#1e293b; padding:15px; border-radius:8px; box-shadow:0 10px 25px rgba(0,0,0,0.5); border:2px solid #8b5cf6; font-family:sans-serif; color:white; width:350px;';
        const header = document.createElement('div');
        header.innerHTML = '⋮⋮ DRAG TO MOVE ⋮⋮';
        header.style.cssText = 'background:#0f172a; margin:-15px -15px 15px -15px; padding:5px; text-align:center; font-size:10px; color:#94a3b8; cursor:move; border-radius:6px 6px 0 0; user-select:none;';
        widget.appendChild(header);
        const playbackControls = document.createElement('div');
        playbackControls.style.cssText = 'margin-bottom:15px; padding-bottom:15px; border-bottom:1px solid #334155;';
        playbackControls.innerHTML = `
            <div style="font-size:12px; color:#94a3b8; margin-bottom:5px;">Next Playwright Action:</div>
            <textarea id="next-action-text" readonly style="font-family:monospace; background:#0f172a; padding:8px; border-radius:4px; font-size:11px; color:#10b981; margin-bottom:10px; width:100%; border:none; resize:none; box-sizing:border-box;">Initializing...</textarea>
            <button id="execute-next-btn" disabled style="width:100%; padding:10px; background:#64748b; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold; font-size:14px;">Please wait...</button>
        `;
        widget.appendChild(playbackControls);
        const content = document.createElement('div');
        widget.appendChild(content);
        document.body.appendChild(widget);
        const toggleDrawingMode = () => {
            let wrapper = document.getElementById('agent-draw-wrapper');
            
            if (!wrapper) {
                wrapper = document.createElement('div');
                wrapper.id = 'agent-draw-wrapper';
                wrapper.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:2147483645; pointer-events:none;';
                document.body.appendChild(wrapper);
                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.id = 'agent-draw-svg';
                svg.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;';
                wrapper.appendChild(svg);
            }
            let backdrop = document.getElementById('agent-draw-backdrop');
            
            if (backdrop) {
                backdrop.remove();
                const btn = document.getElementById('agent-draw-finish-btn');
                if (btn) btn.remove();
            } else {
                backdrop = document.createElement('div');
                backdrop.id = 'agent-draw-backdrop';
                backdrop.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.1); cursor:crosshair; pointer-events:auto;';
                wrapper.appendChild(backdrop);
                const finishBtn = document.createElement('button');
                finishBtn.id = 'agent-draw-finish-btn';
                finishBtn.innerHTML = "✅ Done Drawing <b>[Alt+D]</b>";
                finishBtn.style.cssText = 'position:absolute; top:20px; left:50%; transform:translateX(-50%); background:#ef4444; color:white; border:none; padding:12px 24px; font-weight:bold; border-radius:6px; cursor:pointer; box-shadow:0 4px 10px rgba(0,0,0,0.5); font-size:16px; pointer-events:auto;';
                wrapper.appendChild(finishBtn);
                const svg = document.getElementById('agent-draw-svg');
                let isDrawing = false; let startX = 0, startY = 0; let currentRect = null;
                backdrop.addEventListener('mousedown', (e) => {
                    e.preventDefault(); e.stopImmediatePropagation();
                    isDrawing = true; startX = e.clientX; startY = e.clientY;
                    currentRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    currentRect.setAttribute('fill', 'rgba(234,179,8,0.2)');
                    currentRect.setAttribute('stroke', '#ef4444');
                    currentRect.setAttribute('stroke-width', '4');
                    svg.appendChild(currentRect);
                }, true);
                backdrop.addEventListener('mousemove', (e) => {
                    if(!isDrawing || !currentRect) return;
                    e.preventDefault(); e.stopImmediatePropagation();
                    const x = Math.min(startX, e.clientX); const y = Math.min(startY, e.clientY);
                    const w = Math.abs(e.clientX - startX); const h = Math.abs(e.clientY - startY);
                    currentRect.setAttribute('x', x); currentRect.setAttribute('y', y);
                    currentRect.setAttribute('width', w); currentRect.setAttribute('height', h);
                }, true);
                backdrop.addEventListener('mouseup', (e) => {
                    if(!isDrawing || !currentRect) return;
                    e.preventDefault(); e.stopImmediatePropagation();
                    isDrawing = false;
                    const w = parseFloat(currentRect.getAttribute('width')||0);
                    const h = parseFloat(currentRect.getAttribute('height')||0);
                    if(w > 10 && h > 10) {
                        drawnBoxes.push({
                            x: parseFloat(currentRect.getAttribute('x')),
                            y: parseFloat(currentRect.getAttribute('y')),
                            width: w, 
                            height: h
                        });
                    } else { currentRect.remove(); }
                    currentRect = null;
                }, true);
                backdrop.addEventListener('click', (e) => { e.preventDefault(); e.stopImmediatePropagation(); }, true);
                finishBtn.onclick = (e) => { e.preventDefault(); toggleDrawingMode(); };
            }
        };
        const renderState = () => {
            if(!isRecordingTest) {
                content.innerHTML = `
                    <div style="font-weight:bold; margin-bottom:10px;">🧪 Logical Test Case Config</div>
                    <input id="test-name" type="text" placeholder="e.g. Column Filtering Test" style="width:100%; padding:8px; border-radius:4px; border:none; margin-bottom:10px; box-sizing:border-box; color:black;">
                    <button id="start-test-btn" style="width:100%; padding:8px; background:#10b981; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Start Test Case</button>
                `;
                document.getElementById('start-test-btn').onclick = async () => {
                    const name = document.getElementById('test-name').value;
                    if(!name) return alert("Please enter a test case name!");
                    currentTestName = name;
                    isRecordingTest = true;
                    await window.pyLogEvent(JSON.stringify({type: 'START_TEST', name: currentTestName}));
                    renderState();
                };
            } else {
                content.innerHTML = `
                    <div style="font-weight:bold; margin-bottom:10px; color:#3b82f6;">🟢 Active: ${currentTestName}</div>
                    <button id="draw-btn" style="width:100%; padding:8px; background:#eab308; color:black; border:none; border-radius:4px; cursor:pointer; font-weight:bold; margin-bottom:10px;"><b>[Alt+D]</b> Toggle Draw Mode</button>
                    <textarea id="snap-note" placeholder="2. Describe what the AI should verify..." style="width:100%; height:60px; padding:8px; border-radius:4px; border:none; margin-bottom:10px; resize:none; box-sizing:border-box; font-family:inherit; color:black;"></textarea>
                    <button id="snap-btn" style="width:100%; padding:8px; background:#3b82f6; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold; margin-bottom:10px;"><b>[Alt+S]</b> Take Focused Snapshot</button>
                    <hr style="border:1px solid #334155; margin:10px 0;">
                    <button id="end-test-btn" style="width:100%; padding:8px; background:#ef4444; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">End Test Case</button>
                `;
                
                document.getElementById('draw-btn').onclick = (e) => { e.preventDefault(); toggleDrawingMode(); };
                
                document.getElementById('snap-btn').onclick = async (e) => {
                    e.preventDefault();
                    const note = document.getElementById('snap-note').value;
                    const targetAction = document.getElementById('next-action-text').value; 
                    
                    const btn = document.getElementById('snap-btn');
                    btn.innerHTML = "📸 Capturing..."; btn.style.background = "#64748b"; btn.disabled = true;
                    
                    const backdrop = document.getElementById('agent-draw-backdrop');
                    if (backdrop) toggleDrawingMode();
                    
                    await window.pyLogEvent(JSON.stringify({
                        type: 'TAKE_SNAPSHOT', 
                        note: note,
                        target_action: targetAction,
                        boxes: [...drawnBoxes],
                        scroll_x: window.scrollX,
                        scroll_y: window.scrollY
                    }));
                    
                    document.getElementById('snap-note').value = "";
                    drawnBoxes = []; 
                    
                    btn.innerHTML = "✅ Snapshot Saved!"; btn.style.background = "#10b981";
                    setTimeout(() => { btn.innerHTML = "<b>[Alt+S]</b> Take Focused Snapshot"; btn.style.background = "#3b82f6"; btn.disabled = false; }, 1500);
                };
                document.getElementById('end-test-btn').onclick = async (e) => {
                    e.preventDefault();
                    await window.pyLogEvent(JSON.stringify({type: 'END_TEST', name: currentTestName}));
                    const wrapper = document.getElementById('agent-draw-wrapper');
                    if(wrapper) wrapper.remove();
                    drawnBoxes = [];
                    isRecordingTest = false; currentTestName = "";
                    renderState();
                };
            }
        };
        // --- GLOBAL HOTKEYS ---
        document.addEventListener('keydown', (e) => {
            if (e.altKey && e.key.toLowerCase() === 'd') {
                e.preventDefault(); e.stopPropagation();
                if(isRecordingTest) toggleDrawingMode();
            }
            if (e.altKey && e.key.toLowerCase() === 's') {
                e.preventDefault(); e.stopPropagation();
                const btn = document.getElementById('snap-btn');
                if(btn && !btn.disabled) btn.click();
            }
            if (e.altKey && e.key.toLowerCase() === 'n') {
                e.preventDefault(); e.stopPropagation();
                const btn = document.getElementById('execute-next-btn');
                if(btn && !btn.disabled) btn.click();
            }
        }, true);
        document.addEventListener('click', (e) => {
            if(e.target && e.target.id === 'execute-next-btn') {
                const btn = e.target;
                btn.innerText = "⏳ Executing..."; btn.style.background = "#64748b"; btn.disabled = true;
                window.pyLogEvent(JSON.stringify({type: 'EXECUTE_NEXT'}));
            }
        });
        let startXWidget, startYWidget, initialL, initialTop;
        header.onmousedown = (e) => {
            e.preventDefault(); startXWidget = e.clientX; startYWidget = e.clientY;
            const rect = widget.getBoundingClientRect();
            widget.style.left = rect.left + 'px'; widget.style.top = rect.top + 'px';
            widget.style.right = 'auto'; widget.style.bottom = 'auto';
            initialL = rect.left; initialTop = rect.top;
            document.onmousemove = (me) => {
                widget.style.left = (initialL + me.clientX - startXWidget) + 'px';
                widget.style.top = (initialTop + me.clientY - startYWidget) + 'px';
            };
            document.onmouseup = () => { document.onmousemove = null; document.onmouseup = null; };
        };
        renderState();
    }
    
    document.addEventListener('DOMContentLoaded', injectWidget);
    setInterval(injectWidget, 2000);
})();
'''

# 🔴 ADDED: 6-Tier Fallback Wrapper exclusively for the Annotator
def safe_annotator_action(page, locator, action_name, original_code_str, *args, **kwargs):
    fallback_success = False
    try:
        if 'timeout' not in kwargs: kwargs['timeout'] = 3000
        getattr(locator, action_name)(*args, **kwargs)
        fallback_success = True
    except Exception as e:
        error_msg = str(e)
        print(f"  └── ⚠️ Action failed: {error_msg.splitlines()[0][:80]}...")
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
        print(f"  └── 🛑 ALL FALLBACKS FAILED. INJECTING TARGET MODE...")
        coords = page.evaluate(MANUAL_CAPTURE_JS)
        if coords:
            try:
                if action_name in ['click', 'dblclick', 'check', 'uncheck']:
                    page.mouse.click(coords['x'], coords['y'])
                elif action_name == 'hover':
                    page.mouse.move(coords['x'], coords['y'])
                elif action_name == 'fill' and args:
                    page.mouse.click(coords['x'], coords['y'])
                    page.keyboard.type(str(args[0]))
                print("  └── ✅ Manual intervention executed successfully.")
            except Exception as ex:
                print(f"  └── ❌ Manual intervention failed: {ex}")


def wait_for_user_approval(page, description):
    global current_test_case, snapshot_counter, captured_graphql_apis
    print(f"\n▶ Waiting for user approval: {description}")
    
    for _ in range(20):
        try:
            page.evaluate("([code]) => { if(window.setNextAction) window.setNextAction(code); }", [description])
            break
        except Exception as e:
            if "Execution context was destroyed" in str(e) or "Target page" in str(e): time.sleep(1)
            else: break
    
    while True:
        if command_queue:
            cmd = command_queue.pop(0)
            c_type = cmd.get('type')
            
            if c_type == 'START_TEST':
                test_name = cmd.get('name')
                current_test_case = { "test_name": test_name, "snapshots": [] }
                test_case_kb['test_cases'].append(current_test_case)
                captured_graphql_apis.clear() 
                print(f"  🎬 Started Test Case: {test_name}")
                
            elif c_type == 'TAKE_SNAPSHOT':
                if not current_test_case: continue
                
                note = cmd.get('note', '')
                target_action = cmd.get('target_action', '').strip()
                boxes = cmd.get('boxes', [])
                scroll_x = cmd.get('scroll_x', 0)
                scroll_y = cmd.get('scroll_y', 0)
                
                timestamp = datetime.now().strftime("%H%M%S")
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', current_test_case["test_name"])[:20]
                img_path = f"Screenshots/{safe_name}_{timestamp}_{snapshot_counter}.png"
                
                page.evaluate('''() => { 
                    const w = document.getElementById('agent-annotator-widget'); 
                    if(w) w.style.display = 'none'; 
                }''')
                
                page.screenshot(path=img_path)
                print(f"  📸 Focused Snapshot captured: {img_path}")
                
                page.evaluate('''() => { 
                    const w = document.getElementById('agent-annotator-widget'); 
                    if(w) w.style.display = 'block'; 
                    const drawWrapper = document.getElementById('agent-draw-wrapper');
                    if(drawWrapper) drawWrapper.remove();
                }''')
                
                api_dumps = []
                for api in captured_graphql_apis:
                    api_key = api['api_key']
                    dump_path = f"API_Dumps/{safe_name}_{timestamp}_{snapshot_counter}_{api_key}.json"
                    with open(dump_path, 'w', encoding='utf-8') as f: json.dump(api, f, indent=4)
                    api_dumps.append({"api_key": api_key, "file": dump_path})
                
                current_test_case["snapshots"].append({
                    "target_action": target_action,
                    "bounding_boxes": boxes,
                    "scroll_x": scroll_x,
                    "scroll_y": scroll_y,
                    "image_path": img_path,
                    "human_note": note,
                    "apis_triggered": api_dumps
                })
                
                with open('test_cases_kb.yaml', 'w', encoding='utf-8') as f:
                    yaml.dump(test_case_kb, f, sort_keys=False)
                    
                captured_graphql_apis.clear()
                snapshot_counter += 1
                
            elif c_type == 'END_TEST':
                print(f"  🛑 Ended Test Case: {cmd.get('name')}")
                current_test_case = None
                
            elif c_type == 'EXECUTE_NEXT':
                print("  └── Executing Playwright Action...")
                break 
                
        page.wait_for_timeout(100) 
"""

def main():
    input_py = "clean_codegen.py"
    output_py = "execute_annotator.py"
    if not os.path.exists(input_py): 
        print(f"❌ Error: '{input_py}' not found.")
        return
    with open(input_py, "r", encoding="utf-8") as f: 
        lines = f.readlines()
        
    new_lines = []
    header_injected = False
    
    # Standard matching for Playwright Actions
    action_pattern = re.compile(r'^(\s*)(page.*?\.(click|fill|press|check|uncheck|hover|dblclick)\((.*?)\))(.*)$')
    
    print(f"\n⚙️ Building Step-by-Step Annotator into '{output_py}'...")
    for line in lines:
        stripped = line.strip()
        
        if not header_injected and not stripped.startswith("import ") and not stripped.startswith("from ") and stripped != "":
            new_lines.append(INJECTION_BLOCK + "\n")
            header_injected = True
            
        if stripped.startswith("def test_"):
            new_lines.append(line)
            indent = "    "
            new_lines.append(f"{indent}page.context.expose_binding('pyLogEvent', handle_js_event)\n")
            new_lines.append(f"{indent}page.context.add_init_script(ANNOTATOR_WIDGET_JS)\n")
            new_lines.append(f"{indent}page.on('response', handle_response)\n")
            new_lines.append(f"{indent}init_kb()\n")
            continue
            
        match = action_pattern.search(line)
        if match:
            indent = match.group(1)
            action_code = match.group(2) # e.g. page.locator("...").click()
            remainder = match.group(5)
            
            # 🔴 Extract components to inject into the safe_annotator_action
            inner_match = re.match(r"^(.*?)\.(click|fill|press|check|uncheck|hover|dblclick)\((.*?)\)$", action_code)
            
            new_lines.append(f"{indent}wait_for_user_approval(page, {repr(action_code)})\n")
            
            if inner_match:
                loc = inner_match.group(1)
                action_name = inner_match.group(2)
                args = inner_match.group(3)
                if args:
                    new_lines.append(f"{indent}safe_annotator_action(page, {loc}, '{action_name}', {repr(action_code)}, {args}){remainder}\n")
                else:
                    new_lines.append(f"{indent}safe_annotator_action(page, {loc}, '{action_name}', {repr(action_code)}){remainder}\n")
            else:
                new_lines.append(f"{indent}{action_code}{remainder}\n")
                
            new_lines.append(f"{indent}time.sleep(0.5)\n")
            continue
            
        if "page.close()" in line:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}page.evaluate('() => window.waitForEnd()')\n")
            new_lines.append(f"{indent}print('\\n✅ Annotation Session Complete. Data saved to test_cases_kb.yaml')\n")
            new_lines.append(line)
            continue
            
        new_lines.append(line)
        
    # Safely close the script at the very end in case page.close() isn't caught
    new_lines.append(f"\n    # --- End of Script Wait ---\n")
    new_lines.append(f"    page.evaluate('() => window.waitForEnd()')\n")
    new_lines.append(f"    print('\\n✅ Annotation Session Complete. Data saved to test_cases_kb.yaml')\n")
        
    with open(output_py, "w", encoding="utf-8") as f: 
        f.writelines(new_lines)
        
    print(f"✅ Annotator Executable saved: {output_py}")

if __name__ == "__main__":
    main()

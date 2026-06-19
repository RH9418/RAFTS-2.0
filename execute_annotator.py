import re

from playwright.sync_api import Page, expect






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

def test_example(page: Page) -> None:
    page.context.expose_binding('pyLogEvent', handle_js_event)
    page.context.add_init_script(ANNOTATOR_WIDGET_JS)
    page.on('response', handle_response)
    init_kb()
    # --- MFA & Login Wait Block ---
    try: page.goto("https://stage.bbu.esp.antuit.ai/dp/demand-planning/executive-dashboard?workbookId=4&tabIndex=1", timeout=0)
    except: pass
    print("\n" + "="*60)
    input("ACTION REQUIRED: Log in, pass MFA, then PRESS [ENTER]...\n")
    print("="*60 + "\n")

    # ============================================================
    # SECTION: Global Filters
    # ============================================================
    wait_for_user_approval(page, 'page.locator(".zeb-filter").click()')
    safe_annotator_action(page, page.locator(".zeb-filter"), 'click', 'page.locator(".zeb-filter").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Hierarchy").click()')
    safe_annotator_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Brand Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Brand Level 4"), 'click', 'page.get_by_text("Brand Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_annotator_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Brand Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Brand Level 4"), 'click', 'page.get_by_text("Brand Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Brand Level 3").click()')
    safe_annotator_action(page, page.get_by_text("Brand Level 3"), 'click', 'page.get_by_text("Brand Level 3").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_annotator_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.partial-selected").click()')
    safe_annotator_action(page, page.locator(".pointer.partial-selected"), 'click', 'page.locator(".pointer.partial-selected").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Brand Level 3").click()')
    safe_annotator_action(page, page.get_by_text("Brand Level 3"), 'click', 'page.get_by_text("Brand Level 3").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Attribute").click()')
    safe_annotator_action(page, page.get_by_text("Attribute"), 'click', 'page.get_by_text("Attribute").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Product Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Product Level 4"), 'click', 'page.get_by_text("Product Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Product Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Product Level 4"), 'click', 'page.get_by_text("Product Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location").click()')
    safe_annotator_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location"), 'click', 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Location").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Hierarchy").click()')
    safe_annotator_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 6").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 6"), 'click', 'page.get_by_text("Sales Level 6").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-checked").first, 'click', 'page.locator(".pointer.custom-checkbox-checked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    safe_annotator_action(page, page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first, 'click', 'page.locator(".filter-values.d-flex.align-items-center.p-l-32.p-r-24 > .custom-checkbox-wrapper > .pointer").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer").click()')
    safe_annotator_action(page, page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer"), 'click', 'page.locator("div:nth-child(5) > .custom-checkbox-wrapper > .pointer").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 6").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 6"), 'click', 'page.get_by_text("Sales Level 6").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 5").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 5"), 'click', 'page.get_by_text("Sales Level 5").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 5").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 5"), 'click', 'page.get_by_text("Sales Level 5").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 4"), 'click', 'page.get_by_text("Sales Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked").first, 'click', 'page.locator(".pointer.custom-checkbox-unchecked").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Sales Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Sales Level 4"), 'click', 'page.get_by_text("Sales Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer").click()')
    safe_annotator_action(page, page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer"), 'click', 'page.locator("esp-simple-side-filter-panel-v1").get_by_text("Customer").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Hierarchy").click()')
    safe_annotator_action(page, page.get_by_text("Hierarchy"), 'click', 'page.get_by_text("Hierarchy").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Customer Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Customer Level 4"), 'click', 'page.get_by_text("Customer Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_text("Customer Level 4").click()')
    safe_annotator_action(page, page.get_by_text("Customer Level 4"), 'click', 'page.get_by_text("Customer Level 4").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.zeb-check").click()')
    safe_annotator_action(page, page.locator(".pointer.zeb-check"), 'click', 'page.locator(".pointer.zeb-check").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply Filters").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply Filters"), 'click', 'page.get_by_role("button", name="Apply Filters").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".pointer.custom-checkbox-unchecked").click()')
    safe_annotator_action(page, page.locator(".pointer.custom-checkbox-unchecked"), 'click', 'page.locator(".pointer.custom-checkbox-unchecked").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply Filters").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply Filters"), 'click', 'page.get_by_role("button", name="Apply Filters").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".filter-icon-wrapper").click()')
    safe_annotator_action(page, page.locator(".filter-icon-wrapper"), 'click', 'page.locator(".filter-icon-wrapper").click()')
    time.sleep(0.5)

    # ============================================================
    # SECTION: Alert Types
    # ============================================================
    wait_for_user_approval(page, 'page.locator(".dropdown-caret").first.click()')
    safe_annotator_action(page, page.locator(".dropdown-caret").first, 'click', 'page.locator(".dropdown-caret").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1).click()')
    safe_annotator_action(page, page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^Under Bias$")).nth(1).click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".dropdown-caret").first.click()')
    safe_annotator_action(page, page.locator(".dropdown-caret").first, 'click', 'page.locator(".dropdown-caret").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1).click()')
    safe_annotator_action(page, page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^MAPE$")).nth(1).click()')
    time.sleep(0.5)

    # ============================================================
    # SECTION: Alerts Sumary
    # ============================================================
    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    safe_annotator_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").click()')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'click', 'page.get_by_role("spinbutton", name="Filter Value").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("129406")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("129406")', "129406")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("-6.5")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("-6.5")', "-6.5")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("21")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("21")', "21")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("option", name="Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("7.2")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("7.2")', "7.2")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Stability Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("10")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10")', "10")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("option", name="Less than or equal to").click()')
    safe_annotator_action(page, page.get_by_role("option", name="Less than or equal to"), 'click', 'page.get_by_role("option", name="Less than or equal to").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div:nth-child(7) > .ag-column-select-column").click()')
    safe_annotator_action(page, page.locator("div:nth-child(7) > .ag-column-select-column"), 'click', 'page.locator("div:nth-child(7) > .ag-column-select-column").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("380906")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("380906")', "380906")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("384298")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("384298")', "384298")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper").check()')
    safe_annotator_action(page, page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper"), 'check', 'page.locator("div:nth-child(14) > .ag-column-select-column > .ag-column-select-checkbox > .ag-wrapper").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("#ag-2417-input").check()')
    safe_annotator_action(page, page.locator("#ag-2417-input"), 'check', 'page.locator("#ag-2417-input").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("#ag-2415-input").check()')
    safe_annotator_action(page, page.locator("#ag-2415-input"), 'check', 'page.locator("#ag-2415-input").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("#ag-2413-input").check()')
    safe_annotator_action(page, page.locator("#ag-2413-input"), 'check', 'page.locator("#ag-2413-input").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("100")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("100")', "100")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("option", name="Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("200")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("200")', "200")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("383")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("383")', "383")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Reset"), 'click', 'page.get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("a").filter(has_text="2").click()')
    safe_annotator_action(page, page.locator("a").filter(has_text="2"), 'click', 'page.locator("a").filter(has_text="2").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("a").filter(has_text="1").click()')
    safe_annotator_action(page, page.locator("a").filter(has_text="1"), 'click', 'page.locator("a").filter(has_text="1").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".d-flex > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("View 20 row(s)").click()')
    safe_annotator_action(page, page.get_by_text("View 20 row(s)"), 'click', 'page.get_by_text("View 20 row(s)").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()')
    safe_annotator_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'check', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns"), 'click', 'page.get_by_role("button", name="\ue0bccolumns").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".pointer.zeb-adjustments").click()')
    safe_annotator_action(page, page.locator(".pointer.zeb-adjustments"), 'click', 'page.locator(".pointer.zeb-adjustments").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Save Preference").click()')
    safe_annotator_action(page, page.get_by_text("Save Preference"), 'click', 'page.get_by_text("Save Preference").click()')
    time.sleep(0.5)

    with page.expect_download() as download_info:

        wait_for_user_approval(page, 'page.locator(".icon-color-toolbar-active.zeb-download-underline").click()')
        safe_annotator_action(page, page.locator(".icon-color-toolbar-active.zeb-download-underline"), 'click', 'page.locator(".icon-color-toolbar-active.zeb-download-underline").click()')
        time.sleep(0.5)

    download = download_info.value

    wait_for_user_approval(page, 'page.locator(".pointer.zeb-adjustments").click()')
    safe_annotator_action(page, page.locator(".pointer.zeb-adjustments"), 'click', 'page.locator(".pointer.zeb-adjustments").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Reset Preference").click()')
    safe_annotator_action(page, page.get_by_text("Reset Preference"), 'click', 'page.get_by_text("Reset Preference").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')
    safe_annotator_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("span").filter(has_text="WALMART STORES HQ").first.click(button="right")')
    safe_annotator_action(page, page.locator("span").filter(has_text="WALMART STORES HQ").first, 'click', 'page.locator("span").filter(has_text="WALMART STORES HQ").first.click(button="right")', button="right")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Drill down").click()')
    safe_annotator_action(page, page.get_by_text("Drill down"), 'click', 'page.get_by_text("Drill down").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("span").filter(has_text="WALMART").first.click(button="right")')
    safe_annotator_action(page, page.locator("span").filter(has_text="WALMART").first, 'click', 'page.locator("span").filter(has_text="WALMART").first.click(button="right")', button="right")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Drill up").click()')
    safe_annotator_action(page, page.get_by_text("Drill up"), 'click', 'page.get_by_text("Drill up").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')
    safe_annotator_action(page, page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked)   WALMART STORES HQ").get_by_label("Press Space to toggle row"), 'check', 'page.get_by_role("gridcell", name="Press Space to toggle row selection (unchecked) \uf127 \ue03d WALMART STORES HQ").get_by_label("Press Space to toggle row").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")', "10000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("option", name="Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("20")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20")', "20")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("option", name="Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_role("option", name="Greater than or equal to"), 'click', 'page.get_by_role("option", name="Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("20")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20")', "20")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-cell-filtered.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    safe_annotator_action(page, page.get_by_role("button", name="columns").nth(1), 'click', 'page.get_by_role("button", name="\ue0bccolumns").nth(1).click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User MAPE Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="User Bias Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("1000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("1000")', "1000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Reset"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Reset").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("20000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("20000")', "20000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon"), 'click', 'page.locator(".ag-header-icon.ag-header-cell-filter-button.ag-filter-active > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Apply Reset Clear").click()')
    safe_annotator_action(page, page.get_by_text("Apply Reset Clear"), 'click', 'page.get_by_text("Apply Reset Clear").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("100000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("100000")', "100000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    safe_annotator_action(page, page.locator(".ag-icon.ag-icon-small-down").first, 'click', 'page.locator(".ag-icon.ag-icon-small-down").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Greater than or equal to").click()')
    safe_annotator_action(page, page.get_by_text("Greater than or equal to"), 'click', 'page.get_by_text("Greater than or equal to").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("65000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("65000")', "65000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-column-last.ag-header-parent-hidden.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")')
    safe_annotator_action(page, page.get_by_role("spinbutton", name="Filter Value"), 'fill', 'page.get_by_role("spinbutton", name="Filter Value").fill("10000")', "10000")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="6W-System Forecast Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Forecast Value Add - MAPE").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-User Forecast Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="13W-Actuals Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("#ag-6862-input").check()')
    safe_annotator_action(page, page.locator("#ag-6862-input"), 'check', 'page.locator("#ag-6862-input").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("#ag-6860-input").check()')
    safe_annotator_action(page, page.locator("#ag-6860-input"), 'check', 'page.locator("#ag-6860-input").check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(12) > .ag-column-select-column").click()')
    safe_annotator_action(page, page.locator("div:nth-child(12) > .ag-column-select-column"), 'click', 'page.locator("div:nth-child(12) > .ag-column-select-column").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    safe_annotator_action(page, page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator("div:nth-child(3) > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first.click()')
    safe_annotator_action(page, page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first, 'click', 'page.locator("div").filter(has_text=re.compile(r"^Save Preference$")).first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".checkbox-primary-color").first.check()')
    safe_annotator_action(page, page.locator(".checkbox-primary-color").first, 'check', 'page.locator(".checkbox-primary-color").first.check()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")')
    safe_annotator_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")', button="right")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Drill down").click()')
    safe_annotator_action(page, page.get_by_text("Drill down"), 'click', 'page.get_by_text("Drill down").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")')
    safe_annotator_action(page, page.locator("span").filter(has_text="BARCEL").first, 'click', 'page.locator("span").filter(has_text="BARCEL").first.click(button="right")', button="right")
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Drill up").click()')
    safe_annotator_action(page, page.get_by_text("Drill up"), 'click', 'page.get_by_text("Drill up").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_role("button", name="Apply"), 'click', 'page.get_by_role("button", name="Apply").click()')
    time.sleep(0.5)



    # ============================================================
    # SECTION: Weekly Summary Section
    # ============================================================


    wait_for_user_approval(page, 'page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator("#time-filterId > .wr-20 > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1).click()')
    safe_annotator_action(page, page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^Latest 5 Next 4$")).nth(1).click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    safe_annotator_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    safe_annotator_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    safe_annotator_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first, 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')
    safe_annotator_action(page, page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', 'page.locator(".ag-row-even.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')
    safe_annotator_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right"), 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-0.ag-row-group.ag-row-group-contracted > .ag-cell-value > .ag-cell-wrapper > .ag-group-contracted > .zeb-chevron-right").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".wr-20.font-weight-normal > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first, 'click', 'page.locator(".d-flex.dropdown-option.align-items-center.p-v-5.p-l-32 > .d-flex").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(2) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(2) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(3) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(3) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(4) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(4) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(5) > .d-flex").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(5) > .d-flex"), 'click', 'page.locator(".overflow-auto > div:nth-child(5) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(6) > .d-flex").click()')
    safe_annotator_action(page, page.locator("div:nth-child(6) > .d-flex"), 'click', 'page.locator("div:nth-child(6) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(7)").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', 'page.locator(".overflow-auto > div:nth-child(7)").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(8) > .d-flex").click()')
    safe_annotator_action(page, page.locator("div:nth-child(8) > .d-flex"), 'click', 'page.locator("div:nth-child(8) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.zeb-check").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(9) > .d-flex").click()')
    safe_annotator_action(page, page.locator("div:nth-child(9) > .d-flex"), 'click', 'page.locator("div:nth-child(9) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("div:nth-child(10) > .d-flex").click()')
    safe_annotator_action(page, page.locator("div:nth-child(10) > .d-flex"), 'click', 'page.locator("div:nth-child(10) > .d-flex").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("All").nth(3).click()')
    safe_annotator_action(page, page.get_by_text("All").nth(3), 'click', 'page.get_by_text("All").nth(3).click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')
    safe_annotator_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-12-21 (52) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-12-28 (01) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)"), 'uncheck', 'page.get_by_role("treeitem", name="-01-04 (02) Column").get_by_label("Press SPACE to toggle visibility (visible)").uncheck()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')
    safe_annotator_action(page, page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Weekly Summary Customer:").get_by_role("button").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("svg").get_by_text("User Forecast Total").click()')
    safe_annotator_action(page, page.locator("svg").get_by_text("User Forecast Total"), 'click', 'page.locator("svg").get_by_text("User Forecast Total").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("svg").get_by_text("User Override Total").click()')
    safe_annotator_action(page, page.locator("svg").get_by_text("User Override Total"), 'click', 'page.locator("svg").get_by_text("User Override Total").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("svg").get_by_text("Aged Net Units").click()')
    safe_annotator_action(page, page.locator("svg").get_by_text("Aged Net Units"), 'click', 'page.locator("svg").get_by_text("Aged Net Units").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(7)").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(7)"), 'click', 'page.locator(".overflow-auto > div:nth-child(7)").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".overflow-auto > div:nth-child(8)").click()')
    safe_annotator_action(page, page.locator(".overflow-auto > div:nth-child(8)"), 'click', 'page.locator(".overflow-auto > div:nth-child(8)").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    safe_annotator_action(page, page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first, 'click', 'page.locator(".d-flex.flex-column.justify-content-center.font-size-10.align-items-center.checkbox-v2.m-r-10.deselected").first.click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator(".ellipses > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator("path:nth-child(78)").click()')
    safe_annotator_action(page, page.locator("path:nth-child(78)"), 'click', 'page.locator("path:nth-child(78)").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    safe_annotator_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Save Preference").click()')
    safe_annotator_action(page, page.get_by_text("Save Preference"), 'click', 'page.get_by_text("Save Preference").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    safe_annotator_action(page, page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer"), 'click', 'page.locator(".title.d-flex.align-items-center.font-size-16.font-weight-bold.nunito.title-color > .grid-icons-container > esp-grid-icons-component > .display-grid-icons > div > #preference-iconId > .legend-font > .multiselect-dropdown > .pointer").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.get_by_text("Reset Preference").click()')
    safe_annotator_action(page, page.get_by_text("Reset Preference"), 'click', 'page.get_by_text("Reset Preference").click()')
    time.sleep(0.5)

    wait_for_user_approval(page, 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div").click()')
    safe_annotator_action(page, page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div"), 'click', 'page.locator(".ag-row-odd.ag-row-no-focus.ag-row-not-inline-editing.ag-row.ag-row-level-1.ag-row-position-absolute.ag-row-hover > div:nth-child(4) > span > div").click()')
    time.sleep(0.5)

    # ============================================================
    # SECTION: Events Grid
    # ============================================================
    wait_for_user_approval(page, 'page.locator("div:nth-child(4) > span > .align-middle").click()')
    safe_annotator_action(page, page.locator("div:nth-child(4) > span > .align-middle"), 'click', 'page.locator("div:nth-child(4) > span > .align-middle").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content").click()')
    safe_annotator_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content"), 'click', 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("textbox", name="Filter Value").fill("Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")')
    safe_annotator_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', 'page.get_by_role("textbox", name="Filter Value").fill("Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")', "Promotion-WM BARCEL TAKIS 10CT ROLLBACK 122925 TO 033026")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click(button="right")')
    safe_annotator_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click(button="right")', button="right")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click()')
    safe_annotator_action(page, page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1), 'click', 'page.get_by_role("gridcell", name="Promotion-WM BARCEL TAKIS").nth(1).click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    safe_annotator_action(page, page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon"), 'click', 'page.locator(".ag-header-cell.ag-header-parent-hidden.ag-header-cell-sortable.ag-header-background.ag-focus-managed.ag-header-active > .ag-header-cell-comp-wrapper > .ag-cell-label-container > .ag-header-icon > .ag-icon").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("textbox", name="Filter Value").fill("TOR")')
    safe_annotator_action(page, page.get_by_role("textbox", name="Filter Value"), 'fill', 'page.get_by_role("textbox", name="Filter Value").fill("TOR")', "TOR")
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    safe_annotator_action(page, page.get_by_label("Column Filter").get_by_role("button", name="Apply"), 'click', 'page.get_by_label("Column Filter").get_by_role("button", name="Apply").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("a").nth(2).click()')
    safe_annotator_action(page, page.locator("a").nth(2), 'click', 'page.locator("a").nth(2).click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    safe_annotator_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    safe_annotator_action(page, page.get_by_role("checkbox", name="Toggle All Columns Visibility"), 'uncheck', 'page.get_by_role("checkbox", name="Toggle All Columns Visibility").uncheck()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Event Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="UPC 12 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    safe_annotator_action(page, page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)"), 'check', 'page.get_by_role("treeitem", name="Customer Level 2 Column").get_by_label("Press SPACE to toggle visibility (hidden)").check()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    safe_annotator_action(page, page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button"), 'click', 'page.locator("esp-card-component").filter(has_text="Event Details columns (0)").get_by_role("button").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    safe_annotator_action(page, page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret"), 'click', 'page.locator("div:nth-child(7) > div > esp-grid-container > esp-card-component > .card-container > .card-content > esp-row-dimentional-grid > div > #paginationId > esp-pagination-v2 > .d-flex.w-100 > span:nth-child(3) > esp-multiselect-dropdown > .multiselect-dropdown > div > .w-100 > .d-flex.align-items-center > .dropdown-caret").click()')
    time.sleep(0.5)
    wait_for_user_approval(page, 'page.locator("div").filter(has_text=re.compile(r"^View 20 row\\(s\\)$")).nth(1).click()')
    safe_annotator_action(page, page.locator("div").filter(has_text=re.compile(r"^View 20 row\(s\)$")).nth(1), 'click', 'page.locator("div").filter(has_text=re.compile(r"^View 20 row\\(s\\)$")).nth(1).click()')
    time.sleep(0.5)


    # --- End of Script Wait ---
    page.evaluate('() => window.waitForEnd()')
    print('\n✅ Annotation Session Complete. Data saved to test_cases_kb.yaml')

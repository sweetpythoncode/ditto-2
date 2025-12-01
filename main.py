import os
import sys
import json
import importlib
import traceback
from threading import Thread
from time import sleep
from flask import Flask, Blueprint, request, render_template, render_template_string, jsonify
from litellm import completion, supports_function_calling

app = Flask(__name__)

MODEL_NAME = "gpt-5-mini"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ROUTES_DIR = os.path.join(BASE_DIR, "routes")
AGENTS_DOC_PATH = os.path.join(BASE_DIR, "agents.md")
CONTEXT_DOC_PATH = os.path.join(BASE_DIR, "builder_context.md")
LOG_FILE = "flask_app_builder_log.json"

progress = {
    "status": "idle",
    "iteration": 0,
    "max_iterations": 50,
    "output": "",
    "completed": False,
}

def resolve_path(path):
    if not isinstance(path, str):
        return None
    path = path.strip().lstrip("./").rstrip("/")

    if path == "agents.md":
        return AGENTS_DOC_PATH
    if path == "builder_context.md":
        return CONTEXT_DOC_PATH
    if path == "templates":
        return TEMPLATES_DIR
    if path == "static":
        return STATIC_DIR
    if path == "routes":
        return ROUTES_DIR

    if path.startswith("templates/"):
        base = TEMPLATES_DIR
        rel = path[len("templates/"):]
    elif path.startswith("static/"):
        base = STATIC_DIR
        rel = path[len("static/"):]
    elif path.startswith("routes/"):
        base = ROUTES_DIR
        rel = path[len("routes/"):]
    else:
        return None

    if ".." in rel.split(os.path.sep):
        return None

    full = os.path.abspath(os.path.join(base, rel))
    if not full.startswith(BASE_DIR):
        return None
    return full

def create_directory(path):
    try:
        resolved = resolve_path(path)
        if not resolved:
            return f"Path not allowed: {path}"
        os.makedirs(resolved, exist_ok=True)
        if os.path.abspath(resolved) == os.path.abspath(ROUTES_DIR):
            init_path = os.path.join(ROUTES_DIR, "__init__.py")
            if not os.path.exists(init_path):
                with open(init_path, "w", encoding="utf-8") as f:
                    f.write("")
        return f"Created directory: {resolved}"
    except Exception as e:
        return f"Error creating directory {path}: {e}"

def create_file(path, content):
    try:
        resolved = resolve_path(path)
        if not resolved:
            return f"Path not allowed: {path}"
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created file: {resolved}"
    except Exception as e:
        return f"Error creating/updating file {path}: {e}"

def update_file(path, content):
    try:
        resolved = resolve_path(path)
        if not resolved:
            return f"Path not allowed: {path}"
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Updated file: {resolved}"
    except Exception as e:
        return f"Error updating file {path}: {e}"

def fetch_code(file_path):
    try:
        resolved = resolve_path(file_path)
        if not resolved:
            return f"Path not allowed: {file_path}"
    except Exception:
        return f"Path not allowed: {file_path}"
    if not os.path.exists(resolved):
        return f"File not found: {file_path}"
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error fetching code from {file_path}: {e}"

def log_to_file(history_dict):
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as log_file:
            json.dump(history_dict, log_file, indent=4)
    except Exception:
        pass

def task_completed():
    progress["status"] = "completed"
    progress["completed"] = True
    return "Task marked as completed."

def load_routes():
    try:
        if not os.path.exists(ROUTES_DIR):
            print("No routes directory; nothing to load.")
            return "Routes directory does not exist; nothing to load."

        if BASE_DIR not in sys.path:
            sys.path.append(BASE_DIR)

        try:
            importlib.invalidate_caches()
            routes_pkg = importlib.import_module("routes")
            routes_pkg = importlib.reload(routes_pkg)
            if hasattr(routes_pkg, "register_blueprints") and callable(routes_pkg.register_blueprints):
                try:
                    routes_pkg.register_blueprints(app)
                except Exception as e:
                    print("Error in routes.register_blueprints:", e)
            blueprints_attr = getattr(routes_pkg, "blueprints", None)
            if blueprints_attr:
                try:
                    for bp in blueprints_attr:
                        if isinstance(bp, Blueprint) and bp.name not in app.blueprints:
                            app.register_blueprint(bp)
                except Exception as e:
                    print("Error registering blueprints list from routes:", e)
        except Exception as e:
            print("Error importing routes package:", e)

        for filename in os.listdir(ROUTES_DIR):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                module_path = f"routes.{module_name}"
                try:
                    if module_path in sys.modules:
                        module = importlib.reload(sys.modules[module_path])
                    else:
                        module = importlib.import_module(module_path)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, Blueprint) and attr.name not in app.blueprints:
                            app.register_blueprint(attr)
                except Exception as e:
                    print(f"Error importing module {module_path}: {e}")
                    continue

        print("Routes loaded successfully.")
        return "Routes loaded."
    except Exception as e:
        print("Error in load_routes:", e)
        return f"Error loading routes: {e}"

def ensure_initial_structure():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(ROUTES_DIR, exist_ok=True)
    init_path = os.path.join(ROUTES_DIR, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w", encoding="utf-8") as f:
            f.write("")
    if not os.path.exists(AGENTS_DOC_PATH):
        initial_agents = (
            "# Agent Architecture\n\n"
            "## App Summary\n"
            "- Purpose: (to be filled by the assistant)\n\n"
            "## Routes\n"
            "(will be filled as routes are created)\n\n"
            "## Templates\n"
            "(will be filled as templates are created)\n\n"
            "## Static Assets\n"
            "(will be filled as static files are created)\n\n"
            "## Important Variables & Config\n"
            "(model, flags, etc.)\n\n"
            "## Build History\n"
            "(ordered steps describing what was done)\n\n"
            "## TODO / Future Improvements\n"
            "- [ ] (assistant to add items)\n"
        )
        update_file("agents.md", initial_agents)
    if not os.path.exists(CONTEXT_DOC_PATH):
        initial_context = (
            "# Builder Context\n\n"
            "## High-Level Plan\n"
            "- (Describe the app, architecture, and main ideas here.)\n\n"
            "## Task List\n"
            "- [ ] Define or refine the architecture and main components.\n"
            "- [ ] Implement the main entry template (templates/index.html).\n"
            "- [ ] Implement core routes and blueprints.\n"
            "- [ ] Implement core static assets (CSS/JS).\n"
            "- [ ] Wire everything together and verify end-to-end.\n\n"
            "## Notes\n"
            "- Use this file to track granular tasks and decisions.\n"
        )
        update_file("builder_context.md", initial_context)
    load_routes()

ensure_initial_structure()

available_functions = {
    "create_directory": create_directory,
    "create_file": create_file,
    "update_file": update_file,
    "fetch_code": fetch_code,
    "task_completed": task_completed,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Creates a new directory under templates/, static/, or routes/ using a relative path (e.g. 'templates', 'static/js').",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path, such as 'templates', 'static', 'routes', or a subdirectory like 'templates/components'."
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Creates or overwrites a file with the given content under templates/, static/, routes/, or agents/builder_context files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path, e.g. 'templates/index.html', 'routes/game.py', 'static/js/app.js', 'agents.md', or 'builder_context.md'."
                    },
                    "content": {
                        "type": "string",
                        "description": "The full file content to write."
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_file",
            "description": "Updates an existing file (or creates it) with new content under templates/, static/, routes/, agents.md, or builder_context.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path, e.g. 'templates/game.html', 'routes/api.py', 'agents.md', or 'builder_context.md'."
                    },
                    "content": {
                        "type": "string",
                        "description": "The new full file content."
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_code",
            "description": "Reads a file so you can inspect its current contents before updating it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path, e.g. 'routes/game.py', 'templates/index.html', 'agents.md', or 'builder_context.md'."
                    }
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_completed",
            "description": "Call this only when the app is fully built and works end-to-end from '/' (shell) and '/app' (index.html).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

CORE_SYSTEM_PROMPT = (
    "You are an expert Flask developer and architect. You are building a single Flask application in this environment, "
    "using a single long-running conversation.\n\n"
    "Routing and entrypoint:\n"
    "- The main script defines two special routes:\n"
    "  - '/' is a wrapper shell that shows the app in an iframe and keeps a floating builder panel available.\n"
    "  - '/app' is the main entrypoint for the generated app, which renders 'templates/index.html' via Flask's Jinja engine.\n"
    "- You must not create Blueprints or routes on '/' or '/app'. Use other paths such as '/game', '/dashboard', '/api/...'.\n"
    "- You MUST create and maintain 'templates/index.html' as the canonical main entry point for the app. '/app' will render this file.\n"
    "- If you create additional pages (for example '/game' with 'templates/game.html'), you must ensure that 'index.html' links to them, embeds them, "
    "or otherwise makes the main user journey start from '/app'.\n\n"
    "Templates and static assets:\n"
    "- Templates live under templates/ and are rendered with Jinja2 via render_template.\n"
    "- You may safely use Jinja2 syntax such as {{ url_for('static', filename='css/style.css') }} inside templates.\n"
    "- Static assets (CSS, JS, images) must live under static/ and be referenced with url_for('static', filename='...').\n"
    "- Write real HTML, CSS, and JS. Avoid vague placeholders like 'content goes here'; make pages and interactions actually usable.\n\n"
    "Filesystem and structure:\n"
    "- templates/ : HTML templates, including 'index.html' as the main entrypoint.\n"
    "- static/    : CSS, JS, images.\n"
    "- routes/    : Python modules containing Flask Blueprints for additional routes.\n"
    "- agents.md  : A markdown document at the project root that you maintain as the canonical architecture record.\n"
    "- builder_context.md : A markdown document that holds your high-level plan and a granular task list.\n\n"
    "You must maintain 'agents.md' with:\n"
    "- App summary (purpose, key features, main flows).\n"
    "- Routes (files, blueprints, URL rules, and a short description of each).\n"
    "- Templates (files and their roles; which routes use them).\n"
    "- Static assets (key CSS/JS files and their responsibilities).\n"
    "- Important variables and configuration notes.\n"
    "- Build history: an ordered list of what you have implemented so far.\n"
    "- TODOs / future improvements with checkboxes.\n\n"
    "You must also maintain 'builder_context.md' as your own working memory, including:\n"
    "- A high-level plan for the app.\n"
    "- A detailed task list broken into small, focused tasks.\n"
    "- For each iteration, you should:\n"
    "  1) Read builder_context.md (via fetch_code) to recall the current plan and tasks.\n"
    "  2) Update builder_context.md (via update_file) to refine the plan and task list.\n"
    "  3) Select one or a small cluster of closely related tasks, and work on them using tools.\n"
    "  4) When you complete a task, mark it as done in builder_context.md before moving on.\n\n"
    "Process and behavior:\n"
    "1) Carefully understand the user's description of the app, including desired pages, interactions, and data flows.\n"
    "2) Plan the structure before coding: list the routes, templates, and static assets you intend to create, and how they connect. "
    "Write this plan and task list into builder_context.md.\n"
    "3) Implement step-by-step using the provided tools to create directories, create files, update files, and inspect files. "
    "Never just print JSON that looks like a tool call; you must actually call the tools.\n"
    "4) Prefer to create or update ONE file per tool call. If you need multiple files, make multiple tool calls, one per file.\n"
    "5) Keep 'agents.md' up to date as you add or modify routes, templates, or static files. Treat it as the source of truth for the final architecture.\n"
    "6) Do NOT modify this main script. Only work within templates/, static/, routes/, agents.md, and builder_context.md via the tools.\n"
    "7) Use relative paths such as 'templates/index.html', 'routes/game.py', 'static/css/style.css', 'agents.md', or 'builder_context.md' when calling tools.\n"
    "8) After each meaningful change, consider whether 'agents.md' and 'builder_context.md' should reflect the update and edit them accordingly.\n"
    "9) Before calling task_completed(), mentally simulate loading '/' in a browser, which loads '/app' in an iframe, "
    "and walking through the main user flow. Ensure the app is actually usable end-to-end. For interactive apps (games, dashboards, forms), "
    "ensure the interaction actually works, not just a static screen.\n"
    "10) Only when you are confident the application is complete, coherent, and functional should you call task_completed().\n\n"
    "You may think out loud in your assistant messages to explain what you are doing and why, but all code and files must be written or updated via the tools."
)

def run_main_loop(user_input):
    history_dict = {"iterations": []}
    if not supports_function_calling(MODEL_NAME):
        progress["status"] = "error"
        progress["output"] = "Model does not support function calling."
        progress["completed"] = True
        return "Model does not support function calling."

    max_iterations = progress.get("max_iterations", 50)
    iteration = 0

    try:
        with open(AGENTS_DOC_PATH, "r", encoding="utf-8") as f:
            agents_doc_content = f.read()
    except Exception:
        agents_doc_content = ""

    try:
        with open(CONTEXT_DOC_PATH, "r", encoding="utf-8") as f:
            context_doc_content = f.read()
    except Exception:
        context_doc_content = ""

    messages = [
        {"role": "system", "content": CORE_SYSTEM_PROMPT},
        {"role": "system", "content": f"Current agents.md:\n\n{agents_doc_content}"},
        {"role": "system", "content": f"Current builder_context.md:\n\n{context_doc_content}"},
        {"role": "user", "content": user_input},
    ]

    output_html = ""

    while iteration < max_iterations:
        progress["iteration"] = iteration + 1
        progress["status"] = "running"

        current_iteration = {
            "iteration": iteration + 1,
            "llm_responses": [],
            "tool_results": [],
            "errors": [],
        }
        history_dict["iterations"].append(current_iteration)

        try:
            response = completion(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            choices = getattr(response, "choices", [])
            if not choices or not choices[0].message:
                error = getattr(response, "error", "Unknown error from LLM.")
                current_iteration["errors"].append(
                    {"action": "llm_completion", "error": str(error)}
                )
                log_to_file(history_dict)
                sleep(2)
                iteration += 1
                continue

            response_message = choices[0].message
            content = response_message.content or ""
            current_iteration["llm_responses"].append(content)

            output_html += f"<section><h2>Iteration {iteration + 1}</h2>\n"
            tool_calls = response_message.tool_calls

            if tool_calls:
                if content.strip():
                    output_html += "<h4>Assistant Plan / Thoughts</h4>\n<div>" + content + "</div>\n"
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions.get(function_name)

                    if not function_to_call:
                        error_message = f"Tool '{function_name}' is not available."
                        current_iteration["errors"].append(
                            {
                                "action": f"tool_call_{function_name}",
                                "error": error_message,
                                "traceback": "No traceback available.",
                            }
                        )
                        continue

                    try:
                        function_args = json.loads(tool_call.function.arguments or "{}")
                    except Exception as parse_err:
                        error_message = f"Error parsing arguments for {function_name}: {parse_err}"
                        current_iteration["errors"].append(
                            {
                                "action": f"tool_call_{function_name}",
                                "error": error_message,
                                "traceback": traceback.format_exc(),
                            }
                        )
                        continue

                    try:
                        function_response = function_to_call(**function_args)
                        current_iteration["tool_results"].append(
                            {"tool": function_name, "result": function_response}
                        )
                        output_html += (
                            f"<h5>Tool Result ({function_name})</h5>\n"
                            f"<pre>{function_response}</pre>\n"
                        )
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": str(function_response),
                            }
                        )
                        if function_name == "task_completed":
                            progress["status"] = "completed"
                            progress["completed"] = True
                            output_html += "<h3>COMPLETE</h3>\n"
                            output_html += "</section>"
                            progress["output"] = output_html
                            log_to_file(history_dict)
                            load_routes()
                            return output_html
                    except Exception as tool_error:
                        error_message = f"Error executing {function_name}: {tool_error}"
                        current_iteration["errors"].append(
                            {
                                "action": f"tool_call_{function_name}",
                                "error": error_message,
                                "traceback": traceback.format_exc(),
                            }
                        )
            else:
                if content.strip():
                    output_html += "<h4>Assistant Response</h4>\n<div>" + content + "</div>\n"
                messages.append(response_message)

            output_html += "</section>"
            progress["output"] = output_html

        except Exception as e:
            current_iteration["errors"].append(
                {
                    "action": "main_loop",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )

        iteration += 1
        log_to_file(history_dict)
        sleep(2)

    progress["status"] = "completed"
    progress["completed"] = True
    output_html += "<section><h2>Stopped</h2><div>Reached max iterations without task_completed().</div></section>\n"
    progress["output"] = output_html
    log_to_file(history_dict)
    return output_html

@app.route("/")
def shell():
    has_index = os.path.exists(os.path.join(TEMPLATES_DIR, "index.html"))
    return render_template_string(
        """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Flask App Builder Shell</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" href="https://unpkg.com/milligram@1.4.1/dist/milligram.min.css">
            <style>
                html, body {
                    margin: 0;
                    padding: 0;
                    height: 100%;
                    width: 100%;
                    overflow: hidden;
                    background: #f5f5f5;
                }
                #app-frame {
                    border: none;
                    width: 100vw;
                    height: 100vh;
                }
                #builder-panel {
                    position: fixed;
                    top: 0;
                    right: 0;
                    width: 420px;
                    max-width: 100%;
                    height: 100%;
                    background: #ffffff;
                    box-shadow: -2px 0 8px rgba(0,0,0,0.15);
                    transform: translateX(100%);
                    transition: transform 0.25s ease-out;
                    display: flex;
                    flex-direction: column;
                    z-index: 9998;
                }
                #builder-panel.open {
                    transform: translateX(0);
                }
                #builder-header {
                    padding: 0.75rem 1rem;
                    border-bottom: 1px solid #eee;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 0.9rem;
                    background: #fafafa;
                }
                #builder-iframe {
                    border: none;
                    width: 100%;
                    height: calc(100% - 42px);
                }
                #builder-toggle {
                    position: fixed;
                    bottom: 16px;
                    right: 16px;
                    width: 56px;
                    height: 56px;
                    border-radius: 50%;
                    border: none;
                    background: #111;
                    color: #fff;
                    font-size: 26px;
                    cursor: pointer;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
                    z-index: 9999;
                }
                @media (max-width: 600px) {
                    #builder-panel {
                        width: 100%;
                    }
                    #builder-toggle {
                        width: 52px;
                        height: 52px;
                        font-size: 24px;
                    }
                }
            </style>
        </head>
        <body>
            <iframe id="app-frame" src="/app"></iframe>
            <div id="builder-panel">
                <div id="builder-header">
                    <span>App Builder / Logs</span>
                    <button id="builder-close" class="button button-clear">&times;</button>
                </div>
                <iframe id="builder-iframe" src="/builder"></iframe>
            </div>
            <button id="builder-toggle">🛠</button>
            <script>
                const panel = document.getElementById('builder-panel');
                const toggle = document.getElementById('builder-toggle');
                const closeBtn = document.getElementById('builder-close');
                toggle.addEventListener('click', () => panel.classList.toggle('open'));
                closeBtn.addEventListener('click', () => panel.classList.remove('open'));
                if (!{{ has_index|tojson }}) {
                    panel.classList.add('open');
                }
            </script>
        </body>
        </html>
        """,
        has_index=has_index,
    )

@app.route("/app")
def app_entry():
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        return render_template("index.html")
    return "<h2 style='font-family: system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; padding: 1rem;'>No app built yet. Open the builder panel and describe the app you want.</h2>"

@app.route("/builder", methods=["GET", "POST"])
def builder():
    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            progress["status"] = "running"
            progress["iteration"] = 0
            progress["output"] = ""
            progress["completed"] = False
            thread = Thread(target=run_main_loop, args=(user_input,))
            thread.daemon = True
            thread.start()
    return render_template_string(
        """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Flask App Builder</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" href="https://unpkg.com/milligram@1.4.1/dist/milligram.min.css">
            <style>
                body {
                    padding: 1rem;
                    font-size: 0.9rem;
                }
                textarea {
                    width: 100%;
                    min-height: 120px;
                }
                #status {
                    font-size: 0.85rem;
                    color: #555;
                    margin-bottom: 0.5rem;
                }
                #log {
                    margin-top: 1rem;
                    padding: 0.75rem;
                    background: #f9f9f9;
                    border-radius: 4px;
                    border: 1px solid #eee;
                    max-height: 50vh;
                    overflow-y: auto;
                    font-size: 0.8rem;
                }
                #log section {
                    margin-bottom: 0.75rem;
                    border-bottom: 1px dashed #ddd;
                    padding-bottom: 0.5rem;
                }
                #log h2 {
                    margin: 0 0 0.25rem;
                    font-size: 1rem;
                }
                #log h4 {
                    margin: 0.25rem 0;
                    font-size: 0.9rem;
                }
                #log pre {
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    background: #fff;
                    border-radius: 3px;
                    padding: 0.5rem;
                    border: 1px solid #eee;
                }
                #refresh-btn {
                    display: none;
                    margin-top: 0.5rem;
                }
            </style>
        </head>
        <body>
            <h3>Flask App Builder</h3>
            <div id="status">Status: idle</div>
            <p>Describe the Flask app you want to create or how you want to update it. You can keep chatting to refine and extend the app.</p>
            <form method="post">
                <textarea name="user_input"></textarea><br>
                <button type="submit" class="button">Build / Update App</button>
            </form>
            <h4>Latest Build Log</h4>
            <div id="log"></div>
            <button id="refresh-btn" class="button button-outline">Refresh App</button>
            <script>
                let refreshed = false;
                function tick(){
                    fetch('/progress')
                        .then(r => r.json())
                        .then(d => {
                            document.getElementById('log').innerHTML = d.output || '';
                            document.getElementById('status').textContent = 'Status: ' + (d.status || 'unknown');
                            if (d.completed) {
                                document.getElementById('refresh-btn').style.display = 'inline-block';
                                if (!refreshed) {
                                    refreshed = true;
                                    try {
                                        const appFrame = window.parent.document.getElementById('app-frame');
                                        if (appFrame) appFrame.src = appFrame.src;
                                    } catch(e) {}
                                }
                            }
                        });
                }
                setInterval(tick, 2000);
                tick();
                document.getElementById('refresh-btn').onclick = function(){
                    try {
                        const appFrame = window.parent.document.getElementById('app-frame');
                        if (appFrame) appFrame.src = appFrame.src;
                    } catch(e) {}
                };
            </script>
        </body>
        </html>
        """
    )

@app.route("/progress")
def get_progress():
    return jsonify(progress)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

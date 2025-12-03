# Flask App Builder (LLM-Powered)

This project is a self-building Flask app generator.

You describe the app you want in natural language, and an LLM (via LiteLLM) iteratively plans, creates, and updates files in:

- `templates/` (Jinja2 HTML templates)
- `static/` (CSS / JS / assets)
- `routes/` (Flask blueprints)
- `agents.md` (human-readable architecture record)
- `builder_context.md` (the agent’s planning + task list)

All of this is orchestrated through a single `main.py` Flask server with a built-in “builder panel” that you can open/close while using the generated app.

Live example: https://www.dittoagent.site/
---

## Features

- **Natural language to Flask app**
  - Describe your app in plain English.
  - The LLM plans and implements routes, templates, and static assets.

- **Live builder panel**
  - Root route `/` renders a shell: the app in an iframe plus a floating 🧰 button.
  - Clicking the button opens a side panel with a builder UI and live logs.

- **Single entrypoint**
  - `/app` always renders `templates/index.html`.
  - The LLM must ensure that all user flows start from `/app`.

- **Context and architecture docs**
  - `builder_context.md`: the LLM’s own plan + granular task list.
  - `agents.md`: canonical architecture doc (routes, templates, static assets, build history, TODOs).

- **Sandboxed file operations**
  - Tools only allow reads/writes inside `templates/`, `static/`, `routes/`, `agents.md`, and `builder_context.md`.

- **Hot reload of routes**
  - After a successful build (`task_completed()`), the app reloads blueprints from `routes/` without a server restart.

---

## Requirements

- Python 3.10+
- `pip` for installing dependencies

Python dependencies (minimum):

```bash
pip install flask litellm
```

You can also use a `requirements.txt` like:

```txt
flask
litellm
```

---

## Configuration: API Keys and Model

The app uses [LiteLLM](https://github.com/BerriAI/litellm) to talk to an LLM (e.g. OpenAI models). LiteLLM reads API keys from **environment variables**, which means:

- On Replit, **Secrets** are exposed as environment variables.
- On GitHub / your local machine, you can use `.env` files or shell env vars.

Common configuration:

- `OPENAI_API_KEY` or `LITELLM_API_KEY` 
  - Your API key for the provider you’re using (e.g. OpenAI).

- `LITELLM_MODEL` (optional)
  - The model name to use for code generation.
  - Defaults to `gpt-5-mini` in `main.py`.
  - You can override it, for example:

```bash
export OPENAI_API_KEY="sk-..."
export LITELLM_MODEL="gpt-4o-mini"
python main.py
```

LiteLLM supports many providers; configure according to its docs (env vars like `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

---

## Running from GitHub / Locally

1. **Clone the repo**

```bash
git clone https://github.com/yourname/flask-app-builder.git
cd flask-app-builder
```

2. **Create and activate a virtual environment (recommended)**

```bash
python -m venv .venv
source .venv/bin/activate
# On Windows: .venv\\Scripts\\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
# or
pip install flask litellm
```

4. **Set environment variables**

```bash
export OPENAI_API_KEY="sk-..."
export LITELLM_MODEL="gpt-5-mini"  # optional override
```

5. **Run the app**

```bash
python main.py
```

By default it will bind to `0.0.0.0` and use `PORT` if set, otherwise `5000`.

6. **Open in your browser**

Visit:

- `http://localhost:5000/`

You should see:

- The generated app (iframe) filling the screen
- A floating 🧰 button in the bottom-right
- Clicking the button opens the builder panel (chat + logs)

---

## Running on Replit

You can use this both as a standalone Repl or by importing the GitHub repo.

### Option 1: Import from GitHub

1. In Replit, choose **Import from GitHub** and paste your repo URL.
2. Ensure `main.py` is the run file.
3. Add secrets via **Tools > Secrets**:
   - Key: `OPENAI_API_KEY`, Value: `sk-...`
   - Optional: `LITELLM_MODEL`, Value: `gpt-5-mini` or another supported model.
4. Click **Run**.
5. Use the Replit webview or "Open in browser" to access `/`.

### Option 2: Create a new Repl

1. Create a new **Python** Repl.
2. Upload `main.py` and optionally `requirements.txt`.
3. Add secrets via **Tools > Secrets** as above.
4. If using `requirements.txt`, add:

   ```txt
   flask
   litellm
   ```

5. In the `.replit` or the Replit run configuration, make sure the command is:

   ```bash
   python main.py
   ```

6. Run and open the webview.

---

## How to Use the Builder

1. Go to `/`.
2. If no app exists yet, the builder panel opens automatically.
3. In the builder panel:
   - Type a description of the app you want.
   - Example:

     > Build a simple snake game at /game, render it inside index.html at /app, with a dark theme and score display.

4. The agent will:
   - Read `builder_context.md` to understand or refine the plan.
   - Update `builder_context.md` with a more detailed task list.
   - Create directories and files step-by-step using tools.
   - Update `agents.md` with architecture details and build history.

5. Watch the logs:
   - Each iteration shows:
     - Assistant plan/thoughts
     - Tool results (files created/updated)
   - Status at the top shows: `idle`, `running`, or `completed`.

6. When the build completes:
   - The app iframe auto-refreshes once.
   - A **"Refresh App"** button appears in the builder.
   - You can click it to reload the app manually if needed.

7. To continue iterating:
   - Keep using the same builder panel.
   - Describe changes, e.g.:

     > Add a leaderboard stored in a JSON file and show it on the right side.

   - The agent will update files and docs accordingly.

---

## Route Overview

- `/`
  - Shell UI.
  - Shows `/app` in an iframe.
  - Shows a floating builder button to open/close the side panel.

- `/app`
  - Renders `templates/index.html` via `render_template`.
  - This is the canonical app entrypoint.

- `/builder`
  - Minimal UI for sending new instructions and viewing logs.
  - Polls `/progress` for status and HTML-formatted logs.

- `/progress`
  - JSON endpoint exposing the current `progress` state:
    - `status` (`idle` | `running` | `completed`)
    - `iteration`
    - `output` (HTML-formatted log)

Any additional routes (e.g. `/game`, `/api/...`) are created as Blueprints under `routes/` by the LLM.

---

## Security and Scope

This repository is designed for local / dev use and experimentation. Important notes:

- The LLM has tools to read/write files only in:
  - `templates/`
  - `static/`
  - `routes/`
  - `agents.md`
  - `builder_context.md`
- It cannot directly modify `main.py`.
- Generated code is not audited. Always review before deploying to production.

If you plan to expose this publicly, consider:

- Adding authentication for the builder.
- Running behind a reverse proxy.
- Locking down what the app can do (e.g., via filesystem sandboxing, Docker, etc.).

---

## Contributing

Suggestions, issues, and pull requests are welcome.

Ideas you might explore:

- Better visualization of the iteration log (collapsible iterations, diff views).
- A richer task inspector for `builder_context.md`.
- Multi-model support or offline LLM backends.
- Richer code verification or tests generation.

---

## License

MIT (or your preferred OSS license). Add a LICENSE file at the root of the repo.

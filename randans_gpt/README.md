# Randan's GPT  (v1.0)

A ChatGPT-style **native Windows desktop app** (CustomTkinter - no browser, no
localhost web UI) that chats with your locally installed **Ollama** models.
Tuned for low-resource laptops (Dell Latitude 5310 / i5-10th gen / 16 GB RAM).

## Quick start (Windows)
1. **Extract the zip** (right-click -> *Extract All*). Open the extracted `randans_gpt` folder - it contains
   `main.py`, `requirements.txt` and `setup_and_run.bat`.
2. Install **Python 3.10 - 3.12** (python.org, tick *Add python.exe to PATH*) and **Ollama** (ollama.com).
3. **Double-click `setup_and_run.bat`.** The first run installs everything; afterwards use `run.bat`.

> `ERROR: Could not open requirements file` just means the terminal was not *inside* that folder. Either use the
> .bat files above, or `cd` into the folder first (`dir` should list `requirements.txt`), then run
> `python -m pip install -r requirements.txt`.

The modern interface is HTML/CSS/JavaScript shown in a native window using Windows' built-in **Edge WebView2**
(already on Windows 11 and most Windows 10 PCs; free download otherwise). It does not open a browser and does not
start any web server. `python main.py --classic` runs the older Tk interface as a fallback.

## Features
- Apple-style glass interface (dark + light), bundled Inter font, smooth animations, "Reduce effects" switch for older GPUs
- **Setup wizard:** checks the PC (RAM, CPU, graphics, free disk), asks what you'll use it for (coding, studying, writing, maths, languages)
  and installs the models that run well on it, with live download progress. Re-run it from Settings.
- **Accounts:** sign up / sign in with Supabase (email + password, passwordless code, password reset). Each account has its own private data.
- **Live preview:** when the AI writes a web page, it opens beside the chat (Preview / Code / Console, desktop / tablet / phone sizes, save as .html).
  Runs in a sandbox, so generated code can't touch your chats or files.
- **Pages:** Dashboard, AI Chat, Help (+ About), Account, Settings, Tool servers
- Left tool rail, model picker with smart routing across *your* installed models, **Tools** (MCP / REA), Reasoning, Deep Research, voice typing
- Live streaming, Markdown, highlighted code, history by day, memory, TXT / PDF export, notifications

To publish the app (accounts, installer, signing) see **PUBLISHING.md**.

## Auto-routing
| Question type        | Model              |
|----------------------|--------------------|
| Coding               | `qwen2.5:1.5b`     |
| Math / reasoning     | `deepseek-r1:1.5b` |
| Writing / blogging   | `gemma2:2b`        |
| General chat         | `llama3.2:1b`      |

Edit the keyword lists in `models/router.py` to tune it.

## Build a standalone .exe (PyInstaller)
Double-click `build_exe.bat` (after `setup_and_run.bat` has run once), or run:
```
pip install pyinstaller
pyinstaller --noconfirm --clean --noconsole --onefile --name RandansGPT --icon assets\icon.ico --add-data "assets;assets" --add-data "web;web" --collect-all webview --collect-all customtkinter --collect-submodules pygments.lexers --collect-submodules mcp main.py
```
Result: `dist\RandansGPT.exe`. (Ollama must still be installed on the PC.)
Tip: replace `--onefile` with `--onedir` for faster start-up on slow disks.

## SQLite schema  (`database/schema.sql`)
```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL);
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
```

## Low-resource tuning (`settings/config.py` -> DEFAULTS / settings.json)
`num_ctx` (2048) context window, `history_messages` (10) past messages sent,
`temperature` (0.7). Lower `num_ctx` to save RAM; models stay loaded 10 min (`keep_alive`).

## Project layout
```
randans_gpt/
  main.py                 entry point (HTML interface; --classic = Tk fallback)
  web/                    index.html, css/app.css, js/ (app, markdown, icons), embedded Inter font
  backend/                bridge.py (Python <-> JavaScript), auth.py (Supabase), specs.py + catalog.py (PC check / model picks),
                          prompts.py, winfx.py (Windows title bar / icon)
  database/  models/  memory/  settings/    SQLite, Ollama + MCP clients, router, memory, settings
  ui/                     classic Tk interface (fallback) + export helpers + tool definitions
  assets/                 icon.ico, logo.png (the "R")
  supabase.json.example   copy to supabase.json to enable accounts (see PUBLISHING.md)
  PUBLISHING.md  installer.iss
  requirements.txt  setup_and_run.bat  run.bat  build_exe.bat
```

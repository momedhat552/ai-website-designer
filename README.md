# AI Website Designer

A small Streamlit app that turns a plain-text website request (English or Arabic) into a
single self-contained HTML file using Gemini. You see a live preview, you can ask for
changes until you are happy, undo a change, and download the result as `index.html`.

This is a portfolio project. It is intentionally small: one API call per generation, no
database, no accounts.

## Run it on Windows PowerShell

One-time setup (from `C:\python\website-designer`):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and put your real Gemini key on the `GEMINI_API_KEY=` line.
`.env` is listed in `.gitignore`, so it must never be committed.

Start the app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open <http://localhost:8501> if the browser does not open by itself.

Run the tests:

```powershell
.\.venv\Scripts\python.exe test_core.py
.\.venv\Scripts\python.exe test_app.py
```

`test_core.py` is the main suite (11 tests, fake model, no internet needed).
`test_app.py` covers four small helpers from the UI file.

Optional: `smoke.py` makes one real Gemini call and writes `smoke.html`, which is a quick
way to check the API key without the browser:

```powershell
.\.venv\Scripts\python.exe smoke.py
```

Note: on this machine the `python` command points to the Microsoft Store stub, so the
commands call the virtual environment's Python directly. On a normal install,
`python -m venv .venv` works too.

## How it works, file by file

**`core.py`** holds all the logic that does not depend on Streamlit. It contains the system
prompt that tells Gemini to answer with one complete HTML file and to use `dir="rtl"` for
Arabic requests, the `build_prompt` function that turns a first request or an edit request
into the prompt, and `extract_html`, which finds the HTML inside the model's reply even if
it is wrapped in Markdown code fences or has extra text around it. `generate_site` tries a
list of model names in order, retries temporary errors with increasing waits, and raises one
`RuntimeError` if everything fails. `real_call_model` is the only function that imports
`google-genai`; the import happens inside the function so the tests do not need the package
or the network. The key is read from the environment, never from a file or the code.

**`app.py`** is the Streamlit page. It reads the API key from `.env` locally or from
`st.secrets` on Streamlit Cloud, then shows either the request form or the current website.
Versions are kept as a list of HTML strings in `st.session_state["versions"]`; the last item
is what the user sees. "Generate" and "Apply change" both call `core.generate_site`, with
the current HTML passed as `current_html` for edits, so every edit is a full rewrite of the
page. The preview uses `st.iframe`, which renders the HTML as an iframe in the browser only.
"Open in new tab" uses a second tiny iframe with one button; the button asks the browser to
make a temporary blob URL from the HTML that is already on the page, so nothing is stored or
served by the server. The generated HTML is never executed on the server, never written into
the app's own code, and never saved as an app file. A counter caps each session at 15
generations, and the remaining count is shown at the top. Errors are caught and shown as
short messages, so a stack trace and the API key never reach the page.

## Model fallback and retries

`DEFAULT_MODELS` lists a few Flash model names. `GEMINI_MODEL` can override the list with
comma-separated names. For each model, `generate_site` makes up to two attempts:

- 404 (the model name is retired or wrong): skip to the next model immediately.
- 429, 500, 503, 504 (busy or rate limited): wait 1 second, then 2 seconds, then try again.
- Reply with no usable HTML: count it as a failed attempt and move on.

If every model in the list fails, the UI shows "The model is busy, try again in a minute."
Model names change over time, so a retired default only means one skipped model, not a
broken app.

## Known limits

- Output quality varies. Gemini usually produces a good-looking page, but layout, wording,
  and accessibility details change from run to run. The app does not check the HTML.
- Each edit sends the whole current HTML inside the prompt, and each version keeps the full
  page. After many edits the prompt and the session memory get bigger, which costs more
  tokens and eventually slows the call down.
- Free-tier limits are not published, and the free tier sometimes returns 429 or 503. The
  retries help, but a heavy session can still fail. The 15-generation cap protects quota on
  a public deployment.
- The page is one HTML file with inline CSS and optional small scripts. There are no
  external images, fonts, or frameworks, by design.
- The preview runs the generated JavaScript in the browser iframe. Only use requests you
  wrote yourself, and review the HTML before publishing it.
- "Open in new tab" is a normal pop-up. If the browser blocks pop-ups for the app, the
  button asks you to allow them. The new tab's address is a temporary `blob:` link, so it
  cannot be copied and shared like a normal URL; use the download button for that.

## What I would improve next

- Let the app keep a short change history and send only the diff-relevant parts, instead of
  the whole page, to keep prompts small.
- Validate the HTML before showing it (for example, check headings and required meta tags)
  and show a short quality checklist.
- Add a "start over" button and save named drafts locally so a good result is not lost when
  the page reloads.
- Add a small screenshot or PDF export for sharing a preview with someone who does not run
  the app.
- Cache identical requests during a session to avoid spending quota on accidental double
  clicks.

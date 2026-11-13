"""Streamlit UI for the AI website designer."""
import json
import os

import streamlit as st
from dotenv import load_dotenv

import core

MAX_GENERATIONS = 15


# --- Small pure helpers (tested in test_app.py) -----------------------------

def read_api_key(environ=None, secrets_getter=None):
    """Return the Gemini key from the environment first, then from st.secrets."""
    environ = os.environ if environ is None else environ
    key = (environ.get("GEMINI_API_KEY") or "").strip()
    if key:
        return key

    if secrets_getter is None:
        def secrets_getter(name):
            return st.secrets[name]

    try:
        return (secrets_getter("GEMINI_API_KEY") or "").strip() or None
    except Exception:
        # No env value and no Streamlit secrets (this is also true when testing).
        return None


def remaining_generations(used, cap=MAX_GENERATIONS):
    """How many model calls are left in this session. Never negative."""
    return max(cap - used, 0)


def add_version(versions, html):
    """Version stack: the last item is the site currently shown."""
    return versions + [html]


def undo(versions):
    """Drop the newest version."""
    return versions[:-1]


def new_tab_page(html):
    """HTML for a small button that opens the site in a new browser tab.

    The button makes a temporary blob URL in the browser. Nothing is written to
    disk or served by the server. "<" is escaped so the generated page can never
    break out of the script that carries it.
    """
    site = json.dumps(html).replace("<", "\\u003c")
    return f"""<!DOCTYPE html>
<html>
  <body style="margin: 0; background: transparent;">
    <button id="open-tab" title="Opens a temporary copy in a new browser tab"
      style="width: 100%; height: 40px; box-sizing: border-box; cursor: pointer;
             font-family: 'Source Sans Pro', sans-serif; font-size: 14px;
             color: rgb(49, 51, 63); background: rgb(255, 255, 255);
             border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 8px;">
      Open in new tab ↗
    </button>
    <script>
      const site = {site};
      const button = document.getElementById("open-tab");
      button.addEventListener("click", () => {{
        const url = URL.createObjectURL(new Blob([site], {{ type: "text/html" }}));
        const tab = window.open(url, "_blank");
        if (!tab) {{
          button.textContent = "Pop-up blocked: allow pop-ups, then try again";
        }}
      }});
    </script>
  </body>
</html>"""


# --- Streamlit pieces -------------------------------------------------------

def show_html(html, height):
    """Show HTML in an iframe. It runs only in the browser, never on the server."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        # Older Streamlit without st.iframe.
        import streamlit.components.v1 as components
        components.html(html, height=height, scrolling=True)


def show_preview(html):
    show_html(html, height=700)


def open_in_new_tab(html):
    """Show the new-tab button. The page stays in the browser as a blob URL."""
    show_html(new_tab_page(html), height=40)


def generate(request, current_html):
    """Make one model call and return HTML, or None if it failed.

    The counter goes up before the call, because a failed call still uses quota.
    """
    st.session_state["generations"] += 1
    with st.spinner("Designing your website... this can take up to a minute."):
        try:
            html, _model = core.generate_site(
                core.real_call_model, request, current_html=current_html
            )
        except RuntimeError:
            st.error("The model is busy, try again in a minute.")
            return None
        except Exception:
            # Never show a stack trace or the API key in the UI.
            st.error("Something went wrong while generating the website. Try again.")
            return None
    return html


def main():
    st.set_page_config(page_title="AI Website Designer", page_icon="🌐")
    load_dotenv()

    api_key = read_api_key()
    if api_key is None:
        st.error("No Gemini API key found, so the app cannot start.")
        st.markdown(
            "Create a file named `.env` in this folder with one line:\n\n"
            "```\nGEMINI_API_KEY=your-key-here\n```\n\n"
            "Then restart the app. On Streamlit Cloud, add the same name and value "
            "under the app's secrets instead."
        )
        st.stop()

    # core.real_call_model reads the key from the environment; this also covers
    # the case where the key came from st.secrets on Streamlit Cloud.
    os.environ["GEMINI_API_KEY"] = api_key

    st.title("AI Website Designer")
    st.write(
        "Describe a website in English or Arabic. Gemini writes one HTML file, "
        "you ask for changes, then download it."
    )

    if "versions" not in st.session_state:
        st.session_state["versions"] = []
    if "generations" not in st.session_state:
        st.session_state["generations"] = 0

    versions = st.session_state["versions"]
    remaining = remaining_generations(st.session_state["generations"])

    if remaining == 0:
        st.warning(
            f"This session reached its limit of {MAX_GENERATIONS} generations. "
            "Reload the page to start a new session."
        )
    else:
        st.caption(f"{remaining} of {MAX_GENERATIONS} generations left in this session.")

    if not versions:
        # --- First request: no website yet ---
        request = st.text_area(
            "Describe your website",
            height=140,
            placeholder="A one page website for a bakery in Giza, with the menu and opening hours.",
        )
        if st.button("Generate", type="primary", disabled=remaining == 0):
            if not request.strip():
                st.info("Write a short description first.")
            else:
                html = generate(request, current_html=None)
                if html:
                    st.session_state["versions"] = add_version(versions, html)
                    st.rerun()
        return

    # --- A website exists: preview, edit, undo, download ---
    current_html = versions[-1]

    show_preview(current_html)
    st.caption("Generated by AI. Review before publishing.")

    download_col, tab_col = st.columns(2)
    with download_col:
        st.download_button(
            "Download index.html",
            data=current_html,
            file_name="index.html",
            mime="text/html",
            width="stretch",
        )
    with tab_col:
        open_in_new_tab(current_html)

    st.subheader("Ask for a change")
    change = st.text_area(
        "What should change?",
        height=100,
        key="change_request",
        placeholder="Make the header dark blue and add a contact section.",
    )

    left, right = st.columns(2)
    with left:
        if st.button("Apply change", type="primary", disabled=remaining == 0 or not change.strip()):
            html = generate(change, current_html=current_html)
            if html:
                st.session_state["versions"] = add_version(versions, html)
                st.rerun()
    with right:
        if st.button("Undo", disabled=len(versions) <= 1):
            st.session_state["versions"] = undo(versions)
            st.rerun()


if __name__ == "__main__":
    main()

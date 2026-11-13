"""Core logic for the AI website designer. No Streamlit imports here, so it is testable."""
import os
import re
import time

DEFAULT_MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.5-flash"]

SYSTEM_PROMPT = (
    "You are a web designer. Return ONE complete, self-contained HTML5 file: "
    "inline CSS in <style>, optional tiny inline <script>, no external files, "
    "no external images (use CSS gradients, emoji or inline SVG), responsive, "
    "accessible, valid. Use dir=rtl and lang=ar when the request is in Arabic. "
    "Return ONLY the HTML, no explanation."
)


class RetryableError(Exception):
    """503 / 429 style errors: wait and retry or try the next model."""


class ModelNotFound(Exception):
    """404: model name retired or wrong: skip to the next model."""


def get_models():
    env = os.environ.get("GEMINI_MODEL", "").strip()
    models = [m.strip() for m in env.split(",") if m.strip()] if env else []
    return models or list(DEFAULT_MODELS)


def extract_html(text):
    """Pull the HTML out of the model reply (it may be wrapped in ```html fences)."""
    if not text:
        raise ValueError("Empty reply from model")
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.S | re.I)
    if m:
        text = m.group(1)
    text = text.strip()
    low = text.lower()
    start = low.find("<!doctype")
    if start == -1:
        start = low.find("<html")
    if start == -1:
        raise ValueError("No HTML found in reply")
    end = low.rfind("</html>")
    if end == -1:
        raise ValueError("HTML looks cut off (no closing </html>)")
    return text[start:end + len("</html>")]


def build_prompt(request, current_html=None):
    if current_html:
        return (
            "Here is the current website:\n\n" + current_html +
            "\n\nApply this change and return the FULL updated HTML file:\n" + request
        )
    return "Build a website for this request:\n\n" + request


def generate_site(call_model, request, current_html=None, models=None,
                  retries_per_model=2, sleep=time.sleep, on_event=None):
    """call_model(model, system, prompt) -> text. Tries models in order with retries.

    on_event, when given, is called as on_event("start", "") before each attempt
    and on_event("chunk", text) for every streamed piece of the reply.
    """
    models = models or get_models()
    prompt = build_prompt(request, current_html)
    last_err = None
    for model in models:
        for attempt in range(retries_per_model):
            try:
                if on_event:
                    on_event("start", "")
                    text = call_model(model, SYSTEM_PROMPT, prompt, on_event=on_event)
                else:
                    text = call_model(model, SYSTEM_PROMPT, prompt)
                return extract_html(text), model
            except ModelNotFound as e:
                last_err = e
                break  # next model
            except RetryableError as e:
                last_err = e
                sleep(2 ** attempt)
            except ValueError as e:  # bad/cut-off HTML: one retry then next model
                last_err = e
    raise RuntimeError(f"All models failed. Last error: {last_err}")


def real_call_model(model, system, prompt, on_event=None):
    """The only function that touches google-genai. Imported lazily so tests don't need it.

    Without on_event this is one blocking call. With on_event the reply is
    streamed and each piece is reported as on_event("chunk", text).
    """
    from google import genai
    from google.genai import types, errors
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(system_instruction=system)
    try:
        if on_event is None:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config,
            )
            return resp.text
        parts = []
        for chunk in client.models.generate_content_stream(
            model=model, contents=prompt, config=config,
        ):
            if chunk.text:
                parts.append(chunk.text)
                on_event("chunk", chunk.text)
        return "".join(parts)
    except errors.APIError as e:
        code = getattr(e, "code", None)
        if code in (429, 500, 503, 504):
            raise RetryableError(str(e))
        if code == 404:
            raise ModelNotFound(str(e))
        raise

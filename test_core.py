import unittest
import core
from core import RetryableError, ModelNotFound, extract_html, generate_site

GOOD = "<!DOCTYPE html><html><body>Hi</body></html>"
sleeps = []
nosleep = lambda s: sleeps.append(s)

class T(unittest.TestCase):
    def test_extract_fenced(self):
        self.assertEqual(extract_html("sure!\n```html\n" + GOOD + "\n```\nenjoy"), GOOD)
    def test_extract_plain_with_chatter(self):
        self.assertEqual(extract_html("Here:\n" + GOOD + "\nbye"), GOOD)
    def test_cut_off(self):
        with self.assertRaises(ValueError):
            extract_html("<!DOCTYPE html><html><body>Hi")
    def test_empty(self):
        with self.assertRaises(ValueError):
            extract_html("")
    def test_503_then_success(self):
        calls = []
        def fake(model, system, prompt):
            calls.append(model)
            if len(calls) == 1: raise RetryableError("503")
            return GOOD
        html, model = generate_site(fake, "bakery", models=["a", "b"], sleep=nosleep)
        self.assertEqual((html, model), (GOOD, "a")); self.assertEqual(calls, ["a", "a"])
    def test_404_skips_to_next_model(self):
        def fake(model, system, prompt):
            if model == "old": raise ModelNotFound("404")
            return GOOD
        _, model = generate_site(fake, "x", models=["old", "new"], sleep=nosleep)
        self.assertEqual(model, "new")
    def test_all_fail(self):
        def fake(model, system, prompt): raise RetryableError("429")
        with self.assertRaises(RuntimeError):
            generate_site(fake, "x", models=["a", "b"], sleep=nosleep)
    def test_edit_prompt_contains_current_html_and_request(self):
        seen = {}
        def fake(model, system, prompt): seen["p"] = prompt; return GOOD
        generate_site(fake, "make header dark", current_html=GOOD, models=["a"], sleep=nosleep)
        self.assertIn(GOOD, seen["p"]); self.assertIn("make header dark", seen["p"])
    def test_model_env(self):
        import os
        os.environ["GEMINI_MODEL"] = "m1, m2"
        self.assertEqual(core.get_models(), ["m1", "m2"])
        del os.environ["GEMINI_MODEL"]
        self.assertEqual(core.get_models(), core.DEFAULT_MODELS)
    def test_arabic_request_roundtrip(self):
        def fake(model, system, prompt): return "```html\n<!DOCTYPE html><html lang='ar' dir='rtl'><body>مخبز</body></html>\n```"
        html, _ = generate_site(fake, "موقع لمخبز في الجيزة", models=["a"], sleep=nosleep)
        self.assertIn("مخبز", html)
    def test_real_call_import_is_lazy(self):
        import sys
        self.assertNotIn("google.genai", sys.modules)  # importing core must not need the SDK

unittest.main(verbosity=1)

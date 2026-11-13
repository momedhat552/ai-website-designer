"""Tests for the small helpers in app.py. No Streamlit widgets are tested."""
import unittest

import app


class AppHelpersTest(unittest.TestCase):
    def test_read_api_key_prefers_environment(self):
        # Environment (from .env locally) wins over Streamlit secrets.
        self.assertEqual(
            app.read_api_key({"GEMINI_API_KEY": "env-key"}, lambda name: "secret-key"),
            "env-key",
        )
        # Falls back to st.secrets on Streamlit Cloud.
        self.assertEqual(app.read_api_key({}, lambda name: "secret-key"), "secret-key")
        # Nothing configured, or secrets not available: no key, no crash.
        self.assertIsNone(app.read_api_key({}))

    def test_remaining_generations(self):
        self.assertEqual(app.remaining_generations(0), app.MAX_GENERATIONS)
        self.assertEqual(app.remaining_generations(1), app.MAX_GENERATIONS - 1)
        self.assertEqual(app.remaining_generations(app.MAX_GENERATIONS), 0)
        self.assertEqual(app.remaining_generations(app.MAX_GENERATIONS + 5), 0)

    def test_version_stack(self):
        versions = app.add_version([], "first")
        versions = app.add_version(versions, "second")
        self.assertEqual(versions, ["first", "second"])
        self.assertEqual(app.undo(versions), ["first"])

    def test_expected_html_size(self):
        # An edit should aim for the size of the page it replaces.
        self.assertEqual(app.expected_html_size("<html>" + "x" * 2000 + "</html>"), 2013)
        # A first generation learns from earlier pages in the session.
        self.assertEqual(app.expected_html_size(None, [30000, 50000]), 40000)
        self.assertEqual(app.expected_html_size(None, []), app.DEFAULT_EXPECTED_SIZE)
        # Tiny or missing history never gives a divide-by-zero-sized target.
        self.assertEqual(app.expected_html_size(None, [0]), app.DEFAULT_EXPECTED_SIZE)
        self.assertEqual(app.expected_html_size("hi"), 1000)

    def test_new_tab_page_escapes_site_html(self):
        page = app.new_tab_page("<!DOCTYPE html><html><script>alert(1)</script></html>")
        # The site's own </script> must not close the button's script tag.
        self.assertEqual(page.count("</script>"), 1)
        self.assertIn("\\u003cscript>alert(1)", page)


if __name__ == "__main__":
    unittest.main(verbosity=1)

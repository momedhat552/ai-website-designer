"""One real Gemini call, saved to smoke.html, to check the API key."""
import core
from dotenv import load_dotenv

load_dotenv()

html, model = core.generate_site(core.real_call_model, "a one page website for a bakery in Giza")

with open("smoke.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"OK: {len(html)} characters from {model}, saved to smoke.html")

"""Inline the data and wordmark into the self-contained explainer page.

    python docs/eunice-web/tools/build_page.py   # writes docs/eunice-web/eunice.html

CI (.github/workflows/eunice-page.yml) runs this and fails if the committed eunice.html differs,
so commit the rebuilt page with any change to src/ or data/. Files are read and written as UTF-8
with LF line endings, so the output is the same on Windows as on Linux.
"""
import base64
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1]
t = (D / "src" / "eunice.template.html").read_text(encoding="utf-8")
wm = base64.b64encode((D / "assets" / "wordmark-light.png").read_bytes()).decode()
week = json.dumps(json.loads((D / "data" / "week.json").read_text(encoding="utf-8")), separators=(",", ":"))
year = json.dumps(json.loads((D / "data" / "year_blocks.json").read_text(encoding="utf-8")), separators=(",", ":"))
for k in ("__WM__", "__WEEK__", "__YEAR__"):
    assert t.count(k) == 1, k
out = t.replace("__WM__", wm).replace("__WEEK__", week).replace("__YEAR__", year)
with open(D / "eunice.html", "w", encoding="utf-8", newline="\n") as f:
    f.write(out)
print(f"wrote {D / 'eunice.html'} ({len(out.encode('utf-8')):,} bytes)")

"""Pre-flight check before building an MLP (user, 2026-11-12: "Check each MLP before I start building").

Usage: python tools/preflight.py            (run from the project folder; reads project.json + brief.json)

brief.json (written by Claude from the Final MLP monday update: only the Figma, the MLP content doc and the
button links count, per the brief-reading rule):
  {"figma": "<url>", "figma_ok": true|false|null, "content_doc": "<url>", "doc_ok": true|false|null,
   "links": {"View Inventory": "<url>", ...}, "fonts": ["StratumGMC", "Inter"]}
  figma_ok / doc_ok: Claude sets them after opening the file with the Figma MCP / Google Drive (null = not checked).

Checks: Figma opens, content doc opens, every button has a link, each link answers (HTTP) and is on the dealer's
own domain (project.json "site"), each font is on Google Fonts (otherwise it needs a stand-in), and the dealer's
CMS from the tracker matches project.json "platform".
Writes qa/preflight.txt and prints one QUESTION line per problem (Claude logs them with build_mlp_tracker.py --ask).
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
PROJ = json.loads((ROOT / "project.json").read_text(encoding="utf8"))
BRIEF = json.loads((ROOT / "brief.json").read_text(encoding="utf8")) if (ROOT / "brief.json").exists() else {}
TRACKER = (lambda _p: Path(_p.read_text(encoding="utf-8").strip()) if _p.exists() else Path(__file__).resolve().parents[2] / "tracker")((Path(__import__("os").environ["APPDATA"]) if __import__("sys").platform == "win32" else Path.home() / "Library" / "Application Support") / "MLP Tracker" / "tracker_path.txt")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
ok_lines, questions = [], []


def host(u):
    h = urllib.parse.urlsplit(u).hostname or ""
    return h[4:] if h.startswith("www.") else h


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, u
    except Exception as e:  # DNS, timeout, TLS
        return str(e)[:80], u


# 1. Figma + content doc
for key, flag, label in (("figma", "figma_ok", "Figma design"), ("content_doc", "doc_ok", "MLP content doc")):
    url = BRIEF.get(key)
    if not url:
        questions.append(f"No {label} link in the Final MLP update.")
    elif BRIEF.get(flag) is False:
        questions.append(f"The {label} does not open for Claude: {url}")
    elif BRIEF.get(flag) is None:
        ok_lines.append(f"?    {label}: not checked yet ({url})")
    else:
        ok_lines.append(f"ok   {label} opens")

# 2. Button links
site = host(PROJ.get("site") or "")
links = BRIEF.get("links") or {}
if not links:
    questions.append("No button links in the Final MLP update.")
for label, url in links.items():
    if not url or url.strip() in ("#", ""):
        questions.append(f"Button '{label}' has no link.")
        continue
    h = host(url)
    if site and h and not (h == site or h.endswith("." + site)):
        questions.append(f"Button '{label}' points to another site ({h}), not {site}: {url}")
    code, final = fetch(url)
    if code in (401, 403, 429, 503):
        ok_lines.append(f"?    {label}: site blocks automated checks (HTTP {code}); open it by hand: {url}")
    elif isinstance(code, int) and code < 400:
        moved = f" -> redirects to {final}" if final.rstrip("/") != url.rstrip("/") else ""
        ok_lines.append(f"ok   {label}: HTTP {code}{moved}")
        if moved and site and host(final) and host(final) != site and not host(final).endswith("." + site):
            questions.append(f"Button '{label}' redirects off the dealer site to {final}")
    else:
        questions.append(f"Button '{label}' does not load (HTTP {code}): {url}")

# 3. Fonts
for f in BRIEF.get("fonts") or []:
    code, _ = fetch("https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(f).replace("%20", "+"))
    if code == 200:
        ok_lines.append(f"ok   font {f}: on Google Fonts")
    else:
        questions.append(f"Font '{f}' is not a web font (not on Google Fonts); Claude will use the closest stand-in. OK?")

# 4. CMS matches the platform
try:
    cms = json.loads((TRACKER / "cms_directory.json").read_text(encoding="utf8")).get("cms", {})
    sys.path.insert(0, str(TRACKER))
    from build_mlp_tracker import load_platforms, platform_for  # noqa: E402
    plat = platform_for(PROJ.get("dealer", ""), load_platforms())
    want = "dealer-inspire" if plat.startswith("Dealer Inspire") else ("?" if plat.startswith("?") else "one-file")
    if want == "?":
        questions.append(f"Dealer '{PROJ.get('dealer')}' is not in monday's Dealer Login and Setup CMS list; which CMS?")
    elif want != PROJ.get("platform"):
        questions.append(f"project.json platform is '{PROJ.get('platform')}' but monday says {plat}.")
    else:
        ok_lines.append(f"ok   CMS: {plat}")
except Exception as e:
    ok_lines.append(f"?    CMS check skipped: {e}")

out = [f"Pre-flight {PROJ.get('title')} ({PROJ.get('dealer')})", ""] + ok_lines + [""] + [
    "QUESTION " + q for q in questions] + ["", f"{len(questions)} problem(s)" if questions else "all clear"]
(ROOT / "qa").mkdir(exist_ok=True)
(ROOT / "qa" / "preflight.txt").write_text("\n".join(out), encoding="utf8")
print("\n".join(out))

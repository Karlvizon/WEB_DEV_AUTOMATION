"""Set every <img>/<source> width+height in preview.html to the real pixel size of its assets/webp file.
Run after any image is rebuilt (e.g. when an upscaled copy replaces a source)."""
import re
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parent.parent
p = ROOT / "preview.html"
s = p.read_text(encoding="utf8")
n = 0
def fix(m):
    global n
    tag = m.group(0)
    src = re.search(r'src="assets/webp/([^"]+)"', tag)
    if not src or src.group(1).endswith(".svg"):
        return tag
    w, h = Image.open(ROOT / "assets/webp" / src.group(1)).size
    new = re.sub(r'width="\d+" height="\d+"', f'width="{w}" height="{h}"', tag)
    n += new != tag
    return new
s = re.sub(r"<img [^>]*>", fix, s)
p.write_text(s, encoding="utf8", newline="\n")
print("updated", n, "img size attributes")

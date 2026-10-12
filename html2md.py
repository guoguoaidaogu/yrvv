#!/usr/bin/env python3
"""Convert a saved Zhihu column page into Markdown.

Usage:
    python3 html2md.py                      # html/0.html -> md/0.md
    python3 html2md.py html/1.html md/1.md  # any page
    python3 html2md.py html/1.html md/1.md --assets assets

Conversion rules
----------------
* images are kept: every image that appears in the article is copied to
  ``<assets>/`` next to the Markdown file (default ``md/assets/``) and renamed
  ``<page>_<n><ext>``, where ``page`` is the source file stem (``0``, ``10_1``,
  ...) and ``n`` is the 1-based order of appearance in the article; Markdown
  links point at the copied file. Remote (http) images are left untouched.
* formulas are kept as TeX (``$...$`` inline, ``$$...$$`` for display math),
  taken from the ``data-tex`` attribute of ``span.ztext-math``
* all hyperlinks are dropped: normal links keep their text, entity-word links
  keep their text, and ``RichText-LinkCardContainer`` cards (title + thumbnail
  + vote count) are removed entirely
* ``<h1 class="Post-Title">`` becomes the document title, ``<h2>`` -> ``##``,
  ``<hr>`` -> ``---``, ``<b>/<i>`` -> ``**...**``/``*...*``
"""
from html.parser import HTMLParser
from html import unescape
import argparse
import os
import re
import shutil

# tags whose content is never article text
SKIP = {"script", "style", "svg", "math", "path", "use", "g"}
# tags that open a Markdown block
BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4")
# emphasis tags -> Markdown format
EMPH = {"b": "**%s**", "strong": "**%s**", "i": "*%s*", "em": "*%s*"}
VOID = {"br", "hr", "img", "meta", "link", "input", "source", "area", "base",
        "col", "embed", "param", "track", "wbr"}


# ---------------------------------------------------------------- extraction
def balanced(frag, start, tag):
    """Return (html, end_index) for the element of type `tag` at `start`."""
    depth = 0
    for m in re.finditer(r"<(/?)%s\b[^>]*>" % tag, frag[start:], re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            end = start + m.end()
            return frag[start:end], end
    raise ValueError("unbalanced <%s> at %d" % (tag, start))


def article_html(html):
    """The article body, bounded by the rich-text container."""
    m = re.search(r'<div class="RichText\b[^"]*Post-RichText[^"]*"', html)
    if not m:
        raise ValueError("no RichText Post-RichText container found")
    art, _ = balanced(html, m.start(), "div")
    return art


def document_title(html):
    m = re.search(r'<h1 class="Post-Title">(.*?)</h1>', html, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""


def extract(html):
    """Article HTML with math tokenised and link cards removed, plus the maths."""
    art = article_html(html)

    # 1) tokenise math spans (attribute order is not assumed)
    maths, out, pos = [], [], 0
    for m in re.finditer(r"<span\b[^>]*>", art):
        tag = m.group(0)
        attrs = dict(re.findall(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)="([^"]*)"', tag))
        if "ztext-math" not in attrs.get("class", ""):
            continue
        _, end = balanced(art, m.start(), "span")
        out.append(art[pos:m.start()])
        out.append("\x00M%d\x00" % len(maths))
        maths.append((unescape(attrs.get("data-tex", "")),
                      attrs.get("data-eeimg", "1")))
        pos = end
    out.append(art[pos:])
    art = "".join(out)

    # 2) drop link-card containers (link + thumbnail + description)
    out, pos = [], 0
    for m in re.finditer(r'<div class="RichText-LinkCardContainer">', art):
        _, end = balanced(art, m.start(), "div")
        out.append(art[pos:m.start()])
        pos = end
    out.append(art[pos:])
    art = "".join(out)

    return art, maths


# ---------------------------------------------------------------- assets
IMG_REF = re.compile(r"@@IMG\(([^()]*)\)@@")
LOCAL_IMG = re.compile(r'(src=")\./([^/"]+_files)/([^"]*)"')


def collect_images(art):
    """Local image srcs of an article, in order of appearance (no duplicates)."""
    seen, order = set(), []
    for m in LOCAL_IMG.finditer(art):
        src = "./%s/%s" % (m.group(2), m.group(3))
        if src not in seen:
            seen.add(src)
            order.append(src)
    return order


def copy_images(art, src, assets, page):
    """Copy every local image to `assets` as <page>_<n><ext>; return mapping."""
    files_dir = os.path.dirname(src)
    os.makedirs(assets, exist_ok=True)
    mapping, missing = {}, []
    for i, rel in enumerate(collect_images(art), 1):
        origin = os.path.join(files_dir, rel[2:])          # ./x_files/y -> x_files/y
        if not os.path.isfile(origin):
            missing.append(rel)
            continue
        dest_name = "%s_%d%s" % (page, i, os.path.splitext(origin)[1].lower())
        dest = os.path.join(assets, dest_name)
        if not (os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(origin)):
            shutil.copyfile(origin, dest)
        mapping[rel] = dest_name
    return mapping, missing


def link_images(text, mapping, assets_rel):
    """Replace @@IMG(...)@@ placeholders by paths relative to the markdown file."""
    def sub(m):
        name = mapping.get(m.group(1))
        if name is None:
            return m.group(1)          # remote/copied-none: leave the original
        return assets_rel + name
    return IMG_REF.sub(sub, text)


# ----------------------------------------------------------------- rendering
class Renderer:
    """Collect the article's HTML events into a list of Markdown blocks."""

    def __init__(self):
        self.blocks = []   # (kind, text)
        self.cur = []      # inline fragments of the block being built
        self.emph = []     # (format string, position in self.cur)

    # -- helpers -----------------------------------------------------------
    def raw(self, s):
        self.cur.append(s)

    def flush(self, kind):
        txt = "".join(self.cur).strip()
        self.cur = []
        self.emph = []
        if txt:
            self.blocks.append((kind, txt))

    # -- tag events --------------------------------------------------------
    def start(self, tag, attrs):
        if tag in SKIP:
            return
        if "ztext-empty-paragraph" in attrs.get("class", ""):
            return
        if tag in BLOCK_TAGS:
            pass
        elif tag == "figure":
            self.flush("p")              # illustrations stand alone
        elif tag == "hr":
            self.flush("p")
            self.blocks.append(("hr", ""))
        elif tag == "img":
            if self.cur:
                self.raw("\n\n")
            href = attrs.get("src", "")
            if not re.match(r"(https?:)?//", href):
                href = "@@IMG(%s)@@" % href   # resolved to a copied asset later
            self.raw("![%s](%s)" % (attrs.get("data-caption", ""), href))
        elif tag == "br":
            self.raw("\n")
        elif tag in EMPH:
            self.emph.append((EMPH[tag], len(self.cur)))
        elif tag == "a":
            pass                         # hyperlink dropped, text kept

    def end(self, tag):
        if tag in SKIP:
            return
        if tag in BLOCK_TAGS:
            kind = {"h1": "h1", "h2": "h2", "h3": "h3", "h4": "h3"}.get(tag, "p")
            self.flush(kind)
        elif tag == "figure":
            self.flush("p")
        elif tag in EMPH:
            for k in range(len(self.emph) - 1, -1, -1):
                if self.emph[k][0] is EMPH[tag]:
                    fmt, pos = self.emph.pop(k)
                    break
            else:
                return
            inner = "".join(self.cur[pos:]).strip()
            del self.cur[pos:]
            if inner:
                self.cur.append(fmt % inner)

    def emit_math(self, tex, ee):
        if ee == "1":
            self.raw("$%s$" % tex)
        else:
            self.flush("p")
            self.blocks.append(("math", tex))


def drive(html, r):
    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)

        def handle_starttag(self, tag, attrs):
            r.start(tag, {k.lower(): (v or "") for k, v in attrs})
            if tag in VOID:
                r.end(tag)

        def handle_startendtag(self, tag, attrs):
            r.start(tag, {k.lower(): (v or "") for k, v in attrs})
            r.end(tag)

        def handle_endtag(self, tag):
            r.end(tag)

        def handle_data(self, data):
            r.raw(unescape(data))

        def handle_entityref(self, name):
            r.raw(unescape("&%s;" % name))

        def handle_charref(self, name):
            r.raw(unescape("&#%s;" % name))

    p = P()
    p.feed(html)
    p.close()


def render(art, maths):
    r = Renderer()
    token = re.compile(r"\x00M(\d+)\x00")
    for i, part in enumerate(token.split(art)):
        if i % 2 == 0:
            drive(part, r)
        else:
            r.emit_math(*maths[int(part)])
    r.flush("p")
    return r.blocks


# ---------------------------------------------------------------------- main
def convert(src, dst, assets="assets", quiet=False):
    html = open(src, encoding="utf-8").read()
    page = os.path.splitext(os.path.basename(src))[0]
    art, maths = extract(html)

    assets_dir = os.path.join(os.path.dirname(dst) or ".", assets)
    mapping, missing = copy_images(art, src, assets_dir, page)
    assets_rel = os.path.relpath(assets_dir, os.path.dirname(dst) or ".") + "/"
    if assets_rel.startswith("./"):
        assets_rel = assets_rel[2:]

    blocks = render(art, maths)
    blocks = [(k, link_images(t, mapping, assets_rel)) for k, t in blocks]

    lines = []
    title = document_title(html)
    if title:
        lines += ["# " + title, ""]
    for kind, text in blocks:
        if kind == "hr":
            lines.append("---")
        elif kind == "math":
            lines.append("$$\n%s\n$$" % text)
        elif kind in ("h1", "h2", "h3"):
            lines.append({"h1": "# ", "h2": "## ", "h3": "### "}[kind] + text)
        else:
            lines.append(text)

    out = re.sub(r"[ \t]+\n", "\n", "\n\n".join(lines))
    out = re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    open(dst, "w", encoding="utf-8").write(out)
    if not quiet:
        print("%s -> %s: %d bytes, %d blocks, %d formulas, %d images"
              % (src, dst, len(out), len(blocks), len(maths), len(mapping)))
        for rel in missing:
            print("  ! missing image: %s" % rel)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", nargs="?", default="html/0.html")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--assets", default="assets",
                    help="folder for copied images, relative to the markdown "
                         "file (default: assets)")
    a = ap.parse_args()
    if not a.dst:
        base = os.path.basename(a.src)
        a.dst = os.path.join("md", base[:-5] + ".md")
    convert(a.src, a.dst, a.assets)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the built site's SEO output. Exits 1 on any failure.

    jekyll build && python3 tools/validate-seo.py

Checks title/description lengths, canonical + robots + OG/Twitter completeness,
JSON-LD parseability and @id integrity, sitemap/canonical agreement, feed,
robots.txt directives, manifest icons, llms.txt, internal link resolution,
social-card dimensions, and that no page is stamped with the build clock.
"""
import json, os, re, sys, glob
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = sys.argv[1] if len(sys.argv) > 1 else "_site"
SITE = "https://blog.enzobellissimo.com"
fails, warns, passes = [], [], 0

def ok(m):
    global passes; passes += 1
def fail(m): fails.append(m)
def warn(m): warns.append(m)
def check(cond, m):
    (ok if cond else fail)(m)

pages = sorted(glob.glob(f"{ROOT}/**/*.html", recursive=True))
check(len(pages) == 6, f"6 HTML pages built (got {len(pages)})")

# ---------------------------------------------------------------- per page
for f in pages:
    rel = os.path.relpath(f, ROOT)
    h = open(f, encoding="utf-8").read()

    def one(pat, label):
        m = re.findall(pat, h)
        check(len(m) == 1, f"{rel}: exactly one {label} (got {len(m)})")
        return m[0] if len(m) == 1 else None

    title = one(r"<title>(.*?)</title>", "<title>")
    desc  = one(r'<meta name="description" content="(.*?)">', "meta description")
    canon = one(r'<link rel="canonical" href="(.*?)">', "canonical")
    one(r'<meta name="robots" content="(.*?)">', "robots")
    ogimg = one(r'<meta property="og:image" content="(.*?)">', "og:image")
    one(r'<meta property="og:title" content="(.*?)">', "og:title")
    one(r'<meta name="twitter:card" content="(.*?)">', "twitter:card")

    if title:
        n = len(re.sub(r"&(#\d+|#x[0-9A-Fa-f]+|\w+);", "x", title))
        check(n <= 65, f"{rel}: title {n} chars (<=65)")
        check(not re.search(r"&(?!(?:#\d+|#x[0-9A-Fa-f]+|\w+);)", title), f"{rel}: title has no raw ampersand")
    if desc:
        n = len(re.sub(r"&(#\d+|#x[0-9A-Fa-f]+|\w+);", "x", desc))
        if "noindex" in h:
            ok(f"{rel}: description length not scored (noindex)")
        else:
            check(120 <= n <= 165, f"{rel}: description {n} chars (120-165)")
    if canon:
        check(canon.startswith(SITE), f"{rel}: canonical is absolute + right host")
        check(" " not in canon, f"{rel}: canonical has no spaces")
    if ogimg:
        p = urlparse(ogimg).path.lstrip("/")
        check(os.path.exists(os.path.join(ROOT, p)), f"{rel}: og:image file exists ({p})")
        check(ogimg.startswith("https://"), f"{rel}: og:image absolute https")

    # exactly one h1
    check(len(re.findall(r"<h1[ >]", h)) == 1, f"{rel}: exactly one <h1>")
    # lang
    check('<html lang="en"' in h, f"{rel}: html lang set")
    # rel=me both profiles
    check(h.count('rel="me"') >= 2, f"{rel}: rel=me for both profiles")
    # no unrendered liquid
    check("{{" not in h and "{%" not in h, f"{rel}: no unrendered Liquid")
    # no localhost / example leakage
    check("localhost" not in h, f"{rel}: no localhost URLs")

    # ---- JSON-LD
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
    check(len(blocks) == 1, f"{rel}: exactly one JSON-LD block")
    for b in blocks:
        try:
            d = json.loads(b)
        except Exception as e:
            fail(f"{rel}: JSON-LD parse error: {e}"); continue
        g = d.get("@graph", [])
        ids = {n.get("@id") for n in g}
        types = [n.get("@type") for n in g]
        check(d.get("@context") == "https://schema.org", f"{rel}: @context")
        for t in ("Person", "WebSite", "Blog", "BreadcrumbList"):
            check(t in types, f"{rel}: graph has {t}")
        # every internal @id reference resolves inside the graph
        refs = set()
        def walk(n):
            if isinstance(n, dict):
                if set(n.keys()) == {"@id"}: refs.add(n["@id"])
                for v in n.values(): walk(v)
            elif isinstance(n, list):
                for v in n: walk(v)
        walk(g)
        dangling = refs - ids
        check(not dangling, f"{rel}: all @id refs resolve ({sorted(dangling) or 'ok'})")
        # person sameAs
        person = next(n for n in g if n["@type"] == "Person")
        check(len(person.get("sameAs", [])) == 2, f"{rel}: Person.sameAs has 2 profiles")
        check(any("github.com/ebarroz" in s for s in person["sameAs"]), f"{rel}: sameAs GitHub")
        check(any("enzobbellissimo" in s for s in person["sameAs"]), f"{rel}: sameAs LinkedIn")
        # breadcrumb positions
        bc = next(n for n in g if n["@type"] == "BreadcrumbList")
        pos = [i["position"] for i in bc["itemListElement"]]
        check(pos == list(range(1, len(pos)+1)), f"{rel}: breadcrumb positions sequential")
        # article specifics
        if "BlogPosting" in types:
            a = next(n for n in g if n["@type"] == "BlogPosting")
            for k in ("headline","datePublished","dateModified","author","publisher",
                      "wordCount","timeRequired","articleSection","image","inLanguage"):
                check(k in a, f"{rel}: BlogPosting.{k}")
            check(len(a["headline"]) <= 110, f"{rel}: headline <=110 chars")
            check(a["wordCount"] > 0, f"{rel}: wordCount > 0")
            check(re.match(r"^PT\d+M$", a["timeRequired"]), f"{rel}: timeRequired ISO-8601")

# ------------------------------------------------- dates must never be build time
import datetime
now = datetime.datetime.now().astimezone()
for f in pages:
    rel = os.path.relpath(f, ROOT)
    h = open(f, encoding="utf-8").read()
    for m in re.findall(r'"date(?:Published|Modified)": "([^"]+)"', h):
        try: d = datetime.datetime.fromisoformat(m)
        except ValueError: fail(f"{rel}: unparseable date {m}"); continue
        drift = abs((now - d).total_seconds())
        check(drift > 3600, f"{rel}: date {m} is not the build clock")

# ---------------------------------------------------------------- noindex
n404 = open(f"{ROOT}/404.html", encoding="utf-8").read()
check('content="noindex' in n404, "404: noindex present")
for f in pages:
    if f.endswith("404.html"): continue
    check("noindex" not in open(f, encoding="utf-8").read(), f"{os.path.relpath(f,ROOT)}: NOT noindexed")

# ---------------------------------------------------------------- sitemap
sm = ET.parse(f"{ROOT}/sitemap.xml").getroot()
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
locs = [l.text for l in sm.findall(".//s:loc", ns)]
check(len(locs) == 5, f"sitemap: 5 URLs (got {len(locs)})")
check(all(l.startswith(SITE) for l in locs), "sitemap: all URLs absolute")
check(not any("404" in l for l in locs), "sitemap: 404 excluded")
check(len(locs) == len(set(locs)), "sitemap: no duplicate URLs")
# every indexable page's canonical is in the sitemap
canons = {re.search(r'rel="canonical" href="(.*?)"', open(p, encoding="utf-8").read()).group(1)
          for p in pages if not p.endswith("404.html")}
check(canons == set(locs), f"sitemap matches canonicals (diff: {canons ^ set(locs)})")

# ---------------------------------------------------------------- feed
feed = ET.parse(f"{ROOT}/feed.xml").getroot()
atom = "{http://www.w3.org/2005/Atom}"
entries = feed.findall(f"{atom}entry")
check(len(entries) == 3, f"feed: 3 entries (got {len(entries)})")
check(feed.find(f"{atom}title") is not None, "feed: has title")
check(all(e.find(f"{atom}content") is not None for e in entries), "feed: full-text content")

# ---------------------------------------------------------------- robots
rb = open(f"{ROOT}/robots.txt", encoding="utf-8").read()
check(f"Sitemap: {SITE}/sitemap.xml" in rb, "robots: sitemap line correct")
check(re.search(r"^User-agent: \*\nAllow: /", rb, re.M) is not None, "robots: wildcard allow")
for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot"):
    check(re.search(rf"User-agent: {bot}\nAllow: /", rb) is not None, f"robots: {bot} allowed")
for bot in ("AhrefsBot", "SemrushBot"):
    check(re.search(rf"User-agent: {bot}\nDisallow: /", rb) is not None, f"robots: {bot} blocked")
check("{{" not in rb, "robots: no unrendered Liquid")

# ---------------------------------------------------------------- manifest / llms
mf = json.load(open(f"{ROOT}/site.webmanifest", encoding="utf-8"))
check(mf["start_url"] == "/", "manifest: start_url")
for icon in mf["icons"]:
    p = icon["src"].lstrip("/")
    check(os.path.exists(os.path.join(ROOT, p)), f"manifest: icon exists ({p})")

lt = open(f"{ROOT}/llms.txt", encoding="utf-8").read()
check("{{" not in lt and "{%" not in lt, "llms.txt: no unrendered Liquid")
check("github.com/ebarroz" in lt and "enzobbellissimo" in lt, "llms.txt: both profiles")
for l in locs:
    check(l in lt or l.rstrip("/") in lt, f"llms.txt: lists {l}")

# ---------------------------------------------------------------- link + asset integrity
built = {os.path.relpath(p, ROOT).replace(os.sep, "/") for p in
         glob.glob(f"{ROOT}/**/*", recursive=True) if os.path.isfile(p)}
def resolves(path):
    p = path.lstrip("/")
    return p in built or f"{p.rstrip('/')}/index.html" in built or (p == "" )
for f in pages:
    rel = os.path.relpath(f, ROOT)
    h = open(f, encoding="utf-8").read()
    for attr in re.findall(r'(?:href|src)="(/[^"]*)"', h):
        if attr.startswith("//"): continue
        check(resolves(attr), f"{rel}: internal link resolves -> {attr}")

# ---------------------------------------------------------------- OG image dims
try:
    import struct
    for img in glob.glob(f"{ROOT}/assets/og-*.png"):
        with open(img, "rb") as fh:
            fh.read(16); w, hgt = struct.unpack(">II", fh.read(8))
        check((w, hgt) == (1200, 630), f"{os.path.basename(img)}: 1200x630 (got {w}x{hgt})")
except Exception as e:
    warn(f"png dim check skipped: {e}")

# ---------------------------------------------------------------- report
print(f"\n  PASSED: {passes}")
if warns:
    print(f"  WARN:   {len(warns)}")
    for w in warns: print(f"    ~ {w}")
if fails:
    print(f"  FAILED: {len(fails)}")
    for m in fails: print(f"    x {m}")
    sys.exit(1)
print("  FAILED: 0\n  >>> ALL CHECKS PASSED")

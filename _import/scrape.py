"""Scrape propertymedia.jp (Squarespace) pages, JSON and images into _import/."""
import json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET

BASE = "https://www.propertymedia.jp"
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (compatible; PMJ-migration/1.0)"}
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "i": "http://www.google.com/schemas/sitemap-image/1.1"}


def get(url, tries=3):
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            print("retry", url, e)
            time.sleep(2 + n * 3)
    return None


def slug(path):
    s = path.strip("/").replace("/", "__") or "home"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s)[:150]


os.makedirs(f"{OUT}/pages", exist_ok=True)
os.makedirs(f"{OUT}/images", exist_ok=True)

root = ET.fromstring(get(f"{BASE}/sitemap.xml"))
pages, images = [], {}
for u in root.findall("s:url", NS):
    loc = u.find("s:loc", NS).text.strip()
    pages.append(loc)
    for im in u.findall("i:image", NS):
        src = im.find("i:loc", NS).text.strip()
        rec = images.setdefault(src, {"pages": [], "titles": [], "captions": []})
        rec["pages"].append(loc)
        for tag, key in (("i:title", "titles"), ("i:caption", "captions")):
            el = im.find(tag, NS)
            if el is not None and el.text:
                rec[key].append(el.text.strip())

# also homepage root and any extra pages linked in nav
for extra in [BASE + "/", BASE + "/contact", BASE + "/blog"]:
    if extra not in pages:
        pages.append(extra)

img_re = re.compile(r"https://images\.squarespace-cdn\.com/content/v1/[^\"'\s)<>?]+\.(?:jpe?g|png|webp|gif)", re.I)
for p in pages:
    path = urllib.parse.urlparse(p).path
    s = slug(path)
    html = get(p)
    if html:
        open(f"{OUT}/pages/{s}.html", "wb").write(html)
        for m in set(img_re.findall(html.decode("utf-8", "ignore"))):
            images.setdefault(m, {"pages": [], "titles": [], "captions": []})
            if p not in images[m]["pages"]:
                images[m]["pages"].append(p)
    js = get(p + ("&" if "?" in p else "?") + "format=json-pretty")
    if js:
        open(f"{OUT}/pages/{s}.json", "wb").write(js)
        for m in set(img_re.findall(js.decode("utf-8", "ignore"))):
            images.setdefault(m, {"pages": [], "titles": [], "captions": []})
            if p not in images[m]["pages"]:
                images[m]["pages"].append(p)
    print("page", p, bool(html), bool(js))

manifest = []
for i, (src, rec) in enumerate(sorted(images.items())):
    clean = src.split("?")[0]
    parts = clean.split("/")
    fname = urllib.parse.unquote_plus(parts[-1])
    local = f"{i:03d}_" + re.sub(r"[^A-Za-z0-9.]+", "-", fname).strip("-")[:90]
    data = get(clean + "?format=2500w")
    if data:
        open(f"{OUT}/images/{local}", "wb").write(data)
    manifest.append({"local": local, "src": clean, "ok": bool(data), **rec})
    print("img", i, local, bool(data))

json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=1, ensure_ascii=False)
print("done", len(pages), "pages", len(manifest), "images")

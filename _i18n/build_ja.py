"""Build the Japanese site (/ja/) from the English pages and _i18n/ja.json.

Run from anywhere:  python3 _i18n/build_ja.py
- English pages get hreflang links and the EN / 日本語 switch (idempotent).
- /ja/ pages are generated from the English HTML: text, alt and aria labels,
  title and meta, JSON-LD strings, internal links, lang, hreflang, canonical.
- Strings missing from ja.json are reported (they stay English).
"""
import json, os, re, sys, glob
from bs4 import BeautifulSoup, NavigableString, Comment, Tag
from bs4.formatter import HTMLFormatter

class KeepOrder(HTMLFormatter):
    """Serialise attributes in source order (bs4 sorts them by default)."""
    def attributes(self, tag):
        return list(tag.attrs.items())

FMT = KeepOrder(entity_substitution=HTMLFormatter.REGISTRY['minimal'].entity_substitution, void_element_close_prefix=None)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'https://www.propertymedia.jp'
D = json.load(open(os.path.join(ROOT, '_i18n', 'ja.json')))
# Page specific wording where one English string needs different Japanese in context
OV = json.load(open(os.path.join(ROOT, '_i18n', 'ja_overrides.json')))
CUR = {'rel': None}

INLINE = {'a','em','strong','b','i','span','br','small','sup','sub','abbr','time','code','mark','u','s','wbr','q','cite'}
SKIP = {'script','style','svg','noscript','iframe','video','source','template','picture','img','input','textarea','select','head','meta','link'}
ATTRS = ['alt','title','aria-label','placeholder','data-label','data-caption']
META = {'description','og:title','og:description','twitter:title','twitter:description','og:image:alt','twitter:image:alt'}
LD_KEYS = {'name','description','text','headline','caption','alternateName','jobTitle','serviceType','slogan','disambiguatingDescription','abstract','keywords','areaServed','category','valueName','knowsAbout','award','addressLocality','addressRegion','streetAddress','unitText','contactType','availableLanguage'}
ENTITY_IDS = ('#org', '#business', '#james', '#website')
PAGE_TYPES = {'WebPage','CollectionPage','AboutPage','FAQPage','ItemList','CreativeWork','VideoObject','Service'}
PHRASE_SEL = 'h1, h2, h3, h4, .section-label, .hero-label, .hero-sub, .btn, .nav-cta, .sticky-cta, .faq-question-text, .service-card-title, .advantage-title, .gallery-item-label, .contact-form-title, .stat-label, .advantages-stat-label, figcaption'
FORM_NOTE = '<p class="contact-form-note">フォームの項目名は英語表記ですが、日本語でそのままご記入いただけます。メールやお電話でのご相談も承ります。</p>'

missing = {}

def norm(s):
    return re.sub(r'\s+', ' ', s).strip()

def has_text(el):
    return any(isinstance(d, NavigableString) and not isinstance(d, Comment) and d.parent.name not in SKIP and norm(str(d)) for d in el.descendants)

def inline_only(el):
    return all(not isinstance(d, Tag) or d.name in INLINE for d in el.descendants)

def inner(el):
    return norm(''.join(str(c) for c in el.contents if not isinstance(c, Comment)))

def units(soup):
    res = []
    def walk(el):
        for c in el.children:
            if isinstance(c, Tag):
                if c.name in SKIP or c.get('translate') == 'no':
                    continue
                if inline_only(c) and has_text(c):
                    res.append(c)
                else:
                    walk(c)
    walk(soup.body)
    return res

def needs(s):
    t = re.sub(r'<[^>]+>', '', s).replace('&amp;', '&').strip()
    return bool(t) and bool(re.search(r'[A-Za-z]{2,}', t)) and not re.fullmatch(r'[\w.+-]+@[\w.-]+|https?://\S+', t)

def tr(s, where):
    k = norm(s)
    ov = OV.get(CUR['rel'] or '', {})
    if k in ov:
        return ov[k]
    if where == 'json-ld' and k in CUR.get('faq', {}):
        return CUR['faq'][k]
    if k in D:
        return D[k]
    if needs(k):
        missing.setdefault(k, where)
    return s

def page_url(rel):
    if rel == 'index.html':
        return '/'
    if rel.endswith('/index.html'):
        return '/' + rel[:-len('index.html')]
    return '/' + rel

def to_ja_path(path):
    if path.startswith(('/images', '/media', '/assets', '/favicon', '/ja/', '//', '/llms', '/sitemap', '/robots')):
        return path
    return '/ja' + path

def strip_i18n(html):
    html = re.sub(r'\n?\s*<link rel="alternate" hreflang="[^"]+" href="[^"]+">', '', html)
    html = re.sub(r'\n?\s*<meta property="og:locale(:alternate)?" content="[^"]+">', '', html)
    html = re.sub(r'\n?\s*<div class="lang-switch".*?</div>', '', html, flags=re.S)
    return html

def head_links(en_path, ja_path, lang):
    out = [f'<link rel="alternate" hreflang="en" href="{HOST}{en_path}">',
           f'<link rel="alternate" hreflang="ja" href="{HOST}{ja_path}">',
           f'<link rel="alternate" hreflang="x-default" href="{HOST}{en_path}">',
           f'<meta property="og:locale" content="{"ja_JP" if lang == "ja" else "en_US"}">',
           f'<meta property="og:locale:alternate" content="{"en_US" if lang == "ja" else "ja_JP"}">']
    return '\n  ' + '\n  '.join(out)

def switch(en_path, ja_path, lang):
    cur_en = ' aria-current="true"' if lang == 'en' else ''
    cur_ja = ' aria-current="true"' if lang == 'ja' else ''
    label = '言語' if lang == 'ja' else 'Language'
    return (f'\n    <div class="lang-switch" role="group" aria-label="{label}">'
            f'<a href="{en_path}" hreflang="en" lang="en" title="English"{cur_en}>EN</a>'
            f'<span class="lang-sep" aria-hidden="true">/</span>'
            f'<a href="{ja_path}" hreflang="ja" lang="ja"{cur_ja}>日本語</a></div>')

def insert_switch(html, sw):
    i = html.find('</ul>', html.find('id="navLinks"'))
    assert i > 0
    return html[:i + 5] + sw + html[i + 5:]

def insert_head(html, block):
    m = re.search(r'<link rel="canonical"[^>]*>', html)
    if m:
        return html[:m.end()] + block + html[m.end():]
    i = html.find('</title>') + len('</title>')
    return html[:i] + block + html[i:]

def ld_ja(obj, parent_key=''):
    if isinstance(obj, dict):
        is_entity = str(obj.get('@id', '')).endswith(ENTITY_IDS)
        out = {}
        for k, v in obj.items():
            if isinstance(v, str):
                if k in LD_KEYS:
                    v = tr(v, 'json-ld')
                elif k in ('url', '@id', 'item') and v.startswith(HOST + '/') and not is_entity and not v.endswith(ENTITY_IDS):
                    v = HOST + to_ja_path(v[len(HOST):])
                out[k] = v
            else:
                out[k] = ld_ja(v, k)
        t = out.get('@type')
        if t == 'Organization' and out.get('alternateName') == 'NOMADO合同会社':
            out['name'], out['alternateName'] = 'NOMADO合同会社', 'Nomado Godo Kaisha'
        if isinstance(t, str) and t in PAGE_TYPES and not is_entity:
            out['inLanguage'] = 'ja'
        if t == 'WebSite':
            out['inLanguage'] = ['en', 'ja']
        return out
    if isinstance(obj, list):
        return [tr(v, 'json-ld') if isinstance(v, str) and parent_key in LD_KEYS else ld_ja(v, parent_key) for v in obj]
    return obj

def add_phrases(soup, parser):
    """Insert <wbr> at BudouX phrase boundaries computed over the whole element text,
    so headings break between natural Japanese phrases (with word-break: keep-all)."""
    for el in soup.select(PHRASE_SEL):
        nodes = [t for t in el.find_all(string=True) if not isinstance(t, Comment) and t.parent.name not in ('script', 'style')]
        full = ''.join(str(t) for t in nodes)
        if not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', full):
            continue
        bounds, pos = set(), 0
        for ph in parser.parse(full)[:-1]:
            pos += len(ph)
            if not (full[pos - 1].isascii() or full[pos].isascii()):
                bounds.add(pos)
        start = 0
        for t in nodes:
            s = str(t)
            end = start + len(s)
            cuts = sorted(b - start for b in bounds if start <= b < end)
            if cuts:
                pieces, prev = [], 0
                for c in cuts:
                    if c > prev:
                        pieces.append(NavigableString(s[prev:c]))
                    pieces.append(soup.new_tag('wbr'))
                    prev = c
                pieces.append(NavigableString(s[prev:]))
                for n in reversed(pieces):
                    t.insert_after(n)
                t.extract()
            start = end
        el['class'] = (el.get('class') or []) + ['jp-phrase']

def build():
    import budoux
    parser = budoux.load_default_japanese_parser()
    pages = []
    for f in sorted(glob.glob(ROOT + '/**/*.html', recursive=True)):
        rel = os.path.relpath(f, ROOT)
        if rel.startswith(('ja/', '_', '.git')):
            continue
        pages.append(rel)
    import hashlib
    ver = {n: hashlib.md5(open(os.path.join(ROOT, 'assets', n), 'rb').read()).hexdigest()[:8] for n in ('site.css', 'site.js')}
    for rel in pages:
        CUR['rel'] = rel
        src = strip_i18n(open(os.path.join(ROOT, rel)).read())
        # cache busting: tag shared CSS/JS with a hash of their contents
        src = re.sub(r'/assets/(site\.(?:css|js))(?:\?v=[0-9a-f]+)?"', lambda m: f'/assets/{m.group(1)}?v={ver[m.group(1)]}"', src)
        en_path = page_url(rel)
        is404 = rel == '404.html'
        ja_path = '/ja' + en_path
        sw_en, sw_ja = ('/', '/ja/') if is404 else (en_path, ja_path)

        # English page: hreflang + switch
        en = src if is404 else insert_head(src, head_links(en_path, ja_path, 'en'))
        en = insert_switch(en, switch(sw_en, sw_ja, 'en'))
        open(os.path.join(ROOT, rel), 'w').write(en)

        # Japanese page
        soup = BeautifulSoup(src, 'html.parser')
        soup.html['lang'] = 'ja'
        if soup.title:
            soup.title.string = tr(soup.title.string, rel)
        for m in soup.find_all('meta'):
            k = m.get('name') or m.get('property')
            if k in META and m.get('content'):
                m['content'] = tr(m['content'], rel)
            if k == 'og:url':
                m['content'] = HOST + ja_path
        faq_sel = '.faq-question-text, .faq-answer'
        en_faq = [norm(x.get_text(' ')) for x in soup.select(faq_sel)]
        for u in units(soup):
            k = inner(u)
            v = tr(k, rel)
            if v != k:
                frag = BeautifulSoup(v, 'html.parser')
                u.clear()
                for n in list(frag.contents):
                    u.append(n)
        for el in soup.find_all(True):
            if el.name in ('script', 'style'):
                continue
            for a in ATTRS:
                if el.get(a):
                    el[a] = tr(el[a], rel)
        ja_faq = [norm(x.get_text('')) for x in soup.select(faq_sel)]
        CUR['faq'] = dict(zip(en_faq, ja_faq)) if len(en_faq) == len(ja_faq) else {}
        for s in soup.find_all('script', type='application/ld+json'):
            s.string = json.dumps(ld_ja(json.loads(s.string)), ensure_ascii=False)
        for el in soup.find_all(['a', 'link']):
            h = el.get('href')
            if not h:
                continue
            if el.name == 'link' and el.get('rel') == ['canonical']:
                el['href'] = HOST + ja_path
            elif h.startswith('/') and not h.startswith('//'):
                el['href'] = to_ja_path(h)
            elif h.startswith(HOST + '/') and el.name == 'a':
                el['href'] = HOST + to_ja_path(h[len(HOST):])
        sub = soup.select_one('.contact-form-sub')
        if sub and not soup.select_one('.contact-form-note'):
            sub.insert_after(BeautifulSoup(FORM_NOTE, 'html.parser'))
        add_phrases(soup, parser)
        ja = soup.decode(formatter=FMT)
        if not is404:
            ja = insert_head(ja, head_links(en_path, ja_path, 'ja'))
        ja = insert_switch(ja, switch(sw_en, sw_ja, 'ja'))
        out = os.path.join(ROOT, 'ja', rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w').write(ja)
    print(f'{len(pages)} pages built, {len(missing)} strings missing translation')
    for k, w in list(missing.items())[:40]:
        print('  MISSING', w, '|', k[:110])
    json.dump(missing, open(os.path.join(ROOT, '_i18n', 'missing.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    build()

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
LD_KEYS = {'priceRange', 'name','description','text','headline','caption','alternateName','jobTitle','serviceType','slogan','disambiguatingDescription','abstract','keywords','areaServed','category','valueName','knowsAbout','award','addressLocality','addressRegion','streetAddress','unitText'}
ENTITY_IDS = ('#org', '#business', '#james', '#website')
PAGE_TYPES = {'WebPage','CollectionPage','AboutPage','FAQPage','CreativeWork'}
PHRASE_SEL = 'h1, h2, h3, h4, .section-label, .hero-label, .hero-sub, .btn, .nav-cta, .sticky-cta, .faq-question-text, .service-card-title, .advantage-title, .gallery-item-label, .contact-form-title, .stat-label, .advantages-stat-label, figcaption'
PHRASE_SEL += (', .page-hero-stat-label, .intro-stat-label, .why-video-stat-label, .project-detail-value,'
               ' .project-meta-value, .about-credential-value, .timeline-title, .pricing-row-label > span,'
               ' .drone-item-label, .page-hero-sub, .page-hero-intro')
# compound terms BudouX must never split across lines
KEEP_TOGETHER = ['ドローン空撮', '不動産撮影', '物件写真', '物件動画', '間取り図', '3D間取り図', '2D間取り図', 'バーチャルステージング', '建築写真', 'インテリア撮影', 'ホテル撮影', '撮影実績', '見積もり', 'お問い合わせ', 'ルームツアー', '縦型ショート動画', '夕景撮影', 'CGパース', 'NOMADO合同会社', '国土交通省航空局', 'ニセコエリア', 'スキーイン・スキーアウト', 'よくある', '投資用物件プラン', '住宅プラン', '紹介', '空撮', '手がけ']
# Soft break points allowed inside protected terms, only in h1 (large type on phones)
H1_SOFT = {'バーチャルステージング': [5], '不動産撮影実績': [3, 5], '3D間取り図': [2], 'ドローン空撮': [4],
           'ルームツアー動画': [6], 'プライバシーポリシー': [6], '縦型ショート動画': [2, 6], '投資用物件プラン': [5], 'プロジェクト一覧': [6]}
TRUST = ('<p class="contact-trust">運営：NOMADO合同会社（法人番号 <a href="https://www.houjin-bangou.nta.go.jp/henkorireki-johoto.html?selHouzinNo=9430003018070" rel="noopener" target="_blank">9430003018070</a>）<br>'
         '主な取引先：AK Housing、Niseko WOW、Miaja Design Group</p>')
FOOT_CONTACT = ('<span class="footer-contact"><a href="tel:+819033997122">090-3399-7122</a>　'
                '<a href="mailto:team@propertymedia.jp">team@propertymedia.jp</a></span><br>')
DIRECT = ('<p class="cta-direct">お電話 <a href="tel:+819033997122">090-3399-7122</a>　メール '
          '<a href="mailto:team@propertymedia.jp">team@propertymedia.jp</a><br>営業日であれば通常は当日中にご返信します。</p>')
REASSURE = '<p class="hero-reassure"><span>ニセコエリア内は出張費不要。</span><span>営業日であれば通常は当日中にご返信します。</span></p>'
FORM_NOTE = ('<p class="contact-form-note">送信前に<a href="/ja/privacy/">プライバシーポリシー</a>をご確認ください。'
             'お問い合わせの内容は、顧客管理に利用しているクラウドサービス（Studio Ninja、オーストラリア）で管理します。メールやお電話でのご相談も承ります。</p>')
# Japanese Studio Ninja form under NOMADO GK
SN_FORM_EN = '0a800fc9-9c28-1786-819c-6544eac22534/0a800fc9-9c28-1786-819c-6c4f1c577353'
SN_FORM_JA = '0a800fc9-9c28-1786-819c-6544eac22534/0a800fc8-a182-17c3-81a1-87ca14a72ffb'

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
                    if k == 'description':
                        v = re.sub(r'お見積もり[^。]*ご依頼ください。$', '', v).strip()
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
        bounds |= {i + 1 for i, ch in enumerate(full[:-1]) if ch in '・、'}
        for term in KEEP_TOGETHER:
            for m in re.finditer(re.escape(term), full):
                bounds -= set(range(m.start() + 1, m.end()))
        if el.name in ('h1', 'h2', 'h3'):
            for term, offs in H1_SOFT.items():
                for m in re.finditer(re.escape(term), full):
                    bounds |= {m.start() + o for o in offs}
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
        if el.name in ('h1', 'h2'):
            # keep short Latin names such as "Kutchan House 2" on one line, even across tags
            tn = [t for t in el.find_all(string=True) if not isinstance(t, Comment)]
            txt = ''.join(str(t) for t in tn)
            sp = set()
            for m in re.finditer(r"[A-Za-z0-9\u00C0-\u024F][A-Za-z0-9\u00C0-\u024F.&']*(?: [A-Za-z0-9\u00C0-\u024F][A-Za-z0-9\u00C0-\u024F.&']*)+", txt):
                if len(m.group(0)) <= 16:
                    sp |= {m.start() + i for i, ch in enumerate(m.group(0)) if ch == ' '}
            sp |= {m.start() + 8 for m in re.finditer('Property Media', txt)}
            pos = 0
            for t in tn:
                st = str(t)
                hit = [i - pos for i in sp if pos <= i < pos + len(st)]
                if hit:
                    chars = list(st)
                    for i in hit:
                        chars[i] = '\u00a0'
                    t.replace_with(NavigableString(''.join(chars)))
                pos += len(st)
        el['class'] = (el.get('class') or []) + ['jp-phrase']

# ---------- Japanese-only additions ----------
from urllib.parse import quote
MAIL_SUBJECT = '撮影のお見積もり依頼'
MAIL_BODY = '会社名：\nご担当者名：\n物件の所在地：\n撮影希望日：\nご希望のサービス（写真・動画・ドローン・間取り図など）：\n'
MAIL_BTN = (f'<a class="btn contact-mail-btn" href="mailto:team@propertymedia.jp?subject={quote(MAIL_SUBJECT)}&amp;body={quote(MAIL_BODY)}">'
            'メールで問い合わせる</a>')
EXTRA_FAQ = {
    'index.html': [
        ('お見積もりを依頼するときは、何を伝えればよいですか？',
         '物件の所在地、おおよその広さ（㎡）、ご希望のサービス（写真、動画、ドローン空撮、間取り図など）、撮影希望日をお知らせください。料金は物件の広さと必要なサービスによって決まるため、これらがそろえば、幅のある目安ではなく具体的な金額でお見積もりをお送りします。'),
        ('雪の日や天候が悪い日も撮影できますか？',
         'はい。大雪の時期も含めて一年を通して撮影しています。外観とドローン空撮は天候と光で仕上がりが大きく変わるため、空いている日ではなく、条件の良い日を選んで日程を組みます。'),
        ('ホテルや宿泊施設の撮影も依頼できますか？',
         'はい。ニセコと北海道各地のホテル、ロッジ、サービスアパートメント、貸別荘で、客室、レストラン、ロビー、温泉、建物の外観を撮影し、Booking.comやExpediaなどOTA（予約サイト）の仕様に合わせて納品します。最近の実績には、ヒラフのAlpen Ridge Hotel Niseko、Club Med SahoroのレストランDaichiとMina Mina、貸別荘のMakkari Houseがあります。'),
    ],
    'niseko-real-estate-property-photographer/index.html': [
        ('動画撮影や間取り図も、あわせて依頼できますか？',
         'はい。物件動画、ドローン空撮、間取り図、バーチャルステージングは、どのプランにもオプションとして追加できます。間取り図は写真撮影と同時にご依頼いただくと、別々にご依頼いただくより費用を抑えられます。ドローン空撮は、天候と光の条件が合うタイミングに合わせて行います。'),
    ],
}
# Pages whose main text is written directly in Japanese (legal text)
JA_MAIN = {'privacy/index.html': '_i18n/privacy_ja.html'}
SVC = {
    'photo': ('/ja/niseko-real-estate-property-photographer/', '不動産撮影（物件写真）'),
    'video': ('/ja/niseko-real-estate-property-videographer/', '物件動画・ドローン空撮'),
    'plan': ('/ja/niseko-real-estate-property-floorplan/', '間取り図・3D'),
    'staging': ('/ja/niseko-real-estate-property-floorplan/#virtual-staging', 'バーチャルステージング'),
    'hotel': ('/ja/niseko-hotel-photography/', 'ホテル・宿泊施設の撮影'),
}
RELATED = {
    'kutchan-house-2': ['staging', 'photo'], 'hikari-house': ['photo', 'plan'],
    'makkari-house': ['photo', 'video'], 'pinnacle-niseko': ['video'],
    'alpen-ridge': ['hotel', 'photo'], 'club-med-sahoro': ['hotel', 'photo'],
    'kamana-lakehouse': ['hotel', 'video'],
}

def add_extra_faq(soup, rel):
    items = EXTRA_FAQ.get(rel)
    if not items:
        return []
    last = soup.select('.faq-item')[-1]
    n = len(soup.select('.faq-item'))
    for q, a in items:
        html = (f'<div class="faq-item"><button class="faq-question" type="button" aria-expanded="false" aria-controls="faq-a{n}" id="faq-q{n}">'
                f'<span class="faq-question-text">{q}</span><span class="faq-icon" aria-hidden="true"></span></button>'
                f'<div class="faq-answer" id="faq-a{n}" role="region" aria-labelledby="faq-q{n}"><p>{a}</p></div></div>')
        node = BeautifulSoup(html, 'html.parser')
        last.insert_after(node)
        last = soup.select('.faq-item')[-1]
        n += 1
    return items

def add_related(soup, rel):
    if '/' not in rel or not rel.startswith('niseko-real-estate-property-photographer-hokkaido-japan/'):
        return
    slug = rel.split('/')[1]
    if not slug or slug == 'index.html':
        return
    keys = next((v for k, v in RELATED.items() if slug.startswith(k)), ['photo'])
    box = soup.select_one('.project-intro-right')
    if not box:
        return
    links = '、'.join(f'<a href="{SVC[k][0]}">{SVC[k][1]}</a>' for k in keys)
    box.append(BeautifulSoup(f'<p class="project-related">関連サービス：{links}</p>', 'html.parser'))
    # quote buttons go to the form on the matching service page
    tgt = SVC[keys[0]][0].split('#')[0] + '#contact'
    for a in soup.select('main a.btn-solid'):
        if a.get('href') == '/ja/#contact':
            a['href'] = tgt

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

        if 'og:site_name' not in src and '<meta property="og:type"' in src:
            src = re.sub(r'(<meta property="og:type"[^>]*>)', r'\1\n  <meta property="og:site_name" content="Property Media Japan">', src, count=1)
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
        if rel in JA_MAIN:
            body = soup.select_one('.legal-body')
            body.clear()
            for n in list(BeautifulSoup(open(os.path.join(ROOT, JA_MAIN[rel])).read(), 'html.parser').contents):
                body.append(n)
            body['translate'] = 'no'
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
        for fr in soup.select('iframe[src*="studioninja"]'):
            fr['src'] = fr['src'].replace(SN_FORM_EN, SN_FORM_JA)
        for el in soup.select('.contact-form-privacy'):
            el.decompose()
        sub = soup.select_one('.contact-form-sub')
        if sub and not soup.select_one('.contact-form-note'):
            sub.insert_after(BeautifulSoup(FORM_NOTE + MAIL_BTN + TRUST, 'html.parser'))
        extra = add_extra_faq(soup, rel)
        if extra:
            for sc in soup.find_all('script', type='application/ld+json'):
                d = json.loads(sc.string)
                for node in d.get('@graph', [d]):
                    if node.get('@type') == 'FAQPage':
                        node['mainEntity'] += [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in extra]
                sc.string = json.dumps(d, ensure_ascii=False)
        add_related(soup, rel)
        legal = soup.select_one('footer .footer-legal')
        if legal and not soup.select_one('.footer-contact'):
            legal.insert(0, BeautifulSoup(FOOT_CONTACT, 'html.parser'))
        flinks = soup.select_one('footer .footer-links')
        if flinks and not flinks.select_one('a[href="/ja/advantage/#about"]'):
            flinks.append(BeautifulSoup('<li><a href="/ja/advantage/#about">会社概要</a></li>', 'html.parser'))
        for box in soup.select('.project-cta-actions, .cta-strip-actions'):
            box.insert_after(BeautifulSoup(DIRECT, 'html.parser'))
        for el in soup.select('.hero-actions, .page-hero-actions, .page-hero-inner > a.btn-solid'):
            el.insert_after(BeautifulSoup(REASSURE, 'html.parser'))
        if not soup.select_one('meta[property="og:image:alt"]'):
            img = soup.select_one('.hero img[alt], .page-hero img[alt], .project-hero img[alt], main img[alt]')
            og = soup.select_one('meta[property="og:image:height"]')
            if img and og and img.get('alt'):
                tag = soup.new_tag('meta', attrs={'property': 'og:image:alt', 'content': img['alt']})
                og.insert_after(tag)
        h1 = None
        if soup.h1:
            h1c = BeautifulSoup(str(soup.h1), 'html.parser')
            for br in h1c.find_all('br'):
                br.replace_with(' ')
            h1 = re.sub(r'\s+', ' ', h1c.get_text('')).strip()
        if h1:
            for sc in soup.find_all('script', type='application/ld+json'):
                d = json.loads(sc.string)
                for node in d.get('@graph', [d]):
                    if node.get('@type') == 'CreativeWork':
                        node['headline'] = h1
                sc.string = json.dumps(d, ensure_ascii=False)
        for el in soup.select('.legal-body[translate]'):
            del el['translate']
        add_phrases(soup, parser)
        # number ranges such as 20〜40枚 never split across lines
        for t in list(soup.body.find_all(string=re.compile(r'\d+〜\d+'))):
            if isinstance(t, Comment) or t.parent.name in ('script', 'style', 'title') or 'nowrap' in (t.parent.get('class') or []):
                continue
            html = re.sub(r'(（?\d[\d,]*〜\d[\d,]*(?:[枚件分秒年]|時間|日間|㎡)?）?)', r'<span class="nowrap">\1</span>', str(t))
            t.replace_with(BeautifulSoup(html, 'html.parser'))
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

"""Open Pic-Time galleries, capture data calls and image URLs, click into each set, scroll inner containers."""
import asyncio, json, os, re
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pictime2')
os.makedirs(OUT, exist_ok=True)
URLS = {'alpenridge': 'https://delivery.pic-time.com/-alpenridge/gallery', 'clubmedsahoro': 'https://delivery.pic-time.com/-clubmedsahoro/gallery'}
SCROLL = """() => { let n=0; document.querySelectorAll('*').forEach(e=>{ const s=getComputedStyle(e); if((s.overflowY=='auto'||s.overflowY=='scroll') && e.scrollHeight>e.clientHeight+50){ e.scrollTop+=2000; n++; } }); window.scrollBy(0,2000); return n; }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for slug, u in URLS.items():
            ctx = await b.new_context(viewport={'width': 1600, 'height': 1000})
            pg = await ctx.new_page(); log = []; bodies = []
            async def on_resp(r):
                rt = r.request.resource_type
                log.append({'url': r.url, 'type': rt, 'status': r.status})
                if rt in ('xhr', 'fetch') and r.status == 200:
                    try:
                        t = await r.text()
                        if len(t) < 3_000_000: bodies.append({'url': r.url, 'post': r.request.post_data, 'body': t})
                    except Exception: pass
            pg.on('response', lambda r: asyncio.ensure_future(on_resp(r)))
            await pg.goto(u, wait_until='load', timeout=90000)
            await pg.wait_for_timeout(4000)
            await pg.screenshot(path=f'{OUT}/{slug}-top.png', full_page=False)
            for i in range(30):
                await pg.evaluate(SCROLL); await pg.wait_for_timeout(500)
            await pg.screenshot(path=f'{OUT}/{slug}-scrolled.png', full_page=False)
            # click each set / scene name
            for name in ['GALLERY', 'DRONE', 'EDITED', 'RETOUCHED', 'SNIPPETS']:
                try:
                    loc = pg.get_by_text(name, exact=True).first
                    if await loc.count():
                        await loc.click(timeout=4000); await pg.wait_for_timeout(2500)
                        for i in range(20):
                            await pg.evaluate(SCROLL); await pg.wait_for_timeout(400)
                        await pg.screenshot(path=f'{OUT}/{slug}-{name}.png')
                except Exception as e:
                    log.append({'click_error': name, 'err': str(e)[:200]})
            await pg.wait_for_timeout(2000)
            json.dump(log, open(f'{OUT}/{slug}-log.json', 'w'), indent=0)
            json.dump(bodies, open(f'{OUT}/{slug}-xhr.json', 'w'))
            imgs = sorted({l['url'] for l in log if l.get('type') == 'image' and '/pictures/' in l.get('url', '')})
            print(slug, 'responses', len(log), 'xhr bodies', len(bodies), 'images', len(imgs))
            await ctx.close()
        await b.close()
import traceback
try:
    asyncio.run(main())
except Exception:
    open(os.path.join(OUT, 'error.txt'), 'w').write(traceback.format_exc())
    print(traceback.format_exc())

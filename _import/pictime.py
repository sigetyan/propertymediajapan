"""Open Pic-Time galleries in a headless browser, log image URLs, save screenshots and page info."""
import asyncio, json, os, re
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pictime')
os.makedirs(OUT, exist_ok=True)
URLS = ['https://delivery.pic-time.com/-alpenridge', 'https://delivery.pic-time.com/-clubmedsahoro',
        'https://delivery.pic-time.com/-clubmed', 'https://delivery.pic-time.com/-sahoro',
        'https://delivery.pic-time.com/-clubmedsahorof&b', 'https://delivery.pic-time.com/-miaja']
async def main():
    report = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for u in URLS:
            ctx = await b.new_context(viewport={'width': 1600, 'height': 1000})
            pg = await ctx.new_page(); imgs = []
            pg.on('response', lambda r: imgs.append(r.url) if 'pictures/' in r.url and r.request.resource_type == 'image' else None)
            slug = re.sub(r'\W', '', u.split('-', 1)[1])
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000)
                await pg.wait_for_timeout(3000)
                for _ in range(40):
                    await pg.mouse.wheel(0, 2500); await pg.wait_for_timeout(600)
                title = await pg.title()
                html = await pg.content()
                await pg.screenshot(path=f'{OUT}/{slug}.png')
                dom = await pg.evaluate("""() => [...document.querySelectorAll('img')].map(i => i.currentSrc || i.src)""")
                scenes = await pg.evaluate("""() => [...document.querySelectorAll('a,button,span,div')].map(e=>e.innerText).filter(t=>t && t.length<40)""")
                report[u] = {'title': title, 'final_url': pg.url, 'n_net': len(set(imgs)), 'net': sorted(set(imgs)), 'dom': sorted(set(dom)), 'text': sorted(set(scenes))[:200]}
                open(f'{OUT}/{slug}.html', 'w').write(html)
            except Exception as e:
                report[u] = {'error': str(e)[:300]}
            await ctx.close()
        await b.close()
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1)
    for u, r in report.items(): print(u, r.get('title'), r.get('n_net'), r.get('error'))
asyncio.run(main())

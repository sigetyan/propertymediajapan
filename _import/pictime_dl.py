"""Download every photo from the two Pic-Time galleries at the largest size the CDN serves."""
import json, os, re, urllib.request
from io import BytesIO
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'pictime2')
OUT = os.path.join(HERE, 'ptdl')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36',
      'Referer': 'https://delivery.pic-time.com/'}
FOLDERS = ['hires', 'highres', 'hd', 'fullres', 'largeres', 'bigres', 'midres', 'mediumres', 'medres', 'webres', 'lowres']
report = {}


def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b''
    except Exception as e:
        return str(e), b''


# learn folder names from the photo worker script
st, js = get('https://pictime2seaus1public-pub-dpgtauede2fua8dc.a02.azurefd.net/pictures/scripts/compiled/photoloadworker.js')
names = sorted(set(re.findall(rb'([a-z]{2,12}res)\b', js)))
report['worker_res_names'] = [n.decode() for n in names]
for n in report['worker_res_names']:
    if n not in FOLDERS: FOLDERS.insert(0, n)

for slug in ('alpenridge', 'clubmedsahoro'):
    x = json.load(open(os.path.join(SRC, f'{slug}-xhr.json')))
    gu = [b['url'] for b in x if '/gallery.json.txt' in b['url']][0].split('/gallery.json')[0]
    g = [json.loads(b['body']) for b in x if '/gallery.json.txt' in b['url']][0]
    meta = [json.loads(b['body']) for b in x if 'gallery_meta.json' in b['url']][0]
    mid = int(g['minId'])
    mp = meta['photos']; names_by_idx = {mp[i]: mp[i + 3] for i in range(0, len(mp), 4)}
    scenes = {}
    for sc in g['scenes']:
        ph = sc['photos']
        scenes[sc['nm']] = [mid + ph[i] for i in range(0, len(ph), 5)]
    probe = {}
    first = next(v[0] for v in scenes.values() if v)
    best, bestw = 'lowres', 0
    for f in FOLDERS:
        st, b = get(f'{gu}/{f}/{first}.jpg')
        info = {'status': st, 'bytes': len(b)}
        if b:
            try:
                im = Image.open(BytesIO(b)); info['size'] = im.size
                if max(im.size) > bestw: best, bestw = f, max(im.size)
            except Exception as e:
                info['err'] = str(e)
        probe[f] = info
    rep = {'base': gu, 'probe': probe, 'best': best, 'scenes': {}, 'meta_first': list(names_by_idx.items())[:5]}
    for scn, ids in scenes.items():
        d = os.path.join(OUT, slug, scn.lower()); os.makedirs(d, exist_ok=True)
        got = []
        for pid in ids:
            fn = os.path.join(d, f'{pid}.jpg')
            if os.path.exists(fn): got.append(pid); continue
            for f in (best, 'lowres'):
                st, b = get(f'{gu}/{f}/{pid}.jpg')
                if b:
                    open(fn, 'wb').write(b); got.append(pid); break
        rep['scenes'][scn] = {'count': len(ids), 'downloaded': len(got)}
    report[slug] = rep
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1, default=str)
print(json.dumps(report, indent=1, default=str)[:3000])

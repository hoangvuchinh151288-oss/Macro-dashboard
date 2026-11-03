# -*- coding: utf-8 -*-
"""
Tu dong cap nhat cac field CORE thuan so trong data.js.
Chay tren GitHub Actions runner (co mang), KHONG chay duoc trong moi truong bi chan egress.

NGUYEN TAC AN TOAN — doc truoc khi sua:
  1. Parser nao khong lay duoc so thi BO QUA field do, giu nguyen gia tri cu.
     TUYET DOI khong ghi so doan. Tha cu con hon sai.
  2. Moi gia tri moi phai qua kiem tra bien do hop ly (SANITY). Lech qua nguong
     thi tu choi ghi va ghi vao bao cao — chan truong hop nguon doi format tra ve rac.
  3. Chi dong vao field CORE thuan so. Note, dien giai, kich ban deu lam tay.
  4. Luon ghi tools/last_run.json de kiem chung tu xa khi khong doc duoc log Actions.

NHAT KY LOI DA GAP — dung lap lai:
  * Run #1 (02/11/2026): VCB tra ve 2561000 thay vi 25610. Nguyen nhan: XML VCB dung
    dinh dang My "25,610.00" (phay = phan cach nghin, cham = thap phan) nhung parser
    xoa CA phay VA cham. Lop kiem tra bien do DA CHAN duoc, khong ghi sai vao data.js.
    Sua: chi xoa dau phay.
  * Run #1: stooq tra ve HTTP 404 cho ca 4 ma. Sua: doi sang Yahoo Finance lam nguon
    chinh, giu stooq lam du phong, va ghi lai nguon nao da dung duoc.

Chay tay:  python3 tools/fetch_core.py            (ghi that)
           python3 tools/fetch_core.py --dry-run  (chi in, khong ghi)
"""
import re, io, os, sys, json, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data.js')
REPORT = os.path.join(ROOT, 'tools', 'last_run.json')
DRY = '--dry-run' in sys.argv
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
DSTR = TODAY.strftime('%d/%m/%Y')

report = {'run_at_ict': TODAY.strftime('%Y-%m-%d %H:%M:%S'), 'ok': {}, 'skipped': {},
          'written': [], 'source_tried': {}}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def vn(x, dec=2):
    """So -> chuoi kieu VN: 117.64 -> '117,64'"""
    return ('%.*f' % (dec, x)).replace('.', ',')


# ------------------------------------------------------------------ NGUON
_vcb_cache = {}

def src_vcb():
    """XML ty gia cong khai cua Vietcombank. Tra ve (mua_chuyen_khoan, ban).
    Dinh dang so trong XML la kieu My: '25,610.00' — phay la phan cach nghin."""
    if 'v' in _vcb_cache:
        return _vcb_cache['v']
    x = get('https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=10')
    m = re.search(r'<Exrate[^>]*CurrencyCode="USD"[^>]*>', x)
    if not m:
        raise ValueError('khong tim thay dong USD trong XML VCB')
    tag = m.group(0)
    tr = re.search(r'Transfer="([\d.,]+)"', tag)
    sl = re.search(r'Sell="([\d.,]+)"', tag)
    if not (tr and sl):
        raise ValueError('thieu thuoc tinh Transfer/Sell: ' + tag[:140])
    f = lambda s: float(s.replace(',', ''))          # CHI xoa phay, giu dau cham thap phan
    out = (f(tr.group(1)), f(sl.group(1)))
    if not all(1000 < v < 100000 for v in out):
        raise ValueError('so VCB sau khi parse khong hop ly: %s (tag: %s)' % (out, tag[:140]))
    _vcb_cache['v'] = out
    return out


def yahoo(sym):
    """Yahoo Finance chart API -> gia dong cua gan nhat."""
    u = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d' % sym
    j = json.loads(get(u))
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise ValueError('yahoo %s: khong co result (%s)' % (sym, str(j)[:160]))
    r0 = res[0]
    closes = [c for c in (r0['indicators']['quote'][0].get('close') or []) if c is not None]
    if closes:
        return float(closes[-1])
    mp = (r0.get('meta') or {}).get('regularMarketPrice')
    if mp is None:
        raise ValueError('yahoo %s: khong co gia dong cua' % sym)
    return float(mp)


def stooq(sym, host='stooq.com'):
    """Stooq CSV: Symbol,Date,Time,Open,High,Low,Close,Volume"""
    csv = get('https://%s/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv' % (host, sym))
    rows = [r for r in csv.strip().splitlines() if r.strip()]
    if len(rows) < 2:
        raise ValueError('stooq %s tra ve rong' % sym)
    cols = rows[1].split(',')
    if len(cols) < 7 or cols[6] in ('N/D', ''):
        raise ValueError('stooq %s khong co gia dong cua: %s' % (sym, rows[1][:80]))
    return float(cols[6])


# Moi field co MOT CHUOI nguon du phong. Thu lan luot, cai nao duoc thi dung,
# va ghi lai nguon nao da dung de lan sau biet nguon nao on dinh.
# (ten_field): [ (ten_nguon, ham), ... ], min, max, so chu so thap phan
SOURCES = {
    'fx.vcb_mua':  ([('VCB XML', lambda: src_vcb()[0])],                     20000, 32000, 0),
    'fx.vcb_ban':  ([('VCB XML', lambda: src_vcb()[1])],                     20000, 32000, 0),
    'oil.brent':   ([('yahoo BZ=F',  lambda: yahoo('BZ%3DF')),
                     ('stooq cb.f',  lambda: stooq('cb.f')),
                     ('stooq.pl cb.f', lambda: stooq('cb.f', 'stooq.pl'))],     30,   250, 2),
    'oil.wti':     ([('yahoo CL=F',  lambda: yahoo('CL%3DF')),
                     ('stooq cl.f',  lambda: stooq('cl.f')),
                     ('stooq.pl cl.f', lambda: stooq('cl.f', 'stooq.pl'))],     25,   240, 2),
    'gold.tg_usd': ([('yahoo GC=F',  lambda: yahoo('GC%3DF')),
                     ('stooq xauusd', lambda: stooq('xauusd')),
                     ('stooq.pl xauusd', lambda: stooq('xauusd', 'stooq.pl'))], 1500, 9000, 2),
    'dxy.value':   ([('yahoo DX-Y.NYB', lambda: yahoo('DX-Y.NYB')),
                     ('yahoo DX=F',  lambda: yahoo('DX%3DF')),
                     ('stooq dx.f',  lambda: stooq('dx.f'))],                   80,   130, 2),
}


# ------------------------------------------------------------- GHI data.js
def field_block(d, dom, fn):
    dm = re.search(r'\n  ' + re.escape(dom) + r':\s*\{', d)
    if not dm: return None
    b0 = d.find('{', dm.start()); k = 0
    for j in range(b0, len(d)):
        if d[j] == '{': k += 1
        elif d[j] == '}': k -= 1
        if k == 0: e0 = j + 1; break
    blk = d[b0:e0]
    fm = re.search(r'\b' + re.escape(fn) + r':\s*\{', blk)
    if not fm: return None
    b1 = blk.find('{', fm.start()); k = 0
    for j in range(b1, len(blk)):
        if blk[j] == '{': k += 1
        elif blk[j] == '}': k -= 1
        if k == 0: e1 = j + 1; break
    return (b0, e0, b1, e1, blk)


def current_number(d, dom, fn):
    loc = field_block(d, dom, fn)
    if not loc: return None
    b0, e0, b1, e1, blk = loc
    vm = re.search(r'value:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+)', blk[b1:e1])
    if not vm: return None
    t = vm.group(1).strip('"')
    m = re.search(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?', t)
    if not m: return None
    v = m.group(0)
    if re.fullmatch(r'\d+\.\d{1,2}', v): return float(v)
    return float(v.replace('.', '').replace(',', '.'))


def write_field(d, dom, fn, newval_str, src, note):
    loc = field_block(d, dom, fn)
    if not loc: raise KeyError(dom + '.' + fn)
    b0, e0, b1, e1, blk = loc
    b = blk[b1:e1]
    b = re.sub(r'value:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+)', 'value: "' + newval_str + '"', b, count=1)
    b = re.sub(r'updated:\s*"[^"]*"', 'updated: "' + DSTR + '"', b, count=1)
    b = re.sub(r'source:\s*"(?:[^"\\]|\\.)*"', 'source: "[MARKET] auto ' + src + '"', b, count=1)
    b = re.sub(r'note:\s*"(?:[^"\\]|\\.)*"', 'note: "' + note.replace('"', "'") + '"', b, count=1)
    return d[:b0] + blk[:b1] + b + blk[e1:] + d[e0:]


def main():
    d = io.open(DATA, encoding='utf-8').read()
    for path, (candidates, lo, hi, dec) in SOURCES.items():
        dom, fn = path.split('.')
        val = None; src = None; tried = []
        for name, fetch in candidates:
            try:
                val = fetch(); src = name; tried.append(name + ': OK')
                break
            except Exception as ex:
                tried.append('%s: %s %s' % (name, type(ex).__name__, str(ex)[:110]))
        report['source_tried'][path] = tried
        if val is None:
            report['skipped'][path] = 'TAT CA NGUON DEU LOI'
            continue
        if not (lo <= val <= hi):
            report['skipped'][path] = 'NGOAI BIEN HOP LY [%s,%s]: %s (nguon %s) — tu choi ghi' % (lo, hi, val, src)
            continue
        old = current_number(d, dom, fn)
        if old and old > 0:
            chg = abs(val - old) / old
            if chg > 0.15:
                report['skipped'][path] = 'LECH %.1f%% so gia tri cu %s (moi: %s, nguon %s) — tu choi ghi, can kiem tra tay' % (chg * 100, old, val, src)
                continue
        txt = vn(val, dec) if dec else ('%d' % round(val))
        delta = '' if not old else (' (%+.2f so lan cap nhat truoc)' % (val - old)).replace('.', ',')
        note = ('TU DONG cap nhat %s tu %s%s · Gia tri nay do tools/fetch_core.py ghi, '
                'KHONG phai phan tich. Dien giai va nhan dinh van lam tay.' % (DSTR, src, delta))
        d = write_field(d, dom, fn, txt, src, note)
        report['ok'][path] = {'old': old, 'new': val, 'src': src}
        report['written'].append(path)

    report['summary'] = '%d ghi / %d bo qua' % (len(report['written']), len(report['skipped']))
    out = json.dumps(report, ensure_ascii=False, indent=2)
    if DRY:
        print(out); return 0
    io.open(DATA, 'w', encoding='utf-8').write(d)
    io.open(REPORT, 'w', encoding='utf-8').write(out + '\n')
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

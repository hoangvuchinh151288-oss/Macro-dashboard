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
import re, io, os, sys, json, time, datetime, urllib.request, urllib.error

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
    # Lay ngay cong bo tu chinh XML. Khong co ngay thi ham ghi se gan ngay
    # CHAY, va mot phien cuoi tuan se dong dau ngay moi len dung gia hom
    # thu Sau — so dung im nhung trong nhu vua cap nhat.
    ng = None
    dm = re.search(r'<DateTime>([^<]+)</DateTime>', x)
    if not dm:
        # Khong co the <DateTime> thi ham ghi se lang le gan ngay CHAY. Phai
        # bao ra, neu khong se khong phan biet duoc 'doc dung ngay cong bo'
        # voi 'roi ve ngay hom nay' — hai cai nay trung nhau vao ngay thuong.
        report.setdefault('ghi_chu', []).append(
            'VCB XML KHONG co the <DateTime> — updated se lay ngay chay')
    if dm:
        raw = dm.group(1).strip()
        for pat in ('%m/%d/%Y %I:%M:%S %p', '%d/%m/%Y %I:%M:%S %p',
                    '%m/%d/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                ng = datetime.datetime.strptime(raw, pat).date().isoformat()
                break
            except ValueError:
                continue
        if ng is None:
            report.setdefault('ghi_chu', []).append(
                'VCB <DateTime> khong khop dinh dang nao: %r' % raw[:40])
    out = (out[0], out[1], ng)
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


def fred(series):
    """FRED (Fed St. Louis) CSV cong khai, khong can API key, than thien voi CI.
    Tra ve (gia_tri, ngay_du_lieu). LUU Y: FRED tre vai ngay so thi truong —
    ham tra ve ca ngay de ghi vao note, KHONG duoc trinh bay nhu gia hien tai.

    Run #3 bi TimeoutError: chuoi DCOILBRENTEU co du lieu tu 1987, tai ca chuoi
    qua lau. Sua: them tham so cosd de chi lay 45 ngay gan nhat, va nang timeout."""
    cosd = (TODAY - datetime.timedelta(days=45)).strftime('%Y-%m-%d')
    csv = get('https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s' % (series, cosd),
              timeout=45)
    rows = [r.strip() for r in csv.strip().splitlines() if r.strip()]
    for r in reversed(rows[1:]):
        parts = r.split(',')
        if len(parts) >= 2 and parts[-1] not in ('.', '', 'NA'):
            return float(parts[-1]), parts[0]
    raise ValueError('FRED %s: khong co gia tri hop le trong 45 ngay' % series)


def stooq_dl(sym, host='stooq.com'):
    """Duong dan tai CSV lich su cua stooq, khac duong dan quote nhanh da bi 404."""
    csv = get('https://%s/q/d/l/?s=%s&i=d' % (host, sym))
    rows = [r.strip() for r in csv.strip().splitlines() if r.strip()]
    if len(rows) < 2:
        raise ValueError('stooq_dl %s tra ve rong: %s' % (sym, csv[:80]))
    cols = rows[-1].split(',')
    if len(cols) < 5:
        raise ValueError('stooq_dl %s dong cuoi la: %s' % (sym, rows[-1][:80]))
    return float(cols[4])


def yahoo2(sym):
    """query2 thay cho query1 — doi khi gioi han toc do khac."""
    u = 'https://query2.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d' % sym
    j = json.loads(get(u))
    res = (j.get('chart') or {}).get('result') or []
    if not res: raise ValueError('yahoo2 %s: khong co result' % sym)
    r0 = res[0]
    closes = [c for c in (r0['indicators']['quote'][0].get('close') or []) if c is not None]
    if closes: return float(closes[-1])
    mp = (r0.get('meta') or {}).get('regularMarketPrice')
    if mp is None: raise ValueError('yahoo2 %s: khong co gia' % sym)
    return float(mp)


def gold_api():
    """api.gold-api.com — gia vang GIAO NGAY XAU/USD, khong can khoa.
    Doc them moc thoi gian neu API co tra ve: bao gia truc tiep ma gan ngay
    chay thi mot phien cuoi tuan se dong dau ngay thu Bay len gia dong cua
    hom thu Sau."""
    js = json.loads(get('https://api.gold-api.com/price/XAU', 30))
    gia = float(js['price'])
    for k in ('updatedAt', 'updated_at', 'timestamp', 'time', 'date'):
        v = js.get(k)
        if not v:
            continue
        try:
            if isinstance(v, (int, float)):
                gio = datetime.datetime.fromtimestamp(v / (1000 if v > 1e11 else 1),
                                                      datetime.timezone.utc)
            else:
                gio = datetime.datetime.fromisoformat(str(v).replace('Z', '+00:00'))
            return gia, gio.date().isoformat()
        except (ValueError, OSError, OverflowError):
            continue
    report.setdefault('ghi_chu', []).append(
        'gold-api khong tra ve moc thoi gian (cac khoa co: %s)' % list(js)[:8])
    return gia


def eia_xls(kind):
    """EIA — U.S. Energy Information Administration, CO QUAN CONG BO. Chuoi gia
    GIAO NGAY Brent (RBRTE) va WTI (RWTC), dung chuoi ma FRED phat hanh lai,
    nen thay FRED bang EIA la giu NGUYEN chuoi so chu khong doi cong cu.
    File .xls dinh dang BIFF cu, doc bang xlrd 2.x. Tra ve (gia, ngay quan sat)."""
    import xlrd
    u = ('https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls' if kind == 'brent'
         else 'https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls')
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    wb = xlrd.open_workbook(file_contents=raw)
    sh = wb.sheet_by_index(1)          # sheet 0 la muc luc, sheet 1 la du lieu
    for i in range(sh.nrows - 1, 2, -1):
        gt = sh.cell_value(i, 1)
        if isinstance(gt, float) and gt > 0:
            ng = xlrd.xldate_as_datetime(sh.cell_value(i, 0), wb.datemode)
            return float(gt), ng.strftime('%Y-%m-%d')
    raise ValueError('EIA %s: khong tim thay dong co so' % kind)


def datahub(path):
    """raw.githubusercontent datasets/oil-prices — phat hanh lai chinh chuoi EIA.
    Cap nhat that thuong nen chi dung lam du phong; ngay quan sat duoc tra ve
    de ham main tu choi neu qua cu."""
    csv = get('https://raw.githubusercontent.com/datasets/%s' % path, 30)
    rows = [r for r in csv.strip().split('\n')[1:] if r.strip()]
    last = rows[-1].split(',')
    return float(last[1]), last[0]


def cnbc(sym):
    """CNBC quote json, khong can khoa. LUU Y: @LCO.1 / @CL.1 / @GC.1 la HOP DONG
    TUONG LAI thang gan, KHAC voi gia giao ngay cua EIA — chenh 2-3%. Chi dung
    lam du phong cuoi va phai ghi ro trong note. Rieng .DXY dung la chi so ICE."""
    u = ('https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol'
         '?symbols=%s&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1'
         '&output=json&events=1' % sym)
    js = json.loads(get(u, 30))
    q = js['FormattedQuoteResult']['FormattedQuote'][0]
    return float(str(q['last']).replace(',', '')), str(q.get('last_time', ''))[:10]


def ecb_dxy():
    """DXY suy ra tu ty gia tham chieu ECB theo cong thuc va trong so da cong bo:
       USDX = 50.14348112 x EURUSD^-0.576 x USDJPY^0.136 x GBPUSD^-0.119
                          x USDCAD^0.091 x USDSEK^0.042 x USDCHF^0.036
    Do thu 26/11 cho 104,04 trong khi .DXY that cua ICE la 103,794 — lech 0,24%.
    Day la SO SUY RA, khong phai chi so ICE; chi dung khi CNBC hong."""
    js = json.loads(get('https://api.frankfurter.dev/v1/latest?base=EUR'
                        '&symbols=USD,JPY,GBP,CAD,SEK,CHF', 30))
    r = js['rates']
    eurusd = r['USD']
    usdjpy, gbpusd = r['JPY'] / eurusd, eurusd / r['GBP']
    usdcad, usdsek, usdchf = r['CAD'] / eurusd, r['SEK'] / eurusd, r['CHF'] / eurusd
    v = (50.14348112 * eurusd ** -0.576 * usdjpy ** 0.136 * gbpusd ** -0.119
         * usdcad ** 0.091 * usdsek ** 0.042 * usdchf ** 0.036)
    return round(v, 2), js.get('date', '')


# Moi field co MOT CHUOI nguon du phong. Thu lan luot, cai nao duoc thi dung,
# va ghi lai nguon nao da dung de lan sau biet nguon nao on dinh.
# (ten_field): [ (ten_nguon, ham), ... ], min, max, so chu so thap phan
SOURCES = {
    # (ten_field): [ (ten_nguon, tier, ham), ... ], min, max, so chu so thap phan
    # tier di vao chuoi source cua field — PRIMARY = co quan cong bo truc tiep.
    'fx.vcb_mua':  ([('VCB XML', 'MARKET', lambda: (src_vcb()[0], src_vcb()[2]) if src_vcb()[2] else src_vcb()[0])],              20000, 32000, 0),
    'fx.vcb_ban':  ([('VCB XML', 'MARKET', lambda: (src_vcb()[1], src_vcb()[2]) if src_vcb()[2] else src_vcb()[1])],              20000, 32000, 0),

    # Brent/WTI: GIU NGUYEN chuoi gia giao ngay. FRED truoc day phat hanh lai
    # chuoi cua EIA, nay FRED timeout tu runner (do 26/11: 60s ca 4 lan) nen
    # lay thang tu EIA. CNBC la hop dong tuong lai — KHAC cong cu, chi du phong.
    'oil.brent':   ([('EIA RBRTE giao ngay', 'PRIMARY', lambda: eia_xls('brent')),
                     ('datasets/oil-prices', 'DERIVED', lambda: datahub('oil-prices/main/data/brent-daily.csv')),
                     ('CNBC @LCO.1 [TUONG LAI]', 'MARKET', lambda: cnbc('%40LCO.1'))],  30,  250, 2),
    'oil.wti':     ([('EIA RWTC giao ngay', 'PRIMARY', lambda: eia_xls('wti')),
                     ('datasets/oil-prices', 'DERIVED', lambda: datahub('oil-prices/main/data/wti-daily.csv')),
                     ('CNBC @CL.1 [TUONG LAI]', 'MARKET', lambda: cnbc('%40CL.1'))],    25,  240, 2),

    # Vang the gioi giao ngay XAU/USD. CNBC @GC.1 la COMEX tuong lai, du phong.
    'gold.tg_usd': ([('api.gold-api.com XAU giao ngay', 'MARKET', gold_api),
                     ('CNBC @GC.1 [TUONG LAI]', 'MARKET', lambda: cnbc('%40GC.1'))],  1500, 9000, 2),

    # DXY: .DXY cua CNBC dung la chi so ICE. Du phong la so SUY RA tu ty gia
    # tham chieu ECB theo cong thuc DXY da cong bo (do 26/11 lech 0,24%).
    # TUYET DOI khong dung FRED DTWEXBGS: do la chi so khac, goc 2006=100, ~121.
    'dxy.value':   ([('CNBC .DXY (ICE)', 'MARKET', lambda: cnbc('.DXY')),
                     ('ECB -> cong thuc DXY [SUY RA]', 'DERIVED', ecb_dxy)],            90,  115, 2),
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


def write_field(d, dom, fn, newval_str, src, note, tier='MARKET', ngay=None):
    loc = field_block(d, dom, fn)
    if not loc: raise KeyError(dom + '.' + fn)
    b0, e0, b1, e1, blk = loc
    b = blk[b1:e1]
    b = re.sub(r'value:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+)', 'value: "' + newval_str + '"', b, count=1)
    b = re.sub(r'updated:\s*"[^"]*"', 'updated: "' + (ngay or DSTR) + '"', b, count=1)
    b = re.sub(r'source:\s*"(?:[^"\\]|\\.)*"', 'source: "[%s] auto %s"' % (tier, src), b, count=1)
    b = re.sub(r'note:\s*"(?:[^"\\]|\\.)*"', 'note: "' + note.replace('"', "'") + '"', b, count=1)
    return d[:b0] + blk[:b1] + b + blk[e1:] + d[e0:]


def main():
    d = io.open(DATA, encoding='utf-8').read()
    for path, (candidates, lo, hi, dec) in SOURCES.items():
        dom, fn = path.split('.')
        val = None; src = None; tier = 'MARKET'; ngay = None; tried = []
        for name, tr, fetch in candidates:
            try:
                try:
                    kq = fetch()
                except Exception:
                    # Mot lan truot vi mang chap chon khong dang mat ca ngay
                    # du lieu. Thu lai mot lan roi moi chuyen nguon.
                    time.sleep(3)
                    kq = fetch()
                # Nguon co the tra ve so, hoac (so, ngay quan sat ISO).
                if isinstance(kq, tuple):
                    v, ng_iso = kq
                    # Khong nhan so qua cu: mot bo du lieu dong bang se trong
                    # nhu so moi neu ta gan ngay hom nay cho no. Gap 26/11 voi
                    # datasets/oil-prices — ban chay duoc nhung ngay chot 17/11.
                    tuoi = (TODAY.date() - datetime.date.fromisoformat(ng_iso)).days
                    if tuoi > 7:
                        tried.append('%s: BO QUA, ngay quan sat %s da %d ngay'
                                     % (name, ng_iso, tuoi))
                        continue
                    val, ngay = v, datetime.date.fromisoformat(ng_iso).strftime('%d/%m/%Y')
                else:
                    val, ngay = kq, None     # bao gia truc tiep, lay ngay hom nay
                src, tier = name, tr
                tried.append(name + ': OK')
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
        # Gia tri khong doi va nguon khong cho ngay quan sat: GIU updated cu.
        # Dong dau ngay moi len mot so khong doi se lam no trong nhu vua cap
        # nhat, va do dung la thu lop kiem tuoi sinh ra de phat hien.
        if ngay is None and old is not None and abs(val - old) < 1e-9:
            report['skipped'][path] = ('GIA TRI KHONG DOI (%s) va nguon khong cho '
                                       'ngay quan sat — giu nguyen updated cu' % old)
            continue
        txt = vn(val, dec) if dec else ('%d' % round(val))
        delta = '' if not old else (' (%+.2f so lan cap nhat truoc)' % (val - old)).replace('.', ',')
        note = ('TU DONG chay %s, ngay quan sat %s, nguon %s%s · Gia tri nay do '
                'tools/fetch_core.py ghi, KHONG phai phan tich. Dien giai va nhan '
                'dinh van lam tay.' % (DSTR, ngay or DSTR, src, delta))
        d = write_field(d, dom, fn, txt, src, note, tier, ngay)
        report['ok'][path] = {'old': old, 'new': val, 'src': src, 'tier': tier,
                              'ngay_quan_sat': ngay or DSTR,
                              'ngay_tu': 'nguon' if ngay else 'ngay chay (nguon khong cho ngay)'}
        report['written'].append(path)

    # meta.date = lan cuoi CO du lieu moi. Chi nhay khi thuc su ghi duoc field,
    # khong nhay o nhung lan chay ma moi nguon deu hong — neu khong thi no chi
    # con la ngay chay cron chu khong con noi len dieu gi ve do tuoi du lieu.
    if report['written']:
        cu_date = re.search(r'(\n  meta:\s*\{.*?\bdate:\s*")([^"]*)(")', d, re.S)
        if cu_date:
            report['meta_date'] = {'cu': cu_date.group(2), 'moi': DSTR}
            d = d[:cu_date.start(2)] + DSTR + d[cu_date.end(2):]

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

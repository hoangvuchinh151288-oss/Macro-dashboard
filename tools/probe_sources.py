#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Do thu cac nguon ung vien cho bon field CORE dang hong: oil.brent, oil.wti,
gold.tg_usd, dxy.value.

CHI DOC, khong ghi gi vao data.js. Muc dich la chay tren runner cua GitHub
Actions de biet nguon nao THAT SU goi duoc tu do — moi truong phat trien
chan gan het host ngoai package registry nen thu o day khong noi len dieu gi.

Chay:  python3 tools/probe_sources.py            (tat ca)
       python3 tools/probe_sources.py brent gold (chi vai nhom)

In ra moi nguon: OK/LOI, thoi gian, gia tri doc duoc, va 120 ky tu dau cua
phan hoi khi loi — de phan biet chan bot (tra HTML) voi timeout va 429.
"""
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
CTX = ssl.create_default_context()


def get(url, timeout=30, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode('utf-8', 'replace')


# ─────────────────────────────────────────────────────────── bo doc gia tri
def fred_csv(series):
    csv = get('https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s' % series, 60)
    rows = [r for r in csv.strip().split('\n')[1:] if r and not r.endswith(',.')]
    return float(rows[-1].split(',')[1])


def fred_txt(series):
    """Duong dan khac cua FRED, nhe hon fredgraph (text thuan, khong dung graph)."""
    txt = get('https://fred.stlouisfed.org/data/%s.txt' % series, 60)
    rows = [r.split() for r in txt.strip().split('\n') if re.match(r'^\d{4}-\d{2}-\d{2}\s', r)]
    for r in reversed(rows):
        if r[1] != '.':
            return float(r[1])
    raise ValueError('khong co so')


def datahub_csv(path):
    """datasets/* tren GitHub raw — chac chan goi duoc tu runner, nhung phai
    kiem NGAY cua dong cuoi: nhieu repo datasets da ngung cap nhat."""
    csv = get('https://raw.githubusercontent.com/datasets/%s' % path, 30)
    rows = [r for r in csv.strip().split('\n')[1:] if r.strip()]
    last = rows[-1].split(',')
    return float(last[1]), last[0]


def lbma_json(name):
    """LBMA la co quan cong bo gia vang chuan — nguon GOC, khong phai tin tong hop."""
    js = json.loads(get('https://prices.lbma.org.uk/json/%s.json' % name, 30))
    last = [r for r in js if r.get('v') and r['v'][0] is not None][-1]
    return float(last['v'][0]), last['d']


def gold_api():
    js = json.loads(get('https://api.gold-api.com/price/XAU', 30))
    return float(js['price'])


def goldprice_org():
    js = json.loads(get('https://data-asg.goldprice.org/dbXRates/USD', 30))
    return float(js['items'][0]['xauPrice'])


def stooq_dl(sym, host='stooq.com'):
    csv = get('https://%s/q/d/l/?s=%s&i=d' % (host, sym), 30)
    if '<' in csv[:200]:
        raise ValueError('tra ve HTML (tuong chan bot): ' + csv[:80].replace('\n', ' '))
    rows = [r for r in csv.strip().split('\n')[1:] if r.strip()]
    return float(rows[-1].split(',')[4])


def yahoo(sym, host='query1'):
    u = ('https://%s.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d'
         % (host, sym))
    js = json.loads(get(u, 30))
    res = (js.get('chart') or {}).get('result') or []
    r0 = res[0]
    cl = [c for c in (r0['indicators']['quote'][0].get('close') or []) if c is not None]
    if cl:
        return float(cl[-1])
    return float(r0['meta']['regularMarketPrice'])


def eia_xls(kind):
    """EIA la CO QUAN CONG BO (U.S. Energy Information Administration) — nguon GOC
    cho gia giao ngay Brent (RBRTE) va WTI (RWTC). File .xls dinh dang BIFF cu,
    doc bang xlrd 2.x. Vong do dau tai duoc 452 KB nhung chua parse."""
    import urllib.request as _u
    import xlrd
    u = ('https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls' if kind == 'brent'
         else 'https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls')
    req = _u.Request(u, headers=UA)
    with _u.urlopen(req, timeout=60) as r:
        raw = r.read()
    wb = xlrd.open_workbook(file_contents=raw)
    sh = wb.sheet_by_index(1)          # sheet 0 la muc luc, sheet 1 la du lieu
    for i in range(sh.nrows - 1, 2, -1):
        gt = sh.cell_value(i, 1)
        if isinstance(gt, float) and gt > 0:
            ng = xlrd.xldate_as_datetime(sh.cell_value(i, 0), wb.datemode)
            return float(gt), ng.strftime('%Y-%m-%d')
    raise ValueError('khong tim thay dong co so')


def cnbc(sym):
    """CNBC co endpoint quote json khong can khoa."""
    u = ('https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol'
         '?symbols=%s&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1'
         '&output=json&events=1' % sym)
    js = json.loads(get(u, 30))
    q = js['FormattedQuoteResult']['FormattedQuote'][0]
    return float(str(q['last']).replace(',', '')), str(q.get('last_time', ''))[:10]


def ecb_dxy():
    """Tinh DXY tu ty gia tham chieu ECB theo cong thuc va trong so da cong bo:
       USDX = 50.14348112 x EURUSD^-0.576 x USDJPY^0.136 x GBPUSD^-0.119
                          x USDCAD^0.091 x USDSEK^0.042 x USDCHF^0.036
    Day la SO SUY RA tu nguon goc (ECB), khong phai chi so ICE. Chenh voi DXY
    that do ECB chot mot lan/ngay con DXY chay lien tuc."""
    js = json.loads(get('https://api.frankfurter.dev/v1/latest?base=EUR'
                        '&symbols=USD,JPY,GBP,CAD,SEK,CHF', 30))
    r = js['rates']
    eurusd = r['USD']
    usdjpy = r['JPY'] / eurusd
    gbpusd = eurusd / r['GBP']
    usdcad = r['CAD'] / eurusd
    usdsek = r['SEK'] / eurusd
    usdchf = r['CHF'] / eurusd
    v = (50.14348112 * eurusd ** -0.576 * usdjpy ** 0.136 * gbpusd ** -0.119
         * usdcad ** 0.091 * usdsek ** 0.042 * usdchf ** 0.036)
    return round(v, 2), js.get('date', '')


def sjc_ashx():
    """SJC cong bo gia vang mieng tren trang chinh chu — nguon GOC trong nuoc."""
    raw = get('https://sjc.com.vn/GoldPrice/Services/PriceService.ashx', 30)
    js = json.loads(raw)
    for r in js.get('data', []):
        if 'SJC' in str(r.get('TypeName', '')) and '1L' in str(r.get('TypeName', '')):
            return (float(r['Buy'].replace(',', '')), float(r['Sell'].replace(',', '')))
    r = js['data'][0]
    return (float(str(r['Buy']).replace(',', '')), float(str(r['Sell']).replace(',', '')))


def btmc():
    """Bao Tin Minh Chau — cong bo gia vang mieng, dung doi chieu voi SJC."""
    import xml.etree.ElementTree as ET
    x = ET.fromstring(get('http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3kd8ub1llcg9t45hnoh8hmn7t5kc2v', 30))
    for d in x.iter():
        a = d.attrib
        for k in a:
            if k.startswith('pb_'):
                return float(a[k]) * 1000
    raise ValueError('khong doc duoc gia BTMC')


def bnm_oil(kind):
    """Trading Economics / investing deu chan bot. Thu nguon cua EIA dang
    'browser' khong can API key: bang gia giao ngay dang csv tren eia.gov."""
    u = ('https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls' if kind == 'brent'
         else 'https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls')
    raw = get(u, 45)
    raise ValueError('tai duoc %d byte nhung la .xls, can parse rieng' % len(raw))


# ──────────────────────────────────────────────────────────── danh sach do
UNG_VIEN = {
    'brent': [
        ('FRED DCOILBRENTEU (fredgraph.csv)', lambda: fred_csv('DCOILBRENTEU')),
        ('FRED DCOILBRENTEU (data/*.txt)', lambda: fred_txt('DCOILBRENTEU')),
        ('datasets/oil-prices brent-daily', lambda: datahub_csv('oil-prices/main/data/brent-daily.csv')),
        ('stooq.com cb.f', lambda: stooq_dl('cb.f')),
        ('stooq.pl cb.f', lambda: stooq_dl('cb.f', 'stooq.pl')),
        ('yahoo query1 BZ=F', lambda: yahoo('BZ%3DF', 'query1')),
        ('yahoo query2 BZ=F', lambda: yahoo('BZ%3DF', 'query2')),
        ('EIA RBRTEd.xls (xlrd) [NGUON GOC]', lambda: eia_xls('brent')),
        ('CNBC @LCO.1', lambda: cnbc('%40LCO.1')),
    ],
    'wti': [
        ('FRED DCOILWTICO (fredgraph.csv)', lambda: fred_csv('DCOILWTICO')),
        ('FRED DCOILWTICO (data/*.txt)', lambda: fred_txt('DCOILWTICO')),
        ('datasets/oil-prices wti-daily', lambda: datahub_csv('oil-prices/main/data/wti-daily.csv')),
        ('stooq.pl cl.f', lambda: stooq_dl('cl.f', 'stooq.pl')),
        ('yahoo query2 CL=F', lambda: yahoo('CL%3DF', 'query2')),
        ('EIA RWTCd.xls (xlrd) [NGUON GOC]', lambda: eia_xls('wti')),
        ('CNBC @CL.1', lambda: cnbc('%40CL.1')),
    ],
    'gold': [
        ('LBMA gold_pm (nguon goc)', lambda: lbma_json('gold_pm')),
        ('LBMA gold_am', lambda: lbma_json('gold_am')),
        ('api.gold-api.com XAU', gold_api),
        ('data-asg.goldprice.org', goldprice_org),
        ('stooq.pl xauusd', lambda: stooq_dl('xauusd', 'stooq.pl')),
        ('yahoo query2 GC=F', lambda: yahoo('GC%3DF', 'query2')),
        ('CNBC @GC.1', lambda: cnbc('%40GC.1')),
    ],
    'sjc': [
        ('SJC PriceService.ashx [NGUON GOC]', sjc_ashx),
        ('Bao Tin Minh Chau API', btmc),
    ],
    'dxy': [
        ('yahoo query1 DX-Y.NYB', lambda: yahoo('DX-Y.NYB', 'query1')),
        ('yahoo query2 DX-Y.NYB', lambda: yahoo('DX-Y.NYB', 'query2')),
        ('stooq.com dx.f', lambda: stooq_dl('dx.f')),
        ('stooq.pl dx.f', lambda: stooq_dl('dx.f', 'stooq.pl')),
        # FRED DTWEXBGS la chi so KHAC (broad dollar, goc 2006=100, ~121).
        # Do o day CHI de biet no con song khong, TUYET DOI khong ghi vao
        # field dxy.value — xem canh bao trong fetch_core.py.
        ('CNBC .DXY', lambda: cnbc('.DXY')),
        ('ECB frankfurter -> cong thuc DXY [SUY RA]', ecb_dxy),
    ],
}


def main():
    chon = [a for a in sys.argv[1:] if not a.startswith('-')] or list(UNG_VIEN)
    tong = {'ok': [], 'loi': []}
    for nhom in chon:
        if nhom not in UNG_VIEN:
            print('bo qua nhom la: %s' % nhom)
            continue
        print('\n' + '=' * 70)
        print('NHOM %s' % nhom.upper())
        print('=' * 70)
        for ten, fn in UNG_VIEN[nhom]:
            t0 = time.time()
            try:
                gt = fn()
                dt = time.time() - t0
                print('  OK    %-38s %7.1fs  %s' % (ten, dt, gt))
                tong['ok'].append((nhom, ten, gt))
            except Exception as e:
                dt = time.time() - t0
                mo_ta = ('%s: %s' % (type(e).__name__, e)).replace('\n', ' ')[:120]
                print('  LOI   %-38s %7.1fs  %s' % (ten, dt, mo_ta))
                tong['loi'].append((nhom, ten, mo_ta))

    print('\n' + '=' * 70)
    print('TOM TAT: %d nguon goi duoc, %d nguon loi' % (len(tong['ok']), len(tong['loi'])))
    for nhom, ten, gt in tong['ok']:
        print('  %-7s %-38s %s' % (nhom, ten, gt))
    return 0


if __name__ == '__main__':
    sys.exit(main())

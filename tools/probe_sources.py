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
        ('EIA RBRTEd.xls', lambda: bnm_oil('brent')),
    ],
    'wti': [
        ('FRED DCOILWTICO (fredgraph.csv)', lambda: fred_csv('DCOILWTICO')),
        ('FRED DCOILWTICO (data/*.txt)', lambda: fred_txt('DCOILWTICO')),
        ('datasets/oil-prices wti-daily', lambda: datahub_csv('oil-prices/main/data/wti-daily.csv')),
        ('stooq.pl cl.f', lambda: stooq_dl('cl.f', 'stooq.pl')),
        ('yahoo query2 CL=F', lambda: yahoo('CL%3DF', 'query2')),
        ('EIA RWTCd.xls', lambda: bnm_oil('wti')),
    ],
    'gold': [
        ('LBMA gold_pm (nguon goc)', lambda: lbma_json('gold_pm')),
        ('LBMA gold_am', lambda: lbma_json('gold_am')),
        ('api.gold-api.com XAU', gold_api),
        ('data-asg.goldprice.org', goldprice_org),
        ('stooq.pl xauusd', lambda: stooq_dl('xauusd', 'stooq.pl')),
        ('yahoo query2 GC=F', lambda: yahoo('GC%3DF', 'query2')),
    ],
    'dxy': [
        ('yahoo query1 DX-Y.NYB', lambda: yahoo('DX-Y.NYB', 'query1')),
        ('yahoo query2 DX-Y.NYB', lambda: yahoo('DX-Y.NYB', 'query2')),
        ('stooq.com dx.f', lambda: stooq_dl('dx.f')),
        ('stooq.pl dx.f', lambda: stooq_dl('dx.f', 'stooq.pl')),
        # FRED DTWEXBGS la chi so KHAC (broad dollar, goc 2006=100, ~121).
        # Do o day CHI de biet no con song khong, TUYET DOI khong ghi vao
        # field dxy.value — xem canh bao trong fetch_core.py.
        ('FRED DTWEXBGS [CHI SO KHAC]', lambda: fred_txt('DTWEXBGS')),
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

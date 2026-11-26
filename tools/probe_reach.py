#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Do KHA NANG KET NOI toi cac host co the lam nguon cho duong cong lien ngan hang
va bang lai suat huy dong.

Khac probe_sources.py: script nay KHONG parse gia tri. No chi tra loi mot cau —
runner cua GitHub co voi toi host do khong, va trang tra ve co chua tu khoa can
tim khong. Viet parser cho mot host bi chan la cong cốc, nen do kha nang ket noi
truoc, parse sau.

Chay:  python3 tools/probe_reach.py
In ra: ma HTTP, kich thuoc, va tu khoa nao xuat hien trong than trang.
"""
import gzip
import io
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/json,*/*',
      'Accept-Language': 'vi,en;q=0.9'}
CTX = ssl.create_default_context()

# (nhom, ten, url, [tu khoa can tim trong than trang])
MUC_TIEU = [
    # ── duong cong lien ngan hang: NHNN la co quan cong bo
    ('lnh', 'SBV lai suat BQ lien ngan hang',
     'https://www.sbv.gov.vn/webcenter/portal/vi/menu/rm/ls/lsbqlnh',
     ['qua đêm', 'Qua đêm', 'lien ngan hang', 'liên ngân hàng', '1 tuần']),
    ('lnh', 'SBV trang lai suat (goc)',
     'https://www.sbv.gov.vn/webcenter/portal/vi/menu/rm/ls',
     ['lãi suất', 'Lãi suất']),
    ('lnh', 'SBV API webcenter (thu dang json)',
     'https://www.sbv.gov.vn/webcenter/ShowProperty?nodeId=/UCMServer/SBV',
     ['']),
    ('lnh', 'VNDirect dchart api',
     'https://finfo-api.vndirect.com.vn/v4/interbank_rates?size=20',
     ['data', 'rate']),
    ('lnh', 'Vietstock finance',
     'https://finance.vietstock.vn/du-lieu-vi-mo/52/lai-suat-lien-ngan-hang.htm',
     ['qua đêm', 'Qua đêm', 'liên ngân hàng']),

    # ── bang lai suat huy dong: khong co nguon tap trung, phai tung ngan hang
    ('huydong', 'VCB bieu lai suat',
     'https://portal.vietcombank.com.vn/Personal/TG/Pages/lai-suat.aspx',
     ['lãi suất', 'Lãi suất', 'tháng']),
    ('huydong', 'BIDV bieu lai suat',
     'https://bidv.com.vn/vn/ca-nhan/cong-cu-tien-ich/lai-suat',
     ['lãi suất', 'Lãi suất']),
    ('huydong', 'VietinBank bieu lai suat',
     'https://www.vietinbank.vn/ca-nhan/lai-suat',
     ['lãi suất', 'Lãi suất']),
    ('huydong', 'Agribank bieu lai suat',
     'https://www.agribank.com.vn/vn/lai-suat',
     ['lãi suất', 'Lãi suất']),
    ('huydong', 'Techcombank bieu lai suat',
     'https://techcombank.com/cong-cu-tien-ich/bieu-phi-lai-suat/lai-suat',
     ['lãi suất', 'Lãi suất']),
    ('huydong', 'nguoiquansat tong hop [BAO CHI]',
     'https://nguoiquansat.vn/lai-suat-ngan-hang',
     ['lãi suất', 'Lãi suất']),
]


def thu(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return r.status, raw.decode('utf-8', 'replace'), time.time() - t0


def trich(url, moc, rong=1100):
    """In mot doan HTML quanh tu khoa — de biet SO co nam san trong trang hay
    trang chi la khung roi JS moi nap du lieu. Khong co so trong HTML thi
    urllib khong lay duoc, phai doi cach khac."""
    try:
        _, body, _ = thu(url, 40)
    except Exception as e:
        print('  khong tai duoc: %s' % e)
        return
    i = -1
    for m in moc:
        i = body.find(m)
        if i >= 0:
            break
    if i < 0:
        print('  khong thay moc nao trong %d byte' % len(body))
        return
    doan = re.sub(r'\s+', ' ', body[max(0, i - 200):i + rong])
    print('  ...%s...' % doan)
    so = re.findall(r'\b\d{1,2}[.,]\d{1,2}\b', doan)
    print('  >> cac so dang lai suat trong doan: %s' % (so[:20] or 'KHONG CO'))


def dao(url, ten):
    """Tim duong dan du lieu an trong trang: link file tai ve (.xls/.csv/.json)
    va cac endpoint ma JS se goi. Trang nap bang JS thi so khong nam trong HTML,
    nhung duong dan toi so thuong van nam."""
    try:
        _, body, _ = thu(url, 45)
    except Exception as e:
        print('  khong tai duoc: %s' % e)
        return
    print('  %d byte' % len(body))
    mau = {
        'file tai ve': r'["\']([^"\' ]{4,160}\.(?:xlsx?|csv|json|txt))["\']',
        'ShowProperty/nodeId': r'(ShowProperty[^"\' <>]{0,120})',
        'endpoint ajax/api': r'["\'](/?[\w./-]*(?:api|ajax|service|handler|getdata|rest)[\w./?=&-]{0,90})["\']',
    }
    for nhan, pat in mau.items():
        hit = []
        for m in re.findall(pat, body, re.I):
            m = m if isinstance(m, str) else m[0]
            if m not in hit:
                hit.append(m)
        print('  %-20s %s' % (nhan, hit[:6] if hit else 'khong thay'))


SERVLET = [
    ('BIDV InterestDetailServlet', 'https://bidv.com.vn/ServicesBIDV/InterestDetailServlet'),
    ('BIDV InterestDetailOnlineServlet', 'https://bidv.com.vn/ServicesLaiSuatOnline/InterestDetailOnlineServlet'),
    ('BIDV InterestDetailDepositsServlet', 'https://bidv.com.vn/ServicesLaiSuatOnline/InterestDetailDepositsServlet'),
]


def servlet():
    """Thu truc tiep cac endpoint tim duoc o che do --dao."""
    for ten, url in SERVLET:
        try:
            ma, body, dt = thu(url, 30)
            dau = re.sub(r'\s+', ' ', body[:260])
            so = re.findall(r'\b\d{1,2}[.,]\d{1,2}\b', body)
            print('  %-3s %-36s %6.1fs %7d byte' % (ma, ten[:36], dt, len(body)))
            print('      dau: %s' % dau)
            print('      so dang lai suat: %s' % (so[:14] or 'KHONG CO'))
        except Exception as e:
            print('  LOI %-36s %s: %s' % (ten[:36], type(e).__name__, str(e)[:70]))


def main():
    if '--servlet' in sys.argv:
        servlet()
        return 0
    if '--dao' in sys.argv:
        for g, ten, url, keys in MUC_TIEU:
            if not any(k for k in keys):
                continue
            print('\n--- %s ---' % ten)
            dao(url, ten)
        return 0
    if '--trich' in sys.argv:
        for g, ten, url, keys in MUC_TIEU:
            if not any(k for k in keys):
                continue
            print('\n--- %s ---' % ten)
            trich(url, [k for k in keys if k])
        return 0
    for nhom in ('lnh', 'huydong'):
        print('\n' + '=' * 74)
        print('NHOM %s' % ('DUONG CONG LIEN NGAN HANG' if nhom == 'lnh'
                           else 'BANG LAI SUAT HUY DONG'))
        print('=' * 74)
        for g, ten, url, keys in MUC_TIEU:
            if g != nhom:
                continue
            try:
                ma, body, dt = thu(url)
                thay = [k for k in keys if k and k in body]
                # trang ASP.NET tra 200 kem mot trang loi van la hong
                nghi = 'khong thay tu khoa nao' if (keys != [''] and not thay) else ''
                print('  %-3s %-36s %6.1fs %7d byte  %s'
                      % (ma, ten[:36], dt, len(body),
                         ('tu khoa: ' + ', '.join(thay[:3])) if thay else nghi))
            except urllib.error.HTTPError as e:
                print('  %-3s %-36s %6s %7s      %s' % (e.code, ten[:36], '-', '-', e.reason))
            except Exception as e:
                print('  LOI %-36s %6s %7s      %s: %s'
                      % (ten[:36], '-', '-', type(e).__name__, str(e)[:60]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

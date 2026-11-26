#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Do trang lai suat binh quan lien ngan hang cua SBV bang trinh duyet headless.

Vi sao phai dung trinh duyet: do bang urllib cho 200 va 424 KB nhung SO KHONG
NAM TRONG HTML — portal chay Liferay, bang duoc fragment nap sau. Khong file
.xls va khong endpoint du lieu nao lo ra (xem tools/README.md).

Script nay CHI DO, khong ghi gi. Muc dich la biet:
  1. Bang co that su render ra khong
  2. Cau truc DOM the nao de viet parser
  3. Co request XHR nao mang du lieu khong — neu co thi goi thang request do
     se nhe hon nhieu so voi chay ca trinh duyet moi ngay

Chay:  python3 tools/probe_sbv.py
"""
import re
import sys

URL = 'https://www.sbv.gov.vn/webcenter/portal/vi/menu/rm/ls/lsbqlnh'
MOC = ('Qua đêm', 'qua đêm', '1 tuần', 'Lãi suất bình quân')


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Chua cai playwright. Trong workflow: pip install playwright '
              '&& playwright install --with-deps chromium')
        return 2

    xhr = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(locale='vi-VN')

        def ghi(resp):
            u = resp.url
            if resp.request.resource_type in ('xhr', 'fetch'):
                xhr.append((resp.status, len(u), u[:150]))

        pg.on('response', ghi)
        print('Dang tai %s' % URL)
        # KHONG dung networkidle: portal Liferay poll lien tuc nen trang thai
        # do khong bao gio dat (do 26/11 timeout 90s). Cho DOM roi cho chinh
        # noi dung xuat hien.
        pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
        try:
            pg.wait_for_function(
                "() => /Qua đêm|qua đêm|1 tuần/.test(document.body.innerText)",
                timeout=60000)
            print('da thay noi dung bang')
        except Exception as e:
            print('CHO NOI DUNG THAT BAI: %s' % str(e)[:120])
        pg.wait_for_timeout(3000)

        text = pg.inner_text('body')
        print('\n=== TEXT RENDER: %d ky tu ===' % len(text))
        thay = [m for m in MOC if m in text]
        print('moc tim thay: %s' % (thay or 'KHONG CO'))
        print('URL cuoi: %s' % pg.url)
        print('TITLE   : %s' % pg.title())
        if not thay:
            # Khong thay moc thi phai biet trang nay thuc ra la gi: trang loi,
            # tuong chan, hay chi la khung dieu huong vi URL da doi.
            print('--- 1500 ky tu dau cua trang ---')
            print(re.sub(r'\n{2,}', '\n', text[:1500]))
        for m in thay[:1]:
            i = text.find(m)
            print('--- doan quanh "%s" ---' % m)
            print(re.sub(r'\n{2,}', '\n', text[max(0, i - 400):i + 1200]))

        print('\n=== CAC BANG TRONG TRANG ===')
        bang = pg.query_selector_all('table')
        print('so the <table>: %d' % len(bang))
        for i, b in enumerate(bang[:6]):
            t = re.sub(r'\s+', ' ', b.inner_text())[:300]
            print('  [%d] %s' % (i, t))

        print('\n=== IFRAME ===')
        for f in pg.frames[1:]:
            print('  %s' % f.url[:140])

        print('\n=== XHR/FETCH trang da goi (%d) ===' % len(xhr))
        for st, _, u in xhr[:25]:
            print('  %s  %s' % (st, u))

        br.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

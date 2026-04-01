#!/usr/bin/env python3
"""
DASHBOARD DATE AUDIT TOOL
Chạy trước mỗi lần push để đảm bảo không có stale dates
Usage: python3 check_dates.py [index.html]
"""
import re, sys
from collections import Counter
from datetime import datetime, timedelta

filepath = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    c = f.read()

TODAY = datetime.now().strftime("%d/%m/%Y")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

# Static data — historical numbers không cần update
STATIC_OK = {
    # CPI, BOP, FDI — monthly data với ngày công bố cụ thể
    "06/02/2026", "06/03/2026", "09/03/2026", "07/03/2026",
    # NSNN, M2 historical
    "01/01/2026", "01/03/2026",
    # Baseline pre-war
    "01/12/2025",
    # Các ngày data market đã qua nhưng vẫn valid (source ngày đó)
    "25/03/2026",  # xăng kỳ 25/3 — vẫn hiệu lực đến 9/4
    "13/03/2026",  # Fed FOMC 18/3
    "28/01/2026",  # Fed FOMC January
    "27/03/2026",  # yield curve ước tính
    "30/03/2026",  # data 30/3
    "31/03/2026",  # data 31/3
}

# Scan updated fields
updated = re.findall(r'updated:\s*"(\d{2}/\d{2}/\d{4})"', c)
counter = Counter(updated)

stale = []
for date, count in sorted(counter.items()):
    if date not in STATIC_OK and date < TODAY and date != YESTERDAY:
        stale.append((date, count))

print(f"=== DATE AUDIT: {filepath} ===")
print(f"Ngày hôm nay: {TODAY}")
print(f"Tổng updated fields: {len(updated)}")
print()

if stale:
    print(f"❌ STALE FIELDS (cần cập nhật):")
    for d, n in stale:
        print(f"  {d}: {n} fields")
else:
    print("✅ Tất cả dates đều OK!")

# Check HTML hardcoded table dates
html_dates = re.findall(r'>(\d{1,2}/[34])</td>', c)
if html_dates:
    max_date = max(html_dates, key=lambda x: (int(x.split("/")[1]), int(x.split("/")[0])))
    print(f"\nHormuz table - ngày mới nhất: {max_date}")
    if max_date != TODAY[:5].lstrip("0"):
        print(f"  ⚠️  Cần thêm row cho hôm nay vào bảng Hormuz!")
    else:
        print(f"  ✅ Bảng Hormuz đã cập nhật hôm nay")

# Check source fields với ngày nội bộ
noi_bo = re.findall(r'source:\s*"Nội bộ (\d{1,2}/\d{1,2})"', c)
if noi_bo:
    print(f"\nSource 'Nội bộ' dates: {noi_bo}")

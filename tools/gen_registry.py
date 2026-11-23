#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh TIER_MAP va danh sach FIELD_CHUA_RENDER trong index.html tu tools/models.json.

Ly do ton tai: truoc day them mot field phai nho LAM HAI VIEC doc lap — them dong
trong TIER_MAP de bat kiem tuoi, va them dong drow trong panel de no hien ra. Quen
viec nao cung khong ai bao. Bay gio ca hai deu sinh ra tu models.json:

  TIER_MAP           - sinh toan bo, ghi de khoi `const TIER_MAP = {...};`
  FIELD_CHUA_RENDER  - danh sach field mo hinh co goi nhung khong panel nao ve;
                       index.html ve chung trong mot the LUOI AN TOAN, nen khong
                       field nao bien mat am tham nua

Anh xa tier:
  input            -> dung tan suat cua mo hinh
  output           -> dung tan suat cua mo hinh
  input_phu        -> noi mot bac (CORE->WEEKLY->MONTHLY->QUARTERLY)
  tham_so/lich_su  -> KHONG kiem tuoi (hang so, chuoi da chot)
  doi_chieu        -> KHONG kiem tuoi (moc so sanh, co khi co y giu cu)
Mot field nhieu mo hinh goi -> lay tier CHAT NHAT.

Chay:  python3 tools/gen_registry.py [duong/dan/repo] [--check]
       --check: khong ghi, chi bao file da lech so voi models.json (dung trong CI)
Exit:  0 = da dong bo (hoac da ghi xong)
       1 = --check va file dang lech
       2 = khong tim thay file
"""
import json
import os
import re
import sys

THU_TU = ["CORE", "WEEKLY", "MONTHLY", "QUARTERLY"]
SO_NGAY = {"CORE": 2, "WEEKLY": 8, "MONTHLY": 35, "QUARTERLY": 100}
CHU_THICH = {
    "CORE": "nguong 2 ngay — bien dong hang ngay, quyet dinh nhan dinh",
    "WEEKLY": "nguong 8 ngay — chu ky tuan",
    "MONTHLY": "nguong 35 ngay — cong bo hang thang",
    "QUARTERLY": "nguong 100 ngay — cong bo theo quy",
}
MO_DAU = "// ═══ AUTO-GEN tu tools/models.json — KHONG SUA TAY ═══"
KET_THUC = "// ═══ /AUTO-GEN ═══"


def noi_mot_bac(tier):
    i = THU_TU.index(tier)
    return THU_TU[min(i + 1, len(THU_TU) - 1)]


def chat_hon(a, b):
    if a is None:
        return b
    return a if THU_TU.index(a) <= THU_TU.index(b) else b



def alias_domain(html):
    """{'T': 'trump_tracker', ...} — bat `const T = D.trump_tracker;`
    Panel co the doc field qua bien trung gian; neu khong giai alias thi
    field dang render bi bao nham la chua render (gap 23/11 voi
    trump_tracker, panel ve bang `const T = D.trump_tracker`)."""
    ra = {}
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*D\.([a-z_0-9]+)\s*[;,\n]", html):
        ra[m.group(1)] = m.group(2)
    return ra


def co_render(html, field, alias):
    """field = 'nhom.ten'. Nhan ca `D.nhom.ten` lan `X.ten` khi X la alias cua nhom."""
    nhom, ten = field.split(".", 1)
    if ("D.%s.%s" % (nhom, ten)) in html:
        return True
    for bien, dom in alias.items():
        if dom == nhom and re.search(r"\b%s\.%s\b" % (re.escape(bien), re.escape(ten)), html):
            return True
    return False


def khoi_ngoac(text, start):
    b = text.find("{", start)
    k = 0
    for j in range(b, len(text)):
        if text[j] == "{":
            k += 1
        elif text[j] == "}":
            k -= 1
            if k == 0:
                return b, j + 1
    raise ValueError("khong dong ngoac tu vi tri %d" % start)


def doc_fields(data_js):
    ra = set()
    for m in re.finditer(r"\n  ([a-z_0-9]+):\s*\{", data_js):
        b, e = khoi_ngoac(data_js, m.start())
        blk = data_js[b:e]
        for fm in re.finditer(r"\n    ([a-z_0-9]+)\s*:\s*\{", blk):
            fb, fe = khoi_ngoac(blk, fm.start())
            if "updated:" in blk[fb:fe]:
                ra.add("%s.%s" % (m.group(1), fm.group(1)))
    return ra


def tier_theo_field(reg):
    """{'nhom.field': 'CORE'|...} — chi field CAN kiem tuoi."""
    ra = {}
    for mo in reg["models"].values():
        tier = mo.get("tan_suat", "MONTHLY")
        if tier not in THU_TU:
            tier = "MONTHLY"
        for f in list(mo.get("input", [])) + list(mo.get("output", [])):
            ra[f] = chat_hon(ra.get(f), tier)
        for f in mo.get("input_phu", []):
            ra[f] = chat_hon(ra.get(f), noi_mot_bac(tier))
    return ra


def moi_field_duoc_goi(reg):
    ra = set()
    for mo in reg["models"].values():
        for k in ("input", "tham_so", "lich_su", "input_phu", "output", "doi_chieu"):
            ra.update(mo.get(k, []))
    return ra


def goi_tier_map(theo_tier, co_that):
    nhom = {t: [] for t in THU_TU}
    for f, t in sorted(theo_tier.items()):
        if f in co_that:
            nhom[t].append(f)
    dong = ["const TIER_MAP = {"]
    for i, t in enumerate(THU_TU):
        dong.append("  %s: {  // %s" % (t, CHU_THICH[t]))
        dong.append("    days: %d," % SO_NGAY[t])
        if nhom[t]:
            buf, cac_dong = [], []
            for f in nhom[t]:
                buf.append("'%s'" % f)
                if len(",".join(buf)) > 110:
                    cac_dong.append(",".join(buf))
                    buf = []
            if buf:
                cac_dong.append(",".join(buf))
            dong.append("    fields: [" + (",\n             ".join(cac_dong)) + "]")
        else:
            dong.append("    fields: []")
        dong.append("  }" + ("," if i < len(THU_TU) - 1 else ""))
    dong.append("  // tham_so, lich_su, doi_chieu = KHONG kiem tuoi (xem tools/models.json)")
    dong.append("};")
    return "\n".join(dong)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    chi_kiem = "--check" in sys.argv
    repo = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    p_models = os.path.join(repo, "tools", "models.json")
    p_data = os.path.join(repo, "data.js")
    p_html = os.path.join(repo, "index.html")
    for p in (p_models, p_data, p_html):
        if not os.path.exists(p):
            print("KHONG TIM THAY: %s" % p)
            return 2

    reg = json.load(open(p_models, encoding="utf-8"))
    data_js = open(p_data, encoding="utf-8").read()
    html = open(p_html, encoding="utf-8").read()
    goc = html

    co_that = doc_fields(data_js)
    theo_tier = tier_theo_field(reg)
    duoc_goi = moi_field_duoc_goi(reg)

    khai_thieu = sorted(f for f in duoc_goi if f not in co_that)

    # ---------------------------------------------------------------- TIER_MAP
    m = re.search(r"const TIER_MAP\s*=\s*\{", html)
    if not m:
        print("KHONG TIM THAY khoi `const TIER_MAP = {` trong index.html")
        return 2
    b, e = khoi_ngoac(html, m.start())
    cuoi = e + 1 if html[e:e + 1] == ";" else e
    cu = set(re.findall(r"['\"]([a-z_0-9]+\.[a-z_0-9]+)['\"]", html[b:cuoi]))
    html = html[:m.start()] + goi_tier_map(theo_tier, co_that) + html[cuoi:]
    moi = {f for f, t in theo_tier.items() if f in co_that}
    bi_bo = sorted(cu - moi)
    duoc_them = sorted(moi - cu)

    # -------------------------------------------------- FIELD_CHUA_RENDER
    # tinh tren ban GOC: khoi AUTO chi chua chuoi 'nhom.field', khong co 'D.nhom.field'
    alias = alias_domain(goc)
    chua_render = sorted(f for f in duoc_goi
                         if f in co_that and not co_render(goc, f, alias))
    khoi_moi = "%s\nconst FIELD_CHUA_RENDER = [%s];\n%s" % (
        MO_DAU,
        "".join("\n  '%s'," % f for f in chua_render) + ("\n" if chua_render else ""),
        KET_THUC,
    )
    mm = re.search(re.escape(MO_DAU) + r".*?" + re.escape(KET_THUC), html, re.S)
    if not mm:
        print("KHONG TIM THAY khoi AUTO-GEN trong index.html — them mot lan bang tay:")
        print("  %s\n  const FIELD_CHUA_RENDER = [];\n  %s" % (MO_DAU, KET_THUC))
        return 2
    html = html[:mm.start()] + khoi_moi + html[mm.end():]

    # ------------------------------------------------------------------- bao cao
    print("TIER_MAP : %d field  (CORE %d / WEEKLY %d / MONTHLY %d / QUARTERLY %d)" % (
        len(moi),
        *[sum(1 for f, t in theo_tier.items() if f in co_that and t == x) for x in THU_TU]))
    if duoc_them:
        print("  + them %d: %s" % (len(duoc_them), ", ".join(duoc_them[:8]) +
                                   (" ..." if len(duoc_them) > 8 else "")))
    if bi_bo:
        print("  - bo %d khoi TIER_MAP, ba ly do khac nhau:" % len(bi_bo))
        for f in bi_bo:
            if f not in co_that:
                ly_do = "da xoa khoi data.js"
            elif f in duoc_goi:
                ly_do = "la tham_so/lich_su/doi_chieu — CO Y khong kiem tuoi"
            else:
                ly_do = "khong mo hinh nao goi — ung vien bo"
            print("      %-28s %s" % (f, ly_do))
    print("LUOI AN TOAN: %d field duoc goi nhung khong panel nao ve" % len(chua_render))
    for f in chua_render:
        print("      %s" % f)
    if khai_thieu:
        print("CANH BAO: %d input khai trong models.json nhung khong co trong data.js:"
              % len(khai_thieu))
        for f in khai_thieu:
            print("      %s" % f)

    if html == goc:
        print("\nindex.html da dong bo, khong phai ghi.")
        return 0
    if chi_kiem:
        print("\nLECH: index.html chua dong bo voi models.json. Chay lai khong co --check.")
        return 1
    open(p_html, "w", encoding="utf-8").write(html)
    print("\nDa ghi index.html.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

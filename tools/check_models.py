#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Doi chieu ban khai hop dong mo hinh (tools/models.json) voi du lieu thuc te
trong data.js va phan render trong index.html.

Khac voi check_all.py: check_all kiem FILE (cu phap, kieu, tuoi, mau thuan).
Script nay kiem MO HINH:
  1. Input cua mo hinh co ton tai trong data.js khong
  2. Input co qua han so voi tan suat cua mo hinh khong
  3. Do tin cay tran cua moi mo hinh = muc thap nhat trong cac input
  4. Field nao KHONG duoc mo hinh nao goi ten  -> ung vien bo o ban 2027
  5. Field duoc goi nhung chua dang ky TIER_MAP / chua co drow trong panel

Ba loai input, chi loai dau bi kiem tuoi:
  input    - so DO DUOC, phai tuoi theo tan suat cua mo hinh
  tham_so  - hang so hoac muc chinh sach (base_brent 73, tran OMO, Fed funds,
             xac suat kich ban): doi khi co quyet dinh, khong co lich cap nhat
  lich_su  - chuoi da chot theo thiet ke (CPI thang cu, so thuong nien)
Ca ba deu tinh vao do tin cay tran va deu duoc coi la 'field duoc goi'.

Chay:  python3 tools/check_models.py [duong/dan/repo]
Exit:  0 = khong co mo hinh nao o trang thai KHONG DU DU LIEU
       1 = co it nhat mot mo hinh khong du du lieu de ket luan
       2 = khong tim thay file
"""
import json
import os
import re
import sys
from datetime import date

NGUONG_TUOI = {"CORE": 2, "WEEKLY": 8, "MONTHLY": 35, "QUARTERLY": 100}
THANG = ["do_duoc", "suy_ra", "bao_chi", "uoc_luong", "lac_hau"]


def tim_repo(argv):
    if len(argv) > 1:
        return argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def khoi(text, start):
    """Tra ve (chuoi trong ngoac nhon, vi tri dong), bat dau tu dau '{' sau start."""
    b = text.find("{", start)
    k = 0
    for j in range(b, len(text)):
        if text[j] == "{":
            k += 1
        elif text[j] == "}":
            k -= 1
            if k == 0:
                return text[b:j + 1], j + 1
    return text[b:], len(text)


def doc_fields(data_js):
    """{'nhom.field': {'updated':date|None, 'tier':str, 'source':str}}"""
    out = {}
    for m in re.finditer(r"\n  ([a-z_0-9]+):\s*\{", data_js):
        nhom = m.group(1)
        blk, _ = khoi(data_js, m.start())
        for fm in re.finditer(r"\n    ([a-z_0-9]+)\s*:\s*\{", blk):
            body, _ = khoi(blk, fm.start())
            if "updated:" not in body:
                continue
            u = re.search(r'updated:\s*"(\d{2})/(\d{2})/(\d{4})"', body)
            s = re.search(r'source:\s*"((?:[^"\\]|\\.)*)"', body)
            src = s.group(1) if s else ""
            tm = re.match(r"\s*\[([A-Z]+)\]", src)
            ngay = None
            if u:
                try:
                    ngay = date(int(u.group(3)), int(u.group(2)), int(u.group(1)))
                except ValueError:
                    ngay = None
            out["%s.%s" % (nhom, fm.group(1))] = {
                "updated": ngay,
                "tier": tm.group(1) if tm else "KHONG_NHAN",
                "source": src,
            }
    return out


def doc_tier_map(html):
    m = re.search(r"TIER_MAP\s*=\s*\{(.*?)\n\s*\};", html, re.S)
    if not m:
        return set()
    return set(re.findall(r"['\"]([a-z_0-9]+\.[a-z_0-9]+)['\"]", m.group(1)))


def yeu_hon(a, b):
    """Tra ve muc do tin cay thap hon trong hai muc."""
    return a if THANG.index(a) >= THANG.index(b) else b


def main():
    repo = tim_repo(sys.argv)
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

    fields = doc_fields(data_js)
    tier_map = doc_tier_map(html)
    hom_nay = date.today()
    tier2tin = reg["tier_to_do_tin_cay"]

    duoc_goi = set()
    bao_cao = {"ngay": hom_nay.strftime("%d/%m/%Y"), "models": {}, "field": {}}
    khong_du = []

    print("=" * 72)
    print("DOI CHIEU HOP DONG MO HINH  -  %s" % hom_nay.strftime("%d/%m/%Y"))
    print("=" * 72)
    print("%-18s %-11s %-10s %5s  %s" % ("MO HINH", "TRANG THAI", "TIN CAY", "TUOI", "GHI CHU"))
    print("-" * 72)

    for mid, mo in reg["models"].items():
        do_duoc_list = list(mo.get("input", []))
        khong_kiem_tuoi = list(mo.get("tham_so", [])) + list(mo.get("lich_su", []))
        bat_buoc = do_duoc_list + khong_kiem_tuoi
        phu = list(mo.get("input_phu", [])) + list(mo.get("output", [])) + \
            list(mo.get("doi_chieu", []))
        for f in bat_buoc + phu:
            duoc_goi.add(f)

        thieu = [f for f in bat_buoc if f not in fields]
        nguong = NGUONG_TUOI.get(mo.get("tan_suat", "MONTHLY"), 35)

        tuoi_max = 0
        tran = "do_duoc"
        qua_han = []
        for f in bat_buoc:
            info = fields.get(f)
            if not info:
                continue
            tran = yeu_hon(tran, tier2tin.get(info["tier"], "bao_chi"))
            if f in do_duoc_list and info["updated"]:
                t = (hom_nay - info["updated"]).days
                tuoi_max = max(tuoi_max, t)
                if t > nguong:
                    qua_han.append("%s(%dd)" % (f, t))

        if thieu or tuoi_max > nguong * 3:
            trang_thai = "KHONG DU"
            khong_du.append(mid)
        elif qua_han:
            trang_thai = "CANH BAO"
        elif not bat_buoc:
            trang_thai = "CHUA DUNG"
        elif not do_duoc_list:
            # chay hoan toan bang tham so hoac chuoi lich su, khong co so do duoc
            trang_thai = "TINH TAY"
        else:
            trang_thai = "CHAY"

        ghi = ""
        if thieu:
            ghi = "thieu input: " + ", ".join(thieu)
        elif qua_han:
            ghi = "qua han: " + ", ".join(qua_han[:3])
            if len(qua_han) > 3:
                ghi += " +%d" % (len(qua_han) - 3)

        print("%-18s %-11s %-10s %5s  %s" % (mid, trang_thai, tran, tuoi_max, ghi[:30]))
        bao_cao["models"][mid] = {
            "ten": mo["ten"],
            "nhom": mo["nhom"],
            "trang_thai": trang_thai,
            "do_tin_cay_tran": tran,
            "tuoi_input_cu_nhat": tuoi_max,
            "nguong_tuoi": nguong,
            "input_thieu": thieu,
            "input_qua_han": qua_han,
        }

    # ------------------------------------------------------------------ field
    bo = sorted(f for f in fields if f not in duoc_goi)
    giu = sorted(f for f in fields if f in duoc_goi)
    # Chi input/output moi vao TIER_MAP; tham_so, lich_su, doi_chieu co y khong
    # bi kiem tuoi nen vang mat o day la dung, khong phai thieu sot.
    can_tier = set()
    for mo in reg["models"].values():
        can_tier.update(mo.get("input", []))
        can_tier.update(mo.get("output", []))
    chua_tier = sorted(f for f in giu if f in can_tier and f not in tier_map)
    tier_mo = sorted(f for f in tier_map if f not in fields)
    # Field khong co drow rieng van hien qua LUOI AN TOAN (tools/gen_registry.py
    # sinh danh sach nay vao index.html). Chung van hien, chi la chua co cho dung.
    ml = re.search(r"const FIELD_CHUA_RENDER\s*=\s*\[(.*?)\];", html, re.S)
    qua_luoi = set(re.findall(r"['\"]([a-z_0-9]+\.[a-z_0-9]+)['\"]", ml.group(1))) if ml else set()
    chua_render = sorted(f for f in giu
                         if ("D." + f) not in html and f not in qua_luoi)
    luoi = sorted(f for f in giu if f in qua_luoi)

    print("-" * 72)
    print("FIELD   giu %d / bo %d  (tong %d)" % (len(giu), len(bo), len(fields)))
    print("        giu nhung chua co trong TIER_MAP : %d" % len(chua_tier))
    print("        giu nhung chua render tren trang : %d" % len(chua_render))
    print("        hien qua LUOI AN TOAN (chua co cho): %d" % len(luoi))
    print("        muc TIER_MAP tro vao field da xoa: %d" % len(tier_mo))

    if bo:
        print("\nFIELD KHONG MO HINH NAO GOI (ung vien bo o ban 2027):")
        theo_nhom = {}
        for f in bo:
            theo_nhom.setdefault(f.split(".")[0], []).append(f.split(".")[1])
        for nhom in sorted(theo_nhom, key=lambda n: -len(theo_nhom[n])):
            print("  %-16s %2d  %s" % (nhom, len(theo_nhom[nhom]),
                                       ", ".join(theo_nhom[nhom])))

    if chua_tier:
        print("\nFIELD DUOC MO HINH GOI NHUNG CHUA DANG KY TIER_MAP:")
        for f in chua_tier:
            print("  %s" % f)
    if chua_render:
        print("\nFIELD DUOC MO HINH GOI NHUNG KHONG HIEN TREN TRANG:")
        for f in chua_render:
            print("  %s" % f)
    if luoi:
        print("\nFIELD HIEN QUA LUOI AN TOAN (van thay duoc, nhung chua co cho dung):")
        for f in luoi:
            print("  %s" % f)
    if tier_mo:
        print("\nMUC TIER_MAP TRO VAO FIELD DA XOA (can don):")
        for f in tier_mo:
            print("  %s" % f)

    bao_cao["field"] = {
        "tong": len(fields),
        "giu": giu,
        "bo": bo,
        "giu_chua_tier": chua_tier,
        "giu_chua_render": chua_render,
        "giu_qua_luoi_an_toan": luoi,
        "tier_map_mo_coi": tier_mo,
    }
    out = os.path.join(repo, "tools", "models_report.json")
    json.dump(bao_cao, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nDa ghi bao cao: tools/models_report.json")

    if khong_du:
        print("\nKHONG DU DU LIEU DE KET LUAN: %s" % ", ".join(khong_du))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

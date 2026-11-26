# Hợp đồng mô hình — `tools/models.json` + `tools/check_models.py`

Nguyên tắc của bản 2027: **mô hình chuẩn trước, dữ liệu theo sau.** Mỗi mô hình khai rõ công thức, input, chiều dấu, ngưỡng và cách chấm trong `tools/models.json`. Field chỉ tồn tại nếu ít nhất một mô hình gọi tên nó — field không ai gọi là ứng viên bỏ, không cần quyết định thủ công từng nhóm.

```bash
python3 tools/check_models.py                 # chạy được từ bất kỳ cwd nào
python3 tools/check_models.py /đường/dẫn/repo
```

Exit `0` = không mô hình nào thiếu dữ liệu. Exit `1` = có mô hình ở trạng thái KHÔNG ĐỦ, **không được đăng kết luận của mô hình đó**. Exit `2` = không tìm thấy file. Báo cáo máy đọc được ghi ra `tools/models_report.json`.

## Ba loại input — chỉ loại đầu bị kiểm tuổi

| Khoá | Nghĩa | Ví dụ |
|---|---|---|
| `input` | số **đo được**, phải tươi theo tần suất mô hình | `oil.brent`, `yield_curve.on` |
| `tham_so` | hằng số hoặc mức chính sách, không có lịch cập nhật | `ppp_war.base_brent` 73, trần OMO 4,5%, xác suất KB |
| `lich_su` | chuỗi đã chốt theo thiết kế, không bao giờ mới | `cpi.t1_2026`, kiều hối thường niên |

Cả ba đều tính vào độ tin cậy trần và đều được coi là "field được gọi". Lần chạy đầu tiên (23/11) gắn `base_brent`, trần OMO và lãi suất Fed vào `input` nên bốn mô hình bị báo KHÔNG ĐỦ sai — tách ba loại mới ra đúng.

## Quy tắc đặt tần suất

**Tần suất của mô hình = tần suất công bố của input chậm nhất trong nhóm `input`**, không đặt theo mong muốn cập nhật. Nếu một input nhanh hơn hẳn phần còn lại thì tách thành mô hình riêng chứ không hạ ngưỡng cả cụm. Ví dụ `gap_ccs` để WEEKLY vì đường cong 3M/6M chỉ có quote tuần, dù O/N có hằng ngày.

## Độ tin cậy trần

Mỗi mô hình kế thừa mức **thấp nhất** trong các input của nó, theo thang `do_duoc → suy_ra → bao_chi → uoc_luong → lac_hau`. Ánh xạ từ nhãn tier nằm trong `tier_to_do_tin_cay` của `models.json`. Đây là chỗ sửa lỗi tháng 11/2026: EMP ghép một số VCB XML (gốc) với một số chợ đen (báo) nhưng hiện ra với độ chắc chắn như nhau.

## Sinh tự động — `tools/gen_registry.py`

```bash
python3 tools/gen_registry.py            # ghi lại index.html
python3 tools/gen_registry.py --check    # chỉ báo lệch, dùng trong CI
```

Script này **sinh toàn bộ `TIER_MAP`** và **danh sách `FIELD_CHUA_RENDER`** trong `index.html` từ `models.json`. Hai điểm mù cũ biến mất vì không còn hai đăng ký độc lập để quên:

| Khoá trong hợp đồng | Tier nhận được |
|---|---|
| `input` | tần suất của mô hình |
| `output` | tần suất của mô hình |
| `input_phu` | nới một bậc (CORE→WEEKLY→MONTHLY→QUARTERLY) |
| `tham_so`, `lich_su`, `doi_chieu` | **không vào `TIER_MAP`** — cố ý không kiểm tuổi |

Field được nhiều mô hình gọi lấy tier **chặt nhất**. Script in rõ field nào được thêm, field nào bị bỏ và vì sao (đã xóa khỏi `data.js` / không mô hình nào gọi / là tham số).

**Lưới an toàn render.** Field được mô hình gọi nhưng không panel nào có `drow` sẽ rơi xuống thẻ *LƯỚI AN TOÀN RENDER* ở cuối trang thay vì biến mất. Thẻ tự ẩn khi trống — trống là trạng thái mong muốn, còn field trong lưới nghĩa là nó hiển thị được nhưng chưa có chỗ đúng.

Đừng sửa tay khối giữa `// ═══ AUTO-GEN ... ═══` và `// ═══ /AUTO-GEN ═══`, và đừng sửa tay `TIER_MAP`: lần chạy sau sẽ ghi đè.

## Khi thêm mô hình mới

1. Khai đủ `cong_thuc`, `input`, `chieu_dau`, `nguong`, `tan_suat`, `cham_diem`. Thiếu `cham_diem` thì sau này không biết mô hình đúng hay sai.
2. Chạy `check_models.py`, đảm bảo không có `input_thieu`.
3. Chạy `gen_registry.py` — `TIER_MAP` và lưới an toàn tự cập nhật. Thêm `drow` vào panel đúng chỗ khi muốn field ra khỏi lưới.

## Bài học từ lần sinh đầu tiên

Bản khai đặt `hqla_transform` ở CORE, nên mọi field `omo.*` thành ngưỡng 2 ngày và `check_all.py` báo 15 FAIL. Nhưng input chậm nhất của mô hình đó là `omo.trang_thai` (số tuần) và `omo.fx_swap_182d` (sự kiện) — đúng quy tắc phải là WEEKLY. Sửa lại còn 9 FAIL, và 9 field đó quá hạn thật vì dữ liệu dừng ở 18/11. **Khi `TIER_MAP` sinh tự động báo quá nhiều FAIL, kiểm `tan_suat` của mô hình trước khi nghi ngờ dữ liệu.**

---

# tools/check_all.py

Bộ kiểm tra bắt buộc chạy trước khi push.

```bash
python3 tools/check_all.py                 # chạy được từ bất kỳ cwd nào
python3 tools/check_all.py /đường/dẫn/repo
```

Exit `0` = đủ điều kiện push. Exit `1` = có FAIL, **không được push**. Exit `2` = không tìm thấy file.

## Hai pha — `--pha truoc-commit` / `--pha sau-commit`

```bash
python3 tools/check_all.py --pha truoc-commit   # lớp 1,2,3,4 — chặn commit
python3 tools/check_all.py --pha sau-commit     # lớp 5,5b,6 — chuông báo
python3 tools/check_all.py                      # tất cả, dùng khi push tay
```

Mọi lần chạy đều chạy **đủ bảy lớp và in đủ kết quả**; cờ `--pha` chỉ đổi lớp nào được tính vào mã thoát. Lỗi ngoài pha vẫn in ra dưới nhãn *lỗi ngoài pha này*.

| Pha | Lớp tính vào mã thoát | Vai trò |
|---|---|---|
| `truoc-commit` | 1, 2, 3, 4 — cú pháp, runtime, NaN, kiểu dữ liệu | bảo vệ trang đang chạy; chặn commit |
| `sau-commit` | 5, 5b, 6 — tuổi, nguồn CORE, mâu thuẫn chéo | chuông báo dữ liệu cũ; chạy sau commit |

**Vì sao phải tách.** Workflow cũ chạy fetch → check_all → commit. Dữ liệu cũ làm check_all FAIL ở lớp 5, job dừng, nên số VCB vừa lấy được cũng không vào được repo — dữ liệu cũ làm job hỏng, job hỏng làm dữ liệu cũ thêm. Ba lần chạy 23, 24, 25/11/2026 (run `45144750330`, `45380623267`, `45589770313`) đều như vậy: fetch lấy được `fx.vcb_mua` 25.600 → 25.640 rồi ném đi. Số mới lấy về luôn tốt hơn số cũ, nên không được chặn nó vì chỗ khác cũ. Chuông báo vẫn kêu — job vẫn đỏ khi dữ liệu quá hạn — chỉ không còn giam dữ liệu mới.

## Cấu trúc repo

Từ **v5.82 (01/11/2026)** dữ liệu tách khỏi render:

| File | Nội dung |
|---|---|
| `data.js` | `const D = {...}` — toàn bộ dữ liệu, 186 KB |
| `index.html` | chỉ còn render, 140 KB (trước khi tách: 326 KB một file) |

`index.html` nạp `<script src="data.js">` trước script render. `const D` khai báo ở top-level của classic script nên script sau nhìn thấy được.

Lý do tách: cập nhật trước đây là phẫu thuật regex trên file 326 KB, `git diff` không đọc được, và dữ liệu lẫn trong code render thì không tự động hoá được.

## Bảy lớp kiểm tra

| # | Kiểm tra | Bắt được gì |
|---|---|---|
| 1 | **Syntax** — ghi từng `<script>` ra file rồi `node --check` | Lỗi cú pháp JS |
| 2 | **Runtime** — chạy toàn bộ script với DOM giả lập | Tham chiếu tới section đã xoá, sai kiểu khi render. `node --check` không bắt được loại này |
| 3 | **NaN / undefined** | Giá trị rò rỉ ra HTML hiển thị |
| 4 | **Kiểu dữ liệu** | Chuỗi văn xuôi nhồi vào field lẽ ra là số (danh sách `NUMFIELDS`) |
| 5 | **Tier age** | Field quá ngưỡng tuổi của tier theo `TIER_MAP`. Quá hạn CORE = FAIL, các tier khác = WARN |
| 5b | **Nguồn của CORE** | Field CORE dùng `[PRESS]`. Nguồn tổng hợp đã từng ghi sai lãi suất Big4 6,60–6,80% trong khi VCB thực tế 3,00/5,40 |
| 6 | **Mâu thuẫn chéo** | Một chỉ tiêu được nhắc ở nhiều field với giá trị khác nhau — tức một nơi đã cập nhật, nơi kia chưa. Hiện đối chiếu **11 chỉ tiêu** |

## Ghi chú thiết kế

**Lớp 1 phải ghi ra file.** `node --check /dev/stdin` cho kết quả sai, đã gặp.

**Lớp 2 là bắt buộc.** Đã có lần cả trang trắng vì lỗi runtime mà lớp 1 không bắt được.

**Lớp 6 chỉ quét `value:`, không quét `note:`.** Note chứa chuỗi lịch sử hợp lệ nên quét cả file sinh ra hàng chục cảnh báo giả. Cách làm: lấy giá trị của field chuẩn (`oil.brent`, `fx.nhnn_tc`, `fx.vcb_ban`, `yield_curve.on`), rồi tìm trong các value khác những lần nhắc **có nhãn** như `Brent 109,86`. Lệch nhau nghĩa là một nơi đã cập nhật, nơi kia chưa.

Lớp 6 bỏ qua value chứa các dấu hiệu bản ghi lịch sử có chủ đích: `→`, `Chuỗi:`, `DU BAO CU`, `DA LAC HAU`, `giu lai de DOI CHIEU`, `SO CU`. Khi cố tình lưu số cũ để đối chiếu, dùng một trong các cụm này để không bị cảnh báo giả.

**Lớp 6 cũng bỏ qua value của đường cong khác**: `USD LIEN NGAN HANG`, `DUONG CONG USD`. Đường cong USD liên ngân hàng dùng đúng nhãn kỳ hạn như VND (`O/N`, `1M`), nên không có nhãn phân biệt thì lớp 6 báo mâu thuẫn giả. Gặp ngày 05/11: `irp.thuc_te` ghi `USD ... O/N 3,85` bị báo lệch với `yield_curve.on = 3,70`. **Khi thêm field nhắc kỳ hạn của một đường cong không phải VND, phải có nhãn `USD` trong value.**

## Khi thêm field mới

- Field lẽ ra là số → thêm tên vào `NUMFIELDS` (lớp 4).
- **Field mới phải thêm `drow(...)` vào panel trong `index.html`, KHÔNG chỉ thêm vào `TIER_MAP`.** `TIER_MAP` chỉ bật kiểm tra tuổi; nó **không** làm field hiện trên trang. Gặp 13/11: bốn field thêm trong một tuần (`gap_swap_mkt`, `bom_du_test`, `mua_spot_25500`, `trangthai_usd_q3`) đều có trong `data.js` và qua đủ 7 lớp kiểm tra, nhưng **không hiện trên dashboard** vì panel `omo` render bằng danh sách `drow` cố định. Bảy lớp kiểm tra không bắt được lỗi này — chỉ render check bằng Chromium mới thấy. **Sau khi thêm field, luôn mở trang và tìm chuỗi trong `value` để xác nhận nó hiện.**
- Field cần theo dõi độ tươi → thêm vào `TIER_MAP` trong `index.html`. **Field không nằm trong `TIER_MAP` sẽ không bao giờ bị kiểm tra tuổi** — đây là nguồn điểm mù đã gặp nhiều lần. Ví dụ đã làm đúng: `omo.fx_swap_182d` (thêm 05/11) được đăng ký ngay vào `WEEKLY`.
- Chỉ tiêu hay bị nhắc lại ở nhiều panel → thêm vào `CANON` (lớp 6).

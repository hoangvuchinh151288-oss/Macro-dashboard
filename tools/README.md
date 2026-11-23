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

## Khi thêm mô hình mới

1. Khai đủ `cong_thuc`, `input`, `chieu_dau`, `nguong`, `tan_suat`, `cham_diem`. Thiếu `cham_diem` thì sau này không biết mô hình đúng hay sai.
2. Chạy `check_models.py`, đảm bảo không có `input_thieu`.
3. Field mới vẫn phải đăng ký `TIER_MAP` **và** thêm `drow` — xem mục dưới.

---

# tools/check_all.py

Bộ kiểm tra bắt buộc chạy trước khi push.

```bash
python3 tools/check_all.py                 # chạy được từ bất kỳ cwd nào
python3 tools/check_all.py /đường/dẫn/repo
```

Exit `0` = đủ điều kiện push. Exit `1` = có FAIL, **không được push**. Exit `2` = không tìm thấy file.

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

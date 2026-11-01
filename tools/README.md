# tools/check_all.py

Bộ kiểm tra bắt buộc chạy trước khi push `index.html`.

```bash
python3 tools/check_all.py                 # từ gốc repo
python3 tools/check_all.py /đường/dẫn/index.html
```

Exit `0` = đủ điều kiện push. Exit `1` = có FAIL, **không được push**. Exit `2` = không tìm thấy file.

## Sáu lớp kiểm tra

| # | Kiểm tra | Bắt được gì |
|---|---|---|
| 1 | **Syntax** — ghi từng `<script>` ra file rồi `node --check` | Lỗi cú pháp JS |
| 2 | **Runtime** — chạy toàn bộ script với DOM giả lập | Tham chiếu tới section đã xoá, sai kiểu khi render. `node --check` không bắt được loại này |
| 3 | **NaN / undefined** | Giá trị rò rỉ ra HTML hiển thị |
| 4 | **Kiểu dữ liệu** | Chuỗi văn xuôi nhồi vào field lẽ ra là số (danh sách `NUMFIELDS`) |
| 5 | **Tier age** | Field quá ngưỡng tuổi của tier theo `TIER_MAP`. Quá hạn CORE = FAIL, các tier khác = WARN |
| 6 | **Mâu thuẫn chéo** | Một chỉ tiêu được nhắc ở nhiều field với giá trị khác nhau — tức một nơi đã cập nhật, nơi kia chưa |

## Ghi chú thiết kế

**Lớp 1 phải ghi ra file.** `node --check /dev/stdin` cho kết quả sai, đã gặp.

**Lớp 2 là bắt buộc.** Đã có lần cả trang trắng vì lỗi runtime mà lớp 1 không bắt được.

**Lớp 6 chỉ quét `value:`, không quét `note:`.** Note chứa chuỗi lịch sử hợp lệ nên quét cả file sinh ra hàng chục cảnh báo giả. Cách làm: lấy giá trị của field chuẩn (`oil.brent`, `fx.nhnn_tc`, `fx.vcb_ban`, `yield_curve.on`), rồi tìm trong các value khác những lần nhắc **có nhãn** như `Brent 109,86`. Lệch nhau nghĩa là một nơi đã cập nhật, nơi kia chưa.

Lớp 6 bỏ qua value chứa các dấu hiệu bản ghi lịch sử có chủ đích: `→`, `Chuỗi:`, `DU BAO CU`, `DA LAC HAU`, `giu lai de DOI CHIEU`, `SO CU`. Khi cố tình lưu số cũ để đối chiếu, dùng một trong các cụm này để không bị cảnh báo giả.

## Khi thêm field mới

- Field lẽ ra là số → thêm tên vào `NUMFIELDS` (lớp 4).
- Field cần theo dõi độ tươi → thêm vào `TIER_MAP` trong `index.html`. **Field không nằm trong `TIER_MAP` sẽ không bao giờ bị kiểm tra tuổi** — đây là nguồn điểm mù đã gặp nhiều lần.
- Chỉ tiêu hay bị nhắc lại ở nhiều panel → thêm vào `CANON` (lớp 6).

# derival-media — luật cho Claude

Repo **PUBLIC** lưu ảnh/video/nội dung Claude tạo ra cho studio Derival (đổi tên từ `derival-campaign` ngày 25/10/2026).
Kiến trúc catalog + intel từ 05/11/2026: xem `README.md`.

**Luật đầy đủ ở `AGENTS.md` — đọc trước khi ghi bất cứ gì.** Tóm tắt:

- Ghi vào đây **chỉ** bằng `tools/media.py` (studio `scripts/archive_run.py` gọi tool này). Không tự viết CSV, không sửa tay
  `index.csv` / `intel/summary.csv`. `python3 tools/media.py check` phải sạch trước khi commit.
- File bất biến: không sửa, đổi tên, chuyển hay xoá file đã gửi link; phiên bản mới = file mới `_v<n+1>`. Trạng thái là metadata.
  Ngoại lệ: gói đăng bài `<CT>_post.md` (TD-018). `test/` đóng băng; bản thử mới vào `media/<CT>/` với `--test`.
- Mỗi sản phẩm có `media/<CT>/<CT>_post.md` (TD-018) và kịch bản công khai `media/<CT>/<CT>_<v>_script.md` (TD-023).
  Studio quét các file này (`scripts/script_scan.py`) để nội dung mới không lặp.
- Không bao giờ đưa vào: khoá/token, `secrets/`, bản tin D-family, điểm barem chi tiết, ghi chú nội bộ, số tài khoản, lệnh đang mở,
  dữ liệu cá nhân, file dự án (`projects/`), bản nháp nội bộ không định giao.
- File ≤ 25 MB. Muốn gỡ một video khỏi công khai: hỏi người dùng trước.
- Commit `<CT>_<v>: <loại>` lên `main`. Mọi luật nội dung, công cụ, chiến lược ở repo `derivallcc/derival-studio`.

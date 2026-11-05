# AGENTS.md — luật không thương lượng của derival-media

Áp dụng cho mọi người, agent, bot và script ghi vào repo này. `CLAUDE.md` trỏ tới đây.
Repo **PUBLIC**: mọi thứ đẩy lên là công khai, lịch sử git giữ mãi kể cả khi xoá.

## 1. Chỉ ghi qua `tools/media.py`

- Không tự chép file vào `media/`, không tự sửa CSV trong `catalog/`, `intel/`, `index.csv`.
- `index.csv` và `intel/summary.csv` **sinh tự động** (`media.py build`) — không sửa tay.
- Trước khi commit: `python3 tools/media.py check` phải 0 lỗi. `media.py commit -m … [--push]` làm build + check + commit.
- Commit: `<CT>_<v>: <loại>` (ví dụ `CT-0020_v1: video, frames, script`) hoặc `media: <việc>` cho thay đổi hạ tầng.

## 2. File bất biến

- Không đổi tên, không chuyển, không ghi đè, không xoá file đã vào repo — link raw đã gửi trong bản tin phải sống mãi.
- Phiên bản mới = file mới `_v<n+1>`. Đổi trạng thái là ghi metadata (`media.py status`), **không** chuyển thư mục.
- Ngoại lệ duy nhất: vai trò `mutable=y` trong `schema/vocabulary.csv` (gói đăng bài `<CT>_post.md`); lịch sử nằm ở git.
- `test/` đã **đóng băng** (05/11/2026): giữ file cũ cho link sống, không ghi mới. Bản thử mới vào `media/<CT>/` với `--test`.
- Muốn gỡ một tác phẩm khỏi công khai: **hỏi người dùng trước** (link đã ở trong nhóm, git vẫn giữ file).
  Ghi nhận bằng `media.py status <CT> <v> withdrawn --ref <tin nhắn quyết định>`.
- File ≤ 25 MB.

## 3. Không bao giờ đưa vào

- Khoá, token, mật khẩu, `secrets/`, cấu hình kết nối.
- Bản tin D-family, ghi chú nội bộ (trạng thái chấm, "cần quyết"), bản nháp nội bộ không định giao, file dự án (`projects/`),
  render trung gian, mã nguồn dựng.
- **Điểm barem chi tiết** (video-barem…): giữ ở studio `qa.md`; Media chỉ ghi verdict + `ref` tới studio.
- Dữ liệu cá nhân: tên/ID/@ của khán giả, nguyên văn bình luận, email, số điện thoại, **số tài khoản**, lệnh đang mở.
  Phản hồi khán giả chỉ ghi dạng tổng hợp đã diễn đạt lại (`intel/insights.csv`); bình luận gốc ở Sheet `social` qua `comment_key`.
- Tên thành viên đội ngũ: chỉ ghi **vai trò** (CEO, COO, admin), không ghi tên.
- Bản sao logo/nền gốc của knowledge hay studio: chỉ tham chiếu bằng `relations.csv` (`uses knowledge:…`).

`media.py check` chặn tự động: cột lạ trong bảng, chuỗi giống khoá/token, email, số điện thoại, @tên, "số tài khoản".

## 4. Ai cấp gì

- `work_id` (CT-xxxx) do studio `brain/content/registry.csv` cấp. Media không bao giờ tự cấp mã.
- Nơi gốc của trạng thái đã giao (Thử nghiệm → … → Đã đăng) là `catalog/events.csv`; registry studio là bản sao.
- Dòng AI không bao giờ thay dòng của người. Sửa = thêm dòng mới có `supersedes`.

## 5. Đọc thêm

`README.md` (bắt đầu ở đây) · `docs/storage.md` · `docs/schema.md` · `docs/lifecycle.md` · `docs/integration.md` ·
`docs/intelligence.md` · `docs/migration.md`. Luật nội dung, công cụ, chiến lược: repo `derivallcc/derival-studio`.

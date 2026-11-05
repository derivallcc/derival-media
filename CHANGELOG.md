# CHANGELOG

## 2026-11-05 — Kiến trúc catalog + Media Intelligence (GĐ0, GĐ1, phần Media của GĐ3)

- GĐ0: chụp mốc 77 file + sha256 đủ vào `docs/migration.md`; `check` báo lỗi nếu đường dẫn nào biến mất.
- Thêm `AGENTS.md` (luật), `docs/` (storage, schema, lifecycle, integration, intelligence, migration), `schema/vocabulary.csv`.
- Thêm `tools/media.py` (register · status · publish · metrics · review · insight · build · check · commit · find · show)
  và `tools/test_media.py`.
- Catalog điền ngược từ `index.csv` + file thật + `_post.md`/`_script.md` + git log: 15 tác phẩm, 74 tài sản, sự kiện vòng đời,
  quan hệ (`origin`/`actor` = migration).
- `index.csv` giờ sinh tự động, giữ đúng 9 cột + CRLF; bỏ 2 dòng trùng (`CT-0012_p01.png`, `CT-0013_p01.png`).
- `test/` đóng băng: bản thử mới vào `media/<CT>/` với status `testing`.
- Khung intel rỗng: `catalog/publications.csv`, `intel/metrics/`, `intel/reviews.csv`, `intel/insights.csv`, `intel/summary.csv`.
- `.gitattributes`: `merge=union` cho bảng chỉ thêm.
- Không file media nào bị chuyển, đổi tên hay sửa.

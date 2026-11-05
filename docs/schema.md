# Schema

Tất cả là CSV UTF-8, có dòng tiêu đề, phân cách dấu phẩy. Cột phải **đúng** như dưới đây (`check` báo lỗi cột lạ — cột lạ là
đường lộ dữ liệu cá nhân phổ biến nhất). Mọi giá trị enum lấy từ `schema/vocabulary.csv`
(`field,value,nhan_vi,y_nghia,versioned,mutable,extensions,required_fields`).

Thời gian: ISO 8601 có múi giờ, ví dụ `2026-11-05T19:30:00+07:00`. Dữ liệu điền ngược khi chuyển đổi chỉ có ngày (`2026-10-24`).
Cột y/n: `y`, `n` hoặc trống.

## ID

| ID | Dạng | Ai cấp |
|---|---|---|
| `work_id` | `CT-\d{4}` | Studio `brain/content/registry.csv`. Media không bao giờ tự cấp |
| `version` | `v\d+` | Studio; tăng khi lời, hình hoặc số đổi |
| `asset_id` | Tên file (duy nhất toàn repo nhờ tiền tố CT) | `media.py register` |
| `pub_id` | `platform\|account_id\|platform_post_id` | Trùng `post_key` của social-intel |
| `run_id` | Mã lượt của tiến trình ghi | Tiến trình ghi |
| `review_id`, `insight_id` | `rv-YYYYMMDD-NNN`, `in-YYYYMMDD-NNN` | `media.py` |

Tham chiếu chéo trong `relations.csv`: `asset_id`, `CT-xxxx`, `CT-xxxx_v<n>` hoặc nguồn ngoài dạng `<repo>:<đường dẫn>`
(`knowledge:02-brand/assets/logos/…`, `studio:brand/scenes/…webp`, `studio:brain/brainstorm/C-005`).

## catalog/works.csv — 1 dòng / tác phẩm

| Cột | Bắt buộc | Ghi chú |
|---|---|---|
| `work_id` | ✔ | |
| `kind` | ✔ | vocab `kind`: video, image, carousel, text, discussion, comment-set, brand-derivative, article |
| `title` | ✔ | Tiêu đề chuẩn (social-intel dùng thay cho regex tiêu đề `_post.md`) |
| `created_at`, `created_by` | ✔ | `created_by`: người/agent/tiến trình, ví dụ `studio:archive_run` |
| `status` | ✔ | **Sinh tự động**: trạng thái của `current_version` theo `events.csv` |
| `current_version` | ✔ | Phiên bản hiện hành |
| `format` | | F01… |
| `pillar` | | P1… |
| `series` | | SR… |
| `product` | | vocab `product`: chung, stock, derivative |
| `campaign` | | Giá trị `utm_campaign` |
| `tags` | | Phân cách `\|` |
| `source_ref` | | `studio:brain/content/CT-xxxx`, `studio:brain/brainstorm/C-005` |
| `ai_generated` | | y/n — có hình/giọng tạo bằng AI |
| `note` | | Không ghi chú nội bộ |

## catalog/assets.csv — 1 dòng / file

| Cột | Bắt buộc | Ghi chú |
|---|---|---|
| `asset_id` | ✔ | = tên file |
| `work_id` | ✔ | |
| `version` | ✔ nếu vai trò `versioned=y` | Gói đăng bài: phiên bản áp dụng (có thể trống ở dữ liệu cũ) |
| `role` | ✔ | vocab `role` |
| `path` | ✔ nếu `storage=repo` | `media/<CT>/<file>` |
| `bytes`, `sha256` | ✔ nếu `storage=repo` | sha256 **đủ 64 ký tự** (index.csv chỉ giữ 16 ký tự đầu như cũ) |
| `mime` | ✔ | |
| `created_at`, `created_by` | ✔ | |
| `link` | ✔ | Link raw công khai (dữ liệu cũ: một số gói đăng bài dùng link `blob`) |
| `width`, `height`, `aspect` | | Ảnh/video |
| `duration_s` | ✔ với video | |
| `rendition` | | 9x16, 1x1, png, jpg… |
| `lang`, `tool`, `ai_label` | | `ai_label`: nhãn "nội dung tạo bằng AI" đã gắn khi đăng |
| `storage` | ✔ | repo / external |
| `legacy` | | `y` = file có trước 05/11/2026 (miễn luật tên mới) |
| `note` | | |

## catalog/relations.csv

`subject, rel, object, note`. `rel` ∈ derived_from, rendition_of, cover_of, script_of, variant_of (mã EX- ở note), supersedes, uses.

## catalog/events.csv — CHỈ THÊM

`at, work_id, version, event, from_status, to_status, actor, actor_type, ref, note`

- `event` ∈ created, status, published. `actor_type` ∈ human, ai, system.
- `from_status` phải bằng trạng thái trước đó của phiên bản; chuyển trạng thái phải hợp lệ (`docs/lifecycle.md`).
- `ref`: message_id của lệnh "ok đăng", APPROVAL BS…, mã lượt, `pub_id`, commit.
- `actor`: vai trò hoặc tên tiến trình (CEO, admin, studio:archive_run), không tên cá nhân.

## catalog/publications.csv — 1 dòng / bài đăng thật

`pub_id, work_id, version, asset_id, platform, account, url, published_at, published_by, campaign, utm_content, source, matched_by, note`

- `source` ∈ admin, social-intel, human (vocab `pub_source`). `matched_by` ∈ code, caption, reviewer.
- `account` là tài khoản/trang **của Derival**, không phải người dùng.

## intel/metrics/<yyyy-mm>.csv — CHỈ THÊM

`pub_id, captured_at, run_id, checkpoint, provided_fields, views, reach, likes, reactions, comments, shares, saves, clicks, origin, source, method, confidence, human_check, note`

- Khoá chống trùng: `pub_id|run_id`. File theo tháng của `captured_at` (chỉ để file nhỏ).
- Ô số **trống = nền tảng không cung cấp**, không phải 0. `provided_fields` liệt kê các cột có số (`views|likes|…`).
- `checkpoint` ∈ first, 24h, 72h, 7d, 30d, adhoc. Ảnh chụp đầu tiên của một bài tự nhận `first`.

## intel/reviews.csv — CHỈ THÊM

`review_id, at, work_id, version, asset_id, reviewer_type, reviewer_role, rubric, criterion, verdict, independent, origin, source, method, confidence, human_check, ref, supersedes, note`

- `reviewer_type` ∈ human, ai, system. `verdict` ∈ pass, revise, fail, approve, reject, note.
- **Không có cột điểm**: điểm barem chi tiết ở studio `qa.md` (`ref` trỏ tới đó). Xem `docs/intelligence.md`.

## intel/insights.csv — CHỈ THÊM

`insight_id, at, work_id, version, pub_id, platform, insight_type, topic, count, share, summary, origin, source, method, confidence, human_check, ref, supersedes, note`

- `insight_type` ∈ theme, question, sentiment, objection, request. `share` là tỷ lệ 0–1.
- `summary` diễn đạt lại, không tên, không @, không trích nguyên văn. `ref` có thể là `comment_key` trong Sheet `social`.

## Sinh tự động

- `intel/summary.csv`: `work_id, version, platform, pub_id, first_captured_at, last_captured_at, checkpoint, snapshots, views, reach, likes, comments, shares, saves, clicks, er, delta_views, delta_since`.
  `er = (likes + comments + shares + saves) / views`; `delta_views` so với ảnh chụp trước.
- `index.csv`: **giữ đúng 9 cột cũ** `ngay,ct,phien_ban,loai,file,bytes,sha256,duration_s,link` (CRLF) cho các bot cũ
  (social-intel lấy dòng `loai=post`). Gồm tài sản trong `media/`; **bỏ** phiên bản `testing` thêm sau 05/11/2026 (file cũ giữ
  nguyên dòng như trước). `loai`: still/cover/thumb → `anh`, còn lại = role. `sha256` 16 ký tự đầu.

## Từ vựng

Mỗi dòng role có `versioned` (y/n), `mutable` (y/n), `extensions` (`mp4|mov`), `required_fields` (`duration_s`).
Thêm loại nội dung, nền tảng, quan hệ mới = thêm một dòng vào `schema/vocabulary.csv` + ghi vào `CHANGELOG.md`.

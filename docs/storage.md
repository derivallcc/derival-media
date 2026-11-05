# Lưu trữ: phân loại, đặt tên, phiên bản, trùng lặp

## Một trục thư mục duy nhất

```
media/<CT>/      mọi file của một tác phẩm — mọi loại, mọi trạng thái, mọi phiên bản
```

Loại nội dung, vai trò file, trạng thái, nền tảng, chiến dịch, sản phẩm đều là **metadata** trong `catalog/`, không phải thư mục.
Có loại nội dung mới → thêm một dòng vào `schema/vocabulary.csv`, không thêm thư mục.

`test/<CT>/` (CT-0014, CT-0015) đã **đóng băng** từ 05/11/2026: file cũ giữ nguyên để link sống, không ghi thêm.
Bản thử mới ghi vào `media/<CT>/` với `media.py register --test` (status `testing`).

## Bốn lớp, mỗi sự thật một nơi

| Lớp | Ở đâu | Trả lời câu hỏi | Ghi thế nào |
|---|---|---|---|
| File | `media/<CT>/` | Cái gì tồn tại | `register`, bất biến |
| Catalog | `catalog/works.csv`, `assets.csv`, `relations.csv`, `publications.csv` | Nó là gì, nằm ở đâu, liên quan gì | `register`, `publish` |
| Sổ sự kiện | `catalog/events.csv` | Chuyện gì đã xảy ra | `register`, `status`, `publish` — **chỉ thêm** |
| Intel | `intel/metrics/`, `reviews.csv`, `insights.csv` | Nó hoạt động ra sao | `metrics`, `review`, `insight` — **chỉ thêm** |

Bảng tổng hợp (`index.csv`, `intel/summary.csv`, cột `works.status`) đều **sinh tự động** bằng `media.py build`.

## Luật tên (file thêm từ 05/11/2026)

```
<CT>_<v>[_<role>][-<qualifier>][_<nn>].<ext>
```

- `role` lấy từ `schema/vocabulary.csv` (field `role`), đuôi file phải nằm trong cột `extensions` của vai trò đó.
- Video chính **không** có hậu tố vai trò (giữ tương thích mẫu `_v\d+.mp4` mà các script studio đang dùng).
- `qualifier` (a-z0-9): bản xuất khác (`1x1`, `16x9`, `en`…). `nn`: số thứ tự hai chữ số (trang carousel, ảnh thứ n).
- Gói đăng bài là ngoại lệ: `<CT>_post.md`, không phiên bản (vai trò mutable, lịch sử ở git).

| Ví dụ | Nghĩa |
|---|---|
| `CT-0020_v1.mp4` | Video chính |
| `CT-0020_v1-1x1.mp4` | Bản 1:1 của v1 (`relations: rendition_of CT-0020_v1.mp4`) |
| `CT-0020_v1_frames.jpg` | Tờ 8 khung hình |
| `CT-0020_v1_cover.jpg` | Ảnh bìa |
| `CT-0020_v1_script.md` | Kịch bản công khai |
| `CT-0021_v1_still_01.png` + `CT-0021_v1_still_01.jpg` | PNG gốc + JPG dự phòng (`rendition_of`) |
| `CT-0022_v1_copy.md` | Bài chữ / thảo luận / bộ bình luận gợi ý |
| `CT-0020_post.md` | Gói đăng bài hiện hành |

`media.py register` tự đặt tên từ `--work --version --role [--qualifier] [--nn]` và từ chối tên sai luật.

File cũ (trước 05/11/2026, cột `legacy=y` trong `assets.csv`) giữ nguyên tên — ví dụ `CT-0010_p01.png` — và vẫn có trong catalog.
`check` chỉ áp luật tên cho file mới.

## Phiên bản

- `v<n>` tăng khi lời, hình hoặc số liệu đổi. Mỗi phiên bản là bộ file mới; file cũ không bị đụng tới.
- Trạng thái gắn theo **phiên bản** (`events.csv`). Trạng thái tác phẩm = trạng thái của `current_version`.
- `register --supersede` khi phiên bản mới thay phiên bản cũ: phiên bản cũ chuyển `superseded`, thêm `relations: supersedes`.
  Bản A/B cùng sống thì **không** dùng `--supersede`; ghi `--rel variant_of:<CT>_<v>` kèm mã EX- ở note.

## Trùng lặp

Cùng sha256 với một file đã có → `register` **không** lưu bản thứ hai, chỉ thêm `relations: <CT>_<v> uses <asset_id có sẵn>`.

## Tạm và chính thức

Media chỉ nhận bản **đã giao** (thử hoặc chốt). Bản nháp nội bộ, mã nguồn dự án, render trung gian, ý tưởng ở lại studio
(`brainstorm/`, `projects/`). Bản thử được giao → `--test`.

## Tài sản ngoài repo

Bài website derival.ai, video lưu ngoài (nếu sau này cần): `register --role page --external --link <url>` (`storage=external`).
Media ghi nhận link, không chép nội dung.

## Dung lượng (GĐ5)

Khoảng 6 MB/ngày (~2 GB/năm). `check` cảnh báo khi tổng tài sản trong repo > 1 GB; khi đó quyết định cách lưu video
(GitHub Releases hoặc Drive, `storage=external`) — không xoá file cũ đã có link.

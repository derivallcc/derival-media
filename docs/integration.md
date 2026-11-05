# Tích hợp: ai dùng Media thế nào

Link chuẩn:

- Tải: `https://raw.githubusercontent.com/derivallcc/derival-media/main/<path>` (không cần đăng nhập)
- Xem: `https://github.com/derivallcc/derival-media/blob/main/<path>`
- Link bất biến tuyệt đối: thay `main` bằng mã commit.

Raw URL không liệt kê được thư mục, nên bot luôn bắt đầu từ một file danh mục (`catalog/works.csv` hoặc `index.csv`).

## Studio (người ghi chính)

`scripts/archive_run.py` gọi tool thay vì tự chép file và viết CSV:

```bash
M=../derival-media/tools/media.py
python3 $M register --work CT-0020 --version v1 --role video  --file out/CT-0020_v1.mp4 --by studio:archive_run \
    --kind video --title "…" --format F05 --series SR02 --campaign SR02 --source-ref studio:brain/content/CT-0020 [--test --ref BS…]
python3 $M register --work CT-0020 --version v1 --role frames --file out/CT-0020_v1_frames.jpg --by studio:archive_run \
    --rel derived_from:CT-0020_v1.mp4
python3 $M register --work CT-0020 --version v1 --role script --file out/CT-0020_v1_script.md --by studio:archive_run \
    --rel script_of:CT-0020_v1.mp4
python3 $M register --work CT-0020 --version v1 --role post   --file out/CT-0020_post.md --by studio:archive_run
python3 $M commit -m "CT-0020_v1: frames, post, script, video" --push
```

- `--test` thay cho việc ghi vào `test/` (đã đóng băng).
- Duyệt / đăng trong `routines/studio-daily.md`: `media.py status … approved --ref <message_id>`, `media.py publish …`.
- Các script đọc (`script_scan.py`, `video_check.py`, `style_anchor.py`, `common.post_path`, `social_kit.py`) **không cần sửa**:
  đường dẫn `media/<CT>/…` giữ nguyên. Lưu ý: bản thử mới nằm trong `media/<CT>/` — script nào cần lọc bản thử thì đọc
  `catalog/works.csv` (`status=testing`).
- Bảng trùng ở studio (`interactions/{posts,metrics,comments,account_stats}.csv`, `social_sync.py`) chuyển sang ngừng dùng;
  Media `publications.csv` + `intel/metrics/` thay thế.

## social-intel (system-design `ops/scripts/social_sync.py`)

Đọc (hiện tại, vẫn chạy): `index.csv` (cột `ct, ngay, phien_ban, loai`; dòng `loai=post`) + `media/<CT>/<CT>_post.md`.
`index.csv` giữ đúng 9 cột, CRLF, và vẫn loại bản thử mới.

Nên chuyển sang:

1. Đọc `catalog/works.csv` lấy `title` chuẩn (không regex tiêu đề), lọc `status != testing`.
2. Đọc `catalog/assets.csv` (`role=post`) lấy link gói đăng bài.
3. Ghi lại (nếu có quyền push — Q3): `media.py publish --source social-intel --matched-by code|caption`, rồi
   `media.py metrics --csv <lượt> --run-id <run> --source social-intel`, `media.py insight …`, `media.py commit … --push`.
   Không có quyền push → studio nhập từ Sheet `social` mỗi lượt bằng đúng các lệnh trên.

`pub_id` = `post_key` của social-intel (`platform|account_id|platform_post_id`).

## Brainstorm / Brainwave (bot máy chủ)

- Đọc `catalog/works.csv` → `catalog/assets.csv` → file. Bản thử: `status=testing`; bản chốt: các trạng thái khác.
- `test/<CT>/` cũ vẫn đọc được (CT-0014, CT-0015) và có trong `assets.csv` với đường dẫn `test/…`.

## Bản tin Telegram, registry, status.json

Link đã gửi (`media/…`, `test/…`) sống mãi — không file nào bị chuyển hay đổi tên. Link mới lấy từ cột `link` của `assets.csv`
hoặc dòng cuối `media.py register` in ra.

## Agent / developer

```bash
python3 tools/media.py find --kind video --status published --platform tiktok
python3 tools/media.py find --status testing
python3 tools/media.py find --role frames            # danh sách tờ khung hình + link
python3 tools/media.py show CT-0015 [--json]         # toàn bộ hồ sơ một tác phẩm
python3 tools/media.py check                         # trước mọi commit
python3 tools/test_media.py                          # kiểm thử tool
```

Hai người ghi cùng lúc (studio 4 lượt/ngày, social-intel 1 lượt): bảng chỉ thêm dùng `merge=union` (`.gitattributes`);
`media.py commit --push` chạy `pull --rebase`, tự sinh lại `index.csv` / `summary.csv` nếu xung đột ở đó, và gộp dòng trùng.
Xung đột ở file khác → dừng, báo lỗi, không push.

## Knowledge

Media chỉ tham chiếu: logo gốc và bảng màu (BD-021), `brand-assets.md`, `cross-repo.md`, `shared-vocabulary.md`.
Không chép logo/nền — ghi `relations: uses knowledge:<đường dẫn>`. Chỉ CEO sửa knowledge (BD-019).

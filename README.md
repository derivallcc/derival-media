# derival-media

Kho **ảnh, video và nội dung do Claude tạo ra** cho studio Derival — dùng trên Facebook, TikTok, Instagram, YouTube, LinkedIn và các
kênh Telegram/Zalo của Derival. Repo **public**: link raw tải được không cần đăng nhập, và link đã gửi trong bản tin sống mãi.

Ngoài file, repo giữ **danh mục** (mỗi tác phẩm là gì, đang ở trạng thái nào, có những file nào, liên quan gì) và **Media
Intelligence** (đã đăng ở đâu, hiệu quả ra sao theo thời gian, phản hồi tổng hợp). Công cụ, chiến lược, kịch bản gốc, lịch sử tạo
nằm ở repo studio (private).

Luật bắt buộc: **[AGENTS.md](AGENTS.md)**.

## Vị trí trong hệ sinh thái

```
knowledge (logo gốc, từ vựng) ─┐
system-design (cơ chế, task)   ├─► studio (sản xuất, private) ──media.py register──► MEDIA (public)
d-site-design (nhận diện)      ┘        ▲                                             │ link raw
                                        │ script_scan / video_check (chống lặp)       ├─► bản tin Telegram → admin đăng tay
                                        └─────────────────────────────────────────────┤
                                                                                      ├─► Brainstorm/Brainwave bot
                                                                                      └─► social-intel ⇄ publications + intel
```

## Cấu trúc

| Đường dẫn | Chứa gì |
|---|---|
| `media/<CT>/` | **Mọi** file của một tác phẩm: video, tờ khung hình, ảnh, kịch bản, gói đăng bài — mọi trạng thái, mọi phiên bản |
| `test/<CT>/` | Bản thử cũ (CT-0014, CT-0015). **Đóng băng** từ 05/11/2026, giữ cho link sống |
| `catalog/works.csv` | 1 dòng / tác phẩm: loại, tiêu đề, trạng thái, phiên bản hiện hành, format, series, chiến dịch |
| `catalog/assets.csv` | 1 dòng / file: vai trò, kích thước, sha256, thời lượng, link |
| `catalog/relations.csv` | Quan hệ: tờ khung của video nào, JPG là bản xuất của PNG nào, v2 thay v1, dùng logo nào |
| `catalog/events.csv` | Sổ vòng đời (chỉ thêm): tạo, thử nghiệm, duyệt, đăng, thay, gỡ |
| `catalog/publications.csv` | 1 dòng / bài đăng thật trên một nền tảng |
| `intel/metrics/<yyyy-mm>.csv` | Ảnh chụp chỉ số theo thời gian (chỉ thêm) |
| `intel/reviews.csv`, `intel/insights.csv` | Đánh giá người/AI; phản hồi khán giả tổng hợp, không tên (chỉ thêm) |
| `intel/summary.csv` | Sinh tự động: hiệu quả mới nhất theo tác phẩm × phiên bản × nền tảng |
| `index.csv` | Sinh tự động, giữ đúng 9 cột cũ cho các bot đang đọc |
| `schema/vocabulary.csv` | Mọi giá trị hợp lệ: loại, vai trò file, trạng thái, nền tảng, quan hệ, nguồn dữ liệu |
| `tools/media.py` | API ghi/đọc duy nhất (Python stdlib) · `tools/test_media.py` |
| `docs/` | `storage` · `schema` · `lifecycle` · `integration` · `intelligence` · `migration` |

Tên file: `<CT>_<v>[_<role>][-<qualifier>][_<nn>].<ext>` — ví dụ `CT-0020_v1.mp4`, `CT-0020_v1_frames.jpg`,
`CT-0021_v1_still_01.png`, `CT-0020_post.md`. Chi tiết: [docs/storage.md](docs/storage.md).

## Muốn làm X → lệnh Y

| Muốn | Lệnh |
|---|---|
| Thêm file đã giao | `python3 tools/media.py register --work CT-0020 --version v1 --role video --file … --by studio:archive_run [--test]` |
| Đổi trạng thái | `python3 tools/media.py status CT-0020 v1 approved --actor CEO --actor-type human --ref <message_id>` |
| Ghi bài đã đăng | `python3 tools/media.py publish --work CT-0020 --version v1 --platform tiktok --account … --post-id … --published-at … --source admin` |
| Ghi chỉ số | `python3 tools/media.py metrics --pub-id "tiktok\|…\|…" --run-id … --views … --source social-intel` |
| Ghi đánh giá / phản hồi | `python3 tools/media.py review …` · `python3 tools/media.py insight …` |
| Xem một tác phẩm | `python3 tools/media.py show CT-0015` |
| Tìm | `python3 tools/media.py find --kind video --status testing` |
| Kiểm trước commit | `python3 tools/media.py check` |
| Commit + push | `python3 tools/media.py commit -m "CT-0020_v1: video, frames" --push` |

Bot không có git: đọc `catalog/works.csv` → `catalog/assets.csv` → file qua link raw
`https://raw.githubusercontent.com/derivallcc/derival-media/main/<path>`. Chi tiết: [docs/integration.md](docs/integration.md).

Có mặt trong repo **không** có nghĩa là đã duyệt đăng — xem cột `status` của `catalog/works.csv`
(vòng đời: [docs/lifecycle.md](docs/lifecycle.md)).

## Lưu ý

Nội dung mang tính thông tin, không phải tư vấn đầu tư. Kết quả quá khứ không đảm bảo kết quả tương lai.
Video chỉ nói về lệnh đã đóng. © Công ty TNHH Derival — không dùng lại cho mục đích thương mại khi chưa được phép.

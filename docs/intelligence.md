# Media Intelligence

Mục tiêu: biết mỗi tác phẩm / phiên bản / bài đăng hoạt động ra sao, theo thời gian, mà **không** đưa dữ liệu cá nhân hay
ghi chú nội bộ lên repo public. Mọi file intel **chỉ thêm**; muốn sửa thì thêm dòng mới (`supersedes` cho reviews/insights,
ảnh chụp mới cho metrics).

## Lưu gì, ở đâu

| Nhóm | Lưu thẳng ở Media | Chỉ tham chiếu | Sinh tự động |
|---|---|---|---|
| Bài đăng | `catalog/publications.csv`: nền tảng, tài khoản Derival, URL, giờ đăng, utm | — | — |
| Hiệu quả MXH | `intel/metrics/<yyyy-mm>.csv`: ảnh chụp số **công khai** (views, reach, likes, reactions, comments, shares, saves, clicks) | Sheet `social` (dashboard vận hành) | `intel/summary.csv`: số mới nhất, chênh so với ảnh trước, ER |
| Phản hồi khán giả | `intel/insights.csv`: chủ đề, câu hỏi lặp, tỷ lệ cảm xúc, số lượng, câu tóm ý **diễn đạt lại, không tên** | Bình luận gốc + người viết: Sheet `SOCIAL_COMMENTS` qua `comment_key` (ghi ở `ref`) | — |
| Quyết định đội ngũ | `intel/reviews.csv` `reviewer_type=human`: verdict (approve/reject/revise/note), vai trò (CEO/COO/admin), `ref`=message_id | Nguyên văn tin nhóm Telegram | — |
| Chất lượng | `intel/reviews.csv`: rubric (ví dụ `video-barem v2.0`), tiêu chí, verdict, `independent` | **Điểm chi tiết + bằng chứng: studio `qa.md`** | — |
| Lịch sử | Mọi file intel chỉ thêm; khoá chống trùng `pub_id\|run_id` | — | So sánh tác phẩm / phiên bản / chiến dịch / nền tảng qua `summary.csv` |

Điểm barem **không** lưu ở Media (luật hiện hành của repo public, Q1). Nếu CEO quyết định công khai điểm, thêm cột vào
`reviews.csv` bằng một thay đổi schema có ghi `CHANGELOG.md` — không tự thêm.

## Thực tế và AI

Mọi dòng intel có:

| Cột | Ý nghĩa |
|---|---|
| `origin` | `measured` (API/trang công khai của nền tảng), `human`, `ai`, `computed`, `migration` |
| `source` | Tiến trình/công cụ: `social-intel`, `studio:ai_style_check`, `telegram`… |
| `method` | Cách lấy: tên API, prompt/rubric, cách tính |
| `confidence` | high / medium / low (với `ai`, `computed`) |
| `human_check` | y nếu người đã xác nhận |

- Dòng AI **không bao giờ** thay dòng của người (`media.py` và `check` chặn `supersedes` từ ai → human).
- Số đo (`measured`) không bị sửa: nền tảng đổi số → thêm ảnh chụp mới.

## Số lúc đăng và số sau đó

- Ảnh chụp đầu tiên sau `published_at` tự nhận `checkpoint=first`. Các mốc khác: `24h`, `72h`, `7d`, `30d`, ngoài mốc `adhoc`.
- Mọi ảnh chụp giữ nguyên cạnh nhau; `summary.csv` lấy số mới nhất của từng cột và `delta_views` so với ảnh trước.
- **Ô trống = nền tảng không cung cấp**, không phải 0. `provided_fields` ghi các cột có số.

## Quy tắc ghi

```bash
# một ảnh chụp
python3 tools/media.py metrics --pub-id "tiktok|<acc>|<post>" --run-id si-20261106 --views 1200 --likes 80 \
    --comments 6 --source social-intel --method tiktok-api
# cả lượt từ file CSV (đúng cột intel/metrics)
python3 tools/media.py metrics --csv /tmp/lượt.csv --run-id si-20261106 --source social-intel
# tổng hợp phản hồi
python3 tools/media.py insight --work CT-0015 --insight-type question --topic "phí dịch vụ" --count 4 \
    --summary "Nhiều người hỏi dùng tín hiệu có mất phí không" --source social-intel --origin ai --confidence medium
# quyết định của người
python3 tools/media.py review --work CT-0015 --version v2 --reviewer-type human --reviewer-role CEO \
    --verdict approve --source telegram --ref <message_id>
```

`metrics` cần `pub_id` đã có trong `publications.csv` (ghi `publish` trước). `insight` từ chối `summary` có @tên, email,
số điện thoại.

## Không ghi

Tên/ID/@ của khán giả, nguyên văn bình luận, tin nhắn riêng, chỉ số tài khoản quảng cáo/chi phí, dữ liệu nội bộ của Sheet
không công khai, tên thành viên đội ngũ.

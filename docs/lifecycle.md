# Vòng đời

Trạng thái gắn theo **phiên bản** (`CT-xxxx` + `v<n>`) và nằm ở `catalog/events.csv` (chỉ thêm). Đây là **nơi gốc**;
studio `registry.csv` là bản sao do cùng một lệnh ghi. `works.status` = trạng thái của `current_version` (sinh tự động).
Đổi trạng thái **không bao giờ** chuyển file.

```
            ┌────────────► rejected
            │                 ▲
 testing ───┼──► pending_review ──► approved ──► published ──► archived
   │        │        │                 │            │
   │        └────────┴──► superseded ◄─┘            └──► withdrawn (chỉ khi người dùng quyết)
   └──► archived / withdrawn
```

| Trạng thái | Nhãn studio | Vào khi | Đi tiếp được |
|---|---|---|---|
| `testing` | Thử nghiệm (không đăng) | Brainstorm STAGE: test, phiên thử (`register --test`) | pending_review, rejected, superseded, archived, withdrawn |
| `pending_review` | Chờ duyệt | Qua G-1/G-4, đã giao (`register` mặc định) | approved, rejected, superseded, withdrawn |
| `approved` | Đã duyệt | "ok đăng CT-xxxx" — **phải** `actor_type=human` + `ref` = message_id | published, archived, superseded, withdrawn |
| `published` | Đã đăng | Có ≥ 1 dòng `publications.csv` (`media.py publish`) | archived, withdrawn |
| `rejected` | Không duyệt | Đội ngũ từ chối | (kết thúc) |
| `superseded` | — | Có phiên bản mới thay (`register --supersede`) | (kết thúc) |
| `archived` | — | Hết dùng, file vẫn giữ | (kết thúc) |
| `withdrawn` | Gỡ | **Chỉ khi người dùng quyết** — cần `--ref` tin nhắn quyết định | (kết thúc) |

Một nhãn duy nhất cho bản thử: "Thử nghiệm (không đăng)" (trước đây có cả "Thử nghiệm — không đăng").

Nháp và ý tưởng **không** vào Media: chúng ở studio `brainstorm/`.

## Lệnh

```bash
# giao bản thử
python3 tools/media.py register --work CT-0020 --version v1 --role video --file out/CT-0020_v1.mp4 \
    --by studio:archive_run --test --ref BS261110A --kind video --title "…"
# bản chốt thay bản thử
python3 tools/media.py register --work CT-0020 --version v2 --role video --file … --by studio:archive_run --supersede
# duyệt
python3 tools/media.py status CT-0020 v2 approved --actor CEO --actor-type human --ref <message_id>
# đăng (chuyển published nếu đã duyệt)
python3 tools/media.py publish --work CT-0020 --version v2 --platform tiktok --account <id trang> --post-id <id> \
    --url <url> --published-at 2026-11-10T19:30:00+07:00 --source admin
```

## Bài lên trước khi ghi duyệt

Thực tế thắng: `publish` vẫn ghi bài đăng, nhưng trạng thái giữ nguyên và `check` cảnh báo "đăng khi chưa ghi nhận duyệt".
Khi có lệnh duyệt: `status … approved --ref …`, rồi chạy lại đúng lệnh `publish` (không ghi trùng) để chuyển `published`.

## Dữ liệu cũ

Trạng thái CT-0001…CT-0015 được điền ngược ngày 05/11/2026 (`actor=migration`) theo audit: CT-0001…0007, CT-0011, CT-0014,
CT-0015 = `testing`; CT-0008…0010, CT-0012, CT-0013 = `pending_review`; các phiên bản cũ (CT-0001 v1, CT-0002 v1, CT-0003 v6,
CT-0006 v1) = `superseded`. Khi studio đối chiếu `registry.csv` có khác, ghi tiếp bằng `media.py status` (không sửa dòng cũ).

#!/usr/bin/env python3
"""media.py — API ghi/đọc duy nhất của derival-media (chỉ Python stdlib).

Studio, bot, social-intel và developer đều ghi qua tool này, không tự viết CSV.
Tài liệu: docs/schema.md (bảng), docs/lifecycle.md (trạng thái), docs/integration.md (cách gọi).

Lệnh ghi : register · status · publish · metrics · review · insight
Lệnh sinh: build (works.status, index.csv, intel/summary.csv) · commit (build + check + commit [+ push])
Lệnh đọc : check · find · show

Gốc repo lấy từ --root, biến môi trường MEDIA_ROOT, hoặc thư mục cha của tools/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=7))
RAW = "https://raw.githubusercontent.com/derivallcc/derival-media/main/"
BLOB = "https://github.com/derivallcc/derival-media/blob/main/"
MAX_BYTES = 25 * 1024 * 1024
REPO_WARN_BYTES = 1024 ** 3          # GĐ5: 1 GB thì quyết định cách lưu video
CUTOVER = "2026-11-05"               # file thêm từ ngày này phải theo luật tên mới

CT_RE = re.compile(r"^CT-\d{4}$")
V_RE = re.compile(r"^v\d+$")
NAME_RE = re.compile(
    r"^(?P<ct>CT-\d{4})_(?:(?P<post>post)\.md|(?P<v>v\d+)(?:_(?P<role>[a-z]+))?"
    r"(?:-(?P<q>[a-z0-9]+))?(?:_(?P<nn>\d{2}))?\.(?P<ext>[a-z0-9]+))$")

# ---------------------------------------------------------------- bảng
TABLES = {
    "works": ("catalog/works.csv",
              "work_id kind title created_at created_by status current_version format pillar series product "
              "campaign tags source_ref ai_generated note",
              "work_id kind title created_at created_by status current_version"),
    "assets": ("catalog/assets.csv",
               "asset_id work_id version role path bytes sha256 mime created_at created_by link width height "
               "duration_s aspect rendition lang tool ai_label storage legacy note",
               "asset_id work_id role mime created_at created_by link storage"),
    "relations": ("catalog/relations.csv", "subject rel object note", "subject rel object"),
    "events": ("catalog/events.csv",
               "at work_id version event from_status to_status actor actor_type ref note",
               "at work_id version event to_status actor actor_type"),
    "publications": ("catalog/publications.csv",
                     "pub_id work_id version asset_id platform account url published_at published_by campaign "
                     "utm_content source matched_by note",
                     "pub_id work_id version platform account published_at source"),
    "reviews": ("intel/reviews.csv",
                "review_id at work_id version asset_id reviewer_type reviewer_role rubric criterion verdict "
                "independent origin source method confidence human_check ref supersedes note",
                "review_id at work_id reviewer_type verdict origin source"),
    "insights": ("intel/insights.csv",
                 "insight_id at work_id version pub_id platform insight_type topic count share summary origin "
                 "source method confidence human_check ref supersedes note",
                 "insight_id at work_id insight_type topic summary origin source"),
    "summary": ("intel/summary.csv",
                "work_id version platform pub_id first_captured_at last_captured_at checkpoint snapshots views "
                "reach likes comments shares saves clicks er delta_views delta_since", ""),
}
METRICS_COLS = ("pub_id captured_at run_id checkpoint provided_fields views reach likes reactions comments shares "
                "saves clicks origin source method confidence human_check note").split()
METRICS_REQ = "pub_id captured_at run_id checkpoint origin source".split()
METRIC_NUMS = "views reach likes reactions comments shares saves clicks".split()
INDEX_COLS = "ngay ct phien_ban loai file bytes sha256 duration_s link".split()
INDEX_EOL = "\r\n"                   # index.csv cũ dùng CRLF — giữ nguyên cho bot cũ
LEGACY_LOAI = {"still": "anh", "cover": "anh", "thumb": "anh"}

# kiểm từ vựng: (bảng, cột) -> field trong vocabulary.csv
VOCAB_COLS = {
    ("works", "kind"): "kind", ("works", "status"): "status", ("works", "product"): "product",
    ("assets", "role"): "role", ("assets", "storage"): "storage",
    ("relations", "rel"): "rel",
    ("events", "event"): "event", ("events", "to_status"): "status", ("events", "from_status"): "status",
    ("events", "actor_type"): "actor_type",
    ("publications", "platform"): "platform", ("publications", "source"): "pub_source",
    ("publications", "matched_by"): "matched_by",
    ("reviews", "reviewer_type"): "reviewer_type", ("reviews", "verdict"): "verdict",
    ("reviews", "origin"): "origin", ("reviews", "confidence"): "confidence",
    ("insights", "insight_type"): "insight_type", ("insights", "origin"): "origin",
    ("insights", "platform"): "platform", ("insights", "confidence"): "confidence",
    ("metrics", "checkpoint"): "checkpoint", ("metrics", "origin"): "origin", ("metrics", "confidence"): "confidence",
}
YN_COLS = {("reviews", "independent"), ("reviews", "human_check"), ("insights", "human_check"),
           ("metrics", "human_check"), ("works", "ai_generated"), ("assets", "legacy")}
FREE_TEXT = {"title", "note", "tags", "summary", "topic", "criterion", "reviewer_role", "method", "actor",
             "published_by", "created_by"}

TRANSITIONS = {
    "": {"testing", "pending_review"},
    "testing": {"pending_review", "rejected", "superseded", "withdrawn", "archived"},
    "pending_review": {"approved", "rejected", "superseded", "withdrawn"},
    "approved": {"published", "archived", "superseded", "withdrawn"},
    "published": {"archived", "withdrawn"},
    "rejected": set(), "superseded": set(), "archived": set(), "withdrawn": set(),
}

SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-ant-[\w-]{10,}|\bsk-[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}|xox[abpr]-[\w-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{8,10}:AA[\w-]{30,})")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d.])(?:\+?84|0)(?:[ .]?\d){9}(?![\d])")
HANDLE_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9_.]{3,}")
ACCOUNT_RE = re.compile(r"(số tài khoản|\bSTK\b|account number)", re.I)


class MediaError(Exception):
    pass


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def cols(name):
    return TABLES[name][1].split()


def p(rel) -> Path:
    return ROOT / rel


# ---------------------------------------------------------------- csv io
def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def header_of(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return next(csv.reader(f), [])


def render_csv(columns, rows, eol="\n") -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator=eol, extrasaction="raise")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    return buf.getvalue()


def write_csv(path: Path, columns, rows, eol="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_csv(columns, rows, eol)
    if not path.exists() or path.read_bytes().decode("utf-8") != text:
        path.write_bytes(text.encode("utf-8"))


def append_rows(path: Path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") or "" for c in columns})


def table(name):
    return read_csv(p(TABLES[name][0]))


def save(name, rows):
    write_csv(p(TABLES[name][0]), cols(name), rows)


def append(name, rows):
    append_rows(p(TABLES[name][0]), cols(name), rows)


def metric_files():
    d = p("intel/metrics")
    return sorted(d.glob("*.csv")) if d.exists() else []


def all_metrics():
    out = []
    for f in metric_files():
        out.extend(read_csv(f))
    return out


def vocab() -> dict:
    v = {}
    for r in read_csv(p("schema/vocabulary.csv")):
        v.setdefault(r["field"], {})[r["value"]] = r
    return v


def need(vc, field, value, what=None):
    if value not in vc.get(field, {}):
        raise MediaError(f"{what or field}={value!r} không có trong schema/vocabulary.csv (field {field}). "
                         f"Giá trị hợp lệ: {', '.join(vc.get(field, {}))}")


# ---------------------------------------------------------------- file info
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def image_size(path: Path):
    with path.open("rb") as f:
        head = f.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    return None
                marker = b[0]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    continue
                seglen = struct.unpack(">H", f.read(2))[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(1)
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                f.seek(seglen - 2, 1)
    return None


def probe(path: Path) -> dict:
    """width/height/duration. ffprobe nếu có, không thì đọc header PNG/JPEG."""
    info = {}
    if shutil.which("ffprobe") and path.suffix.lower() in (".mp4", ".mov", ".webm", ".m4a", ".mp3", ".wav"):
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                                  "-show_streams", str(path)], capture_output=True, text=True, timeout=60).stdout
            j = json.loads(out or "{}")
            for s in j.get("streams", []):
                if s.get("codec_type") == "video":
                    info["width"], info["height"] = s.get("width"), s.get("height")
                    break
            dur = j.get("format", {}).get("duration")
            if dur:
                info["duration_s"] = f"{float(dur):.1f}"
        except Exception:
            pass
    else:
        try:
            wh = image_size(path)
        except Exception:
            wh = None
        if wh:
            info["width"], info["height"] = wh
    if info.get("width") and info.get("height"):
        info["aspect"] = aspect(int(info["width"]), int(info["height"]))
    return info


def aspect(w, h):
    r = w / h
    for name, val in (("9:16", 9 / 16), ("16:9", 16 / 9), ("1:1", 1), ("4:5", 4 / 5), ("5:4", 5 / 4),
                      ("3:4", 3 / 4), ("4:3", 4 / 3), ("2:3", 2 / 3), ("1.91:1", 1.91)):
        if abs(r - val) / val < 0.01:
            return name
    return f"{r:.2f}:1" if r >= 1 else f"1:{1 / r:.2f}"


def mime_of(name):
    ext = Path(name).suffix.lower()
    return {".md": "text/markdown", ".mp4": "video/mp4", ".webp": "image/webp", ".srt": "application/x-subrip",
            ".vtt": "text/vtt", ".m4a": "audio/mp4"}.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def asset_name(ct, v, role, ext, qualifier="", nn=""):
    if role == "post":
        return f"{ct}_post.md"
    name = f"{ct}_{v}"
    if role != "video":
        name += f"_{role}"
    if qualifier:
        name += f"-{qualifier}"
    if nn:
        name += f"_{int(nn):02d}"
    return f"{name}.{ext}"


def vnum(v):
    return int(v[1:]) if v and V_RE.match(v) else -1


# ---------------------------------------------------------------- trạng thái
def version_status(events):
    st = {}
    for e in events:
        if e.get("to_status"):
            st[(e["work_id"], e["version"])] = e["to_status"]
    return st


def check_transition(cur, new):
    if new not in TRANSITIONS.get(cur or "", set()):
        allowed = ", ".join(sorted(TRANSITIONS.get(cur or "", set()))) or "(trạng thái kết thúc)"
        raise MediaError(f"Không chuyển được {cur or '(mới)'} → {new}. Hợp lệ: {allowed}. Xem docs/lifecycle.md")


# ---------------------------------------------------------------- build
def merge_dupes(rows, key):
    """Gộp dòng trùng khoá (do merge=union khi hai bên cùng ghi): giữ thứ tự lần đầu, ô không rỗng sau cùng thắng."""
    out, pos = [], {}
    for r in rows:
        k = r[key]
        if k in pos:
            base = out[pos[k]]
            for c, val in r.items():
                if val:
                    base[c] = val
        else:
            pos[k] = len(out)
            out.append(dict(r))
    return out


def gen_index(assets, events):
    st = version_status(events)
    rows = []
    for a in assets:
        if a.get("storage") != "repo" or not a["path"].startswith("media/"):
            continue
        if a.get("legacy") != "y" and st.get((a["work_id"], a["version"])) == "testing":
            continue
        rows.append({"ngay": a["created_at"][:10], "ct": a["work_id"], "phien_ban": a["version"],
                     "loai": LEGACY_LOAI.get(a["role"], a["role"]), "file": a["path"], "bytes": a["bytes"],
                     "sha256": a["sha256"][:16], "duration_s": a.get("duration_s", ""), "link": a["link"]})
    return rows


def num(x):
    try:
        return int(float(x)) if x not in ("", None) else None
    except ValueError:
        return None


def gen_summary(pubs, metrics):
    by = {}
    for m in metrics:
        by.setdefault(m["pub_id"], []).append(m)
    rows = []
    for pb in pubs:
        snaps = sorted(by.get(pb["pub_id"], []), key=lambda m: m["captured_at"])
        if not snaps:
            continue
        last, prev = snaps[-1], (snaps[-2] if len(snaps) > 1 else None)
        r = {"work_id": pb["work_id"], "version": pb["version"], "platform": pb["platform"], "pub_id": pb["pub_id"],
             "first_captured_at": snaps[0]["captured_at"], "last_captured_at": last["captured_at"],
             "checkpoint": last["checkpoint"], "snapshots": len(snaps)}
        for c in "views reach likes comments shares saves clicks".split():
            vals = [num(s.get(c)) for s in snaps if num(s.get(c)) is not None]
            r[c] = vals[-1] if vals else ""
        v = num(r["views"])
        eng = [num(r[c]) for c in ("likes", "comments", "shares", "saves") if num(r[c]) is not None]
        r["er"] = f"{sum(eng) / v:.4f}" if v and eng else ""
        if prev and num(prev.get("views")) is not None and v is not None:
            r["delta_views"] = v - num(prev["views"])
            r["delta_since"] = prev["captured_at"]
        rows.append(r)
    rows.sort(key=lambda r: (r["work_id"], vnum(r["version"]), r["platform"], r["pub_id"]))
    return rows


def build(quiet=False):
    vc = vocab()
    works = merge_dupes(table("works"), "work_id")
    assets = merge_dupes(table("assets"), "asset_id")
    events = table("events")
    # gói đăng bài (mutable) có thể đổi tại chỗ: cập nhật bytes/sha
    for a in assets:
        role = vc.get("role", {}).get(a["role"], {})
        f = p(a["path"]) if a.get("path") else None
        if role.get("mutable") == "y" and a.get("storage") == "repo" and f and f.exists():
            a["bytes"], a["sha256"] = str(f.stat().st_size), sha256(f)
    for name in ("relations", "events", "publications", "reviews", "insights"):
        f = p(TABLES[name][0])
        if not f.exists():
            write_csv(f, cols(name), [])
    st = version_status(events)
    for w in works:
        s = st.get((w["work_id"], w["current_version"]))
        if s:
            w["status"] = s
    save("works", works)
    save("assets", assets)
    write_csv(p("index.csv"), INDEX_COLS, gen_index(assets, events), INDEX_EOL)
    write_csv(p(TABLES["summary"][0]), cols("summary"), gen_summary(table("publications"), all_metrics()))
    if not quiet:
        print(f"build: {len(works)} tác phẩm, {len(assets)} tài sản → index.csv, intel/summary.csv")


# ---------------------------------------------------------------- check
def baseline():
    f = p("docs/migration.md")
    if not f.exists():
        return []
    m = re.search(r"<!-- baseline:start -->\s*```\n(.*?)```\s*<!-- baseline:end -->", f.read_text(encoding="utf-8"), re.S)
    out = []
    for line in (m.group(1).splitlines() if m else []):
        parts = line.split()
        if len(parts) == 3:
            out.append((parts[0], int(parts[1]), parts[2]))
    return out


BASELINE_MUTABLE = {"README.md", "CLAUDE.md", "index.csv"}


def scan_text(label, text, errors, free=True):
    if SECRET_RE.search(text):
        errors.append(f"{label}: có chuỗi giống khoá/token — repo public, không được đưa vào")
    if not free:
        return
    for m in EMAIL_RE.finditer(text):
        if not m.group(0).lower().endswith("@derival.ai"):
            errors.append(f"{label}: có địa chỉ email ({m.group(0)}) — dữ liệu cá nhân")
    if PHONE_RE.search(text):
        errors.append(f"{label}: có số điện thoại — dữ liệu cá nhân")
    if ACCOUNT_RE.search(text):
        errors.append(f"{label}: nhắc tới số tài khoản — không được đưa vào")


def check(args=None) -> int:
    errors, warns = [], []
    vc = vocab()
    if not vc:
        errors.append("thiếu schema/vocabulary.csv")
    data = {}
    for name, (rel, c, req) in TABLES.items():
        path = p(rel)
        if not path.exists():
            errors.append(f"thiếu {rel} (chạy: media.py build)")
            data[name] = []
            continue
        if header_of(path) != c.split():
            errors.append(f"{rel}: cột phải đúng `{c}` (cột lạ có thể làm lộ dữ liệu — xem docs/schema.md)")
        data[name] = read_csv(path)
    for f in metric_files():
        if header_of(f) != METRICS_COLS:
            errors.append(f"{f.relative_to(ROOT)}: cột phải đúng `{' '.join(METRICS_COLS)}`")
    data["metrics"] = all_metrics()

    # bắt buộc + từ vựng + văn bản tự do
    reqs = {n: t[2].split() for n, t in TABLES.items()}
    reqs["metrics"] = METRICS_REQ
    for name, rows in data.items():
        if name == "summary":
            continue
        for i, r in enumerate(rows, 2):
            where = f"{name} dòng {i}"
            for c in reqs[name]:
                if not r.get(c):
                    errors.append(f"{where}: thiếu {c}")
            for c, val in r.items():
                if val is None:
                    errors.append(f"{where}: số ô nhiều hơn số cột")
                    continue
                field = VOCAB_COLS.get((name, c))
                if field and val and val not in vc.get(field, {}):
                    errors.append(f"{where}: {c}={val!r} không có trong vocabulary ({field})")
                if (name, c) in YN_COLS and val not in ("", "y", "n"):
                    errors.append(f"{where}: {c} chỉ nhận y/n")
                if val:
                    scan_text(f"{where} cột {c}", val, errors, free=c in FREE_TEXT)
                    if c in FREE_TEXT and HANDLE_RE.search(val):
                        errors.append(f"{where} cột {c}: có @tên người dùng — không ghi danh tính khán giả")

    works = {w["work_id"]: w for w in data["works"]}
    assets = data["assets"]
    events = data["events"]
    st = version_status(events)
    if len(works) != len(data["works"]):
        errors.append("works.csv: trùng work_id (chạy media.py build để gộp)")
    for w in data["works"]:
        if not CT_RE.match(w["work_id"]):
            errors.append(f"works: work_id {w['work_id']!r} sai dạng CT-dddd")
        if not V_RE.match(w["current_version"] or ""):
            errors.append(f"works {w['work_id']}: current_version phải dạng v<n>")
        s = st.get((w["work_id"], w["current_version"]))
        if s is None:
            errors.append(f"works {w['work_id']}: phiên bản hiện hành {w['current_version']} chưa có sự kiện trong events.csv")
        elif s != w["status"]:
            errors.append(f"works {w['work_id']}: status {w['status']} lệch events.csv ({s}) — chạy media.py build")

    # tài sản
    seen_id, seen_path = set(), {}
    on_disk = set()
    for d in ("media", "test"):
        if p(d).exists():
            on_disk |= {str(f.relative_to(ROOT)) for f in p(d).rglob("*") if f.is_file() and f.name != ".gitkeep"}
    for a in assets:
        aid = a["asset_id"]
        if aid in seen_id:
            errors.append(f"assets: trùng asset_id {aid} (chạy media.py build để gộp)")
        seen_id.add(aid)
        if a["work_id"] not in works:
            errors.append(f"assets {aid}: work_id {a['work_id']} không có trong works.csv")
        role = vc.get("role", {}).get(a["role"], {})
        if role.get("versioned") == "y" and not V_RE.match(a.get("version") or ""):
            errors.append(f"assets {aid}: vai trò {a['role']} cần version dạng v<n>")
        for c in (role.get("required_fields") or "").split("|"):
            if c and not a.get(c):
                errors.append(f"assets {aid}: vai trò {a['role']} cần {c}")
        if a.get("storage") == "external":
            if a.get("path"):
                errors.append(f"assets {aid}: storage=external không có path")
            continue
        path = a.get("path", "")
        if not path:
            errors.append(f"assets {aid}: thiếu path")
            continue
        if path in seen_path:
            errors.append(f"assets: đường dẫn {path} xuất hiện hai lần")
        seen_path[path] = a
        if Path(path).name != aid:
            errors.append(f"assets {aid}: asset_id phải bằng tên file ({Path(path).name})")
        if not path.startswith(f"media/{a['work_id']}/") and not path.startswith(f"test/{a['work_id']}/"):
            errors.append(f"assets {aid}: phải nằm trong media/{a['work_id']}/")
        f = p(path)
        if not f.exists():
            errors.append(f"assets {aid}: file {path} không tồn tại — link đã gửi bị vỡ")
            continue
        size = f.stat().st_size
        if size > MAX_BYTES:
            errors.append(f"{path}: {size / 1e6:.1f} MB > 25 MB")
        if str(size) != a["bytes"] or sha256(f) != a["sha256"]:
            if role.get("mutable") == "y":
                errors.append(f"{path}: đã đổi nội dung — chạy media.py build để cập nhật sha")
            else:
                errors.append(f"{path}: sha256/bytes khác catalog — file bất biến đã bị sửa")
        if len(a["sha256"]) != 64:
            errors.append(f"assets {aid}: sha256 phải đủ 64 ký tự")
        if a.get("legacy") != "y":
            if path.startswith("test/"):
                errors.append(f"{path}: test/ đã đóng băng — bản thử ghi vào media/<CT>/ với status testing")
            m = NAME_RE.match(aid)
            exts = (role.get("extensions") or "").split("|")
            if not m or m.group("ct") != a["work_id"]:
                errors.append(f"{aid}: sai luật tên <CT>_<v>[_<role>][-<qualifier>][_<nn>].<ext> (docs/storage.md)")
            elif not m.group("post") and (m.group("v") != a["version"] or (m.group("role") or "video") != a["role"]
                                          or m.group("ext") not in exts):
                errors.append(f"{aid}: tên không khớp version/role/đuôi trong catalog")
    for f in sorted(on_disk - set(seen_path)):
        errors.append(f"{f}: có trong repo nhưng chưa có trong catalog/assets.csv (chỉ ghi qua media.py register)")
    total = sum(int(a["bytes"] or 0) for a in assets if a.get("storage") == "repo")
    if total > REPO_WARN_BYTES:
        warns.append(f"dung lượng tài sản {total / 1e9:.2f} GB > 1 GB — quyết định cách lưu video (GĐ5, docs/storage.md)")

    # mốc GĐ0
    for sha, size, path in baseline():
        f = p(path)
        if not f.exists():
            errors.append(f"mốc GĐ0: {path} đã biến mất — link đã gửi bị vỡ")
        elif path not in BASELINE_MUTABLE and not path.endswith("_post.md") and sha256(f) != sha:
            errors.append(f"mốc GĐ0: {path} đã bị sửa (sha khác mốc)")

    # sự kiện
    cur = {}
    for i, e in enumerate(events, 2):
        k = (e["work_id"], e["version"])
        if e["work_id"] not in works:
            errors.append(f"events dòng {i}: work_id {e['work_id']} không có trong works.csv")
        if (e.get("from_status") or "") != cur.get(k, ""):
            errors.append(f"events dòng {i}: from_status {e.get('from_status') or '(trống)'} nhưng trạng thái trước đó là "
                          f"{cur.get(k) or '(mới)'}")
        try:
            check_transition(cur.get(k, ""), e["to_status"])
        except MediaError as ex:
            errors.append(f"events dòng {i}: {ex}")
        if e["to_status"] == "approved" and (e["actor_type"] != "human" or not e.get("ref")):
            errors.append(f"events dòng {i}: approved phải do người (actor_type=human) và có ref (message_id)")
        cur[k] = e["to_status"]
    pubs = data["publications"]
    pub_ids = {pb["pub_id"] for pb in pubs}
    if len(pub_ids) != len(pubs):
        errors.append("publications: trùng pub_id")
    for (ct, v), s in cur.items():
        if s == "published" and not any(pb["work_id"] == ct and pb["version"] == v for pb in pubs):
            errors.append(f"{ct}_{v}: published nhưng không có dòng publications")
    approved = {(e["work_id"], e["version"]) for e in events if e["to_status"] == "approved"}
    for pb in pubs:
        if len(pb["pub_id"].split("|")) != 3 or pb["pub_id"].split("|")[0] != pb["platform"]:
            errors.append(f"publications {pb['pub_id']}: pub_id phải là platform|account_id|platform_post_id")
        if pb["work_id"] not in works:
            errors.append(f"publications {pb['pub_id']}: work_id {pb['work_id']} không có trong works.csv")
        if (pb["work_id"], pb["version"]) not in approved:
            warns.append(f"publications {pb['pub_id']}: {pb['work_id']}_{pb['version']} đăng khi chưa ghi nhận duyệt")
        if pb.get("asset_id") and pb["asset_id"] not in seen_id:
            errors.append(f"publications {pb['pub_id']}: asset_id {pb['asset_id']} không có")
    # chỉ số
    keys = set()
    for m in data["metrics"]:
        k = (m["pub_id"], m["run_id"])
        if k in keys:
            errors.append(f"metrics: trùng {m['pub_id']}|{m['run_id']}")
        keys.add(k)
        if m["pub_id"] not in pub_ids:
            errors.append(f"metrics {m['pub_id']}: chưa có trong publications.csv")
        for c in METRIC_NUMS:
            if m.get(c) and not re.fullmatch(r"\d+", m[c]):
                errors.append(f"metrics {m['pub_id']}|{m['run_id']}: {c}={m[c]!r} phải là số nguyên ≥ 0 (để trống nếu không có)")
    # đánh giá / insight
    for name, idc in (("reviews", "review_id"), ("insights", "insight_id")):
        rows = {r[idc]: r for r in data[name]}
        if len(rows) != len(data[name]):
            errors.append(f"{name}: trùng {idc}")
        for r in data[name]:
            sup = r.get("supersedes")
            if sup:
                old = rows.get(sup)
                if not old:
                    errors.append(f"{name} {r[idc]}: supersedes {sup} không tồn tại")
                elif old["origin"] == "human" and r["origin"] == "ai":
                    errors.append(f"{name} {r[idc]}: dòng AI không được thay dòng của người ({sup})")
    for r in data["relations"]:
        for side in ("subject", "object"):
            ref = r[side]
            if ":" not in ref and ref not in seen_id and not re.match(r"^CT-\d{4}(_v\d+)?$", ref):
                errors.append(f"relations: {side} {ref!r} không phải asset_id, CT[_v] hay nguồn ngoài repo:path")

    # sinh tự động phải khớp
    idx = p("index.csv")
    if not idx.exists() or idx.read_bytes().decode("utf-8") != render_csv(
            INDEX_COLS, gen_index(merge_dupes(assets, "asset_id"), events), INDEX_EOL):
        errors.append("index.csv lệch catalog — chạy media.py build (không sửa tay)")
    if p(TABLES["summary"][0]).exists() and p(TABLES["summary"][0]).read_bytes().decode("utf-8") != \
            render_csv(cols("summary"), gen_summary(pubs, data["metrics"])):
        errors.append("intel/summary.csv lệch — chạy media.py build (không sửa tay)")

    # khoá/token trong mọi file chữ
    for f in list(ROOT.glob("*.md")) + list(ROOT.glob("docs/*.md")) + [p(x) for x in on_disk if x.endswith((".md", ".csv"))]:
        if f.exists():
            # tài liệu/luật được nhắc tới tên loại dữ liệu cấm; chỉ quét khoá/token. File nội dung quét cả PII.
            scan_text(str(f.relative_to(ROOT)), f.read_text(encoding="utf-8", errors="ignore"), errors,
                      free=f.is_relative_to(ROOT / "media") or f.is_relative_to(ROOT / "test"))

    for w in warns:
        print(f"CẢNH BÁO  {w}")
    for e in errors:
        print(f"LỖI  {e}")
    print(f"check: {len(errors)} lỗi, {len(warns)} cảnh báo · {len(works)} tác phẩm, {len(assets)} tài sản, "
          f"{len(pubs)} bài đăng, {len(data['metrics'])} ảnh chụp chỉ số")
    return 1 if errors else 0


# ---------------------------------------------------------------- lệnh ghi
def cmd_register(a):
    vc = vocab()
    if not CT_RE.match(a.work):
        raise MediaError("--work phải dạng CT-dddd (mã do studio registry.csv cấp, Media không tự cấp)")
    need(vc, "role", a.role)
    role = vc["role"][a.role]
    if role["versioned"] == "y" and not V_RE.match(a.version or ""):
        raise MediaError(f"vai trò {a.role} cần --version v<n>")
    works = merge_dupes(table("works"), "work_id")
    assets = merge_dupes(table("assets"), "asset_id")
    events = table("events")
    w = next((x for x in works if x["work_id"] == a.work), None)
    ts = now()
    if w is None:
        if not (a.kind and a.title):
            raise MediaError(f"{a.work} chưa có trong works.csv: cần --kind và --title")
        need(vc, "kind", a.kind)
        w = {"work_id": a.work, "kind": a.kind, "title": a.title, "created_at": ts, "created_by": a.by,
             "status": "", "current_version": a.version or ""}
        works.append(w)
    for c in ("kind", "title", "format", "pillar", "series", "product", "campaign", "tags", "source_ref",
              "ai_generated", "note"):
        val = getattr(a, c.replace("-", "_"), None)
        if val:
            if c == "kind":
                need(vc, "kind", val)
            w[c] = val

    if a.external:
        if a.role != "page" and not a.link:
            raise MediaError("--external cần --link")
        aid = a.asset_id or f"{a.work}_{a.version}_{a.role}" + (f"-{a.qualifier}" if a.qualifier else "")
        row = {"asset_id": aid, "work_id": a.work, "version": a.version or "", "role": a.role, "path": "",
               "bytes": "", "sha256": "", "mime": a.mime or "text/html", "created_at": ts, "created_by": a.by,
               "link": a.link, "storage": "external", "legacy": "n", "lang": a.lang or "", "tool": a.tool or "",
               "ai_label": a.ai_label or "", "note": a.note or ""}
        dest_rel = None
    else:
        src = Path(a.file)
        if not src.is_file():
            raise MediaError(f"không thấy file {src}")
        ext = src.suffix.lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        if ext not in role["extensions"].split("|"):
            raise MediaError(f"vai trò {a.role} nhận đuôi {role['extensions']}, file là .{ext}")
        size = src.stat().st_size
        if size > MAX_BYTES:
            raise MediaError(f"{src.name}: {size / 1e6:.1f} MB > 25 MB")
        name = asset_name(a.work, a.version, a.role, ext, a.qualifier or "", a.nn or "")
        if not NAME_RE.match(name):
            raise MediaError(f"tên {name} sai luật (qualifier chỉ gồm a-z0-9)")
        dest_rel = f"media/{a.work}/{name}"
        digest = sha256(src)
        existing = next((x for x in assets if x["asset_id"] == name), None)
        if existing and role["mutable"] != "y":
            if existing["sha256"] == digest:
                print(f"{name}: đã có, cùng nội dung — bỏ qua")
                return
            raise MediaError(f"{name} đã tồn tại và bất biến. Ra phiên bản mới (_v{vnum(a.version) + 1})")
        dup = next((x for x in assets if x.get("sha256") == digest and x["asset_id"] != name), None)
        if dup and role["mutable"] != "y":
            append("relations", [{"subject": f"{a.work}_{a.version}", "rel": "uses", "object": dup["asset_id"],
                                  "note": "trùng sha256 — không lưu bản thứ hai"}])
            print(f"trùng nội dung với {dup['asset_id']}: không chép, đã thêm relations uses")
            save("works", works)
            build(quiet=True)
            return
        dest = p(dest_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        info = probe(dest)
        if a.duration_s:
            info["duration_s"] = a.duration_s
        row = existing or {"asset_id": name, "work_id": a.work, "version": a.version or "", "role": a.role,
                           "path": dest_rel, "created_at": ts, "created_by": a.by, "storage": "repo", "legacy": "n",
                           "link": RAW + dest_rel}
        row.update({"bytes": str(size), "sha256": digest, "mime": mime_of(name),
                    "rendition": a.rendition or row.get("rendition", "") or (a.qualifier or ""),
                    "lang": a.lang or row.get("lang", ""), "tool": a.tool or row.get("tool", ""),
                    "ai_label": a.ai_label or row.get("ai_label", ""), "note": a.note or row.get("note", "")})
        for k in ("width", "height", "duration_s", "aspect"):
            if info.get(k):
                row[k] = str(info[k])
        if existing:
            assets = [row if x["asset_id"] == name else x for x in assets]
    if not any(x["asset_id"] == row["asset_id"] for x in assets):
        assets.append(row)

    # phiên bản mới → sự kiện created
    st = version_status(events)
    if a.version and (a.work, a.version) not in st:
        status = "testing" if a.test else (a.status or "pending_review")
        check_transition("", status)
        append("events", [{"at": ts, "work_id": a.work, "version": a.version, "event": "created", "from_status": "",
                           "to_status": status, "actor": a.by, "actor_type": a.actor_type, "ref": a.ref or "",
                           "note": a.note or ""}])
        if vnum(a.version) > vnum(w.get("current_version")):
            prev = w.get("current_version")
            w["current_version"] = a.version
            if a.supersede and prev and st.get((a.work, prev)) and TRANSITIONS.get(st[(a.work, prev)]) and \
                    "superseded" in TRANSITIONS[st[(a.work, prev)]]:
                append("events", [{"at": ts, "work_id": a.work, "version": prev, "event": "status",
                                   "from_status": st[(a.work, prev)], "to_status": "superseded", "actor": a.by,
                                   "actor_type": a.actor_type, "ref": a.ref or "", "note": f"thay bằng {a.version}"}])
                append("relations", [{"subject": f"{a.work}_{a.version}", "rel": "supersedes",
                                      "object": f"{a.work}_{prev}", "note": ""}])
    rels = []
    for spec in a.rel or []:
        rel, _, obj = spec.partition(":")
        need(vc, "rel", rel, "--rel")
        if not obj:
            raise MediaError("--rel dạng <rel>:<object>, ví dụ rendition_of:CT-0021_v1_still_01.png")
        rels.append({"subject": row["asset_id"], "rel": rel, "object": obj, "note": ""})
    if rels:
        append("relations", rels)
    save("works", works)
    save("assets", assets)
    build(quiet=True)
    print(f"{row['asset_id']} → {row['link']}")


def cmd_status(a):
    vc = vocab()
    need(vc, "status", a.to)
    works = {w["work_id"]: w for w in table("works")}
    if a.work not in works:
        raise MediaError(f"{a.work} chưa có trong works.csv")
    events = table("events")
    cur = version_status(events).get((a.work, a.version))
    if cur is None:
        raise MediaError(f"{a.work}_{a.version} chưa có trong Media")
    check_transition(cur, a.to)
    if a.to == "approved" and (a.actor_type != "human" or not a.ref):
        raise MediaError("approved cần --actor-type human và --ref <message_id của lệnh 'ok đăng'>")
    if a.to == "published" and not any(pb["work_id"] == a.work and pb["version"] == a.version
                                       for pb in table("publications")):
        raise MediaError("published cần ít nhất một bài đăng: ghi bằng media.py publish …")
    if a.to == "withdrawn" and not a.ref:
        raise MediaError("withdrawn chỉ khi người dùng quyết: cần --ref (tin nhắn quyết định)")
    append("events", [{"at": a.at or now(), "work_id": a.work, "version": a.version, "event": "status",
                       "from_status": cur, "to_status": a.to, "actor": a.actor, "actor_type": a.actor_type,
                       "ref": a.ref or "", "note": a.note or ""}])
    build(quiet=True)
    print(f"{a.work}_{a.version}: {cur} → {a.to}")


def cmd_publish(a):
    vc = vocab()
    need(vc, "platform", a.platform)
    need(vc, "pub_source", a.source, "--source")
    if a.matched_by:
        need(vc, "matched_by", a.matched_by)
    events = table("events")
    cur = version_status(events).get((a.work, a.version))
    if cur is None:
        raise MediaError(f"{a.work}_{a.version} chưa có trong Media")
    if cur in ("rejected", "superseded", "withdrawn", "archived", "testing"):
        print(f"CẢNH BÁO: {a.work}_{a.version} đang {cur} — vẫn ghi vì bài đã lên thật")
    for part in (a.account, a.post_id):
        if "|" in part:
            raise MediaError("account/post-id không được chứa '|'")
    pub_id = f"{a.platform}|{a.account}|{a.post_id}"
    pubs = table("publications")
    if any(pb["pub_id"] == pub_id for pb in pubs):
        print(f"{pub_id}: đã có — không ghi lại")
    else:
        append("publications", [{"pub_id": pub_id, "work_id": a.work, "version": a.version, "asset_id": a.asset or "",
                                 "platform": a.platform, "account": a.account, "url": a.url or "",
                                 "published_at": a.published_at, "published_by": a.by or "",
                                 "campaign": a.campaign or "", "utm_content": a.utm_content or "",
                                 "source": a.source, "matched_by": a.matched_by or "", "note": a.note or ""}])
        print(f"publication {pub_id}")
    if cur == "approved":
        append("events", [{"at": a.published_at, "work_id": a.work, "version": a.version, "event": "published",
                           "from_status": cur, "to_status": "published", "actor": a.by or a.source,
                           "actor_type": "human" if a.source in ("admin", "human") else "system",
                           "ref": pub_id, "note": ""}])
        print(f"{a.work}_{a.version}: approved → published")
    elif cur != "published":
        print(f"CẢNH BÁO: {a.work}_{a.version} đang {cur}, chưa ghi nhận duyệt — đã ghi bài đăng nhưng trạng thái "
              f"giữ {cur}. Khi có lệnh duyệt: `media.py status {a.work} {a.version} approved …` rồi chạy lại lệnh "
              f"publish này (không ghi trùng) để chuyển published.")
    build(quiet=True)


def metric_row(d, existing):
    r = {c: (d.get(c) or "").strip() for c in METRICS_COLS}
    for c in METRIC_NUMS:
        if r[c] and not re.fullmatch(r"\d+", r[c]):
            raise MediaError(f"{c}={r[c]!r}: phải là số nguyên ≥ 0, để trống nếu nền tảng không cung cấp")
    if not r["captured_at"]:
        r["captured_at"] = now()
    if not r["checkpoint"]:
        r["checkpoint"] = "adhoc" if any(m["pub_id"] == r["pub_id"] for m in existing) else "first"
    if not r["provided_fields"]:
        r["provided_fields"] = "|".join(c for c in METRIC_NUMS if r[c])
    r["origin"] = r["origin"] or "measured"
    return r


def cmd_metrics(a):
    vc = vocab()
    pubs = {pb["pub_id"] for pb in table("publications")}
    existing = all_metrics()
    keys = {(m["pub_id"], m["run_id"]) for m in existing}
    incoming = []
    if a.csv:
        with open(a.csv, newline="", encoding="utf-8") as f:
            src = list(csv.DictReader(f))
        extra = set(src[0].keys()) - set(METRICS_COLS) if src else set()
        if extra:
            raise MediaError(f"cột lạ {sorted(extra)} — chỉ nhận {' '.join(METRICS_COLS)}")
    else:
        src = [{c: getattr(a, c, None) for c in METRICS_COLS}]
    added, skipped = 0, 0
    for d in src:
        if a.run_id and not d.get("run_id"):
            d["run_id"] = a.run_id
        if a.source and not d.get("source"):
            d["source"] = a.source
        r = metric_row(d, existing + incoming)
        for c in METRICS_REQ:
            if not r[c]:
                raise MediaError(f"chỉ số thiếu {c}")
        if r["pub_id"] not in pubs:
            raise MediaError(f"{r['pub_id']} chưa có trong publications.csv — ghi `media.py publish` trước")
        need(vc, "checkpoint", r["checkpoint"])
        need(vc, "origin", r["origin"])
        if (r["pub_id"], r["run_id"]) in keys:
            skipped += 1
            continue
        keys.add((r["pub_id"], r["run_id"]))
        incoming.append(r)
        added += 1
    by_month = {}
    for r in incoming:
        by_month.setdefault(r["captured_at"][:7], []).append(r)
    for month, rows in by_month.items():
        append_rows(p(f"intel/metrics/{month}.csv"), METRICS_COLS, rows)
    build(quiet=True)
    print(f"metrics: thêm {added}, bỏ {skipped} dòng trùng pub_id|run_id")


def next_id(prefix, rows, key):
    day = datetime.now(TZ).strftime("%Y%m%d")
    n = sum(1 for r in rows if r[key].startswith(f"{prefix}-{day}-")) + 1
    return f"{prefix}-{day}-{n:03d}"


def cmd_review(a):
    vc = vocab()
    need(vc, "reviewer_type", a.reviewer_type)
    need(vc, "verdict", a.verdict)
    origin = a.origin or {"human": "human", "ai": "ai", "system": "computed"}[a.reviewer_type]
    need(vc, "origin", origin)
    rows = table("reviews")
    if a.supersedes:
        old = next((r for r in rows if r["review_id"] == a.supersedes), None)
        if not old:
            raise MediaError(f"không có {a.supersedes}")
        if old["origin"] == "human" and origin == "ai":
            raise MediaError("dòng AI không được thay dòng của người")
    if a.verdict in ("approve", "reject") and a.reviewer_type == "human" and not a.ref:
        raise MediaError("quyết định duyệt cần --ref (message_id)")
    rid = next_id("rv", rows, "review_id")
    append("reviews", [{"review_id": rid, "at": a.at or now(), "work_id": a.work, "version": a.version or "",
                        "asset_id": a.asset or "", "reviewer_type": a.reviewer_type, "reviewer_role": a.reviewer_role or "",
                        "rubric": a.rubric or "", "criterion": a.criterion or "", "verdict": a.verdict,
                        "independent": a.independent or "", "origin": origin, "source": a.source,
                        "method": a.method or "", "confidence": a.confidence or "", "human_check": a.human_check or "",
                        "ref": a.ref or "", "supersedes": a.supersedes or "", "note": a.note or ""}])
    print(rid)


def cmd_insight(a):
    vc = vocab()
    need(vc, "insight_type", a.insight_type)
    origin = a.origin or "ai"
    need(vc, "origin", origin)
    errs = []
    scan_text("summary", a.summary, errs)
    if HANDLE_RE.search(a.summary) or errs:
        raise MediaError("summary có dữ liệu cá nhân (tên, @, email, số điện thoại) — diễn đạt lại, không tên")
    rows = table("insights")
    if a.supersedes:
        old = next((r for r in rows if r["insight_id"] == a.supersedes), None)
        if not old:
            raise MediaError(f"không có {a.supersedes}")
        if old["origin"] == "human" and origin == "ai":
            raise MediaError("dòng AI không được thay dòng của người")
    iid = next_id("in", rows, "insight_id")
    append("insights", [{"insight_id": iid, "at": a.at or now(), "work_id": a.work, "version": a.version or "",
                         "pub_id": a.pub_id or "", "platform": a.platform or "", "insight_type": a.insight_type,
                         "topic": a.topic, "count": a.count or "", "share": a.share or "", "summary": a.summary,
                         "origin": origin, "source": a.source, "method": a.method or "",
                         "confidence": a.confidence or "", "human_check": a.human_check or "", "ref": a.ref or "",
                         "supersedes": a.supersedes or "", "note": a.note or ""}])
    print(iid)


# ---------------------------------------------------------------- git
GENERATED = {"index.csv", "intel/summary.csv"}


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise MediaError(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r


def cmd_commit(a):
    build(quiet=True)
    if check() != 0:
        raise MediaError("check còn lỗi — không commit")
    git("add", "-A", "media", "catalog", "intel", "index.csv")
    if not git("diff", "--cached", "--quiet", check=False).returncode:
        print("không có gì để commit")
    else:
        git("commit", "-q", "-m", a.message)
        print(git("log", "--oneline", "-1").stdout.strip())
    if not a.push:
        return
    for attempt, wait in enumerate((2, 4, 8, 16, 0)):
        r = git("pull", "--rebase", "-q", "origin", a.branch, check=False)
        while r.returncode:
            conflicted = set(git("diff", "--name-only", "--diff-filter=U", check=False).stdout.split())
            if not conflicted or not conflicted <= GENERATED:
                git("rebase", "--abort", check=False)
                raise MediaError(f"pull --rebase xung đột ngoài file sinh tự động: {sorted(conflicted) or r.stderr}")
            for f in conflicted:
                git("checkout", "--theirs", f, check=False)
            build(quiet=True)
            git("add", "-A", "catalog", "intel", "index.csv")
            r = subprocess.run(["git", "-C", str(ROOT), "-c", "core.editor=true", "rebase", "--continue"],
                               capture_output=True, text=True)
        build(quiet=True)
        if git("status", "--porcelain", "catalog", "intel", "index.csv").stdout.strip():
            git("add", "-A", "catalog", "intel", "index.csv")
            git("commit", "-q", "-m", "media: build lại file sinh tự động sau rebase")
        r = git("push", "-u", "origin", f"HEAD:{a.branch}", check=False)
        if not r.returncode:
            print(f"đã push {a.branch}")
            return
        if wait:
            time.sleep(wait)
    raise MediaError(f"push thất bại: {r.stderr.strip()}")


# ---------------------------------------------------------------- lệnh đọc
def cmd_find(a):
    works = table("works")
    pubs = table("publications")
    assets = table("assets")
    events = table("events")
    st = version_status(events)
    out = []
    for w in works:
        if a.kind and w["kind"] != a.kind:
            continue
        if a.status and w["status"] != a.status:
            continue
        if a.platform and not any(pb["work_id"] == w["work_id"] and pb["platform"] == a.platform for pb in pubs):
            continue
        for c in ("format", "pillar", "series", "campaign", "product"):
            if getattr(a, c) and w.get(c) != getattr(a, c):
                break
        else:
            if a.tag and a.tag not in (w.get("tags") or "").split("|"):
                continue
            out.append(w)
    if a.role:
        for w in out:
            for x in assets:
                if x["work_id"] == w["work_id"] and x["role"] == a.role:
                    print(f"{x['asset_id']}\t{st.get((x['work_id'], x['version']), '')}\t{x['link']}")
        return
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    for w in out:
        print(f"{w['work_id']}\t{w['current_version']}\t{w['status']}\t{w['kind']}\t{w['title']}")


def cmd_show(a):
    works = {w["work_id"]: w for w in table("works")}
    w = works.get(a.work)
    if not w:
        raise MediaError(f"{a.work} không có")
    ct = a.work
    st = version_status(table("events"))
    assets = [x for x in table("assets") if x["work_id"] == ct]
    pubs = [x for x in table("publications") if x["work_id"] == ct]
    pub_ids = {pb["pub_id"] for pb in pubs}
    ids = {x["asset_id"] for x in assets}
    rels = [r for r in table("relations")
            if r["subject"] in ids or r["object"] in ids or r["subject"].startswith(ct) or r["object"].startswith(ct)]
    if a.json:
        print(json.dumps({"work": w, "versions": {v: s for (c, v), s in st.items() if c == ct}, "assets": assets,
                          "relations": rels, "events": [e for e in table("events") if e["work_id"] == ct],
                          "publications": pubs,
                          "metrics": [m for m in all_metrics() if m["pub_id"] in pub_ids],
                          "summary": [s for s in table("summary") if s["work_id"] == ct],
                          "reviews": [r for r in table("reviews") if r["work_id"] == ct],
                          "insights": [r for r in table("insights") if r["work_id"] == ct]},
                         ensure_ascii=False, indent=1))
        return
    print(f"{ct} · {w['title']}\n  loại {w['kind']} · hiện hành {w['current_version']} · {w['status']}")
    meta = ", ".join(f"{c}={w[c]}" for c in ("format", "pillar", "series", "product", "campaign", "tags", "source_ref")
                     if w.get(c))
    if meta:
        print(f"  {meta}")
    print("Phiên bản:")
    for (c, v), s in sorted(st.items(), key=lambda kv: vnum(kv[0][1])):
        if c == ct:
            print(f"  {v}: {s}")
    print("Tài sản:")
    for x in assets:
        dim = f" {x['width']}×{x['height']}" if x.get("width") else ""
        dur = f" {x['duration_s']}s" if x.get("duration_s") else ""
        print(f"  {x['version'] or '-':4} {x['role']:8} {x['asset_id']}{dim}{dur}\n       {x['link']}")
    for title, rows, fmt in (
            ("Quan hệ", rels, lambda r: f"{r['subject']} {r['rel']} {r['object']}"),
            ("Sự kiện", [e for e in table("events") if e["work_id"] == ct],
             lambda e: f"{e['at']} {e['version']} {e['from_status'] or '∅'}→{e['to_status']} ({e['actor']})"),
            ("Bài đăng", pubs, lambda r: f"{r['platform']} {r['published_at']} {r['url']}"),
            ("Hiệu quả", [s for s in table("summary") if s["work_id"] == ct],
             lambda s: f"{s['platform']} {s['version']}: views {s['views']} · ER {s['er']} · {s['snapshots']} ảnh chụp"),
            ("Đánh giá", [r for r in table("reviews") if r["work_id"] == ct],
             lambda r: f"{r['at']} {r['reviewer_type']} {r['rubric']} {r['criterion']} → {r['verdict']}"),
            ("Phản hồi", [r for r in table("insights") if r["work_id"] == ct],
             lambda r: f"{r['insight_type']} {r['topic']}: {r['summary']}")):
        if rows:
            print(f"{title}:")
            for r in rows:
                print(f"  {fmt(r)}")


# ---------------------------------------------------------------- cli
def parser():
    ap = argparse.ArgumentParser(prog="media.py", description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="gốc repo derival-media (mặc định: MEDIA_ROOT hoặc thư mục cha của tools/)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    r = sp.add_parser("register", help="thêm file (hoặc link ngoài) cho một tác phẩm")
    r.add_argument("--work", required=True)
    r.add_argument("--version")
    r.add_argument("--role", required=True)
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--external", action="store_true", help="tài sản ngoài repo, cần --link")
    r.add_argument("--link")
    r.add_argument("--asset-id")
    r.add_argument("--mime")
    r.add_argument("--qualifier", help="ví dụ 1x1, jpg")
    r.add_argument("--nn", help="số thứ tự trang/ảnh: 01, 02…")
    r.add_argument("--by", required=True, help="người/agent/tiến trình ghi, ví dụ studio:archive_run")
    r.add_argument("--actor-type", default="system", choices=["human", "ai", "system"])
    r.add_argument("--test", action="store_true", help="bản thử: status testing")
    r.add_argument("--status", choices=["testing", "pending_review"])
    r.add_argument("--supersede", action="store_true", help="phiên bản hiện hành cũ chuyển superseded")
    r.add_argument("--ref", help="mã lượt / BS… / message_id")
    r.add_argument("--rel", action="append", help="<rel>:<object>, lặp được")
    for c in ("kind", "title", "format", "pillar", "series", "product", "campaign", "tags", "source-ref",
              "ai-generated", "note", "duration-s", "rendition", "lang", "tool", "ai-label"):
        r.add_argument(f"--{c}")
    r.set_defaults(fn=cmd_register)

    s = sp.add_parser("status", help="đổi trạng thái một phiên bản")
    s.add_argument("work")
    s.add_argument("version")
    s.add_argument("to")
    s.add_argument("--actor", required=True)
    s.add_argument("--actor-type", required=True, choices=["human", "ai", "system"])
    s.add_argument("--ref")
    s.add_argument("--note")
    s.add_argument("--at")
    s.set_defaults(fn=cmd_status)

    pb = sp.add_parser("publish", help="ghi một bài đăng thật")
    pb.add_argument("--work", required=True)
    pb.add_argument("--version", required=True)
    pb.add_argument("--platform", required=True)
    pb.add_argument("--account", required=True, help="account_id của trang/kênh Derival")
    pb.add_argument("--post-id", required=True)
    pb.add_argument("--published-at", required=True)
    pb.add_argument("--source", required=True, help="admin | social-intel | human")
    for c in ("url", "by", "asset", "campaign", "utm-content", "matched-by", "note"):
        pb.add_argument(f"--{c}")
    pb.set_defaults(fn=cmd_publish)

    m = sp.add_parser("metrics", help="thêm ảnh chụp chỉ số (một dòng hoặc --csv)")
    m.add_argument("--csv", help="file CSV đúng cột intel/metrics")
    for c in METRICS_COLS:
        m.add_argument(f"--{c.replace('_', '-')}", dest=c)
    m.set_defaults(fn=cmd_metrics)

    rv = sp.add_parser("review", help="thêm đánh giá người / AI / hệ thống")
    rv.add_argument("--work", required=True)
    rv.add_argument("--reviewer-type", required=True)
    rv.add_argument("--verdict", required=True)
    rv.add_argument("--source", required=True)
    for c in ("version", "asset", "reviewer-role", "rubric", "criterion", "independent", "origin", "method",
              "confidence", "human-check", "ref", "supersedes", "note", "at"):
        rv.add_argument(f"--{c}")
    rv.set_defaults(fn=cmd_review)

    i = sp.add_parser("insight", help="thêm tổng hợp phản hồi khán giả (không tên, không trích nguyên văn)")
    i.add_argument("--work", required=True)
    i.add_argument("--insight-type", required=True)
    i.add_argument("--topic", required=True)
    i.add_argument("--summary", required=True)
    i.add_argument("--source", required=True)
    for c in ("version", "pub-id", "platform", "count", "share", "origin", "method", "confidence", "human-check",
              "ref", "supersedes", "note", "at"):
        i.add_argument(f"--{c}")
    i.set_defaults(fn=cmd_insight)

    sp.add_parser("build", help="sinh lại works.status, index.csv, intel/summary.csv").set_defaults(
        fn=lambda a: build())
    sp.add_parser("check", help="kiểm toàn vẹn, luật tên, dữ liệu cá nhân, mốc GĐ0").set_defaults(fn=check)

    c = sp.add_parser("commit", help="build + check + git commit [+ pull --rebase + push]")
    c.add_argument("-m", "--message", required=True, help="theo luật: <CT>_<v>: <loại>")
    c.add_argument("--push", action="store_true")
    c.add_argument("--branch", default="main")
    c.set_defaults(fn=cmd_commit)

    f = sp.add_parser("find", help="tìm tác phẩm / tài sản")
    for c in ("kind", "status", "platform", "role", "format", "pillar", "series", "campaign", "product", "tag"):
        f.add_argument(f"--{c}")
    f.add_argument("--json", action="store_true")
    f.set_defaults(fn=cmd_find)

    sh = sp.add_parser("show", help="toàn bộ hồ sơ một tác phẩm")
    sh.add_argument("work")
    sh.add_argument("--json", action="store_true")
    sh.set_defaults(fn=cmd_show)
    return ap


def main(argv=None) -> int:
    global ROOT
    a = parser().parse_args(argv)
    ROOT = Path(a.root or os.environ.get("MEDIA_ROOT") or ROOT).resolve()
    try:
        rc = a.fn(a)
    except MediaError as e:
        print(f"LỖI  {e}", file=sys.stderr)
        return 2
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())

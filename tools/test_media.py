#!/usr/bin/env python3
"""Kiểm thử tools/media.py trên một repo giả trong thư mục tạm (không đụng repo thật).

Chạy: python3 tools/test_media.py
"""
import contextlib
import csv
import io
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import media  # noqa: E402

REAL_ROOT = HERE.parent


def png(path: Path, w=1080, h=1350, seed=0):
    raw = b"".join(b"\x00" + bytes([seed % 256]) * 3 * w for _ in range(2))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "repo"
        (self.root / "schema").mkdir(parents=True)
        shutil.copy(REAL_ROOT / "schema/vocabulary.csv", self.root / "schema/vocabulary.csv")
        self.src = self.tmp / "src"
        self.src.mkdir()
        self.run_ok("build")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cmd(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = media.main(["--root", str(self.root), *args])
        return rc, out.getvalue() + err.getvalue()

    def run_ok(self, *args):
        rc, out = self.run_cmd(*args)
        self.assertEqual(rc, 0, out)
        return out

    def rows(self, rel):
        with (self.root / rel).open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def register_still(self, ct="CT-0021", v="v1", nn="01", seed=1, *extra):
        f = self.src / f"s{seed}.png"
        png(f, seed=seed)
        return self.run_cmd("register", "--work", ct, "--version", v, "--role", "still", "--nn", nn, "--file", str(f),
                            "--by", "test", "--kind", "image", "--title", "Ảnh thử", *extra)

    # ------------------------------------------------------------
    def test_register_names_catalogs_and_checks(self):
        rc, out = self.register_still()
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.root / "media/CT-0021/CT-0021_v1_still_01.png").exists())
        a = self.rows("catalog/assets.csv")[0]
        self.assertEqual((a["width"], a["height"], a["aspect"]), ("1080", "1350", "4:5"))
        self.assertEqual(len(a["sha256"]), 64)
        self.assertEqual(self.rows("catalog/works.csv")[0]["status"], "pending_review")
        self.assertEqual(len(self.rows("index.csv")), 1)
        self.assertEqual(self.run_cmd("check")[0], 0)

    def test_testing_versions_stay_out_of_index(self):
        self.register_still("CT-0030", "v1", "01", 2, "--test")
        self.assertEqual(self.rows("catalog/works.csv")[0]["status"], "testing")
        self.assertEqual(self.rows("index.csv"), [])
        self.run_ok("status", "CT-0030", "v1", "pending_review", "--actor", "studio", "--actor-type", "system")
        self.assertEqual(len(self.rows("index.csv")), 1)

    def test_immutable_and_dedupe(self):
        self.register_still()
        f = self.src / "other.png"
        png(f, seed=9)
        rc, out = self.run_cmd("register", "--work", "CT-0021", "--version", "v1", "--role", "still", "--nn", "01",
                               "--file", str(f), "--by", "test")
        self.assertEqual(rc, 2)
        self.assertIn("bất biến", out)
        # cùng nội dung ở tác phẩm khác → không chép, chỉ thêm relation uses
        rc, out = self.register_still("CT-0022", "v1", "01", 1)
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.root / "media/CT-0022").exists())
        self.assertEqual(self.rows("catalog/relations.csv")[-1]["rel"], "uses")

    def test_lifecycle_rules(self):
        self.register_still()
        rc, out = self.run_cmd("status", "CT-0021", "v1", "published", "--actor", "x", "--actor-type", "system")
        self.assertEqual(rc, 2)
        rc, out = self.run_cmd("status", "CT-0021", "v1", "approved", "--actor", "bot", "--actor-type", "system")
        self.assertEqual(rc, 2, "approved phải là người + ref")
        self.run_ok("status", "CT-0021", "v1", "approved", "--actor", "CEO", "--actor-type", "human", "--ref", "msg-1")
        self.run_ok("publish", "--work", "CT-0021", "--version", "v1", "--platform", "facebook", "--account", "page1",
                    "--post-id", "p1", "--published-at", "2026-11-05T19:30:00+07:00", "--source", "admin")
        self.assertEqual(self.rows("catalog/works.csv")[0]["status"], "published")
        rc, out = self.run_cmd("status", "CT-0021", "v1", "testing", "--actor", "x", "--actor-type", "system")
        self.assertEqual(rc, 2)
        self.assertEqual(self.run_cmd("check")[0], 0)

    def test_publish_before_approval_keeps_status_and_warns(self):
        self.register_still()
        out = self.run_ok("publish", "--work", "CT-0021", "--version", "v1", "--platform", "tiktok", "--account",
                          "acc", "--post-id", "9", "--published-at", "2026-11-05T20:00:00+07:00", "--source",
                          "social-intel", "--matched-by", "code")
        self.assertIn("CẢNH BÁO", out)
        self.assertEqual(self.rows("catalog/works.csv")[0]["status"], "pending_review")
        rc, out = self.run_cmd("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("chưa ghi nhận duyệt", out)

    def test_metrics_summary_and_dedupe(self):
        self.register_still()
        self.run_ok("status", "CT-0021", "v1", "approved", "--actor", "CEO", "--actor-type", "human", "--ref", "m")
        self.run_ok("publish", "--work", "CT-0021", "--version", "v1", "--platform", "facebook", "--account", "pg",
                    "--post-id", "1", "--published-at", "2026-11-05T08:30:00+07:00", "--source", "admin")
        pid = "facebook|pg|1"
        self.run_ok("metrics", "--pub-id", pid, "--run-id", "r1", "--captured-at", "2026-11-06T12:00:00+07:00",
                    "--views", "100", "--likes", "5", "--comments", "3", "--source", "social-intel")
        self.run_ok("metrics", "--pub-id", pid, "--run-id", "r2", "--captured-at", "2026-11-07T12:00:00+07:00",
                    "--views", "250", "--likes", "10", "--source", "social-intel", "--checkpoint", "72h")
        out = self.run_ok("metrics", "--pub-id", pid, "--run-id", "r2", "--views", "999", "--source", "x")
        self.assertIn("bỏ 1", out)
        m = self.rows("intel/metrics/2026-11.csv")
        self.assertEqual([r["checkpoint"] for r in m], ["first", "72h"])
        self.assertEqual(m[0]["provided_fields"], "views|likes|comments")
        s = self.rows("intel/summary.csv")[0]
        self.assertEqual((s["views"], s["comments"], s["delta_views"], s["snapshots"]), ("250", "3", "150", "2"))
        self.assertEqual(s["er"], f"{13 / 250:.4f}")
        rc, out = self.run_cmd("metrics", "--pub-id", "facebook|pg|404", "--run-id", "r", "--source", "x")
        self.assertEqual(rc, 2)
        self.assertEqual(self.run_cmd("check")[0], 0)

    def test_ai_cannot_supersede_human_and_pii_blocked(self):
        self.register_still()
        rid = self.run_ok("review", "--work", "CT-0021", "--reviewer-type", "human", "--verdict", "note",
                          "--source", "telegram").strip()
        rc, out = self.run_cmd("review", "--work", "CT-0021", "--reviewer-type", "ai", "--verdict", "pass",
                               "--source", "ai_style_check", "--supersedes", rid)
        self.assertEqual(rc, 2)
        rc, out = self.run_cmd("insight", "--work", "CT-0021", "--insight-type", "question", "--topic", "phí",
                               "--summary", "Bạn @nguyenvana hỏi phí", "--source", "social-intel")
        self.assertEqual(rc, 2)
        self.run_ok("insight", "--work", "CT-0021", "--insight-type", "question", "--topic", "phí", "--count", "4",
                    "--summary", "Nhiều người hỏi phí dùng tín hiệu", "--source", "social-intel")
        # ghi tay một email vào note → check chặn
        p = self.root / "catalog/works.csv"
        p.write_text(p.read_text(encoding="utf-8").replace("Ảnh thử", "Ảnh thử a.b@gmail.com"), encoding="utf-8")
        rc, out = self.run_cmd("check")
        self.assertEqual(rc, 1)
        self.assertIn("email", out)

    def test_check_catches_tampering_and_untracked(self):
        self.register_still()
        f = self.root / "media/CT-0021/CT-0021_v1_still_01.png"
        f.write_bytes(f.read_bytes() + b"x")
        (self.root / "media/CT-0021/lac.png").write_bytes(b"x")
        rc, out = self.run_cmd("check")
        self.assertEqual(rc, 1)
        self.assertIn("bất biến đã bị sửa", out)
        self.assertIn("lac.png", out)

    def test_post_is_mutable(self):
        f = self.src / "post.md"
        f.write_text("# CT-0021 — Tiêu đề\n", encoding="utf-8")
        self.run_ok("register", "--work", "CT-0021", "--version", "v1", "--role", "post", "--file", str(f), "--by",
                    "t", "--kind", "image", "--title", "x")
        f.write_text("# CT-0021 — Tiêu đề mới\n", encoding="utf-8")
        self.run_ok("register", "--work", "CT-0021", "--version", "v1", "--role", "post", "--file", str(f), "--by", "t")
        a = self.rows("catalog/assets.csv")
        self.assertEqual(len(a), 1)
        self.assertEqual(self.rows("index.csv")[0]["sha256"], a[0]["sha256"][:16])
        self.assertEqual(self.run_cmd("check")[0], 0)

    def test_new_version_supersede_and_union_dupes(self):
        self.register_still("CT-0021", "v1", "01", 1, "--test")
        self.register_still("CT-0021", "v2", "01", 2, "--supersede")
        w = self.rows("catalog/works.csv")[0]
        self.assertEqual((w["current_version"], w["status"]), ("v2", "pending_review"))
        ev = self.rows("catalog/events.csv")
        self.assertIn("superseded", [e["to_status"] for e in ev])
        # mô phỏng merge=union: dòng works trùng → build gộp
        p = self.root / "catalog/works.csv"
        lines = p.read_text(encoding="utf-8").splitlines()
        p.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
        self.assertEqual(self.run_cmd("check")[0], 1)
        self.run_ok("build")
        self.assertEqual(self.run_cmd("check")[0], 0)

    def test_external_article(self):
        rc, out = self.run_cmd("register", "--work", "CT-0040", "--version", "v1", "--role", "page", "--external",
                               "--link", "https://derival.ai/bai-viet/x", "--by", "t", "--kind", "article",
                               "--title", "Bài website")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.rows("index.csv"), [])
        self.assertEqual(self.run_cmd("check")[0], 0)


class RealRepoTest(unittest.TestCase):
    def test_real_repo_check_is_clean(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = media.main(["--root", str(REAL_ROOT), "check"])
        self.assertEqual(rc, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()

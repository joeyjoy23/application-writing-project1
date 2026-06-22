"""Tests for ppt-work intermediate cleanup."""

from pathlib import Path

from scripts.ppt_work_cleanup import cleanup_ppt_work_dir, is_kept_pptx


def test_is_kept_pptx_recognizes_version_archives():
    assert is_kept_pptx("mental_health_classroom.pptx")
    assert is_kept_pptx("mental_health_classroom_V2.pptx")
    assert is_kept_pptx("mental_health_classroom_V3_v4.pptx")
    assert not is_kept_pptx("_verify_test.pptx")


def test_cleanup_removes_json_keeps_versioned_pptx(tmp_path: Path):
    (tmp_path / "stage3.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yingyongwen-source.md").write_text("# x", encoding="utf-8")
    (tmp_path / "_scratch.py").write_text("pass", encoding="utf-8")
    (tmp_path / "mental_health_classroom.pptx").write_bytes(b"pptx")
    (tmp_path / "mental_health_classroom_V1.pptx").write_bytes(b"pptx")
    (tmp_path / "_verify_test.pptx").write_bytes(b"pptx")

    removed = cleanup_ppt_work_dir(tmp_path)

    assert "stage3.json" in removed
    assert "yingyongwen-source.md" in removed
    assert "_scratch.py" in removed
    assert "_verify_test.pptx" in removed
    assert (tmp_path / "mental_health_classroom.pptx").is_file()
    assert (tmp_path / "mental_health_classroom_V1.pptx").is_file()
    assert not (tmp_path / "stage3.json").exists()

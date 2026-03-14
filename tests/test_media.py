import os
from core.media.filesystem import get_file_info, list_media_files


def test_get_file_info_existing():
    info = get_file_info("pyproject.toml")
    assert info["exists"]
    assert info["extension"] == "toml"
    assert info["size_bytes"] > 0


def test_get_file_info_nonexistent():
    info = get_file_info("nonexistent_file.xyz")
    assert not info["exists"]
    assert info["size_bytes"] == 0


def test_list_media_files_empty_dir(tmp_path):
    files = list_media_files(str(tmp_path))
    assert files == []


def test_list_media_files_with_files(tmp_path):
    (tmp_path / "video.mkv").write_text("fake")
    (tmp_path / "video.mp4").write_text("fake")
    (tmp_path / "readme.txt").write_text("not media")
    files = list_media_files(str(tmp_path))
    assert len(files) == 2
    extensions = {f["extension"] for f in files}
    assert extensions == {"mkv", "mp4"}

from __future__ import annotations

import base64
import hashlib
import os
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts.build_zip import build_zip, drop_console_scripts, main

if TYPE_CHECKING:
    from collections.abc import Iterator

FILES = {
    "weather_story_bot/__init__.py": "",
    "weather_story_bot/handler.py": "def lambda_handler(): ...\n",
    "httpx/_client.py": "class Client: ...\n",
    "httpx/py.typed": "",
}


def make_tree(root: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


def test_the_same_tree_with_different_mtimes_gives_identical_bytes(tmp_path: Path) -> None:
    first = make_tree(tmp_path / "first", FILES)
    second = make_tree(tmp_path / "second", FILES)
    for path in second.rglob("*"):
        os.utime(path, (1_000_000_000, 1_000_000_000))

    build_zip(first, tmp_path / "first.zip")
    build_zip(second, tmp_path / "second.zip")

    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()


def test_the_order_the_filesystem_lists_files_in_does_not_change_the_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forward = make_tree(tmp_path / "forward", FILES)
    backward = make_tree(tmp_path / "backward", dict(reversed(FILES.items())))
    real_rglob = Path.rglob

    def reversed_rglob(self: Path, pattern: str) -> Iterator[Path]:
        return iter(sorted(real_rglob(self, pattern), reverse=True))

    build_zip(forward, tmp_path / "forward.zip")
    monkeypatch.setattr(Path, "rglob", reversed_rglob)
    build_zip(backward, tmp_path / "backward.zip")

    assert (tmp_path / "forward.zip").read_bytes() == (tmp_path / "backward.zip").read_bytes()


def test_file_modes_do_not_change_the_bytes(tmp_path: Path) -> None:
    plain = make_tree(tmp_path / "plain", FILES)
    executable = make_tree(tmp_path / "executable", FILES)
    (executable / "weather_story_bot/handler.py").chmod(0o755)

    build_zip(plain, tmp_path / "plain.zip")
    build_zip(executable, tmp_path / "executable.zip")

    assert (tmp_path / "plain.zip").read_bytes() == (tmp_path / "executable.zip").read_bytes()


def test_entries_are_sorted_files_only_with_fixed_timestamps_permissions_and_no_compression(
    tmp_path: Path,
) -> None:
    tree = make_tree(tmp_path / "tree", dict(reversed(FILES.items())))
    (tree / "empty_dir").mkdir()

    build_zip(tree, tmp_path / "out.zip")

    with zipfile.ZipFile(tmp_path / "out.zip") as archive:
        infos = archive.infolist()
    assert [info.filename for info in infos] == sorted(FILES)
    assert {info.date_time for info in infos} == {(1980, 1, 1, 0, 0, 0)}
    assert {info.external_attr >> 16 for info in infos} == {0o100644}
    assert {info.compress_type for info in infos} == {zipfile.ZIP_STORED}


def test_the_zip_keeps_file_contents(tmp_path: Path) -> None:
    tree = make_tree(tmp_path / "tree", FILES)

    build_zip(tree, tmp_path / "out.zip")

    with zipfile.ZipFile(tmp_path / "out.zip") as archive:
        assert archive.testzip() is None
        assert archive.read("weather_story_bot/handler.py") == b"def lambda_handler(): ...\n"


def test_returns_the_base64_sha256_of_the_zip_bytes(tmp_path: Path) -> None:
    tree = make_tree(tmp_path / "tree", FILES)

    digest = build_zip(tree, tmp_path / "out.zip")

    expected = base64.b64encode(hashlib.sha256((tmp_path / "out.zip").read_bytes()).digest())
    assert digest == expected.decode()


def test_changed_content_changes_the_hash(tmp_path: Path) -> None:
    first = make_tree(tmp_path / "first", FILES)
    second = make_tree(tmp_path / "second", FILES | {"weather_story_bot/handler.py": "# new\n"})

    assert build_zip(first, tmp_path / "first.zip") != build_zip(second, tmp_path / "second.zip")


def test_main_prints_only_the_hash(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = make_tree(tmp_path / "tree", FILES)

    assert main([str(tree), str(tmp_path / "out.zip")]) == 0

    out = capsys.readouterr().out
    assert out == build_zip(tree, tmp_path / "again.zip") + "\n"


def test_a_symlinked_directory_is_refused_rather_than_dropped(tmp_path: Path) -> None:
    tree = make_tree(tmp_path / "tree", FILES)
    (tree / "linked").symlink_to(tree / "httpx", target_is_directory=True)

    with pytest.raises(ValueError, match="linked"):
        build_zip(tree, tmp_path / "out.zip")


def installed_tree(root: Path, interpreter: str) -> Path:
    """What `uv pip install --target` leaves: the package, a console script and its RECORD line.

    The script's first line names the interpreter that ran the install, and RECORD holds its hash.
    """
    script = f"#!{interpreter}\nfrom httpx import main\n"
    digest = base64.urlsafe_b64encode(hashlib.sha256(script.encode()).digest()).rstrip(b"=")
    record = (
        "httpx/_client.py,sha256=abc,17\n"
        f"bin/httpx,sha256={digest.decode()},{len(script)}\n"
        "httpx-0.28.1.dist-info/RECORD,,\n"
    )
    return make_tree(root, FILES | {"bin/httpx": script, "httpx-0.28.1.dist-info/RECORD": record})


def test_the_interpreter_that_installed_the_package_does_not_change_the_bytes(
    tmp_path: Path,
) -> None:
    laptop = installed_tree(tmp_path / "laptop", "/Users/someone/project/.venv/bin/python")
    runner = installed_tree(tmp_path / "runner", "/usr/bin/python")

    assert main([str(laptop), str(tmp_path / "laptop.zip")]) == 0
    assert main([str(runner), str(tmp_path / "runner.zip")]) == 0

    assert (tmp_path / "laptop.zip").read_bytes() == (tmp_path / "runner.zip").read_bytes()


def test_console_scripts_are_not_in_the_zip(tmp_path: Path) -> None:
    tree = installed_tree(tmp_path / "tree", "/usr/bin/python")

    main([str(tree), str(tmp_path / "out.zip")])

    with zipfile.ZipFile(tmp_path / "out.zip") as archive:
        names = archive.namelist()
    assert [name for name in names if name.startswith("bin/")] == []
    assert "weather_story_bot/handler.py" in names


def test_record_loses_the_lines_for_the_scripts_and_keeps_the_rest(tmp_path: Path) -> None:
    tree = installed_tree(tmp_path / "tree", "/usr/bin/python")

    drop_console_scripts(tree)

    record = (tree / "httpx-0.28.1.dist-info/RECORD").read_text()
    assert record == "httpx/_client.py,sha256=abc,17\nhttpx-0.28.1.dist-info/RECORD,,\n"
    assert not (tree / "bin").exists()


def test_names_that_only_start_like_bin_are_kept(tmp_path: Path) -> None:
    tree = make_tree(
        tmp_path / "tree",
        FILES
        | {
            "binary/tool.py": "x = 1\n",
            "binary-1.0.dist-info/RECORD": "binary/tool.py,sha256=x,6\nbin/run,sha256=y,3\n",
        },
    )

    drop_console_scripts(tree)

    assert (tree / "binary/tool.py").read_text() == "x = 1\n"
    assert (tree / "binary-1.0.dist-info/RECORD").read_text() == "binary/tool.py,sha256=x,6\n"


def test_a_tree_without_scripts_is_left_alone(tmp_path: Path) -> None:
    tree = make_tree(tmp_path / "tree", FILES | {"httpx-0.28.1.dist-info/RECORD": "a,,\n"})
    before = build_zip(tree, tmp_path / "before.zip")

    drop_console_scripts(tree)
    drop_console_scripts(tree)

    assert build_zip(tree, tmp_path / "after.zip") == before

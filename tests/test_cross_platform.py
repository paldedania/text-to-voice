from __future__ import annotations

import plistlib
import tomllib
from pathlib import Path

from scripts.render_launchd_service import render_service

PROJECT_ROOT = Path(__file__).parents[1]


def test_torch_uses_cuda_index_only_when_requested_on_supported_systems() -> None:
    config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    sources = config["tool"]["uv"]["sources"]["torch"]

    assert len(sources) == 2
    assert {source["index"] for source in sources} == {"pytorch-cpu", "pytorch-cu128"}
    by_extra = {source["extra"]: source for source in sources}
    assert by_extra["cpu"]["index"] == "pytorch-cpu"
    marker = by_extra["cuda"]["marker"]
    assert "Linux" in marker and "x86_64" in marker
    assert "Windows" in marker and "AMD64" in marker

    conflicts = config["tool"]["uv"]["conflicts"]
    assert {entry["extra"] for entry in conflicts[0]} == {"cpu", "cuda"}


def test_launchd_renderer_produces_valid_plist_for_paths_with_spaces(tmp_path: Path) -> None:
    template = (
        PROJECT_ROOT / "launchd/io.github.paldedania.text-to-voice.plist.in"
    ).read_text()
    project_dir = tmp_path / "Text & Voice"
    log_dir = tmp_path / "Logs & output"

    rendered = render_service(template, project_dir, log_dir)
    plist = plistlib.loads(rendered.encode())

    assert plist["WorkingDirectory"] == str(project_dir.resolve())
    assert plist["ProgramArguments"][0] == str(
        project_dir.resolve() / ".venv/bin/uvicorn"
    )
    assert plist["RunAtLoad"] is True
    assert "@PROJECT_DIR@" not in rendered


def test_windows_scripts_use_the_clone_location() -> None:
    runner = (PROJECT_ROOT / "run.ps1").read_text()
    installer = (PROJECT_ROOT / "install-service-windows.ps1").read_text()

    assert "$MyInvocation.MyCommand.Path" in runner
    assert ".venv\\Scripts\\uvicorn.exe" in runner
    assert "$MyInvocation.MyCommand.Path" in installer
    assert "New-ScheduledTaskAction" in installer


def test_readme_has_no_developer_machine_path() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()

    assert "/home/pal" not in readme
    assert all(system in readme for system in ("Windows", "macOS", "Linux"))

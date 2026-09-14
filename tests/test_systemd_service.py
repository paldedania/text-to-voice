from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.render_user_service import render_service, systemd_path

PROJECT_ROOT = Path(__file__).parents[1]


def test_service_renderer_quotes_paths_and_systemd_specifiers(tmp_path: Path) -> None:
    project_dir = tmp_path / 'clone with "quotes" and 100% local'
    template = (PROJECT_ROOT / "systemd/text-to-voice.service.in").read_text()

    rendered = render_service(template, project_dir)

    assert f"WorkingDirectory={systemd_path(str(project_dir.resolve()))}" in rendered
    assert "100%% local" in rendered
    assert "@PROJECT_DIR@" not in rendered
    assert "@UVICORN@" not in rendered
    assert "WantedBy=default.target" in rendered


def test_installer_enables_generated_user_service(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    command_log = tmp_path / "systemctl.log"
    systemctl = fake_bin / "systemctl"
    systemctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SERVICE_TEST_LOG"\n')
    systemctl.chmod(0o755)
    curl = fake_bin / "curl"
    curl.write_text("#!/bin/sh\nexit 0\n")
    curl.chmod(0o755)

    config_home = tmp_path / "config"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "SERVICE_TEST_LOG": str(command_log),
            "XDG_CONFIG_HOME": str(config_home),
        }
    )

    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "install-service.sh")],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    installed = config_home / "systemd/user/text-to-voice.service"
    assert installed.is_file()
    service = installed.read_text()
    assert f"WorkingDirectory={systemd_path(str(PROJECT_ROOT))}" in service
    calls = command_log.read_text()
    assert "--user daemon-reload" in calls
    assert "--user enable --now text-to-voice.service" in calls

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape


def render_service(template: str, project_dir: Path, log_dir: Path) -> str:
    resolved_project = project_dir.resolve()
    replacements = {
        "@PROJECT_DIR@": escape(str(resolved_project)),
        "@UVICORN@": escape(str(resolved_project / ".venv" / "bin" / "uvicorn")),
        "@LOG_DIR@": escape(str(log_dir.resolve())),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    if any(placeholder in rendered for placeholder in replacements):
        raise ValueError("The launchd template contains unresolved placeholders.")
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the Text to Voice LaunchAgent.")
    parser.add_argument("template", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("log_dir", type=Path)
    args = parser.parse_args()

    template = args.template.read_text(encoding="utf-8")
    rendered = render_service(template, args.project_dir, args.log_dir)
    args.destination.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()

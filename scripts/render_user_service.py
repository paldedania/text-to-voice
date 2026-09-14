from __future__ import annotations

import argparse
from pathlib import Path


def systemd_quote(value: str) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Systemd paths cannot contain null bytes or newlines.")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{escaped}"'


def systemd_path(value: str) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Systemd paths cannot contain null bytes or newlines.")

    escaped: list[str] = []
    for character in value:
        codepoint = ord(character)
        if character == "%":
            escaped.append("%%")
        elif character.isascii() and (character.isalnum() or character in "/._-"):
            escaped.append(character)
        elif codepoint <= 0xFF:
            escaped.append(f"\\x{codepoint:02x}")
        elif codepoint <= 0xFFFF:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            escaped.append(f"\\U{codepoint:08x}")
    return "".join(escaped)


def render_service(template: str, project_dir: Path) -> str:
    resolved = project_dir.resolve()
    replacements = {
        "@PROJECT_DIR@": systemd_path(str(resolved)),
        "@UVICORN@": systemd_quote(str(resolved / ".venv" / "bin" / "uvicorn")),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    if "@PROJECT_DIR@" in rendered or "@UVICORN@" in rendered:
        raise ValueError("The systemd service template contains unresolved placeholders.")
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the Text to Voice user service.")
    parser.add_argument("template", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()

    template = args.template.read_text(encoding="utf-8")
    rendered = render_service(template, args.project_dir)
    args.destination.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()

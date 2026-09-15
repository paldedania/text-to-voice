from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
from pathlib import Path


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def inspect_system() -> dict:
    nvidia_smi = shutil.which("nvidia-smi")
    gpu_information = next(
        iter(sorted(Path("/proc/driver/nvidia/gpus").glob("*/information"))),
        None,
    )
    gpu_name = _read(str(gpu_information)) if gpu_information else None
    nvidia = {
        "detected": gpu_name is not None,
        "ready": False,
        "name": "NVIDIA GPU" if gpu_name else "Not detected",
        "detail": "nvidia-smi is unavailable",
    }
    if gpu_name:
        for line in gpu_name.splitlines():
            if line.startswith("Model:"):
                nvidia["name"] = line.split(":", 1)[1].strip()
                break
    if nvidia_smi:
        try:
            result = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            nvidia["detail"] = "nvidia-smi timed out after 5 seconds"
        except OSError as error:
            nvidia["detail"] = f"nvidia-smi failed: {error}"
        else:
            fields = (
                [part.strip() for part in result.stdout.splitlines()[0].split(",")]
                if result.stdout.strip()
                else []
            )
            if result.returncode == 0 and len(fields) == 3:
                name, memory, driver = fields
                nvidia.update(
                    ready=True,
                    name=name,
                    detail=f"{memory} MiB VRAM, driver {driver}",
                )
            elif result.stderr.strip():
                nvidia["detail"] = result.stderr.strip().splitlines()[0]
            elif result.returncode == 0:
                nvidia["detail"] = "nvidia-smi returned an unexpected response"

    torch_state = {"installed": importlib.util.find_spec("torch") is not None, "cuda": False}
    if torch_state["installed"]:
        try:
            import torch

            torch_state["version"] = torch.__version__
            torch_state["cuda"] = torch.cuda.is_available()
        except Exception as error:
            torch_state["error"] = str(error)

    return {
        "computer": _read("/sys/class/dmi/id/product_version") or platform.machine(),
        "python": platform.python_version(),
        "nvidia": nvidia,
        "torch": torch_state,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "offline": True,
    }

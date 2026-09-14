from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from app.system import inspect_system  # noqa: E402


def main() -> int:
    result = inspect_system()
    print(json.dumps(result, indent=2))
    if not result["torch"]["installed"]:
        print("\nPyTorch is not installed. Follow the setup command in README.md.")
        return 2
    if result["nvidia"]["detected"] and not result["nvidia"]["ready"]:
        print("\nAn NVIDIA GPU was detected, but nvidia-smi is not ready. The app will use CPU.")
        return 1
    if not result["torch"]["cuda"]:
        print("\nCUDA is unavailable. Text to Voice will use the CPU.")
        return 0
    import torch

    architectures = torch.cuda.get_arch_list()
    print(f"\nCompiled architectures: {', '.join(architectures)}")
    capability = torch.cuda.get_device_capability()
    active_architecture = f"sm_{capability[0]}{capability[1]}"
    if active_architecture not in architectures:
        print(f"The installed PyTorch wheel does not include this GPU ({active_architecture}).")
        return 4
    try:
        probe = torch.ones(256, device="cuda").sum().item()
    except RuntimeError as error:
        print(f"CUDA was detected, but a test kernel failed: {error}")
        return 5
    print(f"CUDA inference is ready; the test kernel returned {probe:.0f}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

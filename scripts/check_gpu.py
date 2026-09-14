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
    if not result["nvidia"]["ready"]:
        print("\nNVIDIA userspace access is not ready. Fix nvidia-smi before GPU inference.")
        return 1
    if not result["torch"]["installed"]:
        print("\nThe GPU is visible, but PyTorch is not installed in this environment.")
        return 2
    if not result["torch"]["cuda"]:
        print("\nPyTorch is installed, but its CUDA runtime cannot use the GPU.")
        return 3
    import torch

    architectures = torch.cuda.get_arch_list()
    print(f"\nCompiled architectures: {', '.join(architectures)}")
    if "sm_120" not in architectures:
        print("The installed PyTorch wheel does not include RTX 50-series kernels (sm_120).")
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

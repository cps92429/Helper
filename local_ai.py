#!/usr/bin/env python3
"""
Run a local Codex-style code assistant using a Hugging Face model.
"""

from __future__ import annotations

import argparse
import platform
import sys
from typing import Literal

try:
    import torch
    from transformers import pipeline
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Dependencies missing. Install with: pip install -r requirements.txt"
    ) from exc


DEFAULT_MODEL = "bigcode/starcoder2-3b"


def system_summary() -> str:
    summary = [
        f"Python {sys.version.split()[0]}",
        f"Platform {platform.platform()}",
    ]
    if torch.cuda.is_available():
        summary.append(f"GPU {torch.cuda.get_device_name(0)}")
    else:
        summary.append("GPU none (CPU fallback)")
    return "; ".join(summary)


def build_pipeline(model_id: str, device_choice: Literal["auto", "cpu", "cuda"]):
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    device_map = "auto" if (device_choice == "auto" and torch.cuda.is_available()) else None
    pipeline_device = -1
    if device_choice == "cuda":
        if not torch.cuda.is_available():
            raise SystemExit("CUDA requested but no GPU detected.")
        pipeline_device = 0
    elif device_choice == "auto" and torch.cuda.is_available():
        pipeline_device = 0

    return pipeline(
        "text-generation",
        model=model_id,
        tokenizer=model_id,
        torch_dtype=torch_dtype,
        device_map=device_map,
        device=pipeline_device,
        trust_remote_code=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Codex-style runner.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model id")
    parser.add_argument("--prompt", required=True, help="Prompt text with your local context")
    parser.add_argument("--max-new-tokens", type=int, default=128, help="Tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--top-p", type=float, default=0.95, help="Nucleus sampling top-p")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default="auto", help="Execution device preference"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"System: {system_summary()}")
    print(f"Loading model: {args.model}")
    generator = build_pipeline(args.model, args.device)

    result = generator(
        args.prompt,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        pad_token_id=generator.tokenizer.eos_token_id,
        do_sample=args.temperature > 0,
    )
    print("\nResponse:\n")
    print(result[0]["generated_text"])


if __name__ == "__main__":
    main()

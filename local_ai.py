#!/usr/bin/env python3
"""
Run a local Codex-style code assistant using a Hugging Face model.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from typing import Literal

try:
    import torch
    from transformers import pipeline
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Dependencies missing. Install with: pip install -r requirements.txt"
    ) from exc


DEFAULT_MODEL = "bigcode/starcoder2-3b"
DEFAULT_FALLBACK_MODEL = "distilgpt2"


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


def build_pipeline_with_retries(
    model_id: str,
    device_choice: Literal["auto", "cpu", "cuda"],
    retries: int,
    retry_delay: float,
):
    attempts = retries + 1
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return build_pipeline(model_id, device_choice)
        except Exception as exc:  # pragma: no cover - runtime dependent
            last_exc = exc
            if attempt >= attempts:
                break
            print(
                f"Warning: loading '{model_id}' failed (attempt {attempt}/{attempts}). "
                f"Retrying in {retry_delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(retry_delay)

    raise RuntimeError(
        f"Failed to load model '{model_id}' after {attempts} attempt(s)."
    ) from last_exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Codex-style runner.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model id")
    parser.add_argument(
        "--fallback-model",
        default=DEFAULT_FALLBACK_MODEL,
        help=(
            "Fallback Hugging Face model id used when --model fails to load. "
            "Use 'none' to disable fallback."
        ),
    )
    parser.add_argument("--prompt", required=True, help="Prompt text with your local context")
    parser.add_argument("--max-new-tokens", type=int, default=128, help="Tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--top-p", type=float, default=0.95, help="Nucleus sampling top-p")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default="auto", help="Execution device preference"
    )
    parser.add_argument(
        "--load-retries",
        type=int,
        default=2,
        help="Retry count for model loading failures (default: 2).",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.5,
        help="Seconds to wait between model-load retries (default: 1.5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.load_retries < 0:
        raise SystemExit("--load-retries must be >= 0")
    if args.retry_delay < 0:
        raise SystemExit("--retry-delay must be >= 0")

    print(f"System: {system_summary()}")
    print(f"Loading model: {args.model}")
    fallback_model = None if args.fallback_model.strip().lower() == "none" else args.fallback_model.strip()

    try:
        generator = build_pipeline_with_retries(
            args.model,
            args.device,
            retries=args.load_retries,
            retry_delay=args.retry_delay,
        )
        active_model = args.model
    except Exception as primary_exc:  # pragma: no cover - runtime dependent
        if not fallback_model or fallback_model == args.model:
            raise SystemExit(
                f"Failed to load model '{args.model}' and no valid fallback is configured. Error: {primary_exc}"
            ) from primary_exc

        print(
            f"Warning: failed to load '{args.model}'. Falling back to '{fallback_model}'.",
            file=sys.stderr,
        )
        try:
            generator = build_pipeline_with_retries(
                fallback_model,
                args.device,
                retries=args.load_retries,
                retry_delay=args.retry_delay,
            )
            active_model = fallback_model
        except Exception as fallback_exc:  # pragma: no cover - runtime dependent
            raise SystemExit(
                "Failed to load both primary and fallback models. "
                f"Primary error: {primary_exc}; fallback error: {fallback_exc}"
            ) from fallback_exc

    if active_model != args.model:
        print(f"Using fallback model: {active_model}")

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

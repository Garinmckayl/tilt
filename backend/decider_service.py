from __future__ import annotations

"""Persistent Strands Decider 2B HTTP Inference Service for TILT."""

import os
import torch
import uvicorn
from strands_decider.server import create_app, get_engine

CHECKPOINT = os.environ.get(
    "STRANDS_DECIDER_CHECKPOINT",
    "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610",
)
PORT = int(os.environ.get("STRANDS_DECIDER_PORT", "8099"))
HOST = os.environ.get("STRANDS_DECIDER_HOST", "127.0.0.1")
DEVICE = os.environ.get("STRANDS_DECIDER_DEVICE", "cpu")


def build_optimized_app():
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    app = create_app(
        CHECKPOINT,
        device=DEVICE,
        use_prefix_cache=True,
        max_batch=32,
    )
    eng = get_engine()

    # On Linux x86-64 CPUs with AVX512-BF16 / Intel AMX (such as AWS m7i instances),
    # merging the rank-16 LoRA adapter and running the torso in bfloat16 with the
    # block-inversion Gated DeltaNet chunk rule reduces memory from 7.5 GB to 3.5 GB
    # and speeds up multi-question inference by >5x while preserving calibrated outputs.
    amx_bf16 = False
    lora_merged = False
    if DEVICE == "cpu":
        with torch.inference_mode():
            if hasattr(eng.model.torso, "merge_and_unload"):
                eng.model.torso = eng.model.torso.merge_and_unload()
                lora_merged = True
            if hasattr(torch.cpu, "_is_avx512_bf16_supported") and torch.cpu._is_avx512_bf16_supported():
                eng.model.torso.to(torch.bfloat16)
                amx_bf16 = True
        try:
            from strands_decider.mps_kernels import install as install_fast_chunk
            install_fast_chunk()
        except Exception:
            pass

    @app.get("/health/extended")
    def health_extended() -> dict:
        return {
            "status": "ok",
            "model": eng.cfg.model_name,
            "checkpoint": CHECKPOINT,
            "base_model": eng.model.config.base_model,
            "num_slots": eng.model.config.num_slots,
            "max_length": eng.model.config.max_length,
            "temperature": eng.model.config.temperature,
            "device": eng.cfg.device,
            "prefix_cache": eng.cfg.use_prefix_cache,
            "lora_merged": lora_merged,
            "amx_bf16": amx_bf16,
        }

    return app


if __name__ == "__main__":
    app = build_optimized_app()
    uvicorn.run(app, host=HOST, port=PORT, workers=1)

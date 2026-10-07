from app.config import Settings


def test_model_fallback_chain_deduplicates_nvidia():
    s = Settings(
        LLM_PROVIDER="nvidia",
        NVIDIA_MODEL_PRO="nv-pro",
        NVIDIA_MODEL_FAST="nv-fast",
        NVIDIA_MODEL_LITE="nv-lite",
    )
    assert s.model_fallback_chain == ["nv-pro", "nv-fast", "nv-lite"]


def test_model_fallback_chain_skips_duplicate_lite():
    s = Settings(
        LLM_PROVIDER="nvidia",
        NVIDIA_MODEL_PRO="nv-pro",
        NVIDIA_MODEL_FAST="nv-fast",
        NVIDIA_MODEL_LITE="nv-fast",
    )
    assert s.model_fallback_chain == ["nv-pro", "nv-fast"]


def test_role_fallback_starts_with_role_primary():
    s = Settings(
        LLM_PROVIDER="nvidia",
        NVIDIA_MODEL_PRO="nv-pro",
        NVIDIA_MODEL_FAST="nv-fast",
        NVIDIA_MODEL_LITE="nv-lite",
        NVIDIA_MODEL_VLM="nv-vlm",
    )
    assert s.role_fallback_chain("vlm")[0] == "nv-vlm"
    assert "nv-pro" not in s.role_fallback_chain("vlm")
    assert s.role_fallback_chain("fast")[0] == "nv-fast"

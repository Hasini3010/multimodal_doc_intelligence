"""Application configuration loaded from environment / .env."""



from functools import lru_cache

from pathlib import Path



from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict



_REPO_ROOT = Path(__file__).resolve().parents[2]





class Settings(BaseSettings):

    model_config = SettingsConfigDict(

        env_file=_REPO_ROOT / ".env",

        env_file_encoding="utf-8",

        extra="ignore",

    )



    llm_provider: str = Field(default="nvidia", alias="LLM_PROVIDER")



    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")

    nvidia_model_vlm: str = Field(

        default="meta/llama-3.2-90b-vision-instruct", alias="NVIDIA_MODEL_VLM"

    )

    nvidia_vlm_models: str = Field(

        default="", alias="NVIDIA_VLM_MODELS"

    )

    nvidia_model_pro: str = Field(

        default="nvidia/nemotron-3-super-120b-a12b", alias="NVIDIA_MODEL_PRO"

    )

    nvidia_model_fast: str = Field(

        default="nvidia/nemotron-3.5-lightning-30b-a3b", alias="NVIDIA_MODEL_FAST"

    )

    nvidia_model_lite: str = Field(

        default="nvidia/nemotron-3.5-lightning-30b-a3b", alias="NVIDIA_MODEL_LITE"

    )

    nvidia_rpm: int = Field(default=30, alias="NVIDIA_RPM")



    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    gemini_model_pro: str = Field(

        default="gemini-3.1-pro-preview", alias="GEMINI_MODEL_PRO"

    )

    gemini_model_fast: str = Field(

        default="gemini-3.8-flash", alias="GEMINI_MODEL_FAST"

    )

    gemini_model_lite: str = Field(

        default="gemini-3.5-flash-lite", alias="GEMINI_MODEL_LITE"

    )



    data_dir: Path = Field(default=_REPO_ROOT / "data", alias="DATA_DIR")

    index_dir: Path = Field(default=_REPO_ROOT / "data" / "index", alias="INDEX_DIR")

    llm_cache_dir: Path = Field(

        default=_REPO_ROOT / "data" / "cache" / "llm", alias="LLM_CACHE_DIR"

    )

    gemini_cache_dir: Path = Field(

        default=_REPO_ROOT / "data" / "cache" / "gemini", alias="GEMINI_CACHE_DIR"

    )



    api_host: str = Field(default="0.0.0.0", alias="API_HOST")

    api_port: int = Field(default=8000, alias="API_PORT")



    llm_max_retries: int = Field(default=4, alias="LLM_MAX_RETRIES")

    llm_backoff_base_sec: float = Field(default=2.0, alias="LLM_BACKOFF_BASE_SEC")

    llm_backoff_max_sec: float = Field(default=60.0, alias="LLM_BACKOFF_MAX_SEC")

    llm_cache_enabled: bool = Field(default=True, alias="LLM_CACHE_ENABLED")

    llm_strict_multimodal_routing: bool = Field(

        default=False, alias="LLM_STRICT_MULTIMODAL_ROUTING"

    )



    gemini_max_retries: int = Field(default=5, alias="GEMINI_MAX_RETRIES")

    gemini_backoff_base_sec: float = Field(default=1.0, alias="GEMINI_BACKOFF_BASE_SEC")

    gemini_backoff_max_sec: float = Field(default=60.0, alias="GEMINI_BACKOFF_MAX_SEC")

    gemini_cache_enabled: bool = Field(default=True, alias="GEMINI_CACHE_ENABLED")



    @property

    def repo_root(self) -> Path:

        return _REPO_ROOT



    def _active_model_ids(self) -> dict[str, str]:

        if self.llm_provider.lower().strip() == "gemini":

            return {

                "vlm": self.gemini_model_fast,

                "pro": self.gemini_model_pro,

                "fast": self.gemini_model_fast,

                "lite": self.gemini_model_lite,

            }

        return {

            "vlm": self.nvidia_model_vlm,

            "pro": self.nvidia_model_pro,

            "fast": self.nvidia_model_fast,

            "lite": self.nvidia_model_lite,

        }



    def model_role_map(self) -> dict[str, str]:

        return self._active_model_ids()



    def vlm_model_list(self) -> list[str]:

        """Vision-capable model IDs (NVIDIA: comma list or single VLM default)."""

        if self.llm_provider.lower().strip() == "gemini":

            roles = self._active_model_ids()

            return [roles["vlm"]]

        raw = self.nvidia_vlm_models.strip()

        if raw:

            return [m.strip() for m in raw.split(",") if m.strip()]

        return [self.nvidia_model_vlm]



    def vlm_fallback_chain(self) -> list[str]:

        """Fallback chain for image requests — vision models only (no text-only Nemotron)."""

        if self.llm_provider.lower().strip() == "gemini":

            roles = self._active_model_ids()

            order = [roles.get("vlm"), roles.get("fast"), roles.get("pro")]

        else:

            order = list(self.vlm_model_list())

        seen: set[str] = set()

        chain: list[str] = []

        for name in order:

            if name and name not in seen:

                seen.add(name)

                chain.append(name)

        return chain



    def role_fallback_chain(self, model_role: str) -> list[str]:

        """Primary model for role, then PRO -> FAST -> LITE fallbacks (deduped)."""

        if model_role == "vlm":

            return self.vlm_fallback_chain()

        roles = self._active_model_ids()

        primary = roles.get(model_role) or roles.get("fast") or ""

        order = [primary, roles.get("pro"), roles.get("fast"), roles.get("lite")]

        seen: set[str] = set()

        chain: list[str] = []

        for name in order:

            if name and name not in seen:

                seen.add(name)

                chain.append(name)

        return chain



    @property

    def model_fallback_chain(self) -> list[str]:

        """PRO -> FAST -> LITE (deduplicated). Used in tests / health."""

        return self.role_fallback_chain("pro")



    def resolve_path(self, path: Path) -> Path:

        if path.is_absolute():

            return path

        return self.repo_root / path





@lru_cache

def get_settings() -> Settings:

    return Settings()



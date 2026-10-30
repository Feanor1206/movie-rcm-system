from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ChatMessageItem(BaseModel):
    role: str = Field(default="user", description="user or assistant or system")
    content: Optional[str] = None
    text: Optional[str] = None


class MovieItem(BaseModel):
    id: str
    title: str
    year: int = 0
    rating: float = 8.0
    runtime: str = "N/A"
    genres: List[str] = []
    description: str = ""
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    videoUrl: Optional[str] = None
    matchPercentage: Optional[int] = None
    # Multi-level catalog hierarchy fields (series, episode, segment, scene)
    item_type: Optional[str] = Field(default="movie", description="series, episode, segment, scene, movie")
    series_id: Optional[str] = None
    season_id: Optional[str] = None
    episode_id: Optional[str] = None
    segment_id: Optional[str] = None
    episode_number: Optional[int] = None
    air_date: Optional[str] = None
    duration_ms: Optional[int] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    primary_media_asset_id: Optional[str] = None
    media_asset_id: Optional[str] = None
    aliases: Optional[List[str]] = None
    characters: Optional[List[str]] = None
    plot_facts: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    themes: Optional[List[str]] = None
    visual_summary: Optional[str] = None
    dialogue_summary: Optional[str] = None
    sound_events: Optional[List[str]] = None
    series_title: Optional[str] = None
    episode_title: Optional[str] = None
    comparative_attributes: Optional[Dict[str, Any]] = None
    diagnostics: Optional[Dict[str, Any]] = None


class IndexSyncRequest(BaseModel):
    catalog: Optional[Dict[str, Any]] = None
    generation: Optional[int] = None
    content_hash: Optional[str] = None
    reload_from_disk: Optional[bool] = False
    force_rebuild: Optional[bool] = False


class IndexSyncResponse(BaseModel):
    status: str
    message: str
    generation: Optional[int] = None
    item_counts: Dict[str, int] = {}
    content_hash: Optional[str] = None
    index_ready: bool = True




class ChatRequest(BaseModel):
    query: Optional[str] = Field(default=None, max_length=4000)
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=40)
    availableMovies: Optional[List[MovieItem]] = None
    sessionId: Optional[str] = Field(default="default", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if messages is None:
            return None
        normalized = []
        for message in messages:
            content = message.get("content") or message.get("text")
            if message.get("role") not in ("user", "assistant") or not isinstance(content, str) or len(content) > 4000:
                raise ValueError("Each message must have a user or assistant role and text of at most 4000 characters")
            normalized.append({"role": message["role"], "content": content})
        return normalized


class ChatResponse(BaseModel):
    text: str
    recommendedMovies: List[MovieItem] = []
    followUps: List[str] = []
    structuredIntent: Optional[Dict[str, Any]] = None
    pipelineStages: Optional[Dict[str, Any]] = None


class DiscoverRequest(BaseModel):
    query: str = Field(max_length=4000)
    sessionId: Optional[str] = Field(default="default", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    userId: Optional[str] = None
    availableMovies: Optional[List[MovieItem]] = None


class DiscoverResponse(BaseModel):
    structuredIntent: Dict[str, Any]
    explanation: str
    results: List[MovieItem] = []
    followUps: List[str] = []
    pipelineStages: Dict[str, Any] = {}


class RecommendRequest(BaseModel):
    genres: Optional[List[str]] = None
    likedMovieIds: Optional[List[str]] = None
    mood: Optional[str] = None
    limit: int = Field(default=4, ge=1, le=100)


class RecommendResponse(BaseModel):
    recommendedMovies: List[MovieItem]
    reasoning: str


class HealthResponse(BaseModel):
    status: str
    modelLoaded: bool
    modelNameOrPath: str = Field(
        description="Legacy model name/path: configured target when uninitialized, active base model when full PEFT, resolved GGUF when light/fallback, or 'phase23-deterministic-normalizer' when normalizer-only."
    )
    activeBaseModelName: Optional[str] = Field(
        default=None,
        description="Base model name actually loaded in runtime (or resolved GGUF filename). None when uninitialized or normalizer-only."
    )
    activeAdapterPath: Optional[str] = Field(
        default=None,
        description="Adapter path attached to the active base model. None if not full PEFT or in fallback."
    )
    fallbackModelPath: Optional[str] = Field(
        default=None,
        description="Configured fallback model path."
    )
    phase23ArtifactVerified: bool = False
    phase23AdapterLoaded: bool = False
    phase23AdapterPath: Optional[str] = None
    activeInferenceBackend: str = "uninitialized"
    device: str
    servingMode: str = "light"
    requestedDevice: str = "auto"
    actualDevice: str = "uninitialized"
    quantization: str = "none"
    degraded: bool = False
    loadError: Optional[str] = None


class ReadinessResponse(BaseModel):
    ready: bool
    status: str
    servingMode: str
    activeInferenceBackend: str
    phase23AdapterLoaded: bool
    degraded: bool
    loadError: Optional[str] = None
    message: str


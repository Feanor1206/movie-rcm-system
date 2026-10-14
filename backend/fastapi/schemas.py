from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    role: str = Field(default="user", description="user or assistant or system")
    content: Optional[str] = None
    text: Optional[str] = None


class MovieItem(BaseModel):
    id: str
    title: str
    year: int
    rating: float
    runtime: str
    genres: List[str]
    description: str
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    videoUrl: Optional[str] = None
    matchPercentage: Optional[int] = None


class ChatRequest(BaseModel):
    query: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    availableMovies: Optional[List[MovieItem]] = None
    sessionId: Optional[str] = "default"


class ChatResponse(BaseModel):
    text: str
    recommendedMovies: List[MovieItem] = []
    followUps: List[str] = []
    structuredIntent: Optional[Dict[str, Any]] = None
    pipelineStages: Optional[Dict[str, Any]] = None


class DiscoverRequest(BaseModel):
    query: str
    sessionId: Optional[str] = "default"
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
    limit: int = 4


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


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


class ChatRequest(BaseModel):
    query: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    availableMovies: Optional[List[MovieItem]] = None


class ChatResponse(BaseModel):
    text: str
    recommendedMovies: List[MovieItem] = []
    followUps: List[str] = []


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
    modelNameOrPath: str
    device: str


from typing import Literal, Any

from pydantic import BaseModel, EmailStr, Field


GameName = Literal[
    "memory_card",
    "sequence_memory",  # retained so existing saved rows remain readable
    "number_sequence",
    "sequence_recall",
    "stroop_test",
    "pattern_recognition",
    "reaction_time",
]


class GameResult(BaseModel):
    game_name: GameName
    score: float = Field(ge=0, le=100)
    accuracy: float = Field(ge=0, le=100)
    completion_time_seconds: float = Field(gt=0)
    errors: int = Field(ge=0)
    mode: Literal["easy", "medium", "hard"] | None = None
    level: int | None = Field(default=None, ge=1, le=1000)
    max_level: int | None = Field(default=None, ge=1, le=1000)


class SavedGameResult(BaseModel):
    id: int
    user_id: int
    game_name: GameName
    score: float
    accuracy: float
    completion_time_seconds: float
    errors: int
    mode: Literal["easy", "medium", "hard"] | None = None
    level: int | None = None
    max_level: int | None = None


class Recommendation(BaseModel):
    next_game: GameName
    reason: str


class LevelRecommendation(BaseModel):
    game_name: GameName
    recommended_mode: Literal["easy", "medium", "hard"]
    recommended_level: int
    reason: str
    previous_accuracy: float | None = None
    previous_score: float | None = None
    based_on_previous_result: bool
    recent_results_used: int = 0
    average_recent_accuracy: float | None = None
    average_recent_score: float | None = None
    accuracy_trend: float | None = None
    average_recent_errors: float | None = None
    average_recent_time_seconds: float | None = None
    confidence: Literal["low", "medium", "high"] = "low"


class SaveResultResponse(BaseModel):
    message: str
    result: SavedGameResult
    recommendation: Recommendation
    level_recommendation: LevelRecommendation


class ResultsResponse(BaseModel):
    user_id: int
    results: list[SavedGameResult]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    age: int = Field(ge=1, le=120)


class AgeUpdate(BaseModel):
    age: int = Field(ge=1, le=120)


class AptitudeLevels(BaseModel):
    memory: Literal["easy", "medium", "hard"]
    working_memory: Literal["easy", "medium", "hard"]
    pattern_recognition: Literal["easy", "medium", "hard"]
    attention: Literal["easy", "medium", "hard"]
    processing_speed: Literal["easy", "medium", "hard"]


class InitialAssessment(BaseModel):
    memory: int = Field(ge=0, le=100)
    working_memory: int = Field(ge=0, le=100)
    pattern_recognition: int = Field(ge=0, le=100)
    attention: int = Field(ge=0, le=100)
    processing_speed: int = Field(ge=0, le=100)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    age: int | None = None
    aptitude_levels: AptitudeLevels | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    age: int | None = None
    aptitude_levels: AptitudeLevels | None = None
    assessment_scores: InitialAssessment | None = None


# NEW: Save and resume game progress

class GameProgressSave(BaseModel):
    current_level: int = Field(ge=1, le=1000)
    completed_levels: list[int] = Field(default_factory=list)
    game_state: dict[str, Any] | None = None
    status: Literal["in_progress", "completed"] = "in_progress"

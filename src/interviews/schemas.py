import uuid
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class QuestionPublic(BaseModel):
    id: uuid.UUID
    topic: str
    text: str
    difficulty: str

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    topic: str
    questions_count: Optional[int] = Field(5, gt=0, lt=21)


class SessionPublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    topic: str
    status: str
    current_question_index: int
    created_at: datetime
    questions: List[QuestionPublic]

    class Config:
        from_attributes = True


class TopicStats(BaseModel):
    topic: str
    completed_sessions: int
    total_questions_answered: int
    average_score: float
    average_time_per_question_seconds: float
    total_time_spent_seconds: float


class OverallStats(BaseModel):
    total_completed_sessions: int
    total_unique_topics: int
    total_questions_answered: int
    overall_average_score: float
    overall_average_time_per_question_seconds: float


class StatsResponse(BaseModel):
    overall_summary: OverallStats
    by_topic: List[TopicStats]

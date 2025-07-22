import uuid
from pydantic import BaseModel
from datetime import datetime
from typing import List


class QuestionPublic(BaseModel):
    id: uuid.UUID
    topic: str
    text: str
    difficulty: str

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    topic: str


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

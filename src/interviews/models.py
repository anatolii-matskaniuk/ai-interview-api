import uuid
from sqlalchemy import (Column, String, DateTime, ForeignKey, Text, Float,
                        Integer, Enum, Table, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base

session_questions_association = Table(
    'session_questions', Base.metadata,
    Column('session_id', UUID(as_uuid=True), ForeignKey('interview_sessions.id'), primary_key=True),
    Column('question_id', UUID(as_uuid=True), ForeignKey('questions.id'), primary_key=True)
)


class Question(Base):
    __tablename__ = "questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String, index=True, nullable=False)
    text = Column(Text, nullable=False)
    difficulty = Column(String, default='medium')


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    status = Column(Enum(
        'generating',
        'active',
        'completed',
        'failed',
        name='session_status_enum',
    ), default='generating', nullable=False)
    current_question_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    user = relationship("src.auth.models.User")
    questions = relationship("Question", secondary=session_questions_association, lazy="selectin")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    user_answer_text = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("Question")

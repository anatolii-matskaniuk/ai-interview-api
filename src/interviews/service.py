import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from datetime import datetime, timezone

from src.interviews.models import InterviewSession, Answer
from src.auth.models import User
from src.tasks.evaluation import evaluate_answer_task
from src.tasks.generation import generate_questions_for_session


class InterviewService:
    async def create_session(
            self,
            db: AsyncSession,
            user: User,
            topic: str,
            questions_count: int,
    ) -> InterviewSession:
        new_session = InterviewSession(
            user_id=user.id,
            topic=topic,
            status='generating'
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        session_id_str = str(new_session.id)
        print(f"--- service.py: Session {session_id_str} created. Sending to Celery... ---")

        generate_questions_for_session.delay(session_id_str, questions_count)

        print(f"--- service.py: Task for session {session_id_str} is sent. ---")
        return new_session

    async def get_session_by_id(
            self,
            db: AsyncSession,
            session_id: uuid.UUID,
            user_id: uuid.UUID,
    ) -> InterviewSession:
        query = (
            select(InterviewSession)
            .where(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
            .options(selectinload(InterviewSession.questions))
        )
        result = await db.execute(query)
        session = result.scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        return session

    async def get_all_user_sessions(
            self,
            db: AsyncSession,
            user_id: uuid.UUID,
    ) -> list[InterviewSession]:
        query = (
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
            .options(selectinload(InterviewSession.questions))
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def submit_answer(
            self,
            db: AsyncSession,
            session: InterviewSession,
            question_id: uuid.UUID,
            answer_text: str,
    ) -> tuple[Answer, asyncio.Task]:
        new_answer = Answer(
            session_id=session.id,
            question_id=question_id,
            user_answer_text=answer_text,
            submitted_at=datetime.now(timezone.utc)
        )
        db.add(new_answer)
        session.current_question_index += 1
        await db.commit()
        await db.refresh(new_answer)
        await db.refresh(session)

        task = asyncio.create_task(
            evaluate_answer_task(
                question_text=new_answer.question.text,
                answer_text=new_answer.user_answer_text,
                answer_id=new_answer.id,
            )
        )

        return new_answer, task

    async def handle_timeout(
            self,
            db: AsyncSession,
            session: InterviewSession,
            question_id: uuid.UUID,
    ):
        timeout_answer = Answer(
            session_id=session.id,
            question_id=question_id,
            user_answer_text="Timeout",
            score=0.0,
            feedback="There is no more time :(",
            submitted_at=datetime.now(timezone.utc)
        )
        db.add(timeout_answer)
        session.current_question_index += 1
        await db.commit()

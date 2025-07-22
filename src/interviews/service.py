import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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

    async def get_user_stats(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        query = (
            select(
                InterviewSession.topic,
                func.count(func.distinct(Answer.session_id)).label("completed_sessions"),
                func.count(Answer.id).label("total_questions_answered"),
                func.avg(Answer.score).label("average_score"),
                func.sum(
                    func.extract('epoch', Answer.submitted_at - Answer.started_at)
                ).label("total_time_spent_seconds")
            )
            .join(Answer, Answer.session_id == InterviewSession.id)
            .where(
                InterviewSession.user_id == user_id,
                InterviewSession.status == 'completed',
                Answer.submitted_at.is_not(None),
                Answer.started_at.is_not(None)
            )
            .group_by(InterviewSession.topic)
        )

        result = await db.execute(query)
        topic_stats_raw = result.all()

        by_topic = []
        for row in topic_stats_raw:
            total_time = row.total_time_spent_seconds or 0
            total_questions = row.total_questions_answered or 1
            by_topic.append({
                "topic": row.topic,
                "completed_sessions": row.completed_sessions,
                "total_questions_answered": row.total_questions_answered,
                "average_score": round(row.average_score, 2) if row.average_score else 0.0,
                "total_time_spent_seconds": round(total_time, 2),
                "average_time_per_question_seconds": round(total_time / total_questions, 2)
            })

        total_completed = sum(s['completed_sessions'] for s in by_topic)
        total_answered = sum(s['total_questions_answered'] for s in by_topic)
        total_time_all = sum(s['total_time_spent_seconds'] for s in by_topic)

        total_score_sum = sum(s['average_score'] * s['total_questions_answered'] for s in by_topic)
        overall_avg_score = total_score_sum / total_answered if total_answered else 0.0

        overall_summary = {
            "total_completed_sessions": total_completed,
            "total_unique_topics": len(by_topic),
            "total_questions_answered": total_answered,
            "overall_average_score": round(overall_avg_score, 2),
            "overall_average_time_per_question_seconds": round(total_time_all / total_answered,
                                                               2) if total_answered else 0.0
        }

        return {"overall_summary": overall_summary, "by_topic": by_topic}

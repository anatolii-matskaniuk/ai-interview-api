import asyncio
import json
import uuid
from typing import List

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import func

from src.db.session import AsyncSessionFactory
from src.core.celery import celery_app
from src.core.config import settings
from src.interviews.models import InterviewSession, Question
from src.shared.connection_manager import manager
from src.shared.logger import logger

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


async def _get_questions(db: AsyncSession, topic: str, count: int) -> List[Question]:
    try:
        prompt = f"""
        Please generate {count} unique interview questions for a mid-level developer position
        on the topic of "{topic}". The questions should be practical and thought-provoking.
        Provide the output strictly in a JSON format with a single key "questions"
        which contains an array of strings.
        """
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        if texts := data.get("questions"):
            if isinstance(texts, list):
                new_questions = [Question(topic=topic, text=text) for text in texts]
                db.add_all(new_questions)
                return new_questions
    except Exception as e:
        logger.error("Error generating questions from OpenAI: %s", e, exc_info=True)

    logger.warning("OpenAI failed, using fallback.")
    result = await db.execute(
        select(Question).filter(Question.topic == topic).order_by(func.random()).limit(count)
    )
    fallback_questions = result.scalars().all()
    return list(fallback_questions) if len(fallback_questions) >= count else []


@celery_app.task(name="generate_questions_for_session")
def generate_questions_for_session(session_id: str, questions_count: int):
    async def _run_logic():
        try:
            async with AsyncSessionFactory() as db:
                session = await db.get(InterviewSession, uuid.UUID(session_id))
                if not session:
                    logger.warning("SESSION TASK [%s]: Session not found", session_id)
                    return

                final_questions = await _get_questions(db, session.topic, questions_count)

                if final_questions:
                    session.questions.extend(final_questions)
                    session.status = 'active'
                    logger.info("SESSION TASK [%s]: Status changed to 'active'.", session_id)
                else:
                    session.status = 'failed'
                    logger.error("SESSION TASK [%s]: "
                                 "Questions not found. Status 'failed'.", session_id)
                    await manager.send_personal_message(
                        {"type": "session_failed", "reason": "Could not prepare questions."},
                        session.id,
                    )

                await db.commit()
        except Exception as e:
            logger.critical(
                "SESSION TASK CRITICAL ERROR [%s]: %s",
                session_id,
                str(e),
                exc_info=True
            )
            raise

    asyncio.run(_run_logic())

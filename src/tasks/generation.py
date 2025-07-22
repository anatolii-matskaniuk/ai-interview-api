import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List, AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import func

from src.core.celery import celery_app
from src.core.config import settings
from src.interviews.models import InterviewSession, Question
from src.shared.connection_manager import manager

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


@asynccontextmanager
async def get_task_db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.DATABASE_URL)
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
    )
    async with factory() as session:
        yield session
    await engine.dispose()


class QuestionGenerationService:
    async def generate_questions(self, topic: str, count: int) -> Optional[List[str]]:
        prompt = f"""
        Please generate {count} unique interview questions for a mid-level developer position
        on the topic of "{topic}". The questions should be practical and thought-provoking.

        Provide the output strictly in a JSON format with a single key "questions"
        which contains an array of strings.
        """
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content
            questions_data = json.loads(result_text)

            if "questions" in questions_data and isinstance(questions_data["questions"], list):
                return questions_data["questions"]
            else:
                print("AI returned invalid format for questions.")
                return None
        except Exception as e:
            print(f"Error generating questions from OpenAI: {e}")
            return None


question_generator = QuestionGenerationService()


async def get_fallback_questions(
        db: AsyncSession,
        topic: str,
        questions_count: int,
) -> list[Question]:
    questions_query = (
        select(Question)
        .filter(Question.topic == topic)
        .order_by(func.random())
        .limit(questions_count)
    )
    result = await db.execute(questions_query)
    questions = result.scalars().all()
    if len(questions) < questions_count:
        return []
    return list(questions)


@celery_app.task(name="generate_questions_for_session")
def generate_questions_for_session(session_id: str, questions_count: int):
    async def _run_async_logic():
        try:
            async with get_task_db_session() as db:
                session = await db.get(InterviewSession, uuid.UUID(session_id))
                if not session:
                    print(f"--- SESSION TASK [{session_id}]: Session not found")
                    return

                generated_texts = await question_generator.generate_questions(
                    topic=session.topic,
                    count=questions_count,
                )

                final_questions = []
                if generated_texts:
                    final_questions = [
                        Question(topic=session.topic, text=text) for text in generated_texts
                    ]
                    db.add_all(final_questions)
                else:
                    print(f"--- SESSION TASK [{session_id}]: "
                          f"No results from OpenAI, using fallback.")
                    final_questions = await get_fallback_questions(
                        db,
                        session.topic,
                        questions_count,
                    )

                if not final_questions:
                    print(f"--- SESSION TASK [{session_id}]: "
                          f"Questions were not found. Status 'failed'.")
                    session.status = 'failed'
                    await manager.send_personal_message(
                        {"type": "session_failed", "reason": "Could not prepare questions."},
                        session.id,
                    )
                else:
                    session.questions.extend(final_questions)
                    session.status = 'active'
                    print(f"--- SYNC TASK [{session_id}]: Status changed to 'active'.")

                await db.commit()
        except Exception as e:
            print(f"--- !!! SESSION TASK CRITICAL ERROR [{session_id}] !!! ---\n{repr(e)}\n")
            raise

    asyncio.run(_run_async_logic())

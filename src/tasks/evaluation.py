import uuid
import json
from openai import AsyncOpenAI

from src.core.config import settings
from src.db.session import AsyncSessionFactory
from src.interviews.models import Answer
from src.shared.connection_manager import manager
from src.shared.logger import logger

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


async def evaluate_answer_task(
    question_text: str, answer_text: str, answer_id: uuid.UUID, session_id: uuid.UUID
):
    try:
        prompt = f"""
            You are an expert technical interviewer. Evaluate a candidate's answer.
            The question was: "{question_text}"
            The candidate's answer is: "{answer_text}"

            Provide your evaluation strictly in a JSON format with two keys:
            - "score": A numerical score from 0 to 10.
            - "feedback": A short, constructive hint for improvement in English.
            """
        score = 0
        feedback = "No evaluation."

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content
            data = json.loads(result)
            score = data.get("score")
            feedback = data.get("feedback")
        except Exception as e:
            logger.error("EVAL ERROR [OpenAI]: %s", e, exc_info=True)
            feedback = "Error during evaluation."

        question_id = None
        async with AsyncSessionFactory() as db:
            answer = await db.get(Answer, answer_id)
            if answer:
                answer.score = score
                answer.feedback = feedback
                question_id = str(answer.question_id)
                await db.commit()

        if question_id:
            await manager.send_personal_message({
                "type": "evaluation_result",
                "data": {
                    "question_id": question_id,
                    "score": score,
                    "feedback": feedback
                }
            }, session_id)

    except Exception as e:
        logger.error("EVAL TASK ERROR: %s", answer_id, e, exc_info=True)

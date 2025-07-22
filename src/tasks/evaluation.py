import uuid
import json
from openai import AsyncOpenAI

from src.core.config import settings
from src.db.session import AsyncSessionFactory
from src.interviews.models import Answer

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


async def evaluate_answer_task(question_text: str, answer_text: str, answer_id: uuid.UUID):
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
            print(f"[EVAL ERROR] [OpenAI]: {e}")
            feedback = "Error during evaluation."

        async with AsyncSessionFactory() as db:
            answer = await db.get(Answer, answer_id)
            if answer:
                answer.score = score
                answer.feedback = feedback
                await db.commit()

    except Exception as e:
        print(f"[EVAL ERROR] [{answer_id}]: {e}")

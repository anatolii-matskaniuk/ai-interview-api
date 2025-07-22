import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import jwt, JWTError

from src.auth.models import User
from src.auth.service import TokenService, AuthService
from src.core.config import settings
from src.db.session import AsyncSessionFactory
from src.shared.connection_manager import manager
from src.interviews.service import InterviewService

router = APIRouter()
interview_service = InterviewService()
auth_service = AuthService()
token_service = TokenService()
timeout = settings.WEBSOCKET_ANSWER_TIMEOUT_SECONDS


async def get_user_from_token(token: str) -> User | None:
    try:
        async with AsyncSessionFactory() as db:
            if await token_service.is_token_blacklisted(token):
                return None
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                return None
            user = await auth_service.get_by_id(db, user_id=uuid.UUID(user_id))
            if user and user.is_active:
                return user
    except JWTError:
        return None
    return None


@router.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: uuid.UUID):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, session_id)
    print(f"--- WS [{session_id}]: WebSocket connected for user {user.id}.")

    try:
        async with AsyncSessionFactory() as db:
            session = await interview_service.get_session_by_id(db, session_id, user.id)

            while session.status == 'generating':
                print(f"--- WS [{session_id}]: Session is generating, waiting 3 seconds...")
                await asyncio.sleep(3)
                session = await interview_service.get_session_by_id(db, session_id, user.id)

            print(f"--- WS [{session_id}]: "
                  f"Fetched session status: {session.status}")
            print(f"--- WS [{session_id}]: "
                  f"Number of questions found: {len(session.questions)}")
            print(f"--- WS [{session_id}]: "
                  f"Current question index: {session.current_question_index}")

            if session.status != 'active':
                await manager.send_personal_message(
                    {
                        "type": "session_error",
                        "data": {"message": "Could not prepare the interview session."},
                    },
                    session_id
                )
                return
            stats = {
                "total_questions": len(session.questions),
                "answered": 0,
                "total_score": 0.0,
                "total_duration": 0.0,
            }
            print(f"--- WS [{session_id}]: Session is active. Starting interview loop.")
            while session.current_question_index < len(session.questions):
                question_index = session.current_question_index
                current_question = session.questions[question_index]

                await manager.send_personal_message({
                    "type": "question",
                    "data": {
                        "question_id": str(current_question.id),
                        "text": current_question.text,
                        "time_limit_seconds": settings.WEBSOCKET_ANSWER_TIMEOUT_SECONDS
                    }
                }, session_id)

                try:
                    answer_data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=float(settings.WEBSOCKET_ANSWER_TIMEOUT_SECONDS)
                    )
                    if answer_data.get("type") == "answer":
                        answer, eval_task = await interview_service.submit_answer(
                            db,
                            session,
                            current_question.id,
                            answer_data.get("data", {}).get("answer_text"),
                        )
                        await eval_task
                        await db.refresh(answer)
                        if answer.started_at and answer.submitted_at:
                            duration = (answer.submitted_at - answer.started_at).total_seconds()
                        else:
                            duration = 0.0

                        if answer.score is not None:
                            stats["answered"] += 1
                            stats["total_score"] += answer.score
                            stats["total_duration"] += duration
                        await manager.send_personal_message({
                            "type": "evaluation_result",
                            "data": {
                                "question_id": str(current_question.id),
                                "score": answer.score,
                                "feedback": answer.feedback,
                            }
                        }, session_id)
                except asyncio.TimeoutError:
                    await interview_service.handle_timeout(db, session, current_question.id)
                    await manager.send_personal_message(
                        {"type": "timeout", "data": {"question_id": str(current_question.id)}},
                        session_id,
                    )

                await db.refresh(session)

            average_score = round(
                stats["total_score"] / stats["answered"],
                2,
            ) if stats["answered"] else 0.0
            average_time = round(
                stats["total_duration"] / stats["answered"],
                2,
            ) if stats["answered"] else 0.0

            await manager.send_personal_message({
                "type": "session_summary",
                "data": {
                    "total_questions": stats["total_questions"],
                    "average_score": average_score,
                    "total_time_seconds": round(stats["total_duration"], 2),
                    "average_time_seconds": average_time
                }
            }, session_id)
            session.status = 'completed'
            await db.commit()
            await manager.send_personal_message({"type": "session_completed"}, session_id)

    except WebSocketDisconnect:
        print(f"--- WS [{session_id}]: WebSocket disconnected by client.")
    except Exception as e:
        print(f"--- WS [{session_id}]: An unexpected error occurred: {repr(e)}")
    finally:
        manager.disconnect(session_id)
        print(f"--- WS [{session_id}]: Connection closed and cleaned up.")

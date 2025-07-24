import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.service import TokenService, AuthService
from src.core.config import settings
from src.db.session import AsyncSessionFactory
from src.interviews.models import InterviewSession
from src.shared.connection_manager import manager
from src.interviews.service import InterviewService
from src.shared.logger import logger

router = APIRouter()
interview_service = InterviewService()
auth_service = AuthService()
token_service = TokenService()


async def _handle_authentication(websocket: WebSocket) -> User | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    try:
        if await token_service.is_token_blacklisted(token):
            return None
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        async with AsyncSessionFactory() as db:
            user = await auth_service.get_by_id(db, user_id=uuid.UUID(user_id))
            if user and user.is_active:
                return user
    except JWTError:
        return None
    return None


async def _wait_for_session_ready(
        db: AsyncSession, websocket: WebSocket, session_id: uuid.UUID, user_id: uuid.UUID
) -> InterviewSession | None:
    session = await interview_service.get_session_by_id(db, session_id, user_id)
    if session.status == 'generating':
        message = await websocket.receive_json()
        if message.get("type") != "session_ready":
            logger.warning("WS [%s]: "
                           "Failed to prepare session or received unexpected message.", session_id)
            return None
    await db.refresh(session)
    if session.status != 'active':
        await manager.send_personal_message(
            {
                "type": "session_error",
                "data": {"message": f"Session status is '{session.status}', not 'active'."}
            },
            session_id
        )
        return None
    return session


async def _run_interview_loop(db: AsyncSession, websocket: WebSocket, session: InterviewSession):
    while session.current_question_index < len(session.questions):
        current_question = session.questions[session.current_question_index]
        await manager.send_personal_message({
            "type": "question",
            "data": {
                "question_id": str(current_question.id),
                "text": current_question.text,
                "time_limit_seconds": settings.WEBSOCKET_ANSWER_TIMEOUT_SECONDS
            }
        }, session.id)

        try:
            answer_data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=float(settings.WEBSOCKET_ANSWER_TIMEOUT_SECONDS)
            )
            if answer_data.get("type") == "answer":
                is_last_question = session.current_question_index == len(session.questions) - 1

                answer, eval_task = await interview_service.submit_answer(
                    db, session, current_question.id, answer_data.get("data", {}).get("answer_text")
                )

                if is_last_question:
                    logger.info("WS [%s]: Last question. Waiting for evaluation...", session.id)
                    await eval_task

        except asyncio.TimeoutError:
            await interview_service.handle_timeout(db, session, current_question.id)
            await manager.send_personal_message(
                {"type": "timeout", "data": {"question_id": str(current_question.id)}}, session.id
            )

        await db.refresh(session)


@router.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: uuid.UUID):
    user = await _handle_authentication(websocket)
    if not user:
        return

    await manager.connect(websocket, session_id)
    logger.info("WS [%s]: WebSocket connected for user %s.", session_id, user.id)

    try:
        async with AsyncSessionFactory() as db:
            session = await _wait_for_session_ready(db, websocket, session_id, user.id)
            if not session:
                return

            await _run_interview_loop(db, websocket, session)

            summary_data = await interview_service.calculate_session_summary(db, session.id)

            await manager.send_personal_message({
                "type": "session_summary",
                "data": {
                    "total_questions": len(session.questions),
                    "answered_questions": summary_data["answered_questions"],
                    "average_score": summary_data["average_score"],
                    "total_time_seconds": summary_data["total_time_seconds"],
                    "average_time_seconds": summary_data["average_time_seconds"]
                }
            }, session.id)

            session.status = 'completed'
            await db.commit()

            await manager.send_personal_message({"type": "session_completed"}, session.id)

    except WebSocketDisconnect:
        logger.info("WS [%s]: WebSocket disconnected by client.", session_id)
    except Exception as e:
        logger.error("WS [%s]: An unexpected error occurred: %s", session_id, str(e), exc_info=True)
    finally:
        manager.disconnect(session_id)
        logger.info("WS [%s]: Connection closed and cleaned up.", session_id)

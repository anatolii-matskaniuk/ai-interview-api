import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.db.session import get_db
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.interviews.schemas import SessionCreate, SessionPublic
from src.interviews.service import InterviewService

router = APIRouter()
interview_service = InterviewService()


@router.post("/", response_model=SessionPublic, status_code=status.HTTP_202_ACCEPTED)
async def create_new_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await interview_service.create_session(
        db=db,
        user=current_user,
        topic=session_data.topic,
        questions_count=session_data.questions_count,
    )


@router.get("/", response_model=List[SessionPublic])
async def read_user_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await interview_service.get_all_user_sessions(db=db, user_id=current_user.id)


@router.get("/{session_id}", response_model=SessionPublic)
async def read_single_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await interview_service.get_session_by_id(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )

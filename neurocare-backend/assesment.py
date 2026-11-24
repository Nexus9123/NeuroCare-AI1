"""Assessment score endpoints and persistence helpers."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models import User as UserModel
from schemas import InitialAssessment


def create_assessment_router(get_current_user: Callable[..., UserModel]) -> APIRouter:
    """Build the assessment router with the application's auth dependency."""
    router = APIRouter(prefix="/assessment", tags=["Assessment"])

    @router.get("/initial")
    def get_initial_assessment(
        current_user: UserModel = Depends(get_current_user),
    ):
        return {"assessment_scores": current_user.assessment_scores}

    @router.post("/initial")
    def save_initial_assessment(
        scores: InitialAssessment,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
    ):
        current_user.assessment_scores = scores.model_dump()
        try:
            db.commit()
            db.refresh(current_user)
        except SQLAlchemyError as error:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Could not save the assessment results.",
            ) from error
        return {"assessment_scores": current_user.assessment_scores}

    return router

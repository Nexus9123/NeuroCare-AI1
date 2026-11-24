
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from assesment import create_assessment_router
from database import Base, engine, get_db
from models import (
    GameResult as GameResultModel,
    User as UserModel,
    GameProgress as GameProgressModel,
)
from recommendation import recommend_game, recommend_level
from schemas import (
    GameResult,
    GameName,
    GameProgressSave,
    AgeUpdate,
    AptitudeLevels,
    ResultsResponse,
    SaveResultResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
)


load_dotenv()

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from the environment.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(
    title="NeuroCare AI Backend",
    description="Cognitive training and performance tracking API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables, including the new game progress table.
Base.metadata.create_all(bind=engine)

# Add adaptive difficulty fields to existing SQLite databases.
with engine.begin() as connection:
    existing_columns = {
        column["name"]
        for column in inspect(connection).get_columns("game_results")
    }

    if "mode" not in existing_columns:
        connection.execute(
            text("ALTER TABLE game_results ADD COLUMN mode VARCHAR")
        )

    if "level" not in existing_columns:
        connection.execute(
            text("ALTER TABLE game_results ADD COLUMN level INTEGER")
        )

    if "max_level" not in existing_columns:
        connection.execute(
            text("ALTER TABLE game_results ADD COLUMN max_level INTEGER")
        )

    user_columns = {
        column["name"]
        for column in inspect(connection).get_columns("users")
    }

    if "age" not in user_columns:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN age INTEGER")
        )
    if "aptitude_levels" not in user_columns:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN aptitude_levels JSON")
        )
    if "assessment_scores" not in user_columns:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN assessment_scores JSON")
        )
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ==========================================
# AUTHENTICATION
# ==========================================

def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = int(payload.get("sub", ""))

    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized

    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id)
        .first()
    )

    if user is None:
        raise unauthorized

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive.",
        )

    return user


app.include_router(create_assessment_router(get_current_user))


# ==========================================
# HOME AND HEALTH
# ==========================================

@app.get("/")
def home():
    return {"message": "Welcome to NeuroCare AI Backend"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ==========================================
# USER REGISTRATION
# ==========================================

@app.post("/users", response_model=UserResponse, status_code=201)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    email = str(user.email)

    existing_user = (
        db.query(UserModel)
        .filter(UserModel.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        )

    db_user = UserModel(
        email=email,
        hashed_password=password_hash.hash(user.password),
        age=user.age,
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        )

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create user.",
        )

    return {
        "id": db_user.id,
        "email": db_user.email,
        "is_active": db_user.is_active,
        "age": db_user.age,
        "aptitude_levels": db_user.aptitude_levels,
    }


# ==========================================
# USER LOGIN
# ==========================================

@app.post("/token", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(UserModel)
        .filter(UserModel.email == form_data.username)
        .first()
    )

    if user is None or not password_hash.verify(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive.",
        )

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "age": user.age,
        "aptitude_levels": user.aptitude_levels,
        "assessment_scores": user.assessment_scores,
    }


# ==========================================
# UPDATE USER AGE
# ==========================================

@app.patch("/users/me/age")
def update_my_age(
    age_update: AgeUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    current_user.age = age_update.age

    try:
        db.commit()
        db.refresh(current_user)

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save your age.",
        )

    return {"age": current_user.age}


@app.put("/users/me/aptitudes")
def save_aptitude_levels(
    levels: AptitudeLevels,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    current_user.aptitude_levels = levels.model_dump()
    try:
        db.commit()
        db.refresh(current_user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save your game starting levels.",
        )
    return {"aptitude_levels": current_user.aptitude_levels}


# ==========================================
# SAVE GAME RESULT
# ==========================================

@app.post(
    "/results",
    response_model=SaveResultResponse,
    responses={
        500: {
            "description": "Database save failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not save game result. Please try again."
                    }
                }
            },
        }
    },
)
def save_result(
    result: GameResult,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db_result = GameResultModel(
        user_id=current_user.id,
        **result.model_dump(),
    )

    try:
        db.add(db_result)
        db.commit()
        db.refresh(db_result)

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save game result. Please try again.",
        )

    record = {
        "id": db_result.id,
        "user_id": db_result.user_id,
        "game_name": db_result.game_name,
        "score": db_result.score,
        "accuracy": db_result.accuracy,
        "completion_time_seconds": db_result.completion_time_seconds,
        "errors": db_result.errors,
        "mode": db_result.mode,
        "level": db_result.level,
        "max_level": db_result.max_level,
    }

    recent_results = (
        db.query(GameResultModel)
        .filter(
            GameResultModel.user_id == current_user.id,
            GameResultModel.game_name == result.game_name,
        )
        .order_by(GameResultModel.id.desc())
        .limit(3)
        .all()
    )

    level_recommendation = recommend_level(
        result.game_name,
        user_age=current_user.age,
        previous_results=recent_results,
    )

    return {
        "message": "Game result received",
        "result": record,
        "recommendation": recommend_game(result.game_name),
        "level_recommendation": level_recommendation,
    }


# ==========================================
# AI LEVEL RECOMMENDATION
# ==========================================

@app.get("/recommendation/level/{game_name}")
def get_level_recommendation(
    game_name: GameName,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Return the next starting difficulty using recent game history."""

    recent_results = (
        db.query(GameResultModel)
        .filter(
            GameResultModel.user_id == current_user.id,
            GameResultModel.game_name == game_name,
        )
        .order_by(GameResultModel.id.desc())
        .limit(3)
        .all()
    )

    recommendation = recommend_level(
        game_name,
        user_age=current_user.age,
        previous_results=recent_results,
    )
    if not recent_results and current_user.aptitude_levels:
        area_for_game = {
            "memory_card": "memory",
            "number_sequence": "working_memory",
            "sequence_memory": "pattern_recognition",
            "sequence_recall": "pattern_recognition",
            "stroop_test": "attention",
            "reaction_time": "processing_speed",
        }.get(game_name)
        preferred = current_user.aptitude_levels.get(area_for_game) if area_for_game else None
        if preferred in {"easy", "medium", "hard"}:
            recommendation["recommended_mode"] = preferred
            recommendation["reason"] = f"Based on your selected starting level for this area, begin at {preferred.title()} level 1."
    return recommendation


@app.get("/recommendation/games")
def get_game_recommendations(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    areas = [
        ("memory", "Memory Card Match", "memory_card", "games/memory.html"),
        ("working_memory", "Number Sequence Memory", "number_sequence", "games/number_sequence.html"),
        ("pattern_recognition", "Sequence Recall", "sequence_recall", "games/sequence.html"),
        ("attention", "Stroop Colour Challenge", "stroop_test", "games/stroop_game.html"),
        ("processing_speed", "Reaction Time", "reaction_time", "games/reaction_time.html"),
    ]
    results = (
        db.query(GameResultModel)
        .filter(GameResultModel.user_id == current_user.id)
        .order_by(GameResultModel.id.desc())
        .all()
    )
    preferences = current_user.aptitude_levels or {}
    baseline = current_user.assessment_scores or {}
    recommendations = []
    for area, title, game_name, url in areas:
        matching = [item for item in results if item.game_name == game_name]
        mode = preferences.get(area)
        if mode not in {"easy", "medium", "hard"}:
            mode = "easy" if current_user.age is None or current_user.age > 60 else "medium" if current_user.age >= 45 else "hard"
        if matching:
            latest = matching[0]
            recent = matching[:3]
            average_accuracy = round(sum(item.accuracy for item in recent) / len(recent))
            level_advice = recommend_level(
                game_name,
                user_age=current_user.age,
                previous_results=recent,
            )
            recommended_mode = level_advice["recommended_mode"]
            recommended_level = level_advice["recommended_level"]
            if len(recent) > 1:
                prior_average = sum(item.accuracy for item in recent[1:]) / (len(recent) - 1)
                change = latest.accuracy - prior_average
                trend = "improving" if change >= 5 else "declining" if change <= -5 else "steady"
                trend_detail = f"Your accuracy is {trend} (latest {latest.accuracy:.0f}% vs {prior_average:.0f}% on earlier recent play(s))."
            else:
                trend_detail = f"Your latest accuracy was {latest.accuracy:.0f}%; more plays will clarify your trend."
            reason = (
                f"You selected {mode.title()} as your starting level for {area.replace('_', ' ')}. "
                f"Across your last {len(recent)} play(s), average accuracy is {average_accuracy}%. "
                f"{trend_detail} Based on these results, try {recommended_mode.title()} mode, level {recommended_level}."
            )
        else:
            average_accuracy = None
            recommended_mode = mode
            recommended_level = 1
            reason = f"You chose {mode.title()} as your starting level for this area, and haven’t played it yet."
        assessment_score = baseline.get(area)
        if assessment_score is not None:
            assessment_score = int(assessment_score)
            reason += f" Your Level 1 assessment score in this area was {assessment_score}/100."
            if matching:
                reason += f" Together with your recent game accuracy of {average_accuracy}%, this informs the suggestion."
            else:
                reason += " This baseline makes the game a useful place to begin building practice history."
        recommendations.append({
            "aptitude": area.replace("_", " ").title(),
            "game_name": game_name,
            "title": title,
            "url": url,
            "preferred_mode": mode,
            "recommended_mode": recommended_mode,
            "recommended_level": recommended_level,
            "reason": reason,
            "games_played": len(matching),
            "average_accuracy": average_accuracy,
            "assessment_score": assessment_score,
            "priority": (
                ((100 - assessment_score) * 0.6 + (100 - average_accuracy) * 0.4)
                if assessment_score is not None and average_accuracy is not None
                else (100 - assessment_score) if assessment_score is not None
                else (100 - average_accuracy) if average_accuracy is not None
                else -1
            ),
        })
    recommendations.sort(key=lambda item: item["priority"])
    for item in recommendations:
        item.pop("priority")
    return {"recommendations": recommendations}


# ==========================================
# GET USER GAME RESULTS
# ==========================================

@app.get(
    "/results/me",
    response_model=ResultsResponse,
    responses={
        500: {
            "description": "Database retrieval failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not retrieve game results. Please try again."
                    }
                }
            },
        }
    },
)
def get_my_results(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        user_results = (
            db.query(GameResultModel)
            .filter(GameResultModel.user_id == current_user.id)
            .all()
        )

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve game results. Please try again.",
        )

    return {
        "user_id": current_user.id,
        "results": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "game_name": item.game_name,
                "score": item.score,
                "accuracy": item.accuracy,
                "completion_time_seconds": item.completion_time_seconds,
                "errors": item.errors,
                "mode": item.mode,
                "level": item.level,
                "max_level": item.max_level,
            }
            for item in user_results
        ],
    }


# ==========================================
# SAVE GAME PROGRESS
# ==========================================

@app.post("/progress/{game_name}")
def save_game_progress(
    game_name: GameName,
    progress: GameProgressSave,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        saved = (
            db.query(GameProgressModel)
            .filter(
                GameProgressModel.user_id == current_user.id,
                GameProgressModel.game_name == game_name,
            )
            .first()
        )

        if saved is None:
            saved = GameProgressModel(
                user_id=current_user.id,
                game_name=game_name,
                current_level=progress.current_level,
                completed_levels=progress.completed_levels,
                game_state=progress.game_state,
                status=progress.status,
            )
            db.add(saved)

        else:
            saved.current_level = progress.current_level
            saved.completed_levels = progress.completed_levels
            saved.game_state = progress.game_state
            saved.status = progress.status

        db.commit()
        db.refresh(saved)

        return {
            "message": "Progress saved successfully",
            "game_name": saved.game_name,
            "current_level": saved.current_level,
            "completed_levels": saved.completed_levels,
            "game_state": saved.game_state,
            "status": saved.status,
        }

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save game progress.",
        )


# ==========================================
# GET ALL GAME PROGRESS
# ==========================================

@app.get("/progress")
def get_all_game_progress(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        records = (
            db.query(GameProgressModel)
            .filter(
                GameProgressModel.user_id == current_user.id
            )
            .all()
        )

        return [
            {
                "game_name": item.game_name,
                "current_level": item.current_level,
                "completed_levels": item.completed_levels,
                "game_state": item.game_state,
                "status": item.status,
                "updated_at": item.updated_at,
            }
            for item in records
        ]

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve game progress.",
        )


# ==========================================
# RESUME SPECIFIC GAME
# ==========================================

@app.get("/progress/{game_name}")
def get_game_progress(
    game_name: GameName,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        saved = (
            db.query(GameProgressModel)
            .filter(
                GameProgressModel.user_id == current_user.id,
                GameProgressModel.game_name == game_name,
            )
            .first()
        )

        if saved is None:
            return {
                "exists": False,
                "message": "No saved progress found.",
            }

        return {
            "exists": True,
            "game_name": saved.game_name,
            "current_level": saved.current_level,
            "completed_levels": saved.completed_levels,
            "game_state": saved.game_state,
            "status": saved.status,
            "updated_at": saved.updated_at,
        }

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve game progress.",
        )


# ==========================================
# RESET GAME PROGRESS
# ==========================================

@app.delete("/progress/{game_name}")
def reset_game_progress(
    game_name: GameName,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        saved = (
            db.query(GameProgressModel)
            .filter(
                GameProgressModel.user_id == current_user.id,
                GameProgressModel.game_name == game_name,
            )
            .first()
        )

        if saved is None:
            return {
                "message": "No saved progress found."
            }

        db.delete(saved)
        db.commit()

        return {
            "message": "Game progress reset successfully."
        }

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not reset game progress.",
        )

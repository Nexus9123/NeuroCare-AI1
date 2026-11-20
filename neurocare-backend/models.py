
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    String,
    JSON,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False
    )
    game_name: Mapped[str] = mapped_column(
        String, nullable=False
    )
    score: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    accuracy: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    completion_time_seconds: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    errors: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    mode: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    level: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    max_level: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    age: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )


class GameProgress(Base):
    __tablename__ = "game_progress"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "game_name",
            name="uq_user_game_progress"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )

    game_name: Mapped[str] = mapped_column(
        String, nullable=False
    )

    current_level: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )

    completed_levels: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )

    game_state: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    status: Mapped[str] = mapped_column(
        String, default="in_progress", nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

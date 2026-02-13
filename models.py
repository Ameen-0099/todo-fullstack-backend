from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Field, Relationship, SQLModel

class User(SQLModel, table=True):
    """
    Represents a user. This model is for reference within SQLModel for relationships.
    The actual user data (password hashing, etc.) is managed externally by Better Auth.
    The application itself should not write to this table directly.
    """
    id: str = Field(primary_key=True)  # user_id from JWT / Better Auth
    email: str = Field(unique=True, nullable=False)
    hashed_password: str = Field(nullable=False) # Added for local password verification
    name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    tasks: List["Task"] = Relationship(back_populates="user")

    # Pydantic configuration for better JSON serialization/deserialization
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, nullable=False, foreign_key="user.id")
    title: str = Field(max_length=200, nullable=False)
    description: Optional[str] = Field(default=None, max_length=1000)
    completed: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    user: User = Relationship(back_populates="tasks")

    # Pydantic configuration for better JSON serialization/deserialization
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

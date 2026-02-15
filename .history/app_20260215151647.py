from typing import List, Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from enum import Enum


from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()

from database import get_session
from models import User, Task
from security import get_password_hash, verify_password
from auth import create_access_token, verify_token, oauth2_scheme, ACCESS_TOKEN_EXPIRE_MINUTES

def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application.
    """


    app = FastAPI(
        title="AI-Driven Todo App",
        description="A robust backend for a modern todo list application, powered by AI.",
        version="1.0.0"
    )

    # --- Middleware Configuration ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Pydantic Models ---
    class UserCreate(BaseModel):
        email: EmailStr
        password: str = Field(min_length=8)

    class UserLogin(BaseModel):
        email: EmailStr
        password: str

    class Token(BaseModel):
        access_token: str
        token_type: str = "bearer"

    class UserOut(BaseModel):
        user_id: str = Field(alias="id")
        email: EmailStr
        created_at: datetime

        class Config:
            json_encoders = {datetime: lambda v: v.isoformat() if v else None}
            populate_by_name = True

    class Status(str, Enum):
        pending = "pending"
        in_progress = "in_progress"
        completed = "completed"

    class TaskCreate(BaseModel):
        title: str = Field(min_length=1, max_length=200)
        description: Optional[str] = Field(default=None, max_length=1000)
        status: Status = Field(default=Status.pending)

    class TaskUpdate(BaseModel):
        title: Optional[str] = Field(default=None, max_length=200)
        description: Optional[str] = Field(default=None, max_length=1000)
        status: Optional[Status] = Field(default=None)

    class TaskRead(BaseModel):
        id: int
        user_id: str
        title: str
        description: Optional[str]
        completed: bool
        created_at: datetime
        updated_at: datetime

        class Config:
            json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    # --- API Endpoints ---
    @app.get("/")
    def read_root():
        return {"message": "Welcome to the AI-Driven Todo App Backend!"}

    @app.post("/api/register", response_model=Token, status_code=status.HTTP_201_CREATED)
    def register_user(user_in: UserCreate, db: Session = Depends(get_session)):
        if db.exec(select(User).where(User.email == user_in.email)).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        db_user = User(
            id=str(uuid4()),
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            created_at=datetime.now(timezone.utc)
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        access_token = create_access_token(data={"sub": db_user.id})
        return {"access_token": access_token, "token_type": "bearer"}

    @app.post("/api/login", response_model=Token)
    def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)):
        user = db.exec(select(User).where(User.email == form_data.username)).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(data={"sub": user.id})
        return {"access_token": access_token, "token_type": "bearer"}

    def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id or (user := db.exec(select(User).where(User.id == user_id)).first()) is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return user

    @app.get("/api/users/me", response_model=UserOut)
    def read_users_me(current_user: User = Depends(get_current_user)):
        return current_user

    @app.post("/api/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
    def create_task(task_in: TaskCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
        db_task = Task(
            title=task_in.title,
            description=task_in.description,
            completed=(task_in.status == Status.completed),
            user_id=current_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task

    @app.get("/api/tasks", response_model=List[TaskRead])
    def list_tasks(status_filter: Optional[Status] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
        query = select(Task).where(Task.user_id == current_user.id)
        if status_filter:
            query = query.where(Task.completed == (status_filter == Status.completed))
        return db.exec(query).all()

    @app.get("/api/tasks/{id}", response_model=TaskRead)
    def get_task(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
        task = db.exec(select(Task).where(Task.id == id, Task.user_id == current_user.id)).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    @app.put("/api/tasks/{id}", response_model=TaskRead)
    def update_task(id: int, task_update: TaskUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
        task = db.exec(select(Task).where(Task.id == id, Task.user_id == current_user.id)).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
        update_data = task_update.dict(exclude_unset=True)
        if "status" in update_data:
            task.completed = (update_data["status"] == Status.completed)
            del update_data["status"]
            
        for key, value in update_data.items():
            setattr(task, key, value)
        
        task.updated_at = datetime.now(timezone.utc)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @app.delete("/api/tasks/{id}", status_code=status.HTTP_200_OK)
    def delete_task(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
        task = db.exec(select(Task).where(Task.id == id, Task.user_id == current_user.id)).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        db.delete(task)
        db.commit()
        return {"message": "Task deleted successfully"}

    return app

# Create the FastAPI app instance
app = create_app()

# For Vercel deployment, make sure the app object is accessible
# This ensures that Vercel can properly import and serve the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from enum import Enum # Import Enum
from dotenv import load_dotenv

load_dotenv(dotenv_path="backend/.env")

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, Field

from database import get_session
from models import User, Task
from security import get_password_hash, verify_password
from .auth import create_access_token, verify_token, oauth2_scheme, ACCESS_TOKEN_EXPIRE_MINUTES


app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Pydantic models for request and response (Authentication)
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
    user_id: str = Field(alias="id") # Map id to user_id for API response
    email: EmailStr
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        populate_by_name = True # Allow alias to be used for population

# Pydantic models for Task management
class Status(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"

class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Status = Field(default=Status.pending)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Status] = Field(default=None)

class TaskRead(BaseModel): # Response model for tasks
    id: int
    user_id: str
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Driven Todo App Backend!"}

# --- Authentication Endpoints ---

@app.post("/api/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_session)):
    """
    Registers a new user and returns an access token.
    """
    print(f"Attempting to register new user: {user_in.email}")
    existing_user = db.exec(select(User).where(User.email == user_in.email)).first()
    if existing_user:
        print(f"User already exists: {user_in.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    print(f"Hashing password for user: {user_in.email}")
    hashed_password = get_password_hash(user_in.password)
    new_user_id = str(uuid4())

    db_user = User(
        id=new_user_id,
        email=user_in.email,
        hashed_password=hashed_password,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    print(f"User registered successfully: {db_user.email} with id {db_user.id}")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session)
):
    """
    Authenticates a user and returns an access token.
    """
    print(f"Attempting to log in user: {form_data.username}")
    user = db.exec(select(User).where(User.email == form_data.username)).first()
    
    if not user:
        print(f"User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User found: {user.email}")
    is_password_correct = verify_password(form_data.password, user.hashed_password)
    print(f"Password verification for {form_data.username}: {is_password_correct}")

    if not is_password_correct:
        print(f"Incorrect password for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    print(f"User logged in successfully: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/logout")
def logout_user():
    """
    Logout is handled client-side by deleting the JWT token.
    This endpoint simply provides a confirmation.
    """
    return {"message": "Logged out successfully"}

# Dependency to get the current authenticated user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
    """
    Retrieves the current authenticated user from the JWT token.
    """
    payload = verify_token(token)
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# Example of a protected route (will be used for tasks later)
@app.get("/api/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Retrieves information about the current authenticated user.
    """
    return current_user

# --- Task Endpoints ---

@app.post("/api/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Creates a new task for the authenticated user.
    """
    # Determine the completed status based on the incoming task_in.status
    is_completed = (task_in.status == Status.completed)
    
    db_task = Task(
        title=task_in.title,
        description=task_in.description,
        completed=is_completed, # Map the API's 'status' enum to the database's 'completed' boolean field
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/api/tasks", response_model=List[TaskRead])
def list_tasks(
    status: Optional[Status] = None, # Use the Status Enum
    sort: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Lists tasks for the authenticated user, with optional filtering and sorting.
    """
    query = select(Task).where(Task.user_id == current_user.id)

    if status:
        if status == Status.completed:
            query = query.where(Task.completed == True)
        elif status == Status.pending or status == Status.in_progress:
            query = query.where(Task.completed == False)

    if sort == "created_at":
        query = query.order_by(Task.created_at)
    elif sort == "title":
        query = query.order_by(Task.title)
    # Default sorting, or no sorting if not specified

    tasks = db.exec(query).all()
    return tasks

@app.get("/api/tasks/{id}", response_model=TaskRead)
def get_task(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Retrieves a single task by its ID for the authenticated user.
    """
    task = db.exec(
        select(Task).where(Task.id == id, Task.user_id == current_user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task

@app.put("/api/tasks/{id}", response_model=TaskRead)
def update_task(
    id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Updates an existing task for the authenticated user.
    """
    task = db.exec(
        select(Task).where(Task.id == id, Task.user_id == current_user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task_data = task_update.dict(exclude_unset=True)
    if "status" in task_data:
        task.completed = (task_data["status"] == Status.completed)
        del task_data["status"] # Remove status from data to avoid setting it directly

    for key, value in task_data.items():
        setattr(task, key, value)
    
    task.updated_at = datetime.now(timezone.utc) # Update the updated_at timestamp

    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.delete("/api/tasks/{id}", status_code=status.HTTP_200_OK)
def delete_task(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Deletes a task for the authenticated user.
    """
    task = db.exec(
        select(Task).where(Task.id == id, Task.user_id == current_user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}

@app.patch("/api/tasks/{id}/complete", response_model=TaskRead)
def toggle_task_completion(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Toggles the completion status of a task for the authenticated user.
    """
    task = db.exec(
        select(Task).where(Task.id == id, Task.user_id == current_user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.completed = not task.completed
    task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task
from typing import Generator
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
import pytest

from backend.models import User, Task # Absolute import
from backend.security import get_password_hash # Absolute import

# --- Test Database Setup ---
# Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="test_engine")
def test_engine_fixture():
    # Use StaticPool to ensure the same connection is always returned for in-memory DB
    test_engine = create_engine(
        TEST_DATABASE_URL,
        echo=True,  # Keep echo=True for now to observe SQL
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, # Crucial for in-memory SQLite to share the same DB
    )
    # Ensure models are imported and tables created on this specific connection
    import backend.models
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)
    # The in-memory database will be cleared when StaticPool's underlying connection closes.
    # No need for explicit engine dispose or connection close as StaticPool manages it.


# Fixture to provide a test database session for each test function
@pytest.fixture(name="test_db_session")
def test_db_session_fixture(test_engine: Engine): # Depend on the test_engine fixture
    with Session(test_engine) as session:
        yield session # Provide the session to the test


# Fixture to provide a TestClient for a fresh FastAPI app instance for each test
@pytest.fixture(name="client")
def client_fixture(test_db_session: Session):
    # These imports must be local to avoid module-level import issues when pytest scans
    # the test file before fixtures are set up correctly.
    from backend.main import app # Absolute import
    from backend.database import get_session # Absolute import

    def get_session_override():
        return test_db_session  # yield test_db_session was causing issues with closing sessions, direct return for fixture scope

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# --- Tests ---

def test_read_root(client: TestClient):
    """
    Test the root endpoint.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the AI-Driven Todo App Backend!"}

def test_register_user(client: TestClient):
    """
    Test user registration.
    """
    response = client.post(
        "/api/register",
        json={"email": "test@example.com", "password": "strong-password"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify that the user can log in with the registered credentials
    login_response = client.post(
        "/api/login",
        data={"username": "test@example.com", "password": "strong-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"

def test_register_existing_user(client: TestClient):
    """
    Test registering a user with an already existing email.
    """
    # Register first user
    client.post(
        "/api/register",
        json={"email": "existing@example.com", "password": "strong-password"},
    )
    # Attempt to register with the same email
    response = client.post(
        "/api/register",
        json={"email": "existing@example.com", "password": "strong-password-2"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}

def test_login_invalid_credentials(client: TestClient):
    """
    Test login with incorrect username or password.
    """
    # Attempt to login without registering
    response = client.post(
        "/api/login",
        data={"username": "nonexistent@example.com", "password": "bad-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

    # Register a user
    client.post(
        "/api/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    # Attempt to log in with correct email but wrong password
    response = client.post(
        "/api/login",
        data={"username": "user@example.com", "password": "bad-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

@pytest.fixture(name="authenticated_client")
def authenticated_client_fixture(client: TestClient):
    """
    Fixture to register and log in a user, returning a client with an auth token.
    """
    # Register a user
    register_response = client.post(
        "/api/register",
        json={"email": "authuser@example.com", "password": "auth-password"},
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    # Return client with Authorization header set
    client.headers["Authorization"] = f"Bearer {token}"
    return client

# --- Task Tests ---

def test_create_task(authenticated_client: TestClient):
    """
    Test creating a task for an authenticated user.
    """
    response = authenticated_client.post(
        "/api/tasks",
        json={"title": "Test Task", "description": "This is a test description."},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["description"] == "This is a test description."
    assert "id" in data
    assert "user_id" in data
    assert data["completed"] == False
    assert "created_at" in data
    assert "updated_at" in data

def test_create_task_unauthenticated(client: TestClient):
    """
    Test creating a task without authentication.
    """
    response = client.post(
        "/api/tasks",
        json={"title": "Unauthorized Task"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def create_task_for_user(client: TestClient, title: str, description: str = None, status: str = "pending", priority: str = "medium"):
    """
    Helper function to create a task for an authenticated user.
    Assumes client is already authenticated.
    """
    task_data = {"title": title, "status": status, "priority": priority}
    if description:
        task_data["description"] = description
    response = client.post(
        "/api/tasks",
        json=task_data,
    )
    assert response.status_code == 201
    return response.json()


def test_list_tasks(authenticated_client: TestClient):
    """
    Test listing tasks for an authenticated user.
    """
    # Create a few tasks
    task1 = create_task_for_user(authenticated_client, "Task 1")
    task2 = create_task_for_user(authenticated_client, "Task 2")
    task3 = create_task_for_user(authenticated_client, "Task 3", status="completed")

    response = authenticated_client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 3
    assert any(t["title"] == "Task 1" for t in tasks)
    assert any(t["title"] == "Task 2" for t in tasks)
    assert any(t["title"] == "Task 3" for t in tasks)


def test_list_tasks_filtered_by_status(authenticated_client: TestClient):
    """
    Test listing tasks filtered by status.
    """
    create_task_for_user(authenticated_client, "Pending Task", status="pending")
    create_task_for_user(authenticated_client, "Completed Task", status="completed")
    create_task_for_user(authenticated_client, "In Progress Task", status="in_progress")

    # Filter for completed tasks
    response = authenticated_client.get("/api/tasks", params={"status": "completed"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Completed Task"
    assert tasks[0]["completed"] == True

    # Filter for pending tasks
    response = authenticated_client.get("/api/tasks", params={"status": "pending"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2 # Expect 2 tasks (pending and in_progress)
    assert any(t["title"] == "Pending Task" for t in tasks)
    assert any(t["title"] == "In Progress Task" for t in tasks)
    assert tasks[0]["completed"] == False


def test_list_tasks_sorted_by_created_at(authenticated_client: TestClient):
    """
    Test listing tasks sorted by created_at.
    """
    # Create tasks with a slight delay to ensure different created_at timestamps
    task1 = create_task_for_user(authenticated_client, "First Task")
    import time
    time.sleep(0.01) # Ensure distinct timestamps
    task2 = create_task_for_user(authenticated_client, "Second Task")

    response = authenticated_client.get("/api/tasks", params={"sort": "created_at"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    # By default, SQLModel query will order by id which is usually creation order
    # For explicit created_at sorting, we just check if they are in some order
    assert tasks[0]["title"] == "First Task"
    assert tasks[1]["title"] == "Second Task"

def test_list_tasks_unauthenticated(client: TestClient):
    """
    Test listing tasks without authentication.
    """
    response = client.get("/api/tasks")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_single_task(authenticated_client: TestClient):
    """
    Test successful retrieval of a single task for an authenticated user.
    """
    created_task = create_task_for_user(authenticated_client, "Task to Retrieve")
    task_id = created_task["id"]

    response = authenticated_client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    task = response.json()
    assert task["id"] == task_id
    assert task["title"] == "Task to Retrieve"
    assert task["completed"] == False


def test_get_single_task_not_found(authenticated_client: TestClient):
    """
    Test retrieval of a non-existent task.
    """
    non_existent_id = 999999 # Assuming this ID does not exist
    response = authenticated_client.get(f"/api/tasks/{non_existent_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_get_single_task_unauthenticated(client: TestClient, test_db_session: Session):
    """
    Test retrieval of a single task without authentication.
    """
    # Manually create a user and task in the database for this test
    # We need to be careful not to use the 'client' here for creation to avoid mixing concerns.
    # Directly use the db session for creating a user and a task.


    new_user_id = str(uuid4())
    db_user = User(
        id=new_user_id,
        email="unauth_test_user@example.com",
        hashed_password=get_password_hash("password123"),
        created_at=datetime.now(timezone.utc)
    )
    test_db_session.add(db_user)
    test_db_session.commit()
    test_db_session.refresh(db_user)

    db_task = Task(
        user_id=new_user_id,
        title="Task to be accessed unauthenticated",
        completed=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db_session.add(db_task)
    test_db_session.commit()
    test_db_session.refresh(db_task)

    task_id = db_task.id

    # Now, try to get the task with the 'client' fixture, which is guaranteed to be unauthenticated
    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_single_task_unauthorized(authenticated_client: TestClient):
    """
    Test retrieval of another user's task by an authenticated but unauthorized user.
    """
    # User 1 (authenticated_client) creates a task
    user1_task = create_task_for_user(authenticated_client, "User1's Task")
    user1_task_id = user1_task["id"]

    # User 2 registers and tries to access User 1's task
    client_for_user2 = TestClient(authenticated_client.app) # Create a new client instance
    register_response_user2 = client_for_user2.post(
        "/api/register",
        json={"email": "user2@example.com", "password": "user2-password"},
    )
    user2_token = register_response_user2.json()["access_token"]
    client_for_user2.headers["Authorization"] = f"Bearer {user2_token}"

    response = client_for_user2.get(f"/api/tasks/{user1_task_id}")
    assert response.status_code == 404 # Should be 404 Not Found as ownership is enforced
    assert response.json() == {"detail": "Task not found"}


def test_update_task_full(authenticated_client: TestClient):
    """
    Test successful full update of a task for an authenticated user.
    """
    original_task = create_task_for_user(authenticated_client, "Task to Update", description="Old description")
    task_id = original_task["id"]

    updated_data = {
        "title": "Updated Title",
        "description": "New description.",
        "status": "completed"
    }
    response = authenticated_client.put(f"/api/tasks/{task_id}", json=updated_data)
    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["id"] == task_id
    assert updated_task["title"] == "Updated Title"
    assert updated_task["description"] == "New description."
    assert updated_task["completed"] == True
    assert updated_task["updated_at"] != original_task["updated_at"] # updated_at should change


def test_update_task_partial(authenticated_client: TestClient):
    """
    Test successful partial update of a task for an authenticated user.
    """
    original_task = create_task_for_user(authenticated_client, "Partial Update Task", description="Original desc")
    task_id = original_task["id"]

    updated_data = {
        "title": "New Partial Title"
    }
    response = authenticated_client.put(f"/api/tasks/{task_id}", json=updated_data)
    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["id"] == task_id
    assert updated_task["title"] == "New Partial Title"
    assert updated_task["description"] == "Original desc" # Description should remain unchanged
    assert updated_task["completed"] == False # Completed should remain unchanged
    assert updated_task["updated_at"] != original_task["updated_at"]


def test_update_task_not_found(authenticated_client: TestClient):
    """
    Test updating a non-existent task.
    """
    non_existent_id = 999999
    updated_data = {"title": "Non Existent Update"}
    response = authenticated_client.put(f"/api/tasks/{non_existent_id}", json=updated_data)
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_update_task_unauthenticated(client: TestClient, test_db_session: Session):
    """
    Test updating a task without authentication.
    """
    # Manually create a user and task in the database for this test
    from backend.models import User, Task
    from backend.security import get_password_hash

    new_user_id = str(uuid4())
    db_user = User(
        id=new_user_id,
        email="unauth_update_test_user@example.com",
        hashed_password=get_password_hash("password123"),
        created_at=datetime.now(timezone.utc)
    )
    test_db_session.add(db_user)
    test_db_session.commit()
    test_db_session.refresh(db_user)

    db_task = Task(
        user_id=new_user_id,
        title="Task to be updated unauthenticated",
        completed=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db_session.add(db_task)
    test_db_session.commit()
    test_db_session.refresh(db_task)
    task_id = db_task.id

    updated_data = {"title": "Attempted Update"}
    response = client.put(f"/api/tasks/{task_id}", json=updated_data)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_update_task_unauthorized(authenticated_client: TestClient, test_db_session: Session):
    """
    Test updating another user's task by an authenticated but unauthorized user.
    """
    # User 1 (authenticated_client) creates a task
    user1_task = create_task_for_user(authenticated_client, "User1's Task for Update")
    user1_task_id = user1_task["id"]

    # User 2 registers and tries to update User 1's task
    client_for_user2 = TestClient(authenticated_client.app)
    register_response_user2 = client_for_user2.post(
        "/api/register",
        json={"email": "user2_for_update@example.com", "password": "user2-password"},
    )
    user2_token = register_response_user2.json()["access_token"]
    client_for_user2.headers["Authorization"] = f"Bearer {user2_token}"

    updated_data = {"title": "Attempted unauthorized update"}
    response = client_for_user2.put(f"/api/tasks/{user1_task_id}", json=updated_data)
    assert response.status_code == 404 # Should be 404 Not Found as ownership is enforced
    assert response.json() == {"detail": "Task not found"}
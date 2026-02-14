---
title: AI-Driven Todo App Backend
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: fastapi
app_port: 8000
---

# AI-Driven Todo App Backend

This is the backend for an AI-driven Todo application, built with FastAPI and SQLModel.

## Features:
- User authentication (registration, login)
- JWT-based access tokens
- Task management (create, read, update, delete, list tasks)
- Database integration (PostgreSQL via SQLModel)

## How to run locally:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Ameen-0099/backend-deploy.git
    cd backend-deploy/backend-app
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate # On Windows
    # source venv/bin/activate # On Linux/macOS
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file inside the `backend` directory with your database URL and a secret key.
    Example `backend/.env`:
    ```
    DATABASE_URL="postgresql://user:password@host:port/database_name"
    SECRET_KEY="your-super-secret-jwt-key"
    ```
    **Note:** Replace `user`, `password`, `host`, `port`, `database_name`, and `your-super-secret-jwt-key` with your actual database credentials and a strong secret key.

5.  **Run database migrations (if any):**
    *This project might require database schema creation/migrations. You'll need to implement these based on your SQLModel setup, typically using Alembic.*

6.  **Start the application:**
    ```bash
    uvicorn app:app --host 0.0.0.0 --port 8000
    ```

The API documentation will be available at `http://localhost:8000/docs` or `http://localhost:8000/redoc`.

## Deployment to Hugging Face Spaces:

This application is configured for deployment to Hugging Face Spaces using the `fastapi` SDK.
To deploy:

1.  Create a new Space on Hugging Face: `https://huggingface.co/new-space`
2.  Choose "Docker" as the Space SDK and "FastAPI" as the framework.
3.  Connect your repository (e.g., this GitHub repository or a new one you create).
4.  Ensure your `backend/.env` (with appropriate database credentials for your deployed environment) is correctly configured as Space Secrets on Hugging Face to avoid committing sensitive information directly.
5.  Hugging Face will automatically detect `app.py` and `requirements.txt` and build your application.

## API Endpoints:

- `/`: Welcome message
- `/api/register`: Register a new user
- `/api/login`: Authenticate and get a JWT token
- `/api/logout`: Client-side logout confirmation
- `/api/users/me`: Get current user info (protected)
- `/api/tasks`: Create, list tasks (protected)
- `/api/tasks/{id}`: Get, update, delete a specific task (protected)
- `/api/tasks/{id}/complete`: Toggle task completion (protected)

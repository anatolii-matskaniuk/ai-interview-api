from fastapi import FastAPI
from src.auth.routes import router as auth_router

app = FastAPI(
    title="AI Interview Practice API",
    version="1.0.0",
    description="An API to simulate mock interviews "
                "with AI-generated questions and real-time feedback",
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])


@app.get("/", tags=["Root"])
def get_root():
    return {"message": "Welcome to the AI Interview Practice API"}

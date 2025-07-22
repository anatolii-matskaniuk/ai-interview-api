from fastapi import FastAPI
from src.auth.routes import router as auth_router
from src.interviews.routes import router as interviews_router
from src.interviews.ws_routes import router as ws_router

app = FastAPI(
    title="AI Interview Practice API",
    version="1.0.0",
    description="An API to simulate mock interviews "
                "with AI-generated questions and real-time feedback",
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(interviews_router, prefix="/api/v1/sessions", tags=["Interview Sessions"])
app.include_router(ws_router, tags=["Interview WebSocket"])


@app.get("/", tags=["Root"])
def get_root():
    return {"message": "Welcome to the AI Interview Practice API"}

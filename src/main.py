from fastapi import FastAPI

app = FastAPI(
    title="AI Interview Practice API",
    version="1.0.0",
    description="An API to simulate mock interviews with AI-generated questions and real-time feedback",
)

@app.get("/", tags=["Root"])
def get_root():
    return {"message": "Welcome to the AI Interview Practice API"}
from fastapi import FastAPI
from langserve import add_routes

from src.app.server import deep_researcher

app = FastAPI(
    title="Deep Researcher API",
    version="1.0",
    description="A multi-agent research assistant",
)

add_routes(
    app,
    deep_researcher,
    path="/research",
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

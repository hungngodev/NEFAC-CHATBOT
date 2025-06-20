import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llm.main import ask_llm_stream
from load_env import load_env
from vector.load import get_loading_status, is_loading

load_env()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ask-llm")
async def ask_llm(
    query: str,
    convoHistory: str = "",
):
    try:        
        return StreamingResponse(
            ask_llm_stream(None, query, convoHistory),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/loading-status")
async def get_vector_loading_status():
    """Get the current status of document loading into the vector store"""
    try:
        status = get_loading_status()
        status["is_loading"] = is_loading()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

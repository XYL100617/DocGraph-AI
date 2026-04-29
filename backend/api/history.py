from fastapi import APIRouter
from core.history import get_history

router = APIRouter()

@router.get("/history")
def history(session_id: str):
    return get_history(session_id)
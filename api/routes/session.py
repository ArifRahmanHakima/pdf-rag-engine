from fastapi import APIRouter, HTTPException
from api.services.memory import get_session_data

router = APIRouter()

@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get complete session data including PDF info and chat history"""
    try:
        session = get_session_data(session_id)
        
        if not session:
            return {
                "status": "not_found",
                "session": None
            }
        
        return {
            "status": "success",
            "session": session
        }
        
    except Exception as e:
        print(f"❌ Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

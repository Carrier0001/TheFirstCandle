from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["jury"])

@router.get("/jury/pending")
async def pending_jury():
    return {"message": "Jury system endpoints not fully implemented in this modular version yet"}
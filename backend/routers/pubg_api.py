from fastapi import APIRouter

router = APIRouter(prefix="/pubg", tags=["pubg"])


@router.get("/status")
def api_status():
    """PUBG API 연동 상태 확인용 엔드포인트 (이후 단계에서 구현)"""
    return {"status": "PUBG API router ready"}

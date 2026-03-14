from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import PlayerPosition

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/{map_name}/{phase}")
def get_positions(map_name: str, phase: int, db: Session = Depends(get_db)):
    """특정 맵과 페이즈의 포지션 데이터 조회"""
    positions = (
        db.query(PlayerPosition)
        .filter(
            PlayerPosition.map_name == map_name,
            PlayerPosition.phase == phase,
        )
        .all()
    )
    return [{"x": p.x, "y": p.y} for p in positions]

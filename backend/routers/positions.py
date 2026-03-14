import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import PlayerPosition
from clustering import cluster_positions

router = APIRouter(prefix="/positions", tags=["positions"])


# ── 응답 스키마 ──────────────────────────────────────
class PositionPoint(BaseModel):
    x: float
    y: float


class PositionsResponse(BaseModel):
    map_name: str
    phase: int
    total: int
    points: list[PositionPoint]


class ZoneStatsResponse(BaseModel):
    map_name: str
    phase: int
    total: int          # 해당 페이즈 전체 포인트 수
    inside: int         # 자기장 원 안 포인트 수
    percent: float      # inside / total * 100
    points: list[PositionPoint]


class ClusterItem(BaseModel):
    rank: int           # 순위 (1 = 1등 추천)
    cx: float           # 클러스터 중심 X (게임 좌표)
    cy: float           # 클러스터 중심 Y (게임 좌표)
    count: int          # 클러스터 포인트 수
    percent: float      # 해당 클러스터가 차지하는 비율 (%)


class ClustersResponse(BaseModel):
    map_name: str
    phase: int
    total_in_zone: int  # 자기장 원 안 전체 포인트 수
    clusters: list[ClusterItem]


# ── 엔드포인트 ───────────────────────────────────────

@router.get("/{map_name}/{phase}", response_model=PositionsResponse)
def get_positions(map_name: str, phase: int, db: Session = Depends(get_db)):
    """
    특정 맵 + 페이즈의 전체 포지션 데이터 반환
    예: GET /positions/Erangel/3
    """
    rows = (
        db.query(PlayerPosition)
        .filter(
            PlayerPosition.map_name == map_name,
            PlayerPosition.phase == phase,
        )
        .all()
    )
    points = [PositionPoint(x=r.x, y=r.y) for r in rows]
    return PositionsResponse(
        map_name=map_name,
        phase=phase,
        total=len(points),
        points=points,
    )


@router.get("/{map_name}/{phase}/zone", response_model=ZoneStatsResponse)
def get_zone_stats(
    map_name: str,
    phase: int,
    cx: float = Query(..., description="자기장 원 중심 X (게임 좌표)"),
    cy: float = Query(..., description="자기장 원 중심 Y (게임 좌표)"),
    radius: float = Query(..., description="자기장 원 반지름 (게임 좌표)"),
    db: Session = Depends(get_db),
):
    """
    자기장 원 안에 포함되는 포지션과 추천 확률 반환
    예: GET /positions/Erangel/3/zone?cx=400000&cy=400000&radius=100000
    """
    rows = (
        db.query(PlayerPosition)
        .filter(
            PlayerPosition.map_name == map_name,
            PlayerPosition.phase == phase,
        )
        .all()
    )

    all_points = [PositionPoint(x=r.x, y=r.y) for r in rows]
    inside = [
        p for p in all_points
        if math.hypot(p.x - cx, p.y - cy) <= radius
    ]
    total = len(all_points)
    percent = round(len(inside) / total * 100, 1) if total > 0 else 0.0

    return ZoneStatsResponse(
        map_name=map_name,
        phase=phase,
        total=total,
        inside=len(inside),
        percent=percent,
        points=inside,
    )


@router.get("/{map_name}/{phase}/clusters", response_model=ClustersResponse)
def get_clusters(
    map_name: str,
    phase: int,
    cx: float = Query(..., description="자기장 원 중심 X (게임 좌표)"),
    cy: float = Query(..., description="자기장 원 중심 Y (게임 좌표)"),
    radius: float = Query(..., description="자기장 원 반지름 (게임 좌표)"),
    top_n: int = Query(5, description="반환할 클러스터 최대 개수"),
    db: Session = Depends(get_db),
):
    """
    자기장 원 안의 포지션을 DBSCAN으로 클러스터링해서 상위 추천 포지션 반환
    예: GET /positions/Erangel/3/clusters?cx=400000&cy=400000&radius=100000
    """
    rows = (
        db.query(PlayerPosition)
        .filter(
            PlayerPosition.map_name == map_name,
            PlayerPosition.phase == phase,
        )
        .all()
    )

    # 자기장 원 안 포인트만 필터링
    inside_points = [
        {"x": r.x, "y": r.y}
        for r in rows
        if math.hypot(r.x - cx, r.y - cy) <= radius
    ]

    # DBSCAN 클러스터링
    results = cluster_positions(
        points=inside_points,
        zone_radius=radius,
        top_n=top_n,
    )

    clusters = [
        ClusterItem(
            rank=r.rank,
            cx=r.cx,
            cy=r.cy,
            count=r.count,
            percent=r.percent,
        )
        for r in results
    ]

    return ClustersResponse(
        map_name=map_name,
        phase=phase,
        total_in_zone=len(inside_points),
        clusters=clusters,
    )

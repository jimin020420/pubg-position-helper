import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import PositionRecord
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
    total: int
    inside: int
    percent: float
    points: list[PositionPoint]


class ClusterItem(BaseModel):
    rank: int
    cx: float
    cy: float
    count: int
    percent: float


class ClustersResponse(BaseModel):
    map_name: str
    phase: int
    total_in_zone: int
    clusters: list[ClusterItem]


class SearchResponse(BaseModel):
    map_name: str
    phase: int
    matched_matches: int   # 비슷한 자기장 매치 수
    total_points: int      # 반환된 포지션 수
    points: list[PositionPoint]


# ── 엔드포인트 ───────────────────────────────────────

@router.get("/{map_name}/{phase}", response_model=PositionsResponse)
def get_positions(map_name: str, phase: int, db: Session = Depends(get_db)):
    """특정 맵 + 페이즈의 전체 포지션 반환 (히트맵 초기 표시용)"""
    rows = (
        db.query(PositionRecord)
        .filter(
            PositionRecord.map_name == map_name,
            PositionRecord.phase == phase,
        )
        .all()
    )
    points = [PositionPoint(x=r.player_x, y=r.player_y) for r in rows]
    return PositionsResponse(map_name=map_name, phase=phase, total=len(points), points=points)


@router.get("/{map_name}/{phase}/zone", response_model=ZoneStatsResponse)
def get_zone_stats(
    map_name: str,
    phase: int,
    cx: float = Query(...),
    cy: float = Query(...),
    radius: float = Query(...),
    db: Session = Depends(get_db),
):
    """자기장 원 안에 포함되는 포지션 통계 (드래그로 직접 그린 원 기준)"""
    rows = (
        db.query(PositionRecord)
        .filter(PositionRecord.map_name == map_name, PositionRecord.phase == phase)
        .all()
    )
    all_points = [PositionPoint(x=r.player_x, y=r.player_y) for r in rows]
    inside = [p for p in all_points if math.hypot(p.x - cx, p.y - cy) <= radius]
    total = len(all_points)
    percent = round(len(inside) / total * 100, 1) if total > 0 else 0.0
    return ZoneStatsResponse(
        map_name=map_name, phase=phase,
        total=total, inside=len(inside), percent=percent, points=inside,
    )


@router.get("/{map_name}/{phase}/clusters", response_model=ClustersResponse)
def get_clusters(
    map_name: str,
    phase: int,
    cx: float = Query(...),
    cy: float = Query(...),
    radius: float = Query(...),
    top_n: int = Query(5),
    db: Session = Depends(get_db),
):
    """자기장 원 안 포지션을 DBSCAN 클러스터링해서 추천 포지션 반환"""
    rows = (
        db.query(PositionRecord)
        .filter(PositionRecord.map_name == map_name, PositionRecord.phase == phase)
        .all()
    )
    inside_points = [
        {"x": r.player_x, "y": r.player_y}
        for r in rows
        if math.hypot(r.player_x - cx, r.player_y - cy) <= radius
    ]
    results = cluster_positions(points=inside_points, zone_radius=radius, top_n=top_n)
    clusters = [
        ClusterItem(rank=r.rank, cx=r.cx, cy=r.cy, count=r.count, percent=r.percent)
        for r in results
    ]
    return ClustersResponse(
        map_name=map_name, phase=phase,
        total_in_zone=len(inside_points), clusters=clusters,
    )


@router.get("/{map_name}/{phase}/search", response_model=SearchResponse)
def search_by_zone(
    map_name: str,
    phase: int,
    cx: float = Query(..., description="자기장 중심 X (게임 좌표)"),
    cy: float = Query(..., description="자기장 중심 Y (게임 좌표)"),
    radius: float = Query(..., description="자기장 반지름 (게임 좌표)"),
    pos_tol: float = Query(50000, description="자기장 중심 허용 오차 (cm, 기본 500m)"),
    radius_tol: float = Query(0.3, description="반지름 허용 오차 비율 (기본 ±30%)"),
    db: Session = Depends(get_db),
):
    """
    유저가 지정한 자기장과 비슷한 위치/크기의 자기장이 있었던 과거 매치를 검색,
    그 매치들에서 플레이어들이 어디 포지션을 잡았는지 반환.

    검색 조건:
    - 자기장 중심 거리 <= pos_tol
    - |bluezone_radius - radius| / radius <= radius_tol
    """
    rows = (
        db.query(PositionRecord)
        .filter(PositionRecord.map_name == map_name, PositionRecord.phase == phase)
        .all()
    )

    matched_match_ids = set()
    matched_points: list[PositionPoint] = []

    for r in rows:
        dist = math.hypot(r.bluezone_x - cx, r.bluezone_y - cy)
        radius_diff = abs(r.bluezone_radius - radius) / radius if radius > 0 else 1.0

        if dist <= pos_tol and radius_diff <= radius_tol:
            matched_match_ids.add(r.match_id)
            matched_points.append(PositionPoint(x=r.player_x, y=r.player_y))

    return SearchResponse(
        map_name=map_name,
        phase=phase,
        matched_matches=len(matched_match_ids),
        total_points=len(matched_points),
        points=matched_points,
    )

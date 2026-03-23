"""
포지션 추천 API
================
GET /score   — 유저가 그린 자기장 기준으로 격자별 점수 계산 후 반환
GET /health  — DB 현황 확인용
"""

import math
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Bluezone, Position, Combat
import config

router = APIRouter(tags=["score"])


# ── 응답 스키마 ────────────────────────────────────────────────────────────────

class CellScore(BaseModel):
    rank:             int
    cx:               float      # 격자 중심 X (게임 좌표)
    cy:               float      # 격자 중심 Y (게임 좌표)
    sample_count:     int        # 이 격자에 포함된 포지션 수
    score:            float      # 종합 점수 (0~1)
    usage_rate:       float      # ① 사용률
    survival_rate:    float      # ② 생존율
    combat_survival:  float      # ③ 교전 생존율
    win_rate:         float      # ④ 우승 기여율
    low_confidence:   bool       # 샘플 5개 미만이면 True


class ScoreResponse(BaseModel):
    phase:            int
    matched_matches:  int        # 유사 자기장 매치 수
    total_positions:  int        # 조회된 총 포지션 수
    cells:            list[CellScore]


class HealthResponse(BaseModel):
    matches:   int
    positions: int
    combats:   int


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _cell_key(x: float, y: float) -> tuple[int, int]:
    """게임 좌표 → 격자 인덱스 (gi, gj)"""
    return int(x / config.GRID_CELL_SIZE), int(y / config.GRID_CELL_SIZE)


def _cell_center(gi: int, gj: int) -> tuple[float, float]:
    """격자 인덱스 → 격자 중심 게임 좌표"""
    return (gi + 0.5) * config.GRID_CELL_SIZE, (gj + 0.5) * config.GRID_CELL_SIZE


def _in_zone(x: float, y: float, cx: float, cy: float, radius: float) -> bool:
    return math.hypot(x - cx, y - cy) <= radius


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────

@router.get("/score", response_model=ScoreResponse)
def get_score(
    phase:     int   = Query(..., ge=2, le=8, description="페이즈 번호 (2~8)"),
    cx:        float = Query(..., description="자기장 중심 X (게임 좌표 cm)"),
    cy:        float = Query(..., description="자기장 중심 Y (게임 좌표 cm)"),
    radius:    float = Query(..., gt=0, description="자기장 반지름 (게임 좌표 cm)"),
    db: Session = Depends(get_db),
):
    """
    유저가 맵에 그린 자기장을 기준으로 과거 유사 자기장 매치를 검색하고,
    50×50m 격자별 포지션 점수를 계산해서 상위 격자 목록을 반환합니다.

    점수 = 사용률×w1 + 생존율×w2 + 교전생존율×w3 + 우승기여율×w4  (페이즈별 가중치 적용)
    """
    # ── Step 1: 유사 자기장 검색 ───────────────────────────────────────────────
    all_bz = db.query(Bluezone).filter(Bluezone.phase == phase).all()
    pos_tolerance = radius * config.POS_TOLERANCE_RATIO

    similar_match_ids: set[str] = set()
    for bz in all_bz:
        dist = math.hypot(bz.center_x - cx, bz.center_y - cy)
        if dist <= pos_tolerance:
            similar_match_ids.add(bz.match_id)

    if not similar_match_ids:
        # 유사 자기장 없으면 빈 결과 반환 (에러 아님)
        return ScoreResponse(
            phase=phase,
            matched_matches=0,
            total_positions=0,
            cells=[],
        )

    match_ids_list = list(similar_match_ids)

    # ── Step 2: 해당 매치들의 포지션·교전 데이터 조회 ─────────────────────────
    positions = (
        db.query(Position)
        .filter(Position.match_id.in_(match_ids_list), Position.phase == phase)
        .all()
    )
    combats = (
        db.query(Combat)
        .filter(Combat.match_id.in_(match_ids_list), Combat.phase == phase)
        .all()
    )

    if not positions:
        return ScoreResponse(
            phase=phase,
            matched_matches=len(similar_match_ids),
            total_positions=0,
            cells=[],
        )

    # ── Step 3: 격자별 포지션 분류 (자기장 원 내부만) ─────────────────────────
    # cell_data: (gi, gj) -> {"pos": [Position], "atk": int, "atk_survived": int}
    cell_data: dict[tuple, dict] = {}
    total_positions: int = 0  # 원 안 포지션만 카운트

    for pos in positions:
        if not _in_zone(pos.x, pos.y, cx, cy, radius):
            continue
        total_positions += 1
        key = _cell_key(pos.x, pos.y)
        if key not in cell_data:
            cell_data[key] = {"pos": [], "atk": 0, "atk_survived": 0}
        cell_data[key]["pos"].append(pos)

    if total_positions == 0:
        return ScoreResponse(
            phase=phase,
            matched_matches=len(similar_match_ids),
            total_positions=0,
            cells=[],
        )
    total_pos_f: float = float(total_positions)

    # ── Step 4: 격자별 교전 기록 분류 ─────────────────────────────────────────
    # 교전 위치가 해당 격자에 있으면 그 격자의 교전으로 집계
    for combat in combats:
        if not _in_zone(combat.x, combat.y, cx, cy, radius):
            continue
        key = _cell_key(combat.x, combat.y)
        if key not in cell_data:
            continue  # 포지션이 없는 격자는 집계하지 않음
        cell_data[key]["atk"]          += 1
        cell_data[key]["atk_survived"] += combat.attacker_survived

    # ── Step 5: 격자별 4가지 지표 + 종합 점수 계산 ────────────────────────────
    w_usage, w_survival, w_combat, w_win = config.get_weights(phase)
    scored_cells: list[dict] = []

    for (gi, gj), data in cell_data.items():
        pos_list = data["pos"]
        n        = len(pos_list)

        usage_rate      = n / total_pos_f
        survival_rate   = sum(p.survived_phase for p in pos_list) / n
        win_rate        = sum(p.won            for p in pos_list) / n

        atk = data["atk"]
        combat_survival = (data["atk_survived"] / atk
                           if atk > 0 else config.COMBAT_DEFAULT_SCORE)

        score = (
            w_usage    * usage_rate     +
            w_survival * survival_rate  +
            w_combat   * combat_survival +
            w_win      * win_rate
        )

        ccx, ccy = _cell_center(gi, gj)
        scored_cells.append({
            "cx":              ccx,
            "cy":              ccy,
            "sample_count":    n,
            "score":           round(score, 4),
            "usage_rate":      round(usage_rate,     4),
            "survival_rate":   round(survival_rate,  4),
            "combat_survival": round(combat_survival, 4),
            "win_rate":        round(win_rate,        4),
            "low_confidence":  n < config.MIN_SAMPLES_CONFIDENCE,
        })

    # ── Step 6: 신뢰도 낮은 격자 제외 → 점수 내림차순 정렬 → 상위 TOP_N_CELLS 반환
    scored_cells = [c for c in scored_cells if not c["low_confidence"]]
    scored_cells.sort(key=lambda c: c["score"], reverse=True)
    top_cells = scored_cells[: config.TOP_N_CELLS]

    cells = [
        CellScore(rank=i + 1, **cell)
        for i, cell in enumerate(top_cells)
    ]

    return ScoreResponse(
        phase=phase,
        matched_matches=len(similar_match_ids),
        total_positions=total_positions,
        cells=cells,
    )


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    """DB에 쌓인 데이터 현황 확인"""
    from models import Match
    return HealthResponse(
        matches   = db.query(Match).count(),
        positions = db.query(Position).count(),
        combats   = db.query(Combat).count(),
    )

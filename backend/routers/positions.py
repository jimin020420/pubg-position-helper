"""
포지션 추천 API
================
GET /score   — 유저가 그린 자기장 기준으로 격자별 점수 계산 후 반환
GET /health  — DB 현황 확인용
"""

import math
from fastapi import APIRouter, Depends, Query
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
    win_rate:         float      # ④ 우승 기여율 (5~7페이즈만)
    next_zone_rate:   float      # ⑤ 다음 자기장 겹칠 확률
    low_confidence:   bool       # 페이즈별 최소 샘플 미달이면 True


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
    map:       str   = Query("erangel", description="맵 이름 (erangel, miramar, sanhok 등)"),
    db: Session = Depends(get_db),
):
    """
    유저가 맵에 그린 자기장을 기준으로 과거 유사 자기장 매치를 검색하고,
    50×50m 격자별 포지션 점수를 계산해서 상위 격자 목록을 반환합니다.

    점수 = 사용률×w1 + 생존율×w2 + 교전생존율×w3 + 우승기여율×w4 + 다음자기장×w5
    (가중치는 페이즈별 차등 적용)
    """
    # ── Step 1: 유사 자기장 검색 ───────────────────────────────────────────────
    bz_query = db.query(Bluezone).filter(Bluezone.phase == phase)
    if map:
        bz_query = bz_query.filter(
            (Bluezone.map_name == map) | (Bluezone.map_name == None)  # noqa: E711
        )
    all_bz = bz_query.all()
    pos_tolerance = radius * config.get_pos_tolerance_ratio(phase)

    similar_match_ids: set[str] = set()
    for bz in all_bz:
        dist = math.hypot(bz.center_x - cx, bz.center_y - cy)
        if dist <= pos_tolerance:
            similar_match_ids.add(bz.match_id)

    if not similar_match_ids:
        return ScoreResponse(
            phase=phase, matched_matches=0, total_positions=0, cells=[]
        )

    match_ids_list = list(similar_match_ids)

    # ── Step 1.5: 다음 페이즈 자기장 사전 조회 ────────────────────────────────
    next_zones = (
        db.query(Bluezone)
        .filter(
            Bluezone.match_id.in_(match_ids_list),
            Bluezone.phase == phase + 1,
        )
        .all()
    )
    next_zone_map: dict[str, Bluezone] = {nz.match_id: nz for nz in next_zones}

    # ── Step 2: 해당 매치들의 포지션·교전 데이터 조회 ─────────────────────────
    pos_q = (
        db.query(Position)
        .filter(Position.match_id.in_(match_ids_list), Position.phase == phase)
    )
    if map:
        pos_q = pos_q.filter(
            (Position.map_name == map) | (Position.map_name == None)  # noqa: E711
        )
    positions = pos_q.all()

    cbt_q = (
        db.query(Combat)
        .filter(Combat.match_id.in_(match_ids_list), Combat.phase == phase)
    )
    if map:
        cbt_q = cbt_q.filter(
            (Combat.map_name == map) | (Combat.map_name == None)  # noqa: E711
        )
    combats = cbt_q.all()

    if not positions:
        return ScoreResponse(
            phase=phase,
            matched_matches=len(similar_match_ids),
            total_positions=0,
            cells=[],
        )

    # ── Step 3: 격자별 포지션 분류 (자기장 원 내부만) ─────────────────────────
    cell_data: dict[tuple, dict] = {}
    total_positions: int = 0

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
    for combat in combats:
        if not _in_zone(combat.x, combat.y, cx, cy, radius):
            continue
        key = _cell_key(combat.x, combat.y)
        if key not in cell_data:
            continue
        cell_data[key]["atk"]          += 1
        cell_data[key]["atk_survived"] += combat.attacker_survived

    # ── Step 5: 격자별 5지표 + 종합 점수 계산 ─────────────────────────────────
    w_usage, w_survival, w_combat, w_win, w_next = config.get_weights(phase)
    min_samples = config.get_min_samples(phase)
    scored_cells: list[dict] = []

    for (gi, gj), data in cell_data.items():
        pos_list = data["pos"]
        n        = len(pos_list)

        usage_rate    = n / total_pos_f
        survival_rate = sum(p.survived_phase for p in pos_list) / n

        # 우승 기여율: 5~7페이즈만 계산, 나머지 0
        matches_in_cell = {p.match_id for p in pos_list}
        if 5 <= phase <= 7:
            matches_with_win = {p.match_id for p in pos_list if p.won == 1}
            win_rate = len(matches_with_win) / len(matches_in_cell)
        else:
            win_rate = 0.0

        atk = data["atk"]
        combat_survival = (data["atk_survived"] / atk
                           if atk > 0 else config.COMBAT_DEFAULT_SCORE)

        # 다음 자기장 겹칠 확률
        cell_cx, cell_cy = _cell_center(gi, gj)
        if next_zone_map:
            hits = sum(
                1 for mid in matches_in_cell
                if mid in next_zone_map and
                math.hypot(
                    cell_cx - next_zone_map[mid].center_x,
                    cell_cy - next_zone_map[mid].center_y,
                ) <= next_zone_map[mid].radius
            )
            next_zone_rate = hits / len(matches_in_cell)
        else:
            next_zone_rate = config.NEXT_ZONE_DEFAULT_SCORE

        score = (
            w_usage    * usage_rate     +
            w_survival * survival_rate  +
            w_combat   * combat_survival +
            w_win      * win_rate        +
            w_next     * next_zone_rate
        )

        scored_cells.append({
            "cx":              cell_cx,
            "cy":              cell_cy,
            "sample_count":    n,
            "score":           round(score, 4),
            "usage_rate":      round(usage_rate,     4),
            "survival_rate":   round(survival_rate,  4),
            "combat_survival": round(combat_survival, 4),
            "win_rate":        round(win_rate,        4),
            "next_zone_rate":  round(next_zone_rate,  4),
            "low_confidence":  n < min_samples,
        })

    # ── Step 6: 신뢰도 낮은 격자 제외 → 점수 내림차순 → 상위 TOP_N_CELLS 반환
    scored_cells = [c for c in scored_cells if not c["low_confidence"]]
    scored_cells.sort(key=lambda c: c["score"], reverse=True)
    top_cells = scored_cells[: config.TOP_N_CELLS]

    cells = [CellScore(rank=i + 1, **cell) for i, cell in enumerate(top_cells)]

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

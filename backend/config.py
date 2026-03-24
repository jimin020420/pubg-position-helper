# ── 수집/집계 대상 페이즈 범위 (1페이즈 제외) ────────────────────────────────
MIN_PHASE = 2
MAX_PHASE = 8

# ── 페이즈별 점수 가중치 (합계 반드시 1.0) ───────────────────────────────────
# 형식: {(lo, hi): (사용률, 생존율, 교전생존율, 우승기여율, 다음자기장)}
PHASE_WEIGHTS: dict[tuple[int, int], tuple[float, float, float, float, float]] = {
    (2, 4): (0.35, 0.35, 0.30, 0.00, 0.00),
    (5, 7): (0.25, 0.30, 0.25, 0.10, 0.10),
    (8, 8): (0.20, 0.25, 0.20, 0.00, 0.35),
}

def get_weights(phase: int) -> tuple[float, float, float, float, float]:
    """페이즈에 맞는 가중치 반환 (w_usage, w_survival, w_combat, w_win, w_next)"""
    for (lo, hi), weights in PHASE_WEIGHTS.items():
        if lo <= phase <= hi:
            return weights
    raise ValueError(f"페이즈 범위 밖: {phase}")


def _validate_weights() -> None:
    """서버 시작 시 모든 페이즈 가중치 합이 1.0인지 검증"""
    for (lo, hi), weights in PHASE_WEIGHTS.items():
        total = sum(weights)
        assert abs(total - 1.0) < 1e-9, (
            f"페이즈 {lo}~{hi} 가중치 합이 1.0이 아님: {total} "
            f"(usage={weights[0]}, survival={weights[1]}, "
            f"combat={weights[2]}, win={weights[3]}, next={weights[4]})"
        )

_validate_weights()  # import 시점에 즉시 실행


# ── 페이즈별 자기장 유사도 허용 범위 (입력 반지름 × 비율) ───────────────────
POS_TOLERANCE_PER_PHASE: dict[tuple[int, int], float] = {
    (2, 3): 0.3,
    (4, 5): 0.4,
    (6, 7): 0.6,
    (8, 8): 0.8,
}

def get_pos_tolerance_ratio(phase: int) -> float:
    for (lo, hi), ratio in POS_TOLERANCE_PER_PHASE.items():
        if lo <= phase <= hi:
            return ratio
    return 0.5  # fallback


# ── 페이즈별 신뢰도 하한선 ────────────────────────────────────────────────────
MIN_SAMPLES_PER_PHASE: dict[tuple[int, int], int] = {
    (2, 3): 1,   # TODO: 데이터 충분히 쌓이면 30으로
    (4, 5): 1,   # TODO: 15로
    (6, 7): 1,   # TODO: 10으로
    (8, 8): 1,   # TODO: 5로
}

def get_min_samples(phase: int) -> int:
    for (lo, hi), n in MIN_SAMPLES_PER_PHASE.items():
        if lo <= phase <= hi:
            return n
    return 5  # fallback


# ── 교전 없는 격자 중립값 ────────────────────────────────────────────────────
COMBAT_DEFAULT_SCORE = 0.7  # 교전 기록이 없을 때 사용하는 기본 교전 생존율

# ── 다음 자기장 데이터 없을 때 중립값 ────────────────────────────────────────
NEXT_ZONE_DEFAULT_SCORE = 0.5

# ── 격자 설정 ────────────────────────────────────────────────────────────────
GAME_MAP_SIZE  = 816000    # cm (에란겔 전체 크기)
GRID_CELL_SIZE = 5000      # cm (50m × 50m 격자)
GRID_CELLS     = 163       # ceil(816000 / 5000) ≈ 163

# ── 반환 격자 수 ──────────────────────────────────────────────────────────────
TOP_N_CELLS = 10

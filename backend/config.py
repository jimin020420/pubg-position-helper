# ── 수집/집계 대상 페이즈 범위 (1페이즈 제외) ────────────────────────────────
MIN_PHASE = 2
MAX_PHASE = 8

# ── 페이즈별 점수 가중치 (이동 성공률 제거, 합계 반드시 1.0) ──────────────────
# 형식: {페이즈범위: (사용률, 생존율, 교전생존율, 우승기여율)}
PHASE_WEIGHTS: dict[tuple[int, int], tuple[float, float, float, float]] = {
    (2, 3): (0.50, 0.35, 0.15, 0.00),
    (4, 5): (0.35, 0.35, 0.20, 0.10),
    (6, 7): (0.25, 0.30, 0.20, 0.25),
    (8, 8): (0.15, 0.25, 0.20, 0.40),
}

def get_weights(phase: int) -> tuple[float, float, float, float]:
    """페이즈에 맞는 가중치 반환 (w_usage, w_survival, w_combat, w_win)"""
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
            f"combat={weights[2]}, win={weights[3]})"
        )

_validate_weights()  # import 시점에 즉시 실행


# ── 자기장 유사도 허용 범위 ───────────────────────────────────────────────────
# 입력 반지름 × 이 값 이내의 자기장을 유사 자기장으로 간주
POS_TOLERANCE_RATIO = 0.5   # 입력 반지름 × 0.5 이내

# ── 교전 없는 격자 중립값 ────────────────────────────────────────────────────
COMBAT_DEFAULT_SCORE = 0.7  # 교전 기록이 없을 때 사용하는 기본 교전 생존율

# ── 격자 설정 ────────────────────────────────────────────────────────────────
GAME_MAP_SIZE  = 816000    # cm (에란겔 전체 크기)
GRID_CELL_SIZE = 5000      # cm (50m × 50m 격자)
GRID_CELLS     = 163       # ceil(816000 / 5000) ≈ 163

# ── 신뢰도 기준 ──────────────────────────────────────────────────────────────
MIN_SAMPLES_CONFIDENCE = 5    # 이 수치 미만이면 low_confidence = True
TOP_N_CELLS            = 10   # 반환할 상위 격자 수

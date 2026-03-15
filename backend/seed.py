"""
DB 시드 스크립트 — 새 스키마 (PositionRecord) 기반 Mock 데이터 생성
=====================================================================
자기장 위치별 플레이어 포지션 검색 기능을 테스트하기 위해
여러 매치 × 여러 자기장 위치 조합의 Mock 데이터를 생성합니다.

실행 방법:
    cd backend
    python seed.py
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
from models import PositionRecord

# 에란겔 게임 좌표 범위 (cm)
GAME_SIZE = 816000

# 페이즈별 공식 자기장 반지름 (cm)
# 출처: PUBG 공식 White circle diameter → radius = diameter/2 * 100
PHASE_RADII = {
    1: 228235,
    2: 148355,
    3:  74175,
    4:  37090,
    5:  18545,
    6:   9270,
    7:   4635,
    8:   2320,
}

# 페이즈별 자기장 중심이 나타날 수 있는 게임 좌표 범위
# (반지름보다 안쪽에 중심이 있어야 맵 밖으로 나가지 않음)
PHASE_CENTER_RANGE = {
    phase: (GAME_SIZE * 0.1 + r, GAME_SIZE * 0.9 - r)
    for phase, r in PHASE_RADII.items()
}

MATCHES_PER_PHASE = 15   # 페이즈당 시뮬레이션할 매치 수
PLAYERS_PER_MATCH = 20   # 매치당 생존 플레이어 수 (포지션 데이터)
CLUSTERS_PER_MATCH = 3   # 플레이어들이 모이는 클러스터 수


def rand_center(phase: int) -> tuple:
    """해당 페이즈에서 자기장 중심이 될 수 있는 랜덤 좌표 반환"""
    lo, hi = PHASE_CENTER_RANGE[phase]
    return random.uniform(lo, hi), random.uniform(lo, hi)


def generate_players_in_zone(bz_x: float, bz_y: float, bz_r: float, count: int) -> list:
    """자기장 원 안에 클러스터링된 플레이어 위치 생성"""
    # 자기장 안 2~3곳에 핫스팟 생성
    n_clusters = min(CLUSTERS_PER_MATCH, count)
    hotspots = []
    for _ in range(n_clusters):
        # 핫스팟은 자기장 중심 60% 반경 이내
        angle = random.uniform(0, 2 * 3.14159)
        dist = random.uniform(0, bz_r * 0.6)
        hotspots.append((bz_x + dist * (dist ** 0.5 * 0 + 1) * (1 if angle < 3.14 else -1),
                         bz_y + dist * (1 if angle < 1.57 or angle > 4.71 else -1)))

    points = []
    spread = bz_r * 0.15  # 플레이어들이 퍼지는 정도
    for _ in range(count):
        hx, hy = random.choice(hotspots)
        points.append({
            "x": hx + random.gauss(0, spread),
            "y": hy + random.gauss(0, spread),
        })
    return points


def seed():
    # 기존 테이블 모두 삭제 후 재생성 (스키마 변경 반영)
    print("기존 테이블을 삭제하고 새 스키마로 재생성합니다...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    total = 0

    try:
        for phase, bz_radius in PHASE_RADII.items():
            for match_idx in range(MATCHES_PER_PHASE):
                match_id = f"mock-match-p{phase}-{match_idx:03d}"

                # 이 매치의 자기장 중심 (약간씩 다른 위치)
                bz_x, bz_y = rand_center(phase)

                # 자기장 반지름도 ±10% 변동 (실제처럼)
                radius_var = bz_radius * random.uniform(0.9, 1.1)

                # 플레이어 위치 생성
                players = generate_players_in_zone(bz_x, bz_y, radius_var, PLAYERS_PER_MATCH)

                for pt in players:
                    db.add(PositionRecord(
                        match_id=match_id,
                        map_name="Erangel",
                        phase=phase,
                        bluezone_x=bz_x,
                        bluezone_y=bz_y,
                        bluezone_radius=radius_var,
                        player_x=pt["x"],
                        player_y=pt["y"],
                    ))
                total += len(players)

            db.commit()
            print(f"  페이즈 {phase}: {MATCHES_PER_PHASE}개 매치 × {PLAYERS_PER_MATCH}명 = {MATCHES_PER_PHASE * PLAYERS_PER_MATCH}개 삽입")

        print(f"\n완료! 총 {total}개 Mock 포지션 데이터가 DB에 저장되었습니다.")
        print(f"  - 페이즈 8개 × 매치 {MATCHES_PER_PHASE}개 × 플레이어 {PLAYERS_PER_MATCH}명")
        print("\n백엔드를 실행하세요: uvicorn main:app --reload")

    finally:
        db.close()


if __name__ == "__main__":
    print("Mock 포지션 데이터를 DB에 삽입합니다...\n")
    seed()

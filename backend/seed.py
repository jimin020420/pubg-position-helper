"""
DB 시드 스크립트
실제 PUBG API 데이터가 없을 때 Mock 포지션 데이터를 SQLite에 채워 넣습니다.
Step 4(Telemetry 수집) 완료 후에는 이 스크립트 대신 실제 데이터를 사용합니다.

실행 방법:
    cd backend
    python seed.py
"""

import random
import sys
import os

# backend 폴더를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
from models import PlayerPosition

Base.metadata.create_all(bind=engine)

# 에란겔 게임 좌표 범위
GAME_SIZE = 816000

# 페이즈별 포지션 분포 설정 (좌표 범위 + 포인트 수)
PHASE_CONFIG = {
    1: dict(count=200, x_min=100000, x_max=700000, y_min=100000, y_max=700000),
    2: dict(count=180, x_min=150000, x_max=650000, y_min=150000, y_max=650000),
    3: dict(count=150, x_min=200000, x_max=600000, y_min=200000, y_max=600000),
    4: dict(count=120, x_min=250000, x_max=560000, y_min=250000, y_max=560000),
    5: dict(count=100, x_min=300000, x_max=510000, y_min=300000, y_max=510000),
    6: dict(count=80,  x_min=350000, x_max=470000, y_min=350000, y_max=470000),
    7: dict(count=60,  x_min=380000, x_max=440000, y_min=380000, y_max=440000),
    8: dict(count=40,  x_min=400000, x_max=420000, y_min=400000, y_max=420000),
}


def generate_clustered_points(count, x_min, x_max, y_min, y_max):
    """몇 개의 클러스터 주변에 포인트를 생성해서 실제 포지션처럼 보이게 합니다."""
    clusters = [
        {"x": x_min + (x_max - x_min) * 0.2, "y": y_min + (y_max - y_min) * 0.3},
        {"x": x_min + (x_max - x_min) * 0.6, "y": y_min + (y_max - y_min) * 0.5},
        {"x": x_min + (x_max - x_min) * 0.4, "y": y_min + (y_max - y_min) * 0.7},
        {"x": x_min + (x_max - x_min) * 0.8, "y": y_min + (y_max - y_min) * 0.2},
    ]
    spread = (x_max - x_min) * 0.08
    points = []
    for _ in range(count):
        c = random.choice(clusters)
        points.append({
            "x": c["x"] + (random.random() - 0.5) * spread,
            "y": c["y"] + (random.random() - 0.5) * spread,
        })
    return points


def seed():
    db = SessionLocal()
    try:
        existing = db.query(PlayerPosition).count()
        if existing > 0:
            print(f"이미 {existing}개의 데이터가 있습니다. 시드를 건너뜁니다.")
            print("데이터를 초기화하려면 pubg_positions.db 파일을 삭제 후 다시 실행하세요.")
            return

        total = 0
        for phase, cfg in PHASE_CONFIG.items():
            points = generate_clustered_points(
                cfg["count"], cfg["x_min"], cfg["x_max"], cfg["y_min"], cfg["y_max"]
            )
            for i, pt in enumerate(points):
                db.add(PlayerPosition(
                    map_name="Erangel",
                    phase=phase,
                    x=pt["x"],
                    y=pt["y"],
                    match_id=f"mock-match-phase{phase}-{i:03d}",
                    player_name=f"MockPlayer{i:03d}",
                ))
            total += len(points)
            print(f"  페이즈 {phase}: {len(points)}개 삽입")

        db.commit()
        print(f"\n완료! 총 {total}개 Mock 포지션 데이터가 DB에 저장되었습니다.")
        print("백엔드를 실행하세요: uvicorn main:app --reload")

    finally:
        db.close()


if __name__ == "__main__":
    print("Mock 포지션 데이터를 DB에 삽입합니다...\n")
    seed()

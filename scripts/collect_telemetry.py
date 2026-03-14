"""
PUBG Telemetry 데이터 수집 스크립트
- 상위 랭커들의 매치 데이터를 PUBG 공식 API에서 수집
- 자기장 페이즈별 위치 좌표를 DB에 저장

이후 단계(Step 4)에서 구현 예정
"""

# 사용 방법 (Step 4 완료 후):
# python collect_telemetry.py

import os
import sys

# 백엔드 경로를 Python 경로에 추가 (DB 모델 재사용)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))


def main():
    print("PUBG Telemetry 수집 스크립트 - Step 4에서 구현 예정")


if __name__ == "__main__":
    main()

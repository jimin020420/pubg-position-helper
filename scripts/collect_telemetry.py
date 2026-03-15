"""
PUBG Telemetry 수집 스크립트 (Step 4)
=====================================
상위 랭커들의 매치 Telemetry를 PUBG 공식 API로 수집해서
자기장 페이즈별 위치 좌표를 SQLite DB에 저장합니다.

실행 전 준비:
  1. backend/.env 파일에 PUBG_API_KEY 값 입력
  2. backend 가상환경 활성화 (backend/.venv/Scripts/activate)
  3. pip install -r backend/requirements.txt

실행 방법:
  cd scripts
  python collect_telemetry.py                    # 기본 (상위 50명, 매치 5개)
  python collect_telemetry.py --players 30 --matches 10  # 옵션 지정
  python collect_telemetry.py --dry-run          # 실제 저장 없이 테스트
"""

import argparse
import os
import sys
import time
import gzip
import json
import math
import logging

import httpx
from dotenv import load_dotenv

# backend 경로를 Python 경로에 추가 (DB 모델 재사용)
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from database import SessionLocal, engine, Base
from models import PlayerPosition

# ── 설정 ─────────────────────────────────────────────────────────────────────
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

PUBG_API_KEY = os.getenv("PUBG_API_KEY", "")
BASE_URL = "https://api.pubg.com/shards/steam"
HEADERS = {
    "Authorization": f"Bearer {PUBG_API_KEY}",
    "Accept": "application/vnd.api+json",
}

# Erangel 맵 이름 (API에서 반환하는 값)
ERANGEL_MAP_NAMES = {"Baltic_Main", "DihorOtok_Main"}  # Erangel, Erangel Remastered

# 페이즈 감지: safetyZoneRadius (cm 단위) 임계값
# PUBG 에란겔 기준 대략적 자기장 반지름 범위
PHASE_RADIUS_THRESHOLDS = [
    210000,  # phase 1 시작 (이상)
    160000,  # phase 2
    110000,  # phase 3
    80000,   # phase 4
    55000,   # phase 5
    35000,   # phase 6
    20000,   # phase 7
    0,       # phase 8
]

# API 속도 제한 (무료: 분당 10 요청)
REQUEST_INTERVAL = 7  # 초 (안전하게 7초 간격)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── PUBG API 호출 헬퍼 ────────────────────────────────────────────────────────

def api_get(client: httpx.Client, url: str, params: dict = None) -> dict:
    """
    PUBG API GET 요청. 속도 제한 초과 시 자동 재시도.
    """
    for attempt in range(3):
        resp = client.get(url, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            wait = 60
            log.warning(f"속도 제한 초과. {wait}초 대기 후 재시도...")
            time.sleep(wait)
            continue
        log.error(f"API 오류 {resp.status_code}: {url}")
        return {}
    return {}


# ── 데이터 수집 함수 ───────────────────────────────────────────────────────────

def get_current_season(client: httpx.Client) -> str:
    """현재 시즌 ID 조회"""
    data = api_get(client, f"{BASE_URL}/seasons")
    seasons = data.get("data", [])
    for s in seasons:
        if s.get("attributes", {}).get("isCurrentSeason"):
            season_id = s["id"]
            log.info(f"현재 시즌: {season_id}")
            return season_id
    # 현재 시즌이 없으면 마지막 시즌 반환
    return seasons[-1]["id"] if seasons else ""


def get_top_players(client: httpx.Client, season_id: str, top_n: int) -> list[str]:
    """
    랭크 리더보드에서 상위 N명의 플레이어 이름 목록 반환.
    게임 모드: squad-fpp (스쿼드 1인칭)
    """
    data = api_get(client, f"{BASE_URL}/leaderboards/{season_id}/squad-fpp")
    players = data.get("data", {}).get("relationships", {}).get("players", {}).get("data", [])
    included = {p["id"]: p for p in data.get("included", [])}

    names = []
    for p in players[:top_n]:
        player_data = included.get(p["id"], {})
        name = player_data.get("attributes", {}).get("name", "")
        if name:
            names.append(name)

    log.info(f"상위 플레이어 {len(names)}명 조회 완료")
    time.sleep(REQUEST_INTERVAL)
    return names


def get_player_match_ids(client: httpx.Client, player_names: list[str]) -> dict[str, list[str]]:
    """
    플레이어 이름 목록으로 최근 매치 ID 조회.
    한 번에 최대 10명씩 요청 가능.
    반환: { player_name: [match_id, ...] }
    """
    result = {}
    # 10명씩 나눠서 요청
    chunk_size = 10
    for i in range(0, len(player_names), chunk_size):
        chunk = player_names[i : i + chunk_size]
        data = api_get(
            client,
            f"{BASE_URL}/players",
            params={"filter[playerNames]": ",".join(chunk)},
        )
        for player in data.get("data", []):
            name = player.get("attributes", {}).get("name", "")
            match_ids = [
                m["id"]
                for m in player.get("relationships", {}).get("matches", {}).get("data", [])
            ]
            result[name] = match_ids[:5]  # 플레이어당 최신 매치 5개만
        time.sleep(REQUEST_INTERVAL)

    log.info(f"매치 ID 조회 완료: {sum(len(v) for v in result.values())}개")
    return result


def get_telemetry_url(client: httpx.Client, match_id: str) -> tuple[str, str]:
    """
    매치 ID로 Telemetry 다운로드 URL과 맵 이름 반환.
    반환: (telemetry_url, map_name)
    """
    data = api_get(client, f"{BASE_URL}/matches/{match_id}")
    if not data:
        return "", ""

    # 맵 이름 추출
    map_name = data.get("data", {}).get("attributes", {}).get("mapName", "")

    # Telemetry Asset URL 추출
    for asset in data.get("included", []):
        if asset.get("type") == "asset":
            url = asset.get("attributes", {}).get("URL", "")
            if url:
                return url, map_name

    return "", map_name


def download_telemetry(client: httpx.Client, url: str) -> list[dict]:
    """
    Telemetry JSON 다운로드 (gzip 압축 지원).
    반환: 이벤트 리스트
    """
    resp = client.get(url, timeout=120)
    if resp.status_code != 200:
        log.warning(f"Telemetry 다운로드 실패: {resp.status_code}")
        return []

    # Content-Encoding이 gzip인 경우
    content = resp.content
    try:
        if url.endswith(".gz") or resp.headers.get("Content-Encoding") == "gzip":
            content = gzip.decompress(content)
        return json.loads(content)
    except Exception as e:
        log.warning(f"Telemetry 파싱 실패: {e}")
        return []


# ── 페이즈 분석 ────────────────────────────────────────────────────────────────

def detect_phase_boundaries(events: list[dict]) -> list[float]:
    """
    LogGameStatePeriodic 이벤트를 분석해서 각 페이즈가 시작되는 타임스탬프 반환.
    반환: [phase1_start_time, phase2_start_time, ..., phase8_start_time]
    """
    game_states = [
        e for e in events if e.get("_T") == "LogGameStatePeriodic"
    ]
    if not game_states:
        return []

    # 타임스탬프 기준 정렬
    game_states.sort(key=lambda e: e.get("_D", ""))

    phase_starts = []
    prev_radius = None
    current_phase = 0

    for state in game_states:
        gs = state.get("gameState", {})
        radius = gs.get("safetyZoneRadius", 0)
        elapsed = gs.get("elapsedTime", 0)

        if prev_radius is None:
            prev_radius = radius
            continue

        # safetyZoneRadius가 이전보다 5% 이상 줄었으면 새 페이즈로 간주
        if prev_radius > 0 and radius < prev_radius * 0.95:
            current_phase += 1
            if current_phase <= 8:
                phase_starts.append(elapsed)
                log.debug(f"페이즈 {current_phase} 시작: elapsed={elapsed:.0f}s, radius={radius:.0f}")

        prev_radius = radius

    return phase_starts


def get_phase_from_elapsed(elapsed: float, phase_boundaries: list[float]) -> int:
    """
    경과 시간(elapsed)으로 현재 페이즈(1~8)를 반환.
    phase_boundaries: detect_phase_boundaries 결과
    """
    if not phase_boundaries:
        # 페이즈 경계를 못 찾으면 경과 시간으로 대략 추정 (에란겔 기준)
        # 대략 매 90~120초마다 페이즈 전환
        return min(8, max(1, int(elapsed / 100) + 1))

    phase = 1
    for i, boundary in enumerate(phase_boundaries):
        if elapsed >= boundary:
            phase = i + 2  # boundary[0]이 phase 2 시작
    return min(8, max(1, phase))


def extract_positions_by_phase(events: list[dict], phase_boundaries: list[float]) -> list[dict]:
    """
    LogPlayerPosition 이벤트에서 페이즈별 위치 좌표 추출.
    플레이어당 페이즈당 최대 1개 위치만 저장 (중복 방지).
    반환: [{ player_name, phase, x, y, match_id }, ...]
    """
    position_events = [
        e for e in events if e.get("_T") == "LogPlayerPosition"
    ]

    # 플레이어별, 페이즈별로 위치 수집 (여러 이벤트 평균)
    bucket: dict[tuple, list] = {}  # (player_name, phase) -> [(x, y)]

    for event in position_events:
        character = event.get("character", {})
        location = character.get("location", {})
        name = character.get("name", "")
        health = character.get("health", 0)
        elapsed = event.get("elapsedTime", 0)

        # 죽은 플레이어(health=0) 위치는 제외
        if health <= 0 or not name:
            continue

        x = location.get("x", 0)
        y = location.get("y", 0)

        phase = get_phase_from_elapsed(elapsed, phase_boundaries)
        key = (name, phase)
        bucket.setdefault(key, []).append((x, y))

    # 각 버킷에서 중간 위치 계산 (전체 평균 대신 중앙값으로 노이즈 줄이기)
    result = []
    for (player_name, phase), coords in bucket.items():
        # 중간 인덱스 위치 사용 (해당 페이즈 활동 중간 시점)
        mid = coords[len(coords) // 2]
        result.append({
            "player_name": player_name,
            "phase": phase,
            "x": mid[0],
            "y": mid[1],
        })

    return result


# ── DB 저장 ────────────────────────────────────────────────────────────────────

def save_positions(db, positions: list[dict], match_id: str, dry_run: bool = False) -> int:
    """
    추출된 포지션을 DB에 저장. 이미 수집된 매치는 건너뜀.
    반환: 저장된 레코드 수
    """
    # 이미 수집된 매치인지 확인
    existing = db.query(PlayerPosition).filter(
        PlayerPosition.match_id == match_id
    ).first()
    if existing:
        log.info(f"  이미 수집된 매치: {match_id[:20]}... (건너뜀)")
        return 0

    if dry_run:
        log.info(f"  [dry-run] {len(positions)}개 포지션 저장 생략")
        return len(positions)

    for pos in positions:
        db.add(PlayerPosition(
            map_name="Erangel",
            phase=pos["phase"],
            x=pos["x"],
            y=pos["y"],
            match_id=match_id,
            player_name=pos["player_name"],
        ))
    db.commit()
    return len(positions)


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(players=None, matches=None, dry_run=None):
    parser = argparse.ArgumentParser(description="PUBG Telemetry 수집 스크립트")
    parser.add_argument("--players",  type=int, default=50,    help="수집할 상위 랭커 수 (기본: 50)")
    parser.add_argument("--matches",  type=int, default=5,     help="플레이어당 매치 수 (기본: 5)")
    parser.add_argument("--dry-run",  action="store_true",     help="DB 저장 없이 테스트만 실행")
    parser.add_argument("--schedule", action="store_true",     help="하루 1회 자동 반복 실행")
    parser.add_argument("--time",     type=str, default="03:00", help="스케줄 실행 시각 (HH:MM, 기본: 03:00)")
    args = parser.parse_args()

    # 프로그래매틱 호출 시 인자 덮어쓰기
    if players  is not None: args.players  = players
    if matches  is not None: args.matches  = matches
    if dry_run  is not None: args.dry_run  = dry_run

    if not PUBG_API_KEY:
        print("\n오류: PUBG_API_KEY가 설정되지 않았습니다.")
        print("backend/.env 파일에 다음을 추가하세요:")
        print("  PUBG_API_KEY=your_api_key_here\n")
        sys.exit(1)

    log.info("=" * 55)
    log.info("PUBG Telemetry 수집 시작")
    log.info(f"  대상: 상위 {args.players}명 × 매치 {args.matches}개")
    log.info(f"  dry-run: {args.dry_run}")
    log.info("=" * 55)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        with httpx.Client() as client:
            # 1. 현재 시즌 조회
            season_id = get_current_season(client)
            if not season_id:
                log.error("시즌 정보를 가져올 수 없습니다.")
                return

            # 2. 상위 랭커 목록 조회
            top_players = get_top_players(client, season_id, args.players)
            if not top_players:
                log.error("상위 랭커 목록을 가져올 수 없습니다.")
                return

            # 3. 플레이어별 최근 매치 ID 조회
            player_matches = get_player_match_ids(client, top_players)

            # 4. 각 매치 Telemetry 수집
            total_saved = 0
            processed_matches = set()

            for player_name, match_ids in player_matches.items():
                log.info(f"\n플레이어: {player_name} ({len(match_ids)}개 매치)")

                for match_id in match_ids[:args.matches]:
                    if match_id in processed_matches:
                        continue
                    processed_matches.add(match_id)

                    log.info(f"  매치: {match_id[:20]}...")

                    # 4-1. Telemetry URL + 맵 이름 조회
                    telemetry_url, map_name = get_telemetry_url(client, match_id)
                    time.sleep(REQUEST_INTERVAL)

                    if not telemetry_url:
                        log.warning("  Telemetry URL 없음, 건너뜀")
                        continue

                    # 에란겔 맵만 처리
                    if map_name not in ERANGEL_MAP_NAMES:
                        log.info(f"  에란겔이 아닌 맵({map_name}), 건너뜀")
                        continue

                    # 4-2. Telemetry 다운로드 (크기가 크므로 시간이 걸릴 수 있음)
                    log.info("  Telemetry 다운로드 중...")
                    events = download_telemetry(client, telemetry_url)
                    if not events:
                        continue
                    log.info(f"  이벤트 {len(events):,}개 로드")

                    # 4-3. 페이즈 경계 감지
                    phase_boundaries = detect_phase_boundaries(events)
                    log.info(f"  페이즈 경계: {len(phase_boundaries)}개 감지")

                    # 4-4. 페이즈별 포지션 추출
                    positions = extract_positions_by_phase(events, phase_boundaries)
                    log.info(f"  추출된 포지션: {len(positions)}개")

                    # 4-5. DB 저장
                    saved = save_positions(db, positions, match_id, dry_run=args.dry_run)
                    total_saved += saved
                    log.info(f"  저장: {saved}개")

        log.info("\n" + "=" * 55)
        log.info(f"수집 완료! 총 {total_saved}개 포지션 저장됨")
        log.info("이제 백엔드를 재시작하면 실제 데이터가 적용됩니다.")
        log.info("=" * 55)

    finally:
        db.close()


if __name__ == "__main__":
    # --schedule 없으면 한 번만 실행
    import sys as _sys
    if "--schedule" in _sys.argv:
        import schedule as _schedule
        # argparse 먼저 실행해서 --time 값 파싱
        _parser = argparse.ArgumentParser(add_help=False)
        _parser.add_argument("--players",  type=int,  default=50)
        _parser.add_argument("--matches",  type=int,  default=5)
        _parser.add_argument("--dry-run",  action="store_true")
        _parser.add_argument("--time",     type=str,  default="03:00")
        _args, _ = _parser.parse_known_args()

        def _job():
            log.info(f"[스케줄러] 자동 수집 시작")
            main(players=_args.players, matches=_args.matches,
                 dry_run=_args.dry_run)

        _schedule.every().day.at(_args.time).do(_job)
        log.info(f"[스케줄러] 매일 {_args.time} 자동 수집 대기 중... (종료: Ctrl+C)")
        log.info(f"  설정: 상위 {_args.players}명 × {_args.matches}매치")

        # 시작 즉시 1회 실행 후 매일 반복
        _job()
        while True:
            _schedule.run_pending()
            time.sleep(30)
    else:
        main()

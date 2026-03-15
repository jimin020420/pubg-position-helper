"""
PUBG Telemetry 수집 스크립트
=====================================
상위 랭커들의 매치 Telemetry를 PUBG 공식 API로 수집해서
자기장 페이즈별 (자기장 위치 + 플레이어 위치)를 SQLite DB에 저장합니다.

핵심 개념:
  유저가 자기장 위치를 맵에 표시하면, 과거 데이터에서
  비슷한 위치/크기의 자기장이었던 매치들을 찾아
  그때 플레이어들이 어디 포지션을 잡았는지 히트맵으로 보여줍니다.

실행 전 준비:
  1. backend/.env 파일에 PUBG_API_KEY 값 입력
  2. backend 가상환경 활성화 (backend/.venv/Scripts/activate)
  3. pip install -r backend/requirements.txt

실행 방법:
  cd scripts
  python collect_telemetry.py                    # 기본 (상위 50명, 매치 5개)
  python collect_telemetry.py --players 30 --matches 10  # 옵션 지정
  python collect_telemetry.py --dry-run          # 실제 저장 없이 테스트
  python collect_telemetry.py --schedule         # 하루 1회 자동 실행 (03:00)
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
from models import PositionRecord

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

# API 속도 제한 (무료: 분당 10 요청)
REQUEST_INTERVAL = 7  # 초 (안전하게 7초 간격)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── PUBG API 호출 헬퍼 ────────────────────────────────────────────────────────

def api_get(client: httpx.Client, url: str, params: dict = None) -> dict:
    """PUBG API GET 요청. 속도 제한 초과 시 자동 재시도."""
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
    return seasons[-1]["id"] if seasons else ""


def get_top_players(client: httpx.Client, season_id: str, top_n: int) -> list:
    """랭크 리더보드에서 상위 N명의 플레이어 이름 목록 반환."""
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


def get_player_match_ids(client: httpx.Client, player_names: list) -> dict:
    """플레이어 이름 목록으로 최근 매치 ID 조회."""
    result = {}
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
            result[name] = match_ids[:5]
        time.sleep(REQUEST_INTERVAL)

    log.info(f"매치 ID 조회 완료: {sum(len(v) for v in result.values())}개")
    return result


def get_telemetry_url(client: httpx.Client, match_id: str) -> tuple:
    """매치 ID로 Telemetry 다운로드 URL과 맵 이름 반환."""
    data = api_get(client, f"{BASE_URL}/matches/{match_id}")
    if not data:
        return "", ""

    map_name = data.get("data", {}).get("attributes", {}).get("mapName", "")

    for asset in data.get("included", []):
        if asset.get("type") == "asset":
            url = asset.get("attributes", {}).get("URL", "")
            if url:
                return url, map_name

    return "", map_name


def download_telemetry(client: httpx.Client, url: str) -> list:
    """Telemetry JSON 다운로드 (gzip 압축 지원)."""
    resp = client.get(url, timeout=120)
    if resp.status_code != 200:
        log.warning(f"Telemetry 다운로드 실패: {resp.status_code}")
        return []

    content = resp.content
    try:
        if url.endswith(".gz") or resp.headers.get("Content-Encoding") == "gzip":
            content = gzip.decompress(content)
        return json.loads(content)
    except Exception as e:
        log.warning(f"Telemetry 파싱 실패: {e}")
        return []


# ── 페이즈 분석 ────────────────────────────────────────────────────────────────

def detect_phase_boundaries(events: list) -> list:
    """
    LogGameStatePeriodic 이벤트를 분석해서 각 페이즈가 시작되는 경과 시간 반환.
    반환: [phase2_start_elapsed, phase3_start_elapsed, ...]  (phase1 시작=0)
    """
    game_states = [e for e in events if e.get("_T") == "LogGameStatePeriodic"]
    if not game_states:
        return []

    game_states.sort(key=lambda e: e.get("_D", ""))

    phase_starts = []
    prev_radius = None

    for state in game_states:
        gs = state.get("gameState", {})
        radius = gs.get("safetyZoneRadius", 0)
        elapsed = gs.get("elapsedTime", 0)

        if prev_radius is None:
            prev_radius = radius
            continue

        # safetyZoneRadius가 이전보다 5% 이상 줄었으면 새 페이즈
        if prev_radius > 0 and radius < prev_radius * 0.95:
            if len(phase_starts) < 7:  # phase 2~8 시작점 (최대 7개)
                phase_starts.append(elapsed)
                log.debug(f"페이즈 {len(phase_starts)+1} 시작: elapsed={elapsed:.0f}s, radius={radius:.0f}")

        prev_radius = radius

    return phase_starts


def get_phase_from_elapsed(elapsed: float, phase_boundaries: list) -> int:
    """경과 시간으로 현재 페이즈(1~8) 반환."""
    if not phase_boundaries:
        return min(8, max(1, int(elapsed / 100) + 1))

    phase = 1
    for i, boundary in enumerate(phase_boundaries):
        if elapsed >= boundary:
            phase = i + 2
    return min(8, max(1, phase))


def extract_positions_by_phase(events: list, phase_boundaries: list) -> list:
    """
    LogGameStatePeriodic + LogPlayerPosition 이벤트에서
    페이즈별 (자기장 정보 + 플레이어 위치) 추출.

    반환: [
      {
        player_name, phase,
        bluezone_x, bluezone_y, bluezone_radius,  # 해당 페이즈의 자기장
        player_x, player_y                         # 해당 페이즈의 플레이어 위치
      }, ...
    ]
    """
    # 1. 페이즈별 자기장 정보 수집 (각 페이즈의 첫 번째 GameStatePeriodic 사용)
    game_states = [e for e in events if e.get("_T") == "LogGameStatePeriodic"]
    game_states.sort(key=lambda e: e.get("_D", ""))

    phase_bluezones: dict = {}  # phase -> (bz_x, bz_y, bz_radius)

    for state in game_states:
        gs = state.get("gameState", {})
        elapsed = gs.get("elapsedTime", 0)
        radius = gs.get("safetyZoneRadius", 0)

        if radius <= 0:
            continue

        phase = get_phase_from_elapsed(elapsed, phase_boundaries)
        if phase not in phase_bluezones:
            pos = gs.get("safetyZonePosition", {})
            bz_x = pos.get("x", 0)
            # PUBG 텔레메트리는 z축이 맵의 Y 방향
            bz_y = pos.get("z", 0)
            phase_bluezones[phase] = (bz_x, bz_y, radius)

    # 2. 플레이어별·페이즈별 위치 수집
    position_events = [e for e in events if e.get("_T") == "LogPlayerPosition"]

    bucket: dict = {}  # (player_name, phase) -> [(x, y)]

    for event in position_events:
        character = event.get("character", {})
        location = character.get("location", {})
        name = character.get("name", "")
        health = character.get("health", 0)
        elapsed = event.get("elapsedTime", 0)

        if health <= 0 or not name:
            continue

        x = location.get("x", 0)
        y = location.get("y", 0)

        phase = get_phase_from_elapsed(elapsed, phase_boundaries)
        key = (name, phase)
        bucket.setdefault(key, []).append((x, y))

    # 3. 각 버킷 중간 위치 + 자기장 정보 결합
    result = []
    for (player_name, phase), coords in bucket.items():
        mid = coords[len(coords) // 2]
        bz = phase_bluezones.get(phase)
        if bz is None:
            continue  # 자기장 정보 없는 페이즈는 저장 생략

        result.append({
            "player_name": player_name,
            "phase": phase,
            "bluezone_x":     bz[0],
            "bluezone_y":     bz[1],
            "bluezone_radius": bz[2],
            "player_x": mid[0],
            "player_y": mid[1],
        })

    return result


# ── DB 저장 ────────────────────────────────────────────────────────────────────

def save_positions(db, positions: list, match_id: str, dry_run: bool = False) -> int:
    """추출된 포지션을 DB에 저장. 이미 수집된 매치는 건너뜀."""
    existing = db.query(PositionRecord).filter(
        PositionRecord.match_id == match_id
    ).first()
    if existing:
        log.info(f"  이미 수집된 매치: {match_id[:20]}... (건너뜀)")
        return 0

    if dry_run:
        log.info(f"  [dry-run] {len(positions)}개 포지션 저장 생략")
        return len(positions)

    for pos in positions:
        db.add(PositionRecord(
            match_id=match_id,
            map_name="Erangel",
            phase=pos["phase"],
            bluezone_x=pos["bluezone_x"],
            bluezone_y=pos["bluezone_y"],
            bluezone_radius=pos["bluezone_radius"],
            player_x=pos["player_x"],
            player_y=pos["player_y"],
        ))
    db.commit()
    return len(positions)


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(players=None, matches=None, dry_run=None):
    parser = argparse.ArgumentParser(description="PUBG Telemetry 수집 스크립트")
    parser.add_argument("--players",  type=int, default=50,      help="수집할 상위 랭커 수 (기본: 50)")
    parser.add_argument("--matches",  type=int, default=5,       help="플레이어당 매치 수 (기본: 5)")
    parser.add_argument("--dry-run",  action="store_true",       help="DB 저장 없이 테스트만 실행")
    parser.add_argument("--schedule", action="store_true",       help="하루 1회 자동 반복 실행")
    parser.add_argument("--time",     type=str, default="03:00", help="스케줄 실행 시각 (HH:MM, 기본: 03:00)")
    args = parser.parse_args()

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
            season_id = get_current_season(client)
            if not season_id:
                log.error("시즌 정보를 가져올 수 없습니다.")
                return

            top_players = get_top_players(client, season_id, args.players)
            if not top_players:
                log.error("상위 랭커 목록을 가져올 수 없습니다.")
                return

            player_matches = get_player_match_ids(client, top_players)

            total_saved = 0
            processed_matches = set()

            for player_name, match_ids in player_matches.items():
                log.info(f"\n플레이어: {player_name} ({len(match_ids)}개 매치)")

                for match_id in match_ids[:args.matches]:
                    if match_id in processed_matches:
                        continue
                    processed_matches.add(match_id)

                    log.info(f"  매치: {match_id[:20]}...")

                    telemetry_url, map_name = get_telemetry_url(client, match_id)
                    time.sleep(REQUEST_INTERVAL)

                    if not telemetry_url:
                        log.warning("  Telemetry URL 없음, 건너뜀")
                        continue

                    if map_name not in ERANGEL_MAP_NAMES:
                        log.info(f"  에란겔이 아닌 맵({map_name}), 건너뜀")
                        continue

                    log.info("  Telemetry 다운로드 중...")
                    events = download_telemetry(client, telemetry_url)
                    if not events:
                        continue
                    log.info(f"  이벤트 {len(events):,}개 로드")

                    phase_boundaries = detect_phase_boundaries(events)
                    log.info(f"  페이즈 경계: {len(phase_boundaries)}개 감지")

                    positions = extract_positions_by_phase(events, phase_boundaries)
                    log.info(f"  추출된 포지션: {len(positions)}개")

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
    if "--schedule" in sys.argv:
        import schedule as _schedule

        _parser = argparse.ArgumentParser(add_help=False)
        _parser.add_argument("--players",  type=int,  default=50)
        _parser.add_argument("--matches",  type=int,  default=5)
        _parser.add_argument("--dry-run",  action="store_true")
        _parser.add_argument("--time",     type=str,  default="03:00")
        _args, _ = _parser.parse_known_args()

        def _job():
            log.info("[스케줄러] 자동 수집 시작")
            main(players=_args.players, matches=_args.matches, dry_run=_args.dry_run)

        _schedule.every().day.at(_args.time).do(_job)
        log.info(f"[스케줄러] 매일 {_args.time} 자동 수집 대기 중... (종료: Ctrl+C)")

        _job()  # 시작 즉시 1회 실행
        while True:
            _schedule.run_pending()
            time.sleep(30)
    else:
        main()

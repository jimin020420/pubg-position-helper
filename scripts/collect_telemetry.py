"""
PUBG Telemetry 수집 스크립트
=====================================
상위 랭커들의 매치 Telemetry를 PUBG 공식 API로 수집해서
4개 테이블(matches / bluezones / positions / combats)에 저장합니다.

실행 전 준비:
  1. backend/.env 파일에 PUBG_API_KEY 값 입력
  2. backend 가상환경 활성화 (backend/.venv/Scripts/activate)

실행 방법:
  cd scripts
  python collect_telemetry.py --reset-db                        # DB 초기화
  python collect_telemetry.py --names 닉네임1,닉네임2 --dry-run  # 저장 없이 테스트
  python collect_telemetry.py --names 닉네임1,닉네임2 --matches 10
"""

import argparse
import os
import sys
import time
import gzip
import json
import math
import logging
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

# backend 경로를 Python 경로에 추가 (DB 모델 재사용)
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from database import SessionLocal, engine, Base
import models  # noqa: F401 — Base.metadata에 4개 테이블 등록용
from models import Match, Bluezone, Position, Combat

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
REQUEST_INTERVAL = 7  # 초

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
            result[name] = match_ids
        time.sleep(REQUEST_INTERVAL)

    log.info(f"매치 ID 조회 완료: {sum(len(v) for v in result.values())}개")
    return result


def get_telemetry_url(client: httpx.Client, match_id: str) -> tuple:
    """매치 ID로 Telemetry URL, 맵 이름, 날짜, 총 참가자 수 반환."""
    data = api_get(client, f"{BASE_URL}/matches/{match_id}")
    if not data:
        return "", "", None, 0

    attrs    = data.get("data", {}).get("attributes", {})
    map_name = attrs.get("mapName", "")
    date_str = attrs.get("createdAt", "")

    # 날짜 파싱
    match_date = None
    if date_str:
        try:
            match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    # 총 참가자 수
    participants = data.get("data", {}).get("relationships", {}).get("participants", {}).get("data", [])
    total_players = len(participants)

    # Telemetry URL
    for asset in data.get("included", []):
        if asset.get("type") == "asset":
            url = asset.get("attributes", {}).get("URL", "")
            if url:
                return url, map_name, match_date, total_players

    return "", map_name, match_date, total_players


def download_telemetry(client: httpx.Client, url: str) -> list:
    """Telemetry JSON 다운로드 (gzip 압축 자동 감지)."""
    resp = client.get(url, timeout=120)
    if resp.status_code != 200:
        log.warning(f"Telemetry 다운로드 실패: {resp.status_code}")
        return []

    content = resp.content
    try:
        try:
            content = gzip.decompress(content)
        except Exception:
            pass  # plain JSON이면 그대로 사용
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
    prev_elapsed = -999

    for state in game_states:
        gs = state.get("gameState", {})
        radius = gs.get("safetyZoneRadius", 0)
        elapsed = gs.get("elapsedTime", 0)

        if prev_radius is None:
            prev_radius = radius
            continue

        # safetyZoneRadius가 5% 이상 줄고, 직전 경계로부터 60초 이상 지난 경우에만 새 페이즈
        if prev_radius > 0 and radius < prev_radius * 0.95:
            if len(phase_starts) < 7 and (elapsed - prev_elapsed) > 60:
                phase_starts.append(elapsed)
                prev_elapsed = elapsed
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


# ── Telemetry 이벤트 추출 ──────────────────────────────────────────────────────

def _get_player_id(character: dict) -> str:
    """accountId 우선, 없으면 name 사용 (구버전 텔레메트리 호환)."""
    return character.get("accountId") or character.get("name", "")


def extract_bluezones_by_phase(events: list, phase_boundaries: list) -> dict:
    """
    LogGameStatePeriodic에서 페이즈별 자기장 정보 추출.
    반환: {phase: {"center_x": x, "center_y": y, "radius": r}}
    """
    game_states = [e for e in events if e.get("_T") == "LogGameStatePeriodic"]
    game_states.sort(key=lambda e: e.get("_D", ""))

    result = {}
    for state in game_states:
        gs = state.get("gameState", {})
        elapsed = gs.get("elapsedTime", 0)
        radius = gs.get("safetyZoneRadius", 0)
        if radius <= 0:
            continue

        phase = get_phase_from_elapsed(elapsed, phase_boundaries)
        if phase not in result:
            pos = gs.get("safetyZonePosition", {})
            result[phase] = {
                "center_x": pos.get("x", 0),
                "center_y": pos.get("z", 0),  # PUBG 텔레메트리는 z축이 맵의 Y
                "radius":   radius,
            }

    return result


def extract_position_events(events: list, phase_boundaries: list) -> list:
    """
    LogPlayerPosition에서 페이즈별 플레이어 위치 추출.
    각 (player_id, phase) 버킷의 중간 위치를 사용.
    반환: [{"player_id", "phase", "x", "y"}]
    """
    position_events = [e for e in events if e.get("_T") == "LogPlayerPosition"]

    bucket: dict = {}  # (player_id, phase) -> [(x, y)]
    for event in position_events:
        character = event.get("character", {})
        if character.get("health", 0) <= 0:
            continue

        player_id = _get_player_id(character)
        if not player_id:
            continue

        loc   = character.get("location", {})
        x     = loc.get("x", 0)
        y     = loc.get("y", 0)
        phase = get_phase_from_elapsed(event.get("elapsedTime", 0), phase_boundaries)

        bucket.setdefault((player_id, phase), []).append((x, y))

    result = []
    for (player_id, phase), coords in bucket.items():
        mid = coords[len(coords) // 2]
        result.append({"player_id": player_id, "phase": phase, "x": mid[0], "y": mid[1]})

    return result


def extract_kill_events(events: list, phase_boundaries: list) -> list:
    """
    LogPlayerKill에서 교전 기록 추출.
    killer가 없는 경우(자기장/추락사 등)는 건너뜀.
    반환: [{"phase", "x", "y", "attacker_id", "victim_id"}]
    """
    kill_events = [e for e in events if e.get("_T") == "LogPlayerKill"]

    result = []
    for event in kill_events:
        killer = event.get("killer")
        victim = event.get("victim")

        if not killer or not victim:
            continue  # 환경사(자기장/추락/차량)는 건너뜀

        attacker_id = _get_player_id(killer)
        victim_id   = _get_player_id(victim)
        if not attacker_id or not victim_id:
            continue

        loc   = killer.get("location", {})
        phase = get_phase_from_elapsed(event.get("elapsedTime", 0), phase_boundaries)

        result.append({
            "phase":       phase,
            "x":           loc.get("x", 0),
            "y":           loc.get("y", 0),
            "attacker_id": attacker_id,
            "victim_id":   victim_id,
        })

    return result


def extract_match_statistics(events: list) -> dict:
    """
    LogMatchStatistics에서 플레이어별 최종 순위·우승 여부 추출.
    없으면 LogPlayerKill로 사망자를 추적해 winner 추론.
    반환: {player_id: {"final_rank": int|None, "won": 0|1}}
    """
    stats_events = [e for e in events if e.get("_T") == "LogMatchStatistics"]

    if stats_events:
        result = {}
        for event in stats_events:
            for player in event.get("players", []):
                pid  = _get_player_id(player)
                rank = player.get("ranking") or player.get("rank")
                if pid:
                    result[pid] = {
                        "final_rank": rank,
                        "won": 1 if rank == 1 else 0,
                    }
        if result:
            return result

    # Fallback: LogPlayerKill로 사망자 집합 파악 → 생존자 = 우승자
    killed_ids = set()
    for event in events:
        if event.get("_T") != "LogPlayerKill":
            continue
        victim = event.get("victim")
        if victim:
            pid = _get_player_id(victim)
            if pid:
                killed_ids.add(pid)

    # 포지션 이벤트에 등장한 모든 플레이어
    all_players = set()
    for event in events:
        if event.get("_T") != "LogPlayerPosition":
            continue
        character = event.get("character", {})
        pid = _get_player_id(character)
        if pid:
            all_players.add(pid)

    result = {}
    for pid in all_players:
        won = 0 if pid in killed_ids else 1
        result[pid] = {"final_rank": None, "won": won}

    return result


# ── DB 저장 ────────────────────────────────────────────────────────────────────

def save_match_data(
    db,
    match_id: str,
    match_date,
    total_players: int,
    bluezones: dict,
    positions: list,
    kills: list,
    stats: dict,
    dry_run: bool = False,
) -> int:
    """
    매치 데이터를 4개 테이블에 저장.
    이미 수집된 매치면 건너뜀.
    반환: 저장된 포지션 수
    """
    # 중복 매치 확인
    if db.query(Match).filter(Match.match_id == match_id).first():
        log.info(f"  이미 수집된 매치: {match_id[:20]}... (건너뜀)")
        return 0

    if dry_run:
        log.info(f"  [dry-run] positions={len(positions)}, kills={len(kills)} 저장 생략")
        return len(positions)

    # ── survived_phase 계산 (2-pass) ──────────────────────────────────────────
    # 다음 페이즈에 등장하는 (player_id, phase) 쌍 → 현재 페이즈 survived = 1
    next_phase_set = {(p["player_id"], p["phase"]) for p in positions}
    for pos in positions:
        # (player_id, phase+1)이 존재하면 이 페이즈를 살아서 넘긴 것
        pos["survived_phase"] = 1 if (pos["player_id"], pos["phase"] + 1) in next_phase_set else 0

    # ── 저장 ─────────────────────────────────────────────────────────────────
    db.add(Match(
        match_id=match_id,
        date=match_date,
        total_players=total_players,
    ))

    for phase, bz in bluezones.items():
        db.add(Bluezone(
            match_id=match_id,
            phase=phase,
            center_x=bz["center_x"],
            center_y=bz["center_y"],
            radius=bz["radius"],
        ))

    for pos in positions:
        player_stat = stats.get(pos["player_id"], {})
        db.add(Position(
            match_id=match_id,
            phase=pos["phase"],
            player_id=pos["player_id"],
            x=pos["x"],
            y=pos["y"],
            final_rank=player_stat.get("final_rank"),
            survived_phase=pos["survived_phase"],
            won=player_stat.get("won", 0),
        ))

    for kill in kills:
        attacker_stat = stats.get(kill["attacker_id"], {})
        db.add(Combat(
            match_id=match_id,
            phase=kill["phase"],
            x=kill["x"],
            y=kill["y"],
            attacker_id=kill["attacker_id"],
            victim_id=kill["victim_id"],
            attacker_survived=attacker_stat.get("won", 0),
        ))

    db.commit()
    return len(positions)


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PUBG Telemetry 수집 스크립트")
    parser.add_argument(
        "--names", type=str, default="",
        help="수집할 플레이어 닉네임 (쉼표 구분, 필수). 예: --names PlayerA,PlayerB",
    )
    parser.add_argument("--matches",  type=int,          default=5,     help="플레이어당 수집할 매치 수 (기본: 5)")
    parser.add_argument("--dry-run",  action="store_true",              help="DB 저장 없이 테스트만 실행")
    parser.add_argument("--reset-db", action="store_true",              help="DB 초기화 (기존 데이터 전부 삭제)")
    args = parser.parse_args()

    # ── DB 초기화 모드 ────────────────────────────────────────────────────────
    if args.reset_db:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        log.info("DB 초기화 완료. matches / bluezones / positions / combats 테이블이 생성되었습니다.")
        sys.exit(0)

    if not PUBG_API_KEY:
        print("\n오류: PUBG_API_KEY가 설정되지 않았습니다.")
        print("backend/.env 파일에 다음을 추가하세요:")
        print("  PUBG_API_KEY=your_api_key_here\n")
        sys.exit(1)

    if not args.names:
        log.error("--names 옵션이 필요합니다. 예: --names PlayerA,PlayerB,PlayerC")
        sys.exit(1)

    log.info("=" * 55)
    log.info("PUBG Telemetry 수집 시작")
    log.info(f"  dry-run: {args.dry_run}")
    log.info("=" * 55)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        with httpx.Client() as client:
            # ── 플레이어 닉네임으로 매치 ID 수집 ─────────────────────────────
            names = [n.strip() for n in args.names.split(",") if n.strip()]
            log.info(f"  플레이어: {', '.join(names)}")
            player_matches = get_player_match_ids(client, names)

            all_match_ids = []
            for match_ids in player_matches.values():
                all_match_ids.extend(match_ids[:args.matches])
            all_match_ids = list(dict.fromkeys(all_match_ids))  # 중복 제거
            log.info(f"  처리할 매치: {len(all_match_ids)}개")

            total_saved = 0

            for match_id in all_match_ids:
                log.info(f"  매치: {match_id[:20]}...")

                telemetry_url, map_name, match_date, total_players = get_telemetry_url(client, match_id)
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

                bluezones  = extract_bluezones_by_phase(events, phase_boundaries)
                positions  = extract_position_events(events, phase_boundaries)
                kills      = extract_kill_events(events, phase_boundaries)
                match_stats = extract_match_statistics(events)

                log.info(f"  bluezones={len(bluezones)}, positions={len(positions)}, kills={len(kills)}, players_stats={len(match_stats)}")

                saved = save_match_data(
                    db, match_id, match_date, total_players,
                    bluezones, positions, kills, match_stats,
                    dry_run=args.dry_run,
                )
                total_saved += saved
                log.info(f"  저장: {saved}개 포지션")

        log.info("\n" + "=" * 55)
        log.info(f"수집 완료! 총 {total_saved}개 포지션 저장됨")
        log.info("이제 백엔드를 재시작하면 실제 데이터가 적용됩니다.")
        log.info("=" * 55)

    finally:
        db.close()


if __name__ == "__main__":
    main()

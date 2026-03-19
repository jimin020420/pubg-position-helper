"""
자동 수집 스케줄러
================================
매일 지정한 시각에 collect_telemetry.py 를 자동으로 실행합니다.

실행 방법:
  cd scripts
  python scheduler.py                  # 기본: 매일 새벽 3시 실행
  python scheduler.py --time 06:00     # 매일 오전 6시 실행
  python scheduler.py --run-now        # 즉시 1회 실행 후 스케줄 대기
  python scheduler.py --run-now --once # 즉시 1회만 실행하고 종료

설정:
  SCHEDULER_PLAYERS 환경변수에 수집할 플레이어 닉네임을 쉼표로 입력하세요.
  backend/.env 예시:
    SCHEDULER_PLAYERS=PlayerA,PlayerB,PlayerC
    SCHEDULER_MATCHES=10
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import schedule
import time

# ── 경로 설정 ──────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPTS_DIR.parent / "backend"
LOG_DIR     = SCRIPTS_DIR.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── 로깅 설정 ──────────────────────────────────────────────────────────────────
log_file = LOG_DIR / "scheduler.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_env() -> dict:
    """backend/.env 에서 환경변수 로드."""
    env_path = BACKEND_DIR / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def run_collection():
    """collect_telemetry.py 를 서브프로세스로 실행."""
    env_vars = load_env()

    players = env_vars.get("SCHEDULER_PLAYERS", "").strip()
    if not players:
        log.error(
            "SCHEDULER_PLAYERS 가 설정되지 않았습니다.\n"
            "backend/.env 에 다음을 추가하세요:\n"
            "  SCHEDULER_PLAYERS=닉네임1,닉네임2,닉네임3"
        )
        return

    matches = env_vars.get("SCHEDULER_MATCHES", "10")

    python  = sys.executable
    script  = str(SCRIPTS_DIR / "collect_telemetry.py")
    cmd     = [python, script, "--names", players, "--matches", matches]

    log.info("=" * 55)
    log.info(f"수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"  플레이어: {players}")
    log.info(f"  매치 수: {matches}")
    log.info("=" * 55)

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # 터미널에 실시간 출력
            text=True,
            cwd=str(SCRIPTS_DIR),
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            log.info(f"수집 완료 (소요 시간: {elapsed:.0f}초)")
        else:
            log.error(f"수집 실패 (종료 코드: {result.returncode}, 소요 시간: {elapsed:.0f}초)")
    except Exception as e:
        log.error(f"실행 오류: {e}")


def main():
    parser = argparse.ArgumentParser(description="PUBG 자동 수집 스케줄러")
    parser.add_argument(
        "--time", type=str, default="03:00",
        help="매일 실행할 시각 (HH:MM 형식, 기본: 03:00)",
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="시작 즉시 1회 실행 후 스케줄 대기",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="--run-now 와 함께 사용: 1회만 실행하고 종료",
    )
    args = parser.parse_args()

    # 시각 형식 검증
    try:
        datetime.strptime(args.time, "%H:%M")
    except ValueError:
        log.error("--time 은 HH:MM 형식이어야 합니다. 예: 03:00")
        sys.exit(1)

    if args.run_now:
        log.info("즉시 1회 실행합니다.")
        run_collection()
        if args.once:
            log.info("--once 옵션: 1회 실행 후 종료합니다.")
            return

    # 스케줄 등록
    schedule.every().day.at(args.time).do(run_collection)
    log.info(f"스케줄러 시작: 매일 {args.time} 에 자동 수집 실행")
    log.info(f"로그 파일: {log_file}")
    log.info("종료하려면 Ctrl+C 를 누르세요.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("스케줄러 종료.")


if __name__ == "__main__":
    main()

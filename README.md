# PUBG 포지션 추천 웹앱

에란겔 맵에서 자기장 위치를 클릭하면, 과거 비슷한 자기장이었던 매치 데이터를 분석해 **각 자리의 추천 점수를 히트맵으로 보여주는** 웹 서비스입니다.

---

## 핵심 개념

유저가 현재 자기장 위치를 맵에 그리면 → 과거 유사 자기장 매치를 검색 → 격자별 포지션 점수 계산 → 히트맵 표시

### 점수 계산 방식 (5가지 지표 종합)

| 지표 | 가중치 | 설명 |
|------|--------|------|
| ① 사용률 | 0.20 | 얼마나 많이 쓰인 자리인가 |
| ② 생존율 | 0.30 | 거기 있다가 살아남은 비율 |
| ③ 교전 생존율 | 0.20 | 교전 시 이긴 비율 |
| ④ 우승 기여율 | 0.20 | 거기 쓴 사람 중 우승 비율 |
| ⑤ 이동 성공률 | 0.10 | 다음 자기장으로 이동 성공 비율 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React 18 + Vite, Leaflet.js (react-leaflet) |
| 백엔드 | FastAPI, SQLAlchemy, SQLite |
| 데이터 수집 | PUBG 공식 API + httpx |
| 스케줄러 | schedule 라이브러리 |

---

## 프로젝트 구조

```
my-pubg-project/
├── frontend/                     # React + Vite 프론트엔드
│   ├── src/
│   │   ├── App.jsx               # 메인 앱 (Leaflet 맵, 자기장 클릭, 히트맵)
│   │   └── components/
│   │       └── PhaseSelector.jsx # 페이즈 선택 UI
│   └── public/maps/
│       └── erangel.png           # 에란겔 맵 이미지
│
├── backend/                      # FastAPI 백엔드
│   ├── main.py                   # 앱 진입점 + CORS 설정
│   ├── models.py                 # DB 테이블 정의 (4개 테이블)
│   ├── database.py               # SQLite 연결 설정
│   ├── config.py                 # 점수 가중치 및 격자 설정
│   ├── routers/
│   │   └── positions.py          # GET /score, GET /health 엔드포인트
│   ├── seed.py                   # Mock 데이터 삽입 (테스트용)
│   └── requirements.txt
│
├── scripts/
│   ├── collect_telemetry.py      # PUBG API 데이터 수집 스크립트
│   └── scheduler.py              # 자동 수집 스케줄러
│
└── logs/                         # 스케줄러 실행 로그 (자동 생성)
```

---

## DB 구조

```
matches    — match_id, date, total_players
bluezones  — match_id, phase, center_x, center_y, radius
positions  — match_id, phase, player_id, x, y, final_rank, survived_phase, won
combats    — match_id, phase, x, y, attacker_id, victim_id, attacker_survived
```

---

## 실행 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/jimin020420/pubg-position-helper.git
cd pubg-position-helper
```

### 2. 환경변수 설정

```bash
cp .env.example backend/.env
# backend/.env 파일을 열어 PUBG_API_KEY 값을 입력하세요
```

### 3. 백엔드 실행

```bash
cd backend

# 가상환경 생성 (최초 1회)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

# 패키지 설치 (최초 1회)
pip install -r requirements.txt

# DB 초기화 (최초 1회 또는 스키마 변경 시)
cd ../scripts
python collect_telemetry.py --reset-db
cd ../backend

# 백엔드 서버 실행
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs (Swagger API 문서)
```

### 4. 프론트엔드 실행

```bash
cd frontend

# 패키지 설치 (최초 1회)
npm install

# 개발 서버 실행
npm run dev
# → http://localhost:5173
```

### 5. 데이터 수집

```bash
cd scripts

# 테스트 (DB 저장 없음)
python collect_telemetry.py --names 닉네임1,닉네임2 --dry-run

# 실제 수집 (매치 10개)
python collect_telemetry.py --names 닉네임1,닉네임2 --matches 10
```

### 6. 자동 수집 스케줄러

```bash
cd scripts

# 즉시 1회 실행 후 종료
python scheduler.py --run-now --once

# 매일 새벽 3시 자동 실행 (터미널 켜둬야 함)
python scheduler.py

# 매일 오전 6시로 변경
python scheduler.py --time 06:00
```

스케줄러 사용 전 `backend/.env`에 아래 항목을 추가하세요:
```
SCHEDULER_PLAYERS=닉네임1,닉네임2,닉네임3
SCHEDULER_MATCHES=10
```

---

## API 문서

### `GET /score`

유저가 그린 자기장을 기준으로 격자별 포지션 점수를 반환합니다.

**Query Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `phase` | int (1~8) | 자기장 페이즈 번호 |
| `cx` | float | 자기장 중심 X 좌표 (게임 cm) |
| `cy` | float | 자기장 중심 Y 좌표 (게임 cm) |
| `radius` | float | 자기장 반지름 (게임 cm) |

**Response 예시**

```json
{
  "phase": 3,
  "matched_matches": 42,
  "total_positions": 1850,
  "cells": [
    {
      "rank": 1,
      "cx": 412500.0,
      "cy": 308500.0,
      "sample_count": 87,
      "score": 0.734,
      "usage_rate": 0.047,
      "survival_rate": 0.862,
      "combat_survival": 0.75,
      "win_rate": 0.114,
      "move_success": 0.862,
      "low_confidence": false
    }
  ]
}
```

### `GET /health`

DB에 쌓인 데이터 현황을 확인합니다.

```json
{
  "matches": 150,
  "positions": 12480,
  "combats": 3200
}
```

---

## 설정 변경 (`backend/config.py`)

점수 가중치와 격자 크기를 자유롭게 조정할 수 있습니다.

```python
# 점수 계산 가중치 (합계 = 1.0)
W_USAGE_RATE      = 0.20
W_SURVIVAL_RATE   = 0.30
W_COMBAT_SURVIVAL = 0.20
W_WIN_RATE        = 0.20
W_MOVE_SUCCESS    = 0.10

# 자기장 유사도 허용 범위
POS_TOLERANCE    = 50000   # 중심 거리 최대 500m
RADIUS_TOLERANCE = 0.20    # 반지름 오차 ±20%
```

---

## PUBG API 키 발급 방법

1. [https://developer.pubg.com](https://developer.pubg.com) 접속
2. 우측 상단 **Sign Up** 클릭 → 계정 생성 (또는 로그인)
3. 로그인 후 **My Apps** → **Create App** 클릭
4. App 이름 입력 후 생성 → **API Key** 복사
5. `backend/.env` 파일에 붙여넣기:
   ```
   PUBG_API_KEY=발급받은_키_붙여넣기
   ```

> 무료 플랜: 분당 10 요청 / 한 달 1,000 요청 제한

---

## 주의사항

- API 키는 절대 코드에 직접 입력하지 말고 `backend/.env` 파일로 관리하세요.
- `.env` 파일은 `.gitignore`에 포함되어 GitHub에 업로드되지 않습니다.
- 데이터가 없으면 히트맵이 표시되지 않습니다. 수집 스크립트를 먼저 실행하세요.

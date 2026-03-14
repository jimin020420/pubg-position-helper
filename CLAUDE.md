# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Frontend (React + Vite)
```bash
cd frontend
npm install          # 최초 1회
npm run dev          # 개발 서버 (http://localhost:5173)
npm run build        # 프로덕션 빌드
```

### Backend (FastAPI + SQLite)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

python seed.py               # DB Mock 데이터 삽입 (최초 1회)
uvicorn main:app --reload    # 개발 서버 (http://localhost:8000)
```
`http://localhost:8000/docs` 에서 Swagger API 문서 자동 확인 가능.

### 데이터 수집
```bash
cd scripts
python collect_telemetry.py --dry-run        # 테스트 (DB 저장 없음)
python collect_telemetry.py --players 50     # 실제 수집
```
실행 전 `backend/.env`에 `PUBG_API_KEY` 필요.

## Architecture

### 레이어 구조
프론트엔드와 백엔드는 완전히 분리된 서버로 실행된다. 개발 시 Vite의 `/api` 프록시(`vite.config.js`)가 `localhost:5173/api/...` → `localhost:8000/...` 으로 요청을 전달한다.

### 좌표 계산
에란겔 맵은 게임 좌표 `0 ~ 816000` (cm 단위) 를 사용한다. 화면 픽셀(700px)과 게임 좌표 간 변환은 `MapCanvas.jsx`의 `gameToPixel` / `pixelToGame` 함수가 담당하며, 이 함수를 `ClusterMarkers.jsx`와 `HeatmapOverlay.jsx`에서도 import해서 재사용한다.

### 맵 오버레이 레이어 (z-index 순서)
1. `<img>` — 에란겔 맵 배경 이미지 (`frontend/public/maps/erangel.jpg`)
2. `HeatmapOverlay` — heatmap.js 캔버스 (포인트 밀도 시각화)
3. `MapCanvas` — Canvas (자기장 원 + 원 안 노란 점, 마우스 이벤트 수신)
4. `ClusterMarkers` — Canvas (순위 번호 마커, `pointerEvents: none`)

### 클러스터링 (`backend/clustering.py`)
외부 라이브러리 없이 순수 Python DBSCAN을 구현한다. `eps`는 자기장 반지름의 10%로 자동 조정된다. `min_samples`는 전체 포인트 수의 5%로 설정한다. scikit-learn을 추가할 경우 이 파일을 교체하면 된다.

### API 엔드포인트 (`backend/routers/positions.py`)
- `GET /positions/{map}/phase}` — 페이즈 전체 포인트
- `GET /positions/{map}/{phase}/zone` — 자기장 원 안 포인트 수 + 비율
- `GET /positions/{map}/{phase}/clusters` — DBSCAN 클러스터 순위 목록

### PUBG API 수집 (`scripts/collect_telemetry.py`)
- `LogGameStatePeriodic` 이벤트의 `safetyZoneRadius` 변화로 페이즈 경계를 감지
- `LogPlayerPosition` 이벤트에서 생존 플레이어(health > 0) 위치 추출
- 무료 API는 분당 10 요청 제한 → 7초 간격 호출, 429 자동 재시도

## Key Files

| 파일 | 역할 |
|------|------|
| `frontend/src/components/MapCanvas.jsx` | 맵 Canvas, 좌표 변환 함수 export |
| `frontend/src/components/HeatmapOverlay.jsx` | heatmap.js 히트맵 레이어 |
| `frontend/src/components/ClusterMarkers.jsx` | 순위 마커 Canvas 레이어 |
| `backend/clustering.py` | DBSCAN 클러스터링 로직 |
| `backend/routers/positions.py` | 포지션 API 라우터 |
| `scripts/collect_telemetry.py` | PUBG Telemetry 수집 스크립트 |

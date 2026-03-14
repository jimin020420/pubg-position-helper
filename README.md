# pubg-position-helper

PUBG 에란겔 맵에서 자기장 페이즈별로 **고수들이 자주 사용하는 포지션**을 히트맵으로 시각화해주는 웹앱입니다.

## 기능

- 맵 위에서 현재 자기장 원을 직접 지정
- 자기장 페이즈(1~8) 선택
- 해당 영역 내 추천 포지션을 히트맵 + 퍼센트로 표시
- PUBG 공식 API Telemetry로 상위 랭커 데이터 자동 수집

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React + Vite |
| 백엔드 | FastAPI + SQLite |
| 맵 시각화 | Canvas API |
| 히트맵 | heatmap.js |
| API | PUBG Official API |

## 폴더 구조

```
my-pubg-project/
├── frontend/          # React + Vite 앱
├── backend/           # FastAPI + SQLite 서버
├── scripts/           # 데이터 수집 자동화 스크립트
└── README.md
```

## 설치 및 실행 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/jimin020420/pubg-position-helper.git
cd pubg-position-helper
```

### 2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

### 3. 백엔드 실행

Python 3.10 이상 필요

```bash
cd backend

# 가상환경 생성 및 활성화 (Windows)
python -m venv .venv
.venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 PUBG_API_KEY 값을 입력

# 서버 실행
uvicorn main:app --reload
```

서버 실행 후 `http://localhost:8000/docs` 에서 API 문서 확인 가능

### 4. 데이터 수집 스크립트 실행 (Step 4 이후)

```bash
cd scripts
python collect_telemetry.py
```

---

## PUBG API 키 발급 방법

1. [https://developer.pubg.com](https://developer.pubg.com) 접속
2. 우측 상단 **Sign Up** 클릭 → 계정 생성 (또는 로그인)
3. 로그인 후 **My Apps** → **Create App** 클릭
4. App 이름 입력 후 생성 → **API Key** 복사
5. 프로젝트의 `backend/.env` 파일에 붙여넣기:
   ```
   PUBG_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

> 무료 플랜: 분당 10 요청 / 한 달 1,000 요청 제한

---

## 개발 로드맵

- [x] Step 1: 프로젝트 폴더 구조
- [x] Step 2: 에란겔 맵 + 히트맵 프론트엔드
- [x] Step 3: FastAPI 백엔드 + SQLite 연동
- [x] Step 4: PUBG API Telemetry 수집 스크립트
- [x] Step 5: 클러스터링 + 퍼센트 계산
- [x] Step 6: 자기장 원 지정 → 추천 포지션 표시 (완성)

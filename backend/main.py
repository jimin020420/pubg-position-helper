from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import positions, pubg_api

# DB 테이블 자동 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title="PUBG Position Helper API")

# 프론트엔드(localhost:5173)에서 API 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(positions.router)
app.include_router(pubg_api.router)


@app.get("/")
def root():
    return {"message": "PUBG Position Helper API is running"}

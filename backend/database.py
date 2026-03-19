import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 이 파일(database.py)이 있는 backend/ 디렉토리를 기준으로 절대경로 사용
# → scripts/에서 실행해도, uvicorn에서 실행해도 항상 같은 DB 파일을 사용
_HERE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{_HERE}/pubg_positions.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """API 요청마다 DB 세션을 열고, 끝나면 닫는 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

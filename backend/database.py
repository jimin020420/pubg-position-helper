from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./pubg_positions.db"

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

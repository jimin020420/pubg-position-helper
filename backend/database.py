import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

_HERE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{_HERE}/pubg_positions.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _migrate(conn):
    """기존 테이블에 새 컬럼 추가 (없을 때만)."""
    migrations = [
        ("matches",   "map_name",  "TEXT"),
        ("bluezones", "map_name",  "TEXT"),
        ("positions", "map_name",  "TEXT"),
        ("combats",   "map_name",  "TEXT"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
        except Exception:
            pass  # 이미 컬럼이 존재하면 무시


def init_db():
    """테이블 생성 + 마이그레이션 실행."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        _migrate(conn)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func
from database import Base


class PlayerPosition(Base):
    """상위 랭커의 자기장 페이즈별 위치 좌표 테이블"""

    __tablename__ = "player_positions"

    id = Column(Integer, primary_key=True, index=True)
    map_name = Column(String, default="Erangel")       # 맵 이름 (예: Erangel)
    phase = Column(Integer, nullable=False)            # 자기장 페이즈 (1~8)
    x = Column(Float, nullable=False)                  # X 좌표 (게임 내 좌표)
    y = Column(Float, nullable=False)                  # Y 좌표 (게임 내 좌표)
    match_id = Column(String, nullable=False)          # PUBG 매치 ID
    player_name = Column(String, nullable=True)        # 플레이어 이름
    created_at = Column(DateTime, server_default=func.now())

from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func
from database import Base


class PositionRecord(Base):
    """매치별 자기장 정보 + 플레이어 위치 테이블.

    핵심 아이디어: 유저가 자기장 위치를 지정하면
    과거에 비슷한 위치/크기의 자기장이었던 매치들을 찾아
    그때 플레이어들이 어디 있었는지 히트맵으로 보여준다.
    """

    __tablename__ = "position_records"

    id               = Column(Integer, primary_key=True, index=True)
    match_id         = Column(String, nullable=False, index=True)
    map_name         = Column(String, default="Erangel")
    phase            = Column(Integer, nullable=False, index=True)

    # 해당 페이즈의 자기장 (bluezone) 정보
    bluezone_x       = Column(Float, nullable=False)   # 자기장 중심 X (게임 좌표 cm)
    bluezone_y       = Column(Float, nullable=False)   # 자기장 중심 Y (게임 좌표 cm)
    bluezone_radius  = Column(Float, nullable=False)   # 자기장 반지름 (게임 좌표 cm)

    # 해당 페이즈의 플레이어 위치
    player_x         = Column(Float, nullable=False)   # 플레이어 위치 X
    player_y         = Column(Float, nullable=False)   # 플레이어 위치 Y

    created_at       = Column(DateTime, server_default=func.now())

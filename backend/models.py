from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from database import Base


class Match(Base):
    """매치 기본 정보"""
    __tablename__ = "matches"

    match_id      = Column(String, primary_key=True, index=True)
    date          = Column(DateTime, nullable=True)
    total_players = Column(Integer, default=0)

    bluezones = relationship("Bluezone", back_populates="match", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="match", cascade="all, delete-orphan")
    combats   = relationship("Combat",   back_populates="match", cascade="all, delete-orphan")


class Bluezone(Base):
    """페이즈별 자기장 정보"""
    __tablename__ = "bluezones"

    id       = Column(Integer, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.match_id"), nullable=False, index=True)
    phase    = Column(Integer, nullable=False, index=True)
    center_x = Column(Float, nullable=False)
    center_y = Column(Float, nullable=False)
    radius   = Column(Float, nullable=False)

    match = relationship("Match", back_populates="bluezones")


class Position(Base):
    """페이즈별 플레이어 위치 + 생존/우승 결과"""
    __tablename__ = "positions"

    id             = Column(Integer, primary_key=True, index=True)
    match_id       = Column(String, ForeignKey("matches.match_id"), nullable=False, index=True)
    phase          = Column(Integer, nullable=False, index=True)
    player_id      = Column(String, nullable=False, index=True)
    x              = Column(Float, nullable=False)
    y              = Column(Float, nullable=False)
    final_rank     = Column(Integer, nullable=True)   # LogMatchStatistics에서 채움
    survived_phase = Column(Integer, default=0)       # 1 = 이 페이즈 끝까지 생존
    won            = Column(Integer, default=0)        # 1 = 매치 우승

    match = relationship("Match", back_populates="positions")


class Combat(Base):
    """페이즈별 교전 기록"""
    __tablename__ = "combats"

    id                = Column(Integer, primary_key=True, index=True)
    match_id          = Column(String, ForeignKey("matches.match_id"), nullable=False, index=True)
    phase             = Column(Integer, nullable=False, index=True)
    x                 = Column(Float, nullable=False)
    y                 = Column(Float, nullable=False)
    attacker_id       = Column(String, nullable=True)
    victim_id         = Column(String, nullable=True)
    attacker_survived = Column(Integer, default=0)   # 1 = 공격자가 매치 우승

    match = relationship("Match", back_populates="combats")


# 복합 인덱스 (쿼리 성능 향상)
Index("ix_position_match_phase", Position.match_id, Position.phase)
Index("ix_combat_match_phase",   Combat.match_id,   Combat.phase)
Index("ix_bluezone_match_phase", Bluezone.match_id, Bluezone.phase)

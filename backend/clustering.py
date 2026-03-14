"""
DBSCAN 기반 포지션 클러스터링 모듈
=====================================
고수들의 위치 데이터를 클러스터(무리)로 묶어서
"이 구역에 몇 %의 플레이어가 위치했는가"를 계산합니다.

DBSCAN 선택 이유:
- K-means와 달리 클러스터 개수를 미리 지정할 필요 없음
- 밀도가 낮은 노이즈 포인트를 자동으로 제거
- 자연스러운 모양의 클러스터를 잘 찾아냄
"""

import math
from dataclasses import dataclass, field

# ── 데이터 클래스 ──────────────────────────────────────────────────────────────

@dataclass
class ClusterResult:
    rank: int       # 순위 (1 = 가장 많이 사용된 포지션)
    cx: float       # 클러스터 중심 X (게임 좌표)
    cy: float       # 클러스터 중심 Y (게임 좌표)
    count: int      # 클러스터 안 포인트 수
    percent: float  # count / 전체 포인트 수 * 100


# ── DBSCAN 구현 ───────────────────────────────────────────────────────────────

def _distance(p1: tuple, p2: tuple) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _region_query(points: list[tuple], idx: int, eps: float) -> list[int]:
    """idx 포인트에서 eps 반지름 안에 있는 이웃 포인트 인덱스 반환"""
    return [
        i for i, p in enumerate(points)
        if _distance(points[idx], p) <= eps
    ]


def dbscan(points: list[tuple], eps: float, min_samples: int) -> list[int]:
    """
    DBSCAN 클러스터링
    반환: labels 리스트 (인덱스 = 포인트 순서, 값 = 클러스터 번호, -1 = 노이즈)
    """
    n = len(points)
    labels = [-2] * n  # -2: 미방문
    cluster_id = 0

    for i in range(n):
        if labels[i] != -2:
            continue  # 이미 방문한 포인트

        neighbors = _region_query(points, i, eps)

        if len(neighbors) < min_samples:
            labels[i] = -1  # 노이즈
            continue

        # 새 클러스터 시작
        labels[i] = cluster_id
        seed_queue = list(neighbors)
        seed_queue.remove(i)

        j = 0
        while j < len(seed_queue):
            q = seed_queue[j]
            if labels[q] == -1:
                labels[q] = cluster_id  # 노이즈 → 테두리 포인트
            if labels[q] == -2:
                labels[q] = cluster_id
                q_neighbors = _region_query(points, q, eps)
                if len(q_neighbors) >= min_samples:
                    seed_queue.extend(
                        nb for nb in q_neighbors if nb not in seed_queue
                    )
            j += 1

        cluster_id += 1

    return labels


# ── 메인 함수 ─────────────────────────────────────────────────────────────────

def cluster_positions(
    points: list[dict],
    zone_radius: float = None,
    top_n: int = 5,
) -> list[ClusterResult]:
    """
    포지션 포인트 목록을 클러스터링해서 상위 N개 반환.

    Args:
        points: [{"x": float, "y": float}, ...] 형태의 포인트 목록
        zone_radius: 자기장 원 반지름 (게임 좌표, cm). eps 자동 계산에 사용.
                     None이면 데이터 분포로 추정.
        top_n: 반환할 클러스터 최대 개수

    Returns:
        퍼센트 기준 상위 top_n 클러스터 목록
    """
    if len(points) < 3:
        return []

    coords = [(p["x"], p["y"]) for p in points]
    total = len(coords)

    # eps 계산: 자기장 반지름의 10% 또는 최소 10000cm (100m)
    if zone_radius and zone_radius > 0:
        eps = max(10000, zone_radius * 0.10)
    else:
        # 데이터 범위로 eps 추정
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        data_range = max(max(xs) - min(xs), max(ys) - min(ys), 1)
        eps = max(10000, data_range * 0.08)

    min_samples = max(2, total // 20)  # 전체 포인트의 5% 이상이어야 클러스터

    labels = dbscan(coords, eps=eps, min_samples=min_samples)

    # 클러스터별 포인트 수집
    clusters: dict[int, list[tuple]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue  # 노이즈 제외
        clusters.setdefault(label, []).append(coords[i])

    if not clusters:
        return []

    # 각 클러스터의 중심(평균)과 퍼센트 계산
    results = []
    for label, pts in clusters.items():
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        percent = round(len(pts) / total * 100, 1)
        results.append(ClusterResult(
            rank=0,  # 아래서 정렬 후 재할당
            cx=cx,
            cy=cy,
            count=len(pts),
            percent=percent,
        ))

    # 포인트 수 기준 내림차순 정렬 + 순위 부여
    results.sort(key=lambda r: r.count, reverse=True)
    for i, r in enumerate(results[:top_n]):
        r.rank = i + 1

    return results[:top_n]

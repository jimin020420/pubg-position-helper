import { useEffect, useRef } from "react";
import h337 from "heatmap.js";
import { gameToPixel } from "./MapCanvas";

const MAP_DISPLAY_SIZE = 700;

/**
 * heatmap.js를 활용해 포지션 데이터를 히트맵으로 시각화
 * Props:
 *   points: [{ x, y }] - 게임 좌표 배열
 *   zone: { cx, cy, radius } | null - 현재 자기장 원 (게임 좌표)
 */
const HeatmapOverlay = ({ points = [], zone = null }) => {
  const containerRef = useRef(null);
  const heatmapRef = useRef(null);

  // heatmap 인스턴스 초기화 (최초 1회)
  useEffect(() => {
    if (!containerRef.current) return;
    heatmapRef.current = h337.create({
      container: containerRef.current,
      radius: 25,
      maxOpacity: 0.7,
      minOpacity: 0,
      blur: 0.85,
      gradient: {
        0.2: "#0000ff",
        0.5: "#00ff00",
        0.8: "#ffff00",
        1.0: "#ff0000",
      },
    });
  }, []);

  // points가 바뀔 때마다 히트맵 데이터 업데이트
  useEffect(() => {
    if (!heatmapRef.current) return;

    // 원이 지정된 경우 원 안의 포인트만, 아니면 전체
    const filtered = zone
      ? points.filter(({ x, y }) => {
          const { px, py } = gameToPixel(x, y);
          const { px: cx, py: cy } = gameToPixel(zone.cx, zone.cy);
          const radiusPx = (zone.radius / 816000) * MAP_DISPLAY_SIZE;
          return Math.hypot(px - cx, py - cy) <= radiusPx;
        })
      : points;

    const heatData = filtered.map(({ x, y }) => {
      const { px, py } = gameToPixel(x, y);
      return { x: Math.round(px), y: Math.round(py), value: 1 };
    });

    heatmapRef.current.setData({
      max: Math.max(1, Math.ceil(heatData.length / 5)),
      data: heatData,
    });
  }, [points, zone]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: MAP_DISPLAY_SIZE,
        height: MAP_DISPLAY_SIZE,
        pointerEvents: "none", // 클릭 이벤트는 Canvas로 통과
      }}
    />
  );
};

export default HeatmapOverlay;

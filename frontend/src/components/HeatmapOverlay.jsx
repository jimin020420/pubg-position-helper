import { useEffect, useRef } from "react";
import { gameToPixel } from "./MapCanvas";

const MAP_DISPLAY_SIZE = 700;
const POINT_RADIUS = 28;

/**
 * Canvas 기반 히트맵 (heatmap.js 대체)
 * Props:
 *   points: [{ x, y }] - 게임 좌표 배열
 *   zone: { cx, cy, radius } | null - 현재 자기장 원 (게임 좌표)
 */
const HeatmapOverlay = ({ points = [], zone = null }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);

    if (points.length === 0) return;

    // zone이 있으면 원 안 포인트만, 없으면 전체
    const filtered = zone
      ? points.filter(({ x, y }) => {
          const { px, py } = gameToPixel(x, y);
          const { px: cx, py: cy } = gameToPixel(zone.cx, zone.cy);
          const radiusPx = (zone.radius / 816000) * MAP_DISPLAY_SIZE;
          return Math.hypot(px - cx, py - cy) <= radiusPx;
        })
      : points;

    // 각 포인트마다 방사형 그라디언트로 열 효과
    filtered.forEach(({ x, y }) => {
      const { px, py } = gameToPixel(x, y);
      const grad = ctx.createRadialGradient(px, py, 0, px, py, POINT_RADIUS);
      grad.addColorStop(0, "rgba(255, 0, 0, 0.25)");
      grad.addColorStop(0.4, "rgba(255, 165, 0, 0.12)");
      grad.addColorStop(1, "rgba(0, 0, 255, 0)");
      ctx.beginPath();
      ctx.arc(px, py, POINT_RADIUS, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    });
  }, [points, zone]);

  return (
    <canvas
      ref={canvasRef}
      width={MAP_DISPLAY_SIZE}
      height={MAP_DISPLAY_SIZE}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        pointerEvents: "none",
      }}
    />
  );
};

export default HeatmapOverlay;

import { useEffect, useRef } from "react";
import { gameToPixel } from "./MapCanvas";

const MAP_DISPLAY_SIZE = 700;

// 순위별 색상
const RANK_COLORS = ["#ff4444", "#ff9900", "#ffdd00", "#44ff88", "#44ccff"];

/**
 * 클러스터 마커를 Canvas에 그리는 컴포넌트
 * Props:
 *   clusters: [{ rank, cx, cy, count, percent }] - 게임 좌표
 */
const ClusterMarkers = ({ clusters = [] }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);

    clusters.forEach(({ rank, cx, cy, percent }) => {
      const { px, py } = gameToPixel(cx, cy);
      const color = RANK_COLORS[(rank - 1) % RANK_COLORS.length];
      const radius = 18;

      // 외곽 광채 효과
      ctx.beginPath();
      ctx.arc(px, py, radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = `${color}33`; // 20% 투명도
      ctx.fill();

      // 채워진 원
      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // 테두리
      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "#000";
      ctx.lineWidth = 2;
      ctx.stroke();

      // 순위 숫자
      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#000";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(rank), px, py);

      // 퍼센트 라벨 (마커 위)
      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#fff";
      ctx.strokeStyle = "#000";
      ctx.lineWidth = 3;
      const label = `${percent}%`;
      ctx.strokeText(label, px, py - radius - 8);
      ctx.fillText(label, px, py - radius - 8);
    });
  }, [clusters]);

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

export default ClusterMarkers;

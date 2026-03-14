import { useRef, useEffect, useState, useCallback } from "react";

const GAME_SIZE = 816000;
const MAP_DISPLAY_SIZE = 700;

export function gameToPixel(x, y) {
  return {
    px: (x / GAME_SIZE) * MAP_DISPLAY_SIZE,
    py: (y / GAME_SIZE) * MAP_DISPLAY_SIZE,
  };
}

export function pixelToGame(px, py) {
  return {
    x: (px / MAP_DISPLAY_SIZE) * GAME_SIZE,
    y: (py / MAP_DISPLAY_SIZE) * GAME_SIZE,
  };
}

/**
 * 에란겔 맵 이미지 위에 Canvas 오버레이
 * Props:
 *   onZoneChange({ cx, cy, radius }) - 원 확정 시 호출 (게임 좌표)
 *   heatPoints: [{ x, y }]            - 원 안 강조용 포인트 (게임 좌표)
 *   zone: { cx, cy, radius } | null   - 외부 zone 상태 (null이면 원 초기화)
 */
const MapCanvas = ({ onZoneChange, heatPoints = [], zone }) => {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef(null);
  const [circle, setCircle] = useState(null); // px 기준 내부 상태

  // 외부에서 zone이 null로 바뀌면 내부 원도 초기화
  useEffect(() => {
    if (zone === null) setCircle(null);
  }, [zone]);

  // Canvas 그리기: 자기장 원 + 원 안 포인트 강조
  const draw = useCallback(
    (ctx, currentCircle) => {
      ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);

      if (!currentCircle) return;

      const { cx, cy, radius } = currentCircle;

      // 원 바깥 영역 어둡게 (비네팅 효과)
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      ctx.fillRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.clip();
      ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);
      ctx.restore();

      // 자기장 원 테두리 (점선 스타일)
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([8, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // 원 안 포인트 강조 (노란 점)
      heatPoints.forEach(({ x, y }) => {
        const { px, py } = gameToPixel(x, y);
        if (Math.hypot(px - cx, py - cy) <= radius) {
          ctx.beginPath();
          ctx.arc(px, py, 4, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255, 220, 0, 0.75)";
          ctx.fill();
        }
      });
    },
    [heatPoints]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    draw(canvas.getContext("2d"), circle);
  }, [circle, draw]);

  const getPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const handleMouseDown = (e) => {
    dragStart.current = getPos(e);
    setIsDragging(true);
  };

  const handleMouseMove = (e) => {
    if (!isDragging || !dragStart.current) return;
    const pos = getPos(e);
    const r = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);
    setCircle({ cx: dragStart.current.x, cy: dragStart.current.y, radius: r });
  };

  const handleMouseUp = (e) => {
    if (!isDragging || !dragStart.current) return;
    setIsDragging(false);
    const pos = getPos(e);
    const r = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);
    if (r > 10) {
      const finalCircle = { cx: dragStart.current.x, cy: dragStart.current.y, radius: r };
      setCircle(finalCircle);
      if (onZoneChange) {
        const center = pixelToGame(dragStart.current.x, dragStart.current.y);
        onZoneChange({ cx: center.x, cy: center.y, radius: (r / MAP_DISPLAY_SIZE) * GAME_SIZE });
      }
    }
    dragStart.current = null;
  };

  return (
    <div className="map-wrapper">
      <img
        src="/maps/erangel.jpg"
        alt="Erangel Map"
        className="map-image"
        draggable={false}
        onError={(e) => { e.target.style.display = "none"; }}
      />
      <canvas
        ref={canvasRef}
        width={MAP_DISPLAY_SIZE}
        height={MAP_DISPLAY_SIZE}
        className={`map-canvas ${isDragging ? "dragging" : ""}`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => setIsDragging(false)}
      />
      <p className="map-hint">
        {circle
          ? "다시 그리려면 새로 드래그하세요"
          : "클릭 + 드래그로 현재 자기장 범위를 지정하세요"}
      </p>
    </div>
  );
};

export default MapCanvas;

import { useRef, useEffect, useState, useCallback } from "react";

// 에란겔 게임 좌표 범위 (cm 단위)
const GAME_SIZE = 816000;
// 화면에 표시할 맵 크기 (px)
const MAP_DISPLAY_SIZE = 700;

/**
 * 게임 좌표 → 화면 픽셀 좌표 변환
 */
export function gameToPixel(x, y) {
  return {
    px: (x / GAME_SIZE) * MAP_DISPLAY_SIZE,
    py: (y / GAME_SIZE) * MAP_DISPLAY_SIZE,
  };
}

/**
 * 화면 픽셀 좌표 → 게임 좌표 변환
 */
export function pixelToGame(px, py) {
  return {
    x: (px / MAP_DISPLAY_SIZE) * GAME_SIZE,
    y: (py / MAP_DISPLAY_SIZE) * GAME_SIZE,
  };
}

/**
 * 에란겔 맵 이미지 위에 Canvas를 겹쳐
 * - 마우스 드래그로 자기장 원 지정
 * - 히트맵 포인트 표시
 * Props:
 *   onZoneChange({ cx, cy, radius }) - 원이 확정될 때 호출 (게임 좌표)
 *   heatPoints: [{ x, y }] - 표시할 포지션 포인트 (게임 좌표)
 */
const MapCanvas = ({ onZoneChange, heatPoints = [] }) => {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef(null);
  const [circle, setCircle] = useState(null); // { cx, cy, radius } in px

  // Canvas에 원과 히트 포인트 그리기
  const draw = useCallback(
    (ctx, currentCircle) => {
      ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);

      // 히트 포인트 (파란 점)
      heatPoints.forEach(({ x, y }) => {
        const { px, py } = gameToPixel(x, y);
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 150, 255, 0.5)";
        ctx.fill();
      });

      // 자기장 원
      if (currentCircle) {
        const { cx, cy, radius } = currentCircle;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.strokeStyle = "#00e5ff";
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.fillStyle = "rgba(0, 229, 255, 0.08)";
        ctx.fill();

        // 원 안에 들어오는 포인트 강조 (노란 점)
        heatPoints.forEach(({ x, y }) => {
          const { px, py } = gameToPixel(x, y);
          const dist = Math.hypot(px - cx, py - cy);
          if (dist <= radius) {
            ctx.beginPath();
            ctx.arc(px, py, 5, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(255, 220, 0, 0.85)";
            ctx.fill();
          }
        });
      }
    },
    [heatPoints]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    draw(ctx, circle);
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
    const radius = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);
    setCircle({ cx: dragStart.current.x, cy: dragStart.current.y, radius });
  };

  const handleMouseUp = (e) => {
    if (!isDragging || !dragStart.current) return;
    setIsDragging(false);
    const pos = getPos(e);
    const radius = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);
    const finalCircle = { cx: dragStart.current.x, cy: dragStart.current.y, radius };
    setCircle(finalCircle);

    if (onZoneChange && radius > 5) {
      const center = pixelToGame(dragStart.current.x, dragStart.current.y);
      const radiusGame = (radius / MAP_DISPLAY_SIZE) * GAME_SIZE;
      onZoneChange({ cx: center.x, cy: center.y, radius: radiusGame });
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
          ? "원 안의 노란 점이 추천 포지션이에요"
          : "맵 위에서 클릭 + 드래그로 자기장 범위를 지정하세요"}
      </p>
    </div>
  );
};

export default MapCanvas;

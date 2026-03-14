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

// 에란겔 페이즈별 자기장 반지름 (게임 좌표 cm)
// 출처: PUBG 공식 White circle diameter → radius = diameter/2 * 100
// Phase 1: 4564.7m  2: 2967.1m  3: 1483.5m  4: 741.8m
// Phase 5: 370.9m   6: 185.4m   7: 92.7m    8: 46.4m
const PHASE_RADII = {
  1: 228235,
  2: 148355,
  3:  74175,
  4:  37090,
  5:  18545,
  6:   9270,
  7:   4635,
  8:   2320,
};

/**
 * Props:
 *   onZoneChange({ cx, cy, radius }) - 원 확정 시 호출 (게임 좌표)
 *   heatPoints: [{ x, y }]
 *   zone: { cx, cy, radius } | null
 *   phase: number (1~8)
 *   zoom: number (1~4)
 *   onPanDelta({ dx, dy }) - Ctrl+드래그 패닝 델타
 */
const MapCanvas = ({ onZoneChange, heatPoints = [], zone, phase = 1, zoom = 1, onPanDelta }) => {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef(null);
  const isPanning = useRef(false);
  const panStart = useRef(null);
  const [circle, setCircle] = useState(null);

  useEffect(() => {
    if (zone === null) setCircle(null);
  }, [zone]);

  const draw = useCallback((ctx, currentCircle) => {
    ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);
    if (!currentCircle) return;

    const { cx, cy, radius } = currentCircle;

    // 원 바깥 어둡게
    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    ctx.fillRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.clip();
    ctx.clearRect(0, 0, MAP_DISPLAY_SIZE, MAP_DISPLAY_SIZE);
    ctx.restore();

    // 자기장 원 테두리
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([8, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // 원 안 포인트 강조
    heatPoints.forEach(({ x, y }) => {
      const { px, py } = gameToPixel(x, y);
      if (Math.hypot(px - cx, py - cy) <= radius) {
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 220, 0, 0.75)";
        ctx.fill();
      }
    });
  }, [heatPoints]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    draw(canvas.getContext("2d"), circle);
  }, [circle, draw]);

  // zoom 적용된 canvas 내부 좌표 계산
  const getPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / zoom,
      y: (e.clientY - rect.top) / zoom,
    };
  };

  const handleMouseDown = (e) => {
    if (e.ctrlKey) {
      isPanning.current = true;
      panStart.current = { x: e.clientX, y: e.clientY };
      return;
    }
    dragStart.current = getPos(e);
    setIsDragging(true);
  };

  const handleMouseMove = (e) => {
    if (isPanning.current && panStart.current && onPanDelta) {
      onPanDelta({
        dx: e.clientX - panStart.current.x,
        dy: e.clientY - panStart.current.y,
      });
      panStart.current = { x: e.clientX, y: e.clientY };
      return;
    }
    if (!isDragging || !dragStart.current) return;
    const pos = getPos(e);
    const r = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);
    setCircle({ cx: dragStart.current.x, cy: dragStart.current.y, radius: r });
  };

  const handleMouseUp = (e) => {
    if (isPanning.current) {
      isPanning.current = false;
      panStart.current = null;
      return;
    }
    if (!isDragging || !dragStart.current) return;
    setIsDragging(false);
    const pos = getPos(e);
    const r = Math.hypot(pos.x - dragStart.current.x, pos.y - dragStart.current.y);

    // 드래그 거리 짧으면 클릭 → 페이즈 기본 반지름 사용
    let pixelRadius;
    if (r <= 10) {
      const gameRadius = PHASE_RADII[phase] ?? PHASE_RADII[1];
      pixelRadius = (gameRadius / GAME_SIZE) * MAP_DISPLAY_SIZE;
    } else {
      pixelRadius = r;
    }

    const finalCircle = { cx: dragStart.current.x, cy: dragStart.current.y, radius: pixelRadius };
    setCircle(finalCircle);
    if (onZoneChange) {
      const center = pixelToGame(finalCircle.cx, finalCircle.cy);
      onZoneChange({
        cx: center.x,
        cy: center.y,
        radius: (finalCircle.radius / MAP_DISPLAY_SIZE) * GAME_SIZE,
      });
    }
    dragStart.current = null;
  };

  const handleMouseLeave = () => {
    setIsDragging(false);
    isPanning.current = false;
    panStart.current = null;
  };

  return (
    <div className="map-wrapper">
      <img
        src="/maps/erangel.png"
        alt="Erangel Map"
        className="map-image"
        draggable={false}
        onError={(e) => { e.target.style.background = "#1e3a2f"; }}
      />
      <canvas
        ref={canvasRef}
        width={MAP_DISPLAY_SIZE}
        height={MAP_DISPLAY_SIZE}
        className={`map-canvas ${isDragging ? "dragging" : ""}`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      />
      <p className="map-hint">
        {circle
          ? "드래그로 크기 재조정 · Ctrl+드래그로 이동 · 휠로 확대"
          : "클릭 → 페이즈 자기장 배치 · 드래그 → 직접 크기 지정"}
      </p>
    </div>
  );
};

export default MapCanvas;

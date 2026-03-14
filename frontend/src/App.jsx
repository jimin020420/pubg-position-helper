import { useState, useMemo } from "react";
import MapCanvas from "./components/MapCanvas";
import PhaseSelector from "./components/PhaseSelector";
import HeatmapOverlay from "./components/HeatmapOverlay";
import "./App.css";

// ─── Mock 데이터 (Step 4 이후 실제 API로 교체) ───────────────────────────────
function generateMockPoints(count, xMin, xMax, yMin, yMax) {
  const clusters = [
    { x: xMin + (xMax - xMin) * 0.2, y: yMin + (yMax - yMin) * 0.3 },
    { x: xMin + (xMax - xMin) * 0.6, y: yMin + (yMax - yMin) * 0.5 },
    { x: xMin + (xMax - xMin) * 0.4, y: yMin + (yMax - yMin) * 0.7 },
    { x: xMin + (xMax - xMin) * 0.8, y: yMin + (yMax - yMin) * 0.2 },
  ];
  const spread = (xMax - xMin) * 0.08;
  return Array.from({ length: count }, () => {
    const c = clusters[Math.floor(Math.random() * clusters.length)];
    return {
      x: c.x + (Math.random() - 0.5) * spread,
      y: c.y + (Math.random() - 0.5) * spread,
    };
  });
}

const MOCK_POSITIONS = {
  1: generateMockPoints(200, 100000, 700000, 100000, 700000),
  2: generateMockPoints(180, 150000, 650000, 150000, 650000),
  3: generateMockPoints(150, 200000, 600000, 200000, 600000),
  4: generateMockPoints(120, 250000, 560000, 250000, 560000),
  5: generateMockPoints(100, 300000, 510000, 300000, 510000),
  6: generateMockPoints(80,  350000, 470000, 350000, 470000),
  7: generateMockPoints(60,  380000, 440000, 380000, 440000),
  8: generateMockPoints(40,  400000, 420000, 400000, 420000),
};
// ─────────────────────────────────────────────────────────────────────────────

function App() {
  const [phase, setPhase] = useState(1);
  const [zone, setZone] = useState(null); // { cx, cy, radius } 게임 좌표

  const points = useMemo(() => MOCK_POSITIONS[phase] ?? [], [phase]);

  const insideCount = useMemo(() => {
    if (!zone) return 0;
    return points.filter(({ x, y }) =>
      Math.hypot(x - zone.cx, y - zone.cy) <= zone.radius
    ).length;
  }, [points, zone]);

  const handlePhaseChange = (newPhase) => {
    setPhase(newPhase);
    setZone(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">PUBG 포지션 추천</h1>
        <p className="app-subtitle">에란겔 · 자기장 페이즈별 고수 포지션 히트맵</p>
      </header>

      <main className="app-main">
        <section className="map-section">
          <div style={{ position: "relative", display: "inline-block" }}>
            <MapCanvas onZoneChange={setZone} heatPoints={points} />
            <HeatmapOverlay points={points} zone={zone} />
          </div>
        </section>

        <aside className="control-panel">
          <PhaseSelector phase={phase} onChange={handlePhaseChange} />

          <div className="stats-box">
            <h3>현재 데이터</h3>
            <div className="stat-row">
              <span>전체 포지션 수</span>
              <strong>{points.length}개</strong>
            </div>
            {zone && (
              <>
                <div className="stat-row highlight">
                  <span>자기장 안 포지션</span>
                  <strong>{insideCount}개</strong>
                </div>
                <div className="stat-row highlight">
                  <span>추천 확률</span>
                  <strong>
                    {points.length > 0
                      ? Math.round((insideCount / points.length) * 100)
                      : 0}
                    %
                  </strong>
                </div>
              </>
            )}
          </div>

          <div className="guide-box">
            <h3>사용 방법</h3>
            <ol>
              <li>자기장 페이즈를 선택하세요</li>
              <li>맵에서 <b>클릭 + 드래그</b>로 현재 자기장 범위를 그리세요</li>
              <li>원 안의 <b>노란 점</b>이 추천 포지션이에요</li>
              <li>히트맵 색상이 빨갈수록 고수들이 자주 간 위치예요</li>
            </ol>
          </div>

          <p className="data-notice">
            * 현재는 Mock 데이터입니다.<br />
            Step 4 완료 후 실제 상위 랭커 데이터로 교체됩니다.
          </p>
        </aside>
      </main>
    </div>
  );
}

export default App;

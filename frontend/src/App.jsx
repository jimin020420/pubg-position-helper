import { useState, useCallback, useMemo } from "react";
import { MapContainer, TileLayer, Circle, Rectangle, useMapEvents, useMap, ZoomControl } from "react-leaflet";
import L from "leaflet";
import "./App.css";

// ── 상수 ──────────────────────────────────────────────────────────────────────
const MAP_M = 8160;
const CELL_M = 50;
const HALF_CELL = CELL_M / 2;
const MAP_BOUNDS = [[0, 0], [MAP_M, MAP_M]];
const API = "http://127.0.0.1:8000";
const PHASES = [2, 3, 4, 5, 6, 7, 8];

const PHASE_RADII = {
  2: 148355, 3: 74175, 4: 37090,
  5: 18545, 6: 9270, 7: 4635, 8: 2320,
};

// ── CRS ───────────────────────────────────────────────────────────────────────
const pubgCRS = L.extend({}, L.CRS.Simple, {
  transformation: new L.Transformation(1 / MAP_M, 0, -1 / MAP_M, 1),
  scale: (z) => 256 * Math.pow(2, z),
  zoom: (s) => Math.log2(s / 256),
});

// ── 좌표 변환 ─────────────────────────────────────────────────────────────────
const g2l = (x, y) => [MAP_M - y / 100, x / 100];
const l2g = (lat, lng) => ({ x: lng * 100, y: (MAP_M - lat) * 100 });
const cellBounds = (cx, cy) => {
  const lat = MAP_M - cy / 100;
  const lng = cx / 100;
  return [[lat - HALF_CELL, lng - HALF_CELL], [lat + HALF_CELL, lng + HALF_CELL]];
};

// 점수(0~1) → 색상
const scoreColor = (score, lowConf) => {
  if (lowConf) return "rgba(150,150,150,0.25)";
  const r = Math.min(255, Math.round(score * 2 * 255));
  const g = Math.min(255, Math.round((1 - Math.abs(score - 0.5) * 2) * 180));
  const b = Math.round((1 - score) * 220);
  return `rgba(${r},${g},${b},0.65)`;
};

const pct = (v) => `${(v * 100).toFixed(1)}%`;
const pts = (v) => `${(v * 100).toFixed(1)}점`;

// 초기 줌: CSS .map-wrap 크기와 동일한 공식
// CSS: min(100dvw - 288px, 100dvh - 24px)  (PC)
//      min(100dvw, 100dvh - 52px)          (모바일)
function calcInitZoom() {
  const isMobile = window.innerWidth < 768;
  const dim = isMobile
    ? Math.min(window.innerWidth, window.innerHeight - 52)
    : Math.min(window.innerWidth - 288, window.innerHeight - 24);
  return Math.log2(Math.max(dim, 100) / 256);
}

// ── Leaflet 내부 컴포넌트 ──────────────────────────────────────────────────────
function DragController({ initZoom }) {
  const map = useMap();
  useMapEvents({
    zoomend() {
      if (map.getZoom() > initZoom) map.dragging.enable();
      else map.dragging.disable();
    },
  });
  return null;
}

function MapEvents({ phase, onZonePlace, zone, cells, onCellClick, initZoom }) {
  const map = useMap();

  useMapEvents({
    click(e) {
      const game = l2g(e.latlng.lat, e.latlng.lng);
      const radius = PHASE_RADII[phase] ?? PHASE_RADII[2];
      onZonePlace({ cx: game.x, cy: game.y, radius });

      const { width, height } = map.getContainer().getBoundingClientRect();
      const halfDim = Math.min(width, height) / 2;
      const radiusM = radius / 100;
      const zoom = Math.log2((halfDim * MAP_M) / (radiusM * 256));
      const clampedZoom = Math.min(Math.max(zoom - 0.5, initZoom), 6);
      map.flyTo(g2l(game.x, game.y), clampedZoom, { duration: 0.8 });
    },
  });

  return (
    <>
      {zone && (
        <Circle
          center={g2l(zone.cx, zone.cy)}
          radius={zone.radius / 100}
          pathOptions={{ color: "#00e5ff", fill: false, weight: 2.5, dashArray: "8 4" }}
        />
      )}
      {cells.map((cell) => (
        <Rectangle
          key={`${cell.cx}-${cell.cy}`}
          bounds={cellBounds(cell.cx, cell.cy)}
          pathOptions={{
            color: cell.rank <= 5 ? "#ffd700" : "transparent",
            weight: cell.rank <= 5 ? 2 : 0,
            fillColor: scoreColor(cell.score, cell.low_confidence),
            fillOpacity: cell.low_confidence ? 0.25 : 0.7,
          }}
          eventHandlers={{
            click(e) { L.DomEvent.stop(e); onCellClick(cell); },
          }}
        />
      ))}
    </>
  );
}

// ── 격자 상세 카드 ─────────────────────────────────────────────────────────────
function CellDetail({ cell, phase, onClose }) {
  const metrics = [
    ["사용률",      cell.usage_rate],
    ["생존율",      cell.survival_rate],
    ["교전 생존율", cell.combat_survival],
    ...(phase >= 5 && phase <= 7 ? [["우승 기여율", cell.win_rate]] : []),
    ["다음 자기장", cell.next_zone_rate],
  ];

  return (
    <div className="cell-detail">
      <div className="detail-head">
        <span className="rank-badge">#{cell.rank}</span>
        <span className="detail-title">격자 상세</span>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>
      {cell.low_confidence && (
        <div className="low-conf">⚠ 샘플 {cell.sample_count}개 · 신뢰도 낮음</div>
      )}
      <div className="score-row">
        <span>종합 점수</span>
        <strong className="big-score">{pts(cell.score)}</strong>
      </div>
      <div className="metrics">
        {metrics.map(([label, val]) => (
          <div key={label} className="metric-row">
            <span className="metric-label">{label}</span>
            <div className="metric-bar-bg">
              <div className="metric-bar" style={{ width: pct(val) }} />
            </div>
            <span className="metric-val">{pct(val)}</span>
          </div>
        ))}
      </div>
      {!cell.low_confidence && (
        <p className="sample-note">샘플 {cell.sample_count}개</p>
      )}
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [phase, setPhase] = useState(2);
  const [zone, setZone] = useState(null);
  const [cells, setCells] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const initZoom = useMemo(() => calcInitZoom(), []);

  const [selectedMap, setSelectedMap] = useState("erangel");

  const fetchScore = useCallback(async (z, p, m) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/score?phase=${p}&cx=${z.cx}&cy=${z.cy}&radius=${z.radius}&map=${m}`);
      if (!res.ok) throw new Error(`서버 오류 ${res.status}`);
      const data = await res.json();
      setCells(data.cells);
      setStats({ matched: data.matched_matches, total: data.total_positions });
      if (data.cells.length > 0) setSheetOpen(true);
    } catch {
      setError("서버 연결 오류");
      setCells([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleZonePlace = useCallback(
    (z) => { setZone(z); setSelectedCell(null); setSheetOpen(false); fetchScore(z, phase, selectedMap); },
    [phase, fetchScore, selectedMap]
  );

  const handleReset = () => {
    setZone(null); setCells([]); setStats(null);
    setSelectedCell(null); setSheetOpen(false);
  };

  const handlePhaseChange = (p) => { setPhase(p); handleReset(); };

  const top5 = cells.slice(0, 5);

  return (
    <div className="app">
      {/* ── 상단 바 (모바일) ── */}
      <header className="top-bar">
        <div className="phase-scroll">
          {PHASES.map(p => (
            <button
              key={p}
              className={`phase-btn ${phase === p ? "active" : ""}`}
              onClick={() => handlePhaseChange(p)}
            >
              {p}P
            </button>
          ))}
        </div>
        {zone && (
          <button className="reset-top-btn" onClick={handleReset}>초기화</button>
        )}
      </header>

      {/* ── 맵 + PC 사이드 ── */}
      <div className="content-wrap">
        <div className="map-wrap">
          <div className="map-logo">pubgmap.gg</div>
          {loading && <div className="map-pill loading-pill">분석 중...</div>}
          {error && <div className="map-pill error-pill">{error}</div>}
          {!zone && !loading && (
            <div className="map-pill hint-pill">터치해서 자기장 위치 선택</div>
          )}
          <MapContainer
            crs={pubgCRS}
            center={[MAP_M / 2, MAP_M / 2]}
            zoom={initZoom}
            minZoom={initZoom}
            maxZoom={6}
            style={{ width: "100%", height: "100%" }}
            zoomSnap={0}
            zoomDelta={0.5}
            dragging={false}
            maxBounds={MAP_BOUNDS}
            maxBoundsViscosity={1.0}
            attributionControl={false}
            zoomControl={false}
          >
            <ZoomControl position="bottomright" />
            <TileLayer
              url="https://tiles3-v2.pubgmap.net/tiles/erangel/v19/{z}/{x}/{y}.png"
              tileSize={256}
              minNativeZoom={1}
              maxNativeZoom={5}
              bounds={MAP_BOUNDS}
              noWrap={true}
            />
            <DragController initZoom={initZoom} />
            <MapEvents
              phase={phase}
              onZonePlace={handleZonePlace}
              zone={zone}
              cells={cells}
              onCellClick={(cell) => { setSelectedCell(cell); setSheetOpen(false); }}
              initZoom={initZoom}
            />
          </MapContainer>
        </div>

        {/* PC 사이드바 */}
        <aside className="pc-panel">
          <div className="phase-heading">
            <span className="phase-num">{phase}</span>
            <span className="phase-word">PHASE</span>
          </div>
          <div className="panel-section">
            <div className="pc-phase-btns">
              {PHASES.map(p => (
                <button
                  key={p}
                  className={`phase-btn ${phase === p ? "active" : ""}`}
                  onClick={() => handlePhaseChange(p)}
                >
                  {p}P
                </button>
              ))}
            </div>
          </div>


          {zone && !selectedCell && (
            <button className="reset-btn" onClick={handleReset}>자기장 초기화</button>
          )}

          {selectedCell ? (
            <CellDetail cell={selectedCell} phase={phase} onClose={() => setSelectedCell(null)} />
          ) : stats ? (
            <div className="stats-section">
              <div className="stat-row"><span>유사 자기장</span><strong>{stats.matched}개</strong></div>
              <div className="stat-row"><span>분석 포지션</span><strong>{stats.total}개</strong></div>
              <div className="stat-row"><span>추천 격자</span><strong>{cells.length}개</strong></div>
            </div>
          ) : (
            <p className="empty-hint">맵을 클릭해<br />자기장을 배치하세요</p>
          )}
        </aside>
      </div>

      {/* ── 모바일: 격자 상세 시트 ── */}
      <div className={`detail-sheet ${selectedCell ? "open" : ""}`}>
        {selectedCell && (
          <CellDetail cell={selectedCell} phase={phase} onClose={() => setSelectedCell(null)} />
        )}
      </div>

      {/* ── 모바일: 하단 추천 시트 ── */}
      <div className={`bottom-sheet ${sheetOpen && !selectedCell ? "open" : ""}`}>
        <div className="sheet-top" onClick={() => setSheetOpen(false)}>
          <div className="drag-handle" />
        </div>
        <div className="sheet-header">
          <span className="sheet-title">추천 포지션</span>
          <span className="sheet-count">{cells.length}개</span>
          <button className="sheet-close" onClick={() => setSheetOpen(false)}>✕</button>
        </div>
        <div className="sheet-cards">
          {top5.map(cell => (
            <button
              key={`${cell.cx}-${cell.cy}`}
              className="cell-card"
              onClick={() => setSelectedCell(cell)}
            >
              <span className="card-rank">#{cell.rank}</span>
              <div className="card-mid">
                <div className="card-bar-bg">
                  <div className="card-bar" style={{ width: pct(cell.score) }} />
                </div>
              </div>
              <span className="card-score">{pts(cell.score)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

import { useState, useCallback } from "react";
import { MapContainer, TileLayer, Circle, Rectangle, useMapEvents } from "react-leaflet";
import L from "leaflet";
import PhaseSelector from "./components/PhaseSelector";
import "./App.css";

// ── 상수 ─────────────────────────────────────────────────────────────────────
const MAP_M     = 8160;     // 미터 단위 (816000cm)
const CELL_M    = 50;       // 격자 한 변 (미터)
const HALF_CELL = CELL_M / 2;
const MAP_BOUNDS  = [[0, 0], [MAP_M, MAP_M]];
const API = "http://127.0.0.1:8000";

// 커스텀 CRS: 게임 좌표(m) → pubgmap.net 타일 좌표계
// zoom 0 = 256×256px 타일 1개가 전체 맵 커버
const pubgCRS = L.extend({}, L.CRS.Simple, {
  transformation: new L.Transformation(1 / MAP_M, 0, -1 / MAP_M, 1),
  scale: (z) => 256 * Math.pow(2, z),
  zoom:  (s) => Math.log2(s / 256),
  infinite: false,
});

// 700px 컨테이너에 전체 맵이 꽉 차는 줌 레벨 (≈ 1.45)
const INIT_ZOOM = Math.log2(700 / 256);

// 에란겔 페이즈별 자기장 반지름 (게임 cm)
const PHASE_RADII = {
  1: 228235, 2: 148355, 3: 74175, 4: 37090,
  5: 18545,  6: 9270,   7: 4635,  8: 2320,
};

// ── 좌표 변환 ─────────────────────────────────────────────────────────────────
// 게임 cm → Leaflet [lat, lng] (Y축 반전: 게임 Y=0 = 맵 상단 = Leaflet lat 최대값)
const g2l = (x, y) => [MAP_M - y / 100, x / 100];

// Leaflet lat, lng → 게임 cm
const l2g = (lat, lng) => ({ x: lng * 100, y: (MAP_M - lat) * 100 });

// 격자 중심(게임 cm) → Leaflet Rectangle bounds
const cellBounds = (cx, cy) => {
  const lat = MAP_M - cy / 100;
  const lng = cx / 100;
  return [[lat - HALF_CELL, lng - HALF_CELL], [lat + HALF_CELL, lng + HALF_CELL]];
};

// 점수(0~1) → rgba 색상
const scoreColor = (score, lowConf) => {
  if (lowConf) return "rgba(150,150,150,0.25)";
  const r = Math.min(255, Math.round(score * 2 * 255));
  const g = Math.min(255, Math.round((1 - Math.abs(score - 0.5) * 2) * 180));
  const b = Math.round((1 - score) * 220);
  return `rgba(${r},${g},${b},0.65)`;
};

// ── 맵 이벤트 핸들러 (MapContainer 내부에 있어야 함) ──────────────────────────
function MapEvents({ phase, onZonePlace, zone, cells, onCellClick }) {
  useMapEvents({
    click(e) {
      // 격자 클릭은 Rectangle eventHandlers에서 처리하므로 여기선 맵 클릭만
      const game = l2g(e.latlng.lat, e.latlng.lng);
      onZonePlace({
        cx: game.x,
        cy: game.y,
        radius: PHASE_RADII[phase] ?? PHASE_RADII[1],
      });
    },
  });

  return (
    <>
      {/* 자기장 원 */}
      {zone && (
        <Circle
          center={g2l(zone.cx, zone.cy)}
          radius={zone.radius / 100}   // cm → 미터
          pathOptions={{
            color: "#00e5ff",
            fill: false,
            weight: 2.5,
            dashArray: "8 4",
          }}
        />
      )}

      {/* 격자 히트맵 */}
      {cells.map((cell) => (
        <Rectangle
          key={`${cell.cx}-${cell.cy}`}
          bounds={cellBounds(cell.cx, cell.cy)}
          pathOptions={{
            color:        cell.rank <= 5 ? "#ffd700" : "transparent",
            weight:       cell.rank <= 5 ? 2 : 0,
            fillColor:    scoreColor(cell.score, cell.low_confidence),
            fillOpacity:  cell.low_confidence ? 0.25 : 0.7,
          }}
          eventHandlers={{
            click(e) {
              L.DomEvent.stop(e);   // 맵 click 이벤트 전파 차단
              onCellClick(cell);
            },
          }}
        />
      ))}
    </>
  );
}

// ── 메인 앱 ───────────────────────────────────────────────────────────────────
export default function App() {
  const [phase,        setPhase]        = useState(1);
  const [zone,         setZone]         = useState(null);
  const [cells,        setCells]        = useState([]);
  const [stats,        setStats]        = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState(null);

  const fetchScore = useCallback(async (z, p) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API}/score?phase=${p}&cx=${z.cx}&cy=${z.cy}&radius=${z.radius}`
      );
      if (!res.ok) throw new Error(`서버 오류 ${res.status}`);
      const data = await res.json();
      setCells(data.cells);
      setStats({ matched: data.matched_matches, total: data.total_positions });
    } catch {
      setError("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.");
      setCells([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleZonePlace = useCallback(
    (z) => { setZone(z); setSelectedCell(null); fetchScore(z, phase); },
    [phase, fetchScore]
  );

  const handleReset = () => {
    setZone(null); setCells([]); setStats(null); setSelectedCell(null);
  };

  const handlePhaseChange = (p) => {
    setPhase(p); handleReset();
  };

  const pct = (v) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="app">
      <header className="app-header">
        <h1>PUBG 포지션 추천</h1>
        <p>에란겔 · 자기장 기반 포지션 점수 히트맵</p>
      </header>

      <main className="app-main">
        {/* ── 맵 ── */}
        <section className="map-section">
          {error   && <div className="banner error-banner">{error}</div>}
          {loading && <div className="banner loading-banner">분석 중...</div>}

          <MapContainer
            crs={pubgCRS}
            center={[MAP_M / 2, MAP_M / 2]}
            zoom={INIT_ZOOM}
            minZoom={INIT_ZOOM}
            maxZoom={6}
            style={{ width: 700, height: 700 }}
            zoomSnap={0}
            zoomDelta={0.5}
            dragging={false}
            maxBounds={MAP_BOUNDS}
            maxBoundsViscosity={1.0}
            attributionControl={false}
          >
            <TileLayer
              url="https://tiles3-v2.pubgmap.net/tiles/erangel/v19/{z}/{x}/{y}.png"
              tileSize={256}
              minNativeZoom={0}
              maxNativeZoom={5}
              noWrap={true}
            />
            <MapEvents
              phase={phase}
              onZonePlace={handleZonePlace}
              zone={zone}
              cells={cells}
              onCellClick={setSelectedCell}
            />
          </MapContainer>

          <p className="map-hint">
            {zone
              ? "격자를 클릭하면 상세 점수를 볼 수 있어요 · 스크롤로 확대/축소"
              : "맵을 클릭하면 현재 자기장 위치가 배치됩니다"}
          </p>
        </section>

        {/* ── 사이드 패널 ── */}
        <aside className="control-panel">
          <PhaseSelector phase={phase} onChange={handlePhaseChange} />

          {zone && (
            <button className="reset-btn" onClick={handleReset}>
              자기장 초기화
            </button>
          )}

          {/* 클릭된 격자 상세 */}
          {selectedCell && (
            <div className="cell-detail">
              <div className="cell-detail-header">
                <span className="cell-rank-badge">#{selectedCell.rank}</span>
                <span>격자 상세 정보</span>
                <button className="close-btn" onClick={() => setSelectedCell(null)}>✕</button>
              </div>
              {selectedCell.low_confidence && (
                <div className="low-conf-badge">
                  ⚠ 데이터 부족 (샘플 {selectedCell.sample_count}개, 신뢰도 낮음)
                </div>
              )}
              <div className="detail-score-row">
                <span>종합 점수</span>
                <strong className="detail-score">
                  {(selectedCell.score * 100).toFixed(1)}점
                </strong>
              </div>
              <div className="detail-grid">
                {[
                  ["① 사용률",     selectedCell.usage_rate],
                  ["② 생존율",     selectedCell.survival_rate],
                  ["③ 교전 생존율", selectedCell.combat_survival],
                  ["④ 우승 기여율", selectedCell.win_rate],
                  ["⑤ 이동 성공률", selectedCell.move_success],
                ].map(([label, val]) => (
                  <div key={label} className="detail-item">
                    <span className="detail-label">{label}</span>
                    <div className="detail-bar-wrap">
                      <div
                        className="detail-bar"
                        style={{ width: pct(val) }}
                      />
                    </div>
                    <span className="detail-val">{pct(val)}</span>
                  </div>
                ))}
              </div>
              <p className="detail-sample">샘플 수: {selectedCell.sample_count}개</p>
            </div>
          )}

          {/* 통계 요약 */}
          <div className="stats-box">
            <h3>데이터 현황</h3>
            {stats ? (
              <>
                <div className="stat-row highlight">
                  <span>유사 자기장 매치</span>
                  <strong>{stats.matched}개</strong>
                </div>
                <div className="stat-row highlight">
                  <span>분석된 포지션</span>
                  <strong>{stats.total}개</strong>
                </div>
                <div className="stat-row">
                  <span>반환된 추천 격자</span>
                  <strong>{cells.length}개</strong>
                </div>
              </>
            ) : (
              <p className="stats-empty">
                자기장을 클릭하면<br />포지션 점수가 표시됩니다
              </p>
            )}
          </div>

          {/* 색상 범례 */}
          <div className="legend-box">
            <h3>점수 범례</h3>
            <div className="legend-bar-row">
              <span className="legend-label">낮음</span>
              <div className="legend-gradient" />
              <span className="legend-label">높음</span>
            </div>
            <div className="legend-items">
              <span>
                <span className="legend-dot gold" />상위 5위 (금색 테두리)
              </span>
              <span>
                <span className="legend-dot grey" />데이터 부족
              </span>
            </div>
          </div>

          {/* 사용 방법 */}
          <div className="guide-box">
            <h3>사용 방법</h3>
            <ol>
              <li>페이즈를 선택하세요</li>
              <li>맵을 <b>클릭</b> → 자기장 배치</li>
              <li>색칠된 격자 = 추천 포지션</li>
              <li><b>격자 클릭</b> → 5가지 지표 확인</li>
              <li><b>스크롤</b>로 맵 확대/축소</li>
            </ol>
          </div>
        </aside>
      </main>
    </div>
  );
}

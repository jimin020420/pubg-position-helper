import { useState, useEffect, useCallback, useRef } from "react";
import MapCanvas from "./components/MapCanvas";
import PhaseSelector from "./components/PhaseSelector";
import HeatmapOverlay from "./components/HeatmapOverlay";
import ClusterMarkers from "./components/ClusterMarkers";
import "./App.css";

const RANK_COLORS = ["#ff4444", "#ff9900", "#ffdd00", "#44ff88", "#44ccff"];
const API = "http://127.0.0.1:8000";
const MAP_SIZE = 700;

function App() {
  const [phase, setPhase] = useState(1);
  const [zone, setZone] = useState(null);
  const [points, setPoints] = useState([]);
  const [stats, setStats] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [zoneLoading, setZoneLoading] = useState(false);
  const [error, setError] = useState(null);

  // 줌/패닝 상태
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const mapContainerRef = useRef(null);
  const zoomRef = useRef(zoom);
  const panRef = useRef(pan);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panRef.current = pan; }, [pan]);

  const clampPan = (x, y, z) => ({
    x: Math.min(0, Math.max(MAP_SIZE * (1 - z), x)),
    y: Math.min(0, Math.max(MAP_SIZE * (1 - z), y)),
  });

  // 마우스 휠 줌 (passive: false 필요)
  useEffect(() => {
    const el = mapContainerRef.current;
    if (!el) return;
    const handler = (e) => {
      e.preventDefault();
      const currentZoom = zoomRef.current;
      const currentPan = panRef.current;
      const rect = el.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newZoom = Math.min(4, Math.max(1, currentZoom * factor));

      if (newZoom === 1) {
        setZoom(1);
        setPan({ x: 0, y: 0 });
        return;
      }

      const newPanX = mouseX - (mouseX - currentPan.x) * (newZoom / currentZoom);
      const newPanY = mouseY - (mouseY - currentPan.y) * (newZoom / currentZoom);
      const clamped = clampPan(newPanX, newPanY, newZoom);
      setZoom(newZoom);
      setPan(clamped);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl+드래그 패닝 콜백 (MapCanvas에서 호출)
  const handlePanDelta = useCallback(({ dx, dy }) => {
    setZoom(z => {
      setPan(p => clampPan(p.x + dx, p.y + dy, z));
      return z;
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchPositions = useCallback(async (p) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/positions/Erangel/${p}`);
      if (!res.ok) throw new Error(`서버 오류: ${res.status}`);
      const data = await res.json();
      setPoints(data.points);
    } catch {
      setError("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.");
      setPoints([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions(phase);
  }, [phase, fetchPositions]);

  const fetchZoneData = useCallback(async (newZone, currentPhase) => {
    if (!newZone) { setStats(null); setClusters([]); return; }
    const { cx, cy, radius } = newZone;
    const base = `${API}/positions/Erangel/${currentPhase}`;
    const qs = `cx=${cx}&cy=${cy}&radius=${radius}`;
    setZoneLoading(true);
    try {
      const [searchRes, clusterRes] = await Promise.all([
        fetch(`${base}/search?${qs}`),          // 비슷한 자기장 매치 검색
        fetch(`${base}/clusters?${qs}&top_n=5`), // 추천 포지션 클러스터
      ]);
      if (searchRes.ok) {
        const d = await searchRes.json();
        setPoints(d.points);  // 히트맵을 비슷한 자기장 매치의 포지션으로 교체
        setStats({ matchedMatches: d.matched_matches, total: d.total_points });
      }
      if (clusterRes.ok) {
        const d = await clusterRes.json();
        setClusters(d.clusters);
      }
    } catch {
      setStats(null);
      setClusters([]);
    } finally {
      setZoneLoading(false);
    }
  }, []);

  const handleZoneChange = (newZone) => {
    setZone(newZone);
    fetchZoneData(newZone, phase);
  };

  const handlePhaseChange = (newPhase) => {
    setPhase(newPhase);
    handleReset();
  };

  const handleReset = () => {
    setZone(null);
    setStats(null);
    setClusters([]);
    fetchPositions(phase); // 히트맵을 페이즈 전체 데이터로 복원
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">PUBG 포지션 추천</h1>
        <p className="app-subtitle">에란겔 · 자기장 페이즈별 고수 포지션 히트맵</p>
      </header>

      <main className="app-main">
        {/* ── 맵 영역 ── */}
        <section className="map-section">
          {error && <div className="error-banner">{error}</div>}

          {/* 줌/오버플로 컨테이너 */}
          <div
            ref={mapContainerRef}
            className="map-outer"
          >
            {/* 트랜스폼 레이어 */}
            <div
              style={{
                position: "absolute",
                width: MAP_SIZE,
                height: MAP_SIZE,
                transformOrigin: "0 0",
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              }}
            >
              <MapCanvas
                onZoneChange={handleZoneChange}
                heatPoints={points}
                zone={zone}
                phase={phase}
                zoom={zoom}
                onPanDelta={handlePanDelta}
              />
              <HeatmapOverlay points={points} zone={zone} />
              <ClusterMarkers clusters={clusters} />
              {(loading || zoneLoading) && (
                <div className="map-loading">
                  {loading ? "포지션 데이터 로딩 중..." : "추천 포지션 분석 중..."}
                </div>
              )}
            </div>

            {/* 줌 표시 (zoom > 1일 때) */}
            {zoom > 1 && (
              <div className="zoom-badge" onDoubleClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>
                {Math.round(zoom * 100)}% · 더블클릭 초기화
              </div>
            )}
          </div>

          {/* 색상 범례 */}
          <div className="legend">
            <span className="legend-item">
              <span className="legend-dot" style={{ background: "#0000ff" }} />낮음
            </span>
            <span className="legend-arrow">→</span>
            <span className="legend-item">
              <span className="legend-dot" style={{ background: "#ff8800" }} />보통
            </span>
            <span className="legend-arrow">→</span>
            <span className="legend-item">
              <span className="legend-dot" style={{ background: "#ff0000" }} />핫스팟
            </span>
            <span className="legend-sep" />
            <span className="legend-item">
              <span className="legend-dot" style={{ background: "#ffd700" }} />추천 포지션
            </span>
          </div>
        </section>

        {/* ── 컨트롤 패널 ── */}
        <aside className="control-panel">
          <PhaseSelector phase={phase} onChange={handlePhaseChange} />

          {zone && (
            <button className="reset-btn" onClick={handleReset}>
              자기장 초기화
            </button>
          )}

          {/* 통계 */}
          <div className="stats-box">
            <h3>현재 데이터</h3>
            <div className="stat-row">
              <span>전체 포지션 수</span>
              <strong>{points.length}개</strong>
            </div>
            {stats && (
              <>
                <div className="stat-row highlight">
                  <span>유사 자기장 매치</span>
                  <strong>{stats.matchedMatches}개</strong>
                </div>
                <div className="stat-row highlight">
                  <span>포지션 데이터</span>
                  <strong>{stats.total}개</strong>
                </div>
              </>
            )}
            {!zone && (
              <p className="stats-empty">자기장을 지정하면<br />통계가 표시됩니다</p>
            )}
          </div>

          {/* 추천 포지션 순위 */}
          {clusters.length > 0 && (
            <div className="cluster-box">
              <h3>추천 포지션 순위</h3>
              {clusters.map((c) => (
                <div key={c.rank} className="cluster-row">
                  <span
                    className="cluster-rank"
                    style={{ background: RANK_COLORS[(c.rank - 1) % RANK_COLORS.length] }}
                  >
                    {c.rank}
                  </span>
                  <span className="cluster-info">
                    포지션 #{c.rank}
                    <small>{c.count}명 사용</small>
                  </span>
                  <span className="cluster-percent">{c.percent}%</span>
                </div>
              ))}
              <p className="cluster-note">맵의 번호 마커 위치가 추천 포지션이에요</p>
            </div>
          )}

          {zone && clusters.length === 0 && !zoneLoading && (
            <div className="cluster-box">
              <p className="cluster-empty">
                범위 안에 데이터가 부족합니다.<br />더 넓게 드래그해 보세요.
              </p>
            </div>
          )}

          {/* 사용 방법 */}
          <div className="guide-box">
            <h3>사용 방법</h3>
            <ol>
              <li>자기장 페이즈를 선택하세요</li>
              <li>맵 <b>클릭</b> → 현재 자기장 위치 지정</li>
              <li><b>드래그</b> → 자기장 범위 직접 지정</li>
              <li>히트맵이 <b>비슷한 자기장</b>이었던 과거 매치의 포지션으로 업데이트됩니다</li>
              <li>번호 마커 <b>①②③</b>이 추천 포지션이에요</li>
            </ol>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;

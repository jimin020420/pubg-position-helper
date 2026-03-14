import { useState, useEffect, useCallback } from "react";
import MapCanvas from "./components/MapCanvas";
import PhaseSelector from "./components/PhaseSelector";
import HeatmapOverlay from "./components/HeatmapOverlay";
import ClusterMarkers from "./components/ClusterMarkers";
import "./App.css";

const RANK_COLORS = ["#ff4444", "#ff9900", "#ffdd00", "#44ff88", "#44ccff"];

function App() {
  const [phase, setPhase] = useState(1);
  const [zone, setZone] = useState(null);
  const [points, setPoints] = useState([]);
  const [stats, setStats] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [zoneLoading, setZoneLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchPositions = useCallback(async (p) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/positions/Erangel/${p}`);
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
    const base = `/api/positions/Erangel/${currentPhase}`;
    const qs = `cx=${cx}&cy=${cy}&radius=${radius}`;
    setZoneLoading(true);
    try {
      const [zoneRes, clusterRes] = await Promise.all([
        fetch(`${base}/zone?${qs}`),
        fetch(`${base}/clusters?${qs}&top_n=5`),
      ]);
      if (zoneRes.ok) {
        const d = await zoneRes.json();
        setStats({ inside: d.inside, percent: d.percent, total: d.total });
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
          <div style={{ position: "relative", display: "inline-block" }}>
            <MapCanvas onZoneChange={handleZoneChange} heatPoints={points} zone={zone} />
            <HeatmapOverlay points={points} zone={zone} />
            <ClusterMarkers clusters={clusters} />
            {(loading || zoneLoading) && (
              <div className="map-loading">
                {loading ? "포지션 데이터 로딩 중..." : "추천 포지션 분석 중..."}
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
              <span className="legend-dot" style={{ background: "#00ff00" }} />보통
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

          {/* 초기화 버튼 */}
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
                  <span>자기장 안 포지션</span>
                  <strong>{stats.inside}개</strong>
                </div>
                <div className="stat-row highlight">
                  <span>자기장 커버율</span>
                  <strong>{stats.percent}%</strong>
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
              <li>맵에서 <b>클릭 + 드래그</b>로 현재 자기장 범위를 그리세요</li>
              <li>번호 마커 <b>①②③</b>이 추천 포지션이에요</li>
              <li>히트맵이 빨갈수록 고수들이 자주 간 위치예요</li>
            </ol>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;

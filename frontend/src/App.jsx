import { useState, useEffect, useCallback } from "react";
import MapCanvas from "./components/MapCanvas";
import PhaseSelector from "./components/PhaseSelector";
import HeatmapOverlay from "./components/HeatmapOverlay";
import ClusterMarkers from "./components/ClusterMarkers";
import "./App.css";

const RANK_COLORS = ["#ff4444", "#ff9900", "#ffdd00", "#44ff88", "#44ccff"];

function App() {
  const [phase, setPhase] = useState(1);
  const [zone, setZone] = useState(null);       // { cx, cy, radius } 게임 좌표
  const [points, setPoints] = useState([]);      // [{ x, y }]
  const [stats, setStats] = useState(null);      // { inside, percent, total }
  const [clusters, setClusters] = useState([]);  // [{ rank, cx, cy, count, percent }]
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 페이즈가 바뀔 때마다 전체 포지션 데이터 fetch
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

  // 자기장 원 확정 시 zone 통계 + 클러스터 동시 fetch
  const fetchZoneData = useCallback(async (newZone, currentPhase) => {
    if (!newZone) {
      setStats(null);
      setClusters([]);
      return;
    }
    const { cx, cy, radius } = newZone;
    const base = `/api/positions/Erangel/${currentPhase}`;
    const qs = `cx=${cx}&cy=${cy}&radius=${radius}`;

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
    }
  }, []);

  const handleZoneChange = (newZone) => {
    setZone(newZone);
    fetchZoneData(newZone, phase);
  };

  const handlePhaseChange = (newPhase) => {
    setPhase(newPhase);
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
        <section className="map-section">
          {error && <div className="error-banner">{error}</div>}
          <div style={{ position: "relative", display: "inline-block" }}>
            <MapCanvas onZoneChange={handleZoneChange} heatPoints={points} />
            <HeatmapOverlay points={points} zone={zone} />
            <ClusterMarkers clusters={clusters} />
            {loading && <div className="map-loading">데이터 로딩 중...</div>}
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
          </div>

          {/* 추천 포지션 순위 목록 */}
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
                    <small>({c.count}명 사용)</small>
                  </span>
                  <span className="cluster-percent">{c.percent}%</span>
                </div>
              ))}
              <p className="cluster-note">
                맵의 번호 마커 위치가 추천 포지션이에요
              </p>
            </div>
          )}

          {zone && clusters.length === 0 && !loading && (
            <div className="cluster-box">
              <p style={{ color: "#8b949e", fontSize: "0.85rem", margin: 0 }}>
                자기장 범위 안에 데이터가 부족해서<br />클러스터를 찾지 못했어요.<br />
                더 넓은 범위를 지정해 보세요.
              </p>
            </div>
          )}

          <div className="guide-box">
            <h3>사용 방법</h3>
            <ol>
              <li>자기장 페이즈를 선택하세요</li>
              <li>맵에서 <b>클릭 + 드래그</b>로 현재 자기장 범위를 그리세요</li>
              <li>번호 마커(<b>1, 2, 3...</b>)가 추천 포지션이에요</li>
              <li>히트맵 색상이 빨갈수록 고수들이 자주 간 위치예요</li>
            </ol>
          </div>

          <p className="data-notice">
            * 현재는 Seed 데이터입니다.<br />
            Step 4 완료 후 실제 상위 랭커 데이터로 교체됩니다.
          </p>
        </aside>
      </main>
    </div>
  );
}

export default App;

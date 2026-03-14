import { useState } from "react";
import MapCanvas from "./components/MapCanvas";
import PhaseSelector from "./components/PhaseSelector";
import HeatmapOverlay from "./components/HeatmapOverlay";
import "./App.css";

function App() {
  const [phase, setPhase] = useState(1);

  return (
    <div style={{ padding: "20px", fontFamily: "sans-serif" }}>
      <h1>PUBG 포지션 추천</h1>
      <p>에란겔 맵에서 자기장 페이즈별 고수들의 포지션을 확인하세요.</p>

      <PhaseSelector phase={phase} onChange={setPhase} />

      <div style={{ marginTop: "20px" }}>
        <MapCanvas phase={phase} />
        <HeatmapOverlay data={[]} />
      </div>
    </div>
  );
}

export default App;

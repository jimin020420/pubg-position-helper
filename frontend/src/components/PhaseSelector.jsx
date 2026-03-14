/**
 * 자기장 페이즈(1~8) 선택 UI
 * 페이즈가 높을수록 자기장이 좁아지고 후반 전투
 */
const PHASE_LABELS = [
  { phase: 1, label: "1페이즈 — 초반 (맵 전체)" },
  { phase: 2, label: "2페이즈 — 초반" },
  { phase: 3, label: "3페이즈 — 중반" },
  { phase: 4, label: "4페이즈 — 중반" },
  { phase: 5, label: "5페이즈 — 후반" },
  { phase: 6, label: "6페이즈 — 후반" },
  { phase: 7, label: "7페이즈 — 최종권" },
  { phase: 8, label: "8페이즈 — 결승전" },
];

const PhaseSelector = ({ phase, onChange }) => {
  return (
    <div className="phase-selector">
      <span className="phase-label">자기장 페이즈</span>
      <div className="phase-buttons">
        {PHASE_LABELS.map(({ phase: p, label }) => (
          <button
            key={p}
            className={`phase-btn ${phase === p ? "active" : ""}`}
            onClick={() => onChange(p)}
            title={label}
          >
            {p}
          </button>
        ))}
      </div>
      <span className="phase-desc">{PHASE_LABELS[phase - 1]?.label}</span>
    </div>
  );
};

export default PhaseSelector;

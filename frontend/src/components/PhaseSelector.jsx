/**
 * 자기장 페이즈(2~8) 선택 UI
 * 1페이즈는 수집/분석 대상에서 제외
 */
const PHASE_LABELS = [
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
      <span className="phase-desc">{PHASE_LABELS.find((l) => l.phase === phase)?.label}</span>
    </div>
  );
};

export default PhaseSelector;

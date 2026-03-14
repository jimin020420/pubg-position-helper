// 자기장 페이즈(1~8) 선택 UI 컴포넌트
// 이후 단계에서 구현 예정

const PhaseSelector = ({ phase, onChange }) => {
  return (
    <div>
      <label>자기장 페이즈: </label>
      <select value={phase} onChange={(e) => onChange(Number(e.target.value))}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((p) => (
          <option key={p} value={p}>
            {p} 페이즈
          </option>
        ))}
      </select>
    </div>
  );
};

export default PhaseSelector;

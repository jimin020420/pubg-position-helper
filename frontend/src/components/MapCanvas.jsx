// 에란겔 맵 이미지 위에 Canvas를 겹쳐 자기장 원을 그리는 컴포넌트
// 이후 단계에서 구현 예정

const MapCanvas = () => {
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      {/* 에란겔 맵 이미지 */}
      <img
        src="/maps/erangel.jpg"
        alt="Erangel Map"
        style={{ width: "800px", height: "800px" }}
      />
      {/* Canvas 오버레이 (자기장 원, 히트맵 표시용) */}
      <canvas
        style={{ position: "absolute", top: 0, left: 0 }}
        width={800}
        height={800}
      />
    </div>
  );
};

export default MapCanvas;

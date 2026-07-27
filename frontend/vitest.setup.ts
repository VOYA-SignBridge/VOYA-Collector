import '@testing-library/jest-dom';

// jsdom không có requestAnimationFrame trừ khi bật pretendToBeVisual —
// polyfill để các hook playback (usePlayback) chạy được trong test.
if (typeof window.requestAnimationFrame === 'undefined') {
  window.requestAnimationFrame = ((cb: FrameRequestCallback) =>
    setTimeout(() => cb(performance.now()), 16)) as unknown as typeof window.requestAnimationFrame;
  window.cancelAnimationFrame = ((id: number) =>
    clearTimeout(id)) as typeof window.cancelAnimationFrame;
}

// jsdom không hiện thực canvas 2D → getContext log "Not implemented" mỗi khi
// component vẽ (Skeleton2DPlayer). Cung cấp context no-op để test im lặng; các
// test cần assert lệnh vẽ vẫn spyOn/mockReturnValue đè lên stub này bình thường.
const _noop = () => {};
HTMLCanvasElement.prototype.getContext = (() => ({
  fillRect: _noop, clearRect: _noop, beginPath: _noop, moveTo: _noop, lineTo: _noop,
  stroke: _noop, arc: _noop, fill: _noop, closePath: _noop, save: _noop, restore: _noop,
  translate: _noop, scale: _noop, setTransform: _noop, fillText: _noop,
  fillStyle: '', strokeStyle: '', lineWidth: 1, lineCap: 'butt',
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;

// Tiêm biến môi trường giả lập cho Vitest
Object.defineProperty(window, '__ENV__', {
  value: {
    VITE_API_URL: 'http://localhost:8000',
    VITE_BASE_PATH: '/'
  },
  writable: true
});

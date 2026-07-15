import '@testing-library/jest-dom';

// Tiêm biến môi trường giả lập cho Vitest
Object.defineProperty(window, '__ENV__', {
  value: {
    VITE_API_URL: 'http://localhost:8000',
    VITE_BASE_PATH: '/'
  },
  writable: true
});

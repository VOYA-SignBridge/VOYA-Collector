import React, { useState, useEffect } from 'react';
import axiosClient from '../api/axiosClient';
import './DebugPanel.css';

export interface DebugOperation {
  timestamp: number;
  operation: 'UPLOAD_VIDEO' | 'UPLOAD_CAMERA' | 'JOB_STATUS' | 'CONNECTIVITY';
  status: 'SUCCESS' | 'FAILURE' | 'IN_PROGRESS';
  duration_ms?: number;
  session_id?: string;
  job_id?: string;
  message?: string;
  error?: string;
  response?: Record<string, unknown>;
}

export interface DebugState {
  enabled: boolean;
  operations: DebugOperation[];
  lastBackendPing: number | null;
  backendConnected: boolean;
}

interface DebuggerInterface {
  log: (operation: DebugOperation) => void;
  getState: () => DebugState;
  setState: (newState: Partial<DebugState>) => void;
}

type DebugWindow = Window & {
  __voyadebug?: DebuggerInterface;
};

const DebugPanel: React.FC = () => {
  const [debugState, setDebugState] = useState<DebugState>(() => {
    // Try to load from localStorage
    const saved = localStorage.getItem('voya_debug_state');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        // If parsing fails, use default
      }
    }
    return {
      enabled: false,
      operations: [],
      lastBackendPing: null,
      backendConnected: false,
    };
  });

  // Persist debug state to localStorage
  useEffect(() => {
    localStorage.setItem('voya_debug_state', JSON.stringify(debugState));
  }, [debugState]);

  // Global debug tracker (expose to window for easy access from upload functions)
  useEffect(() => {
    const debugWindow = window as DebugWindow;
    debugWindow.__voyadebug = {
      log: (operation: DebugOperation) => {
        setDebugState((prev) => ({
          ...prev,
          operations: [operation, ...prev.operations].slice(0, 50), // Keep last 50
        }));
      },
      getState: () => debugState,
      setState: (newState: Partial<DebugState>) => {
        setDebugState((prev) => ({ ...prev, ...newState }));
      },
    };
  }, [debugState]);

  const toggleDebugMode = () => {
    setDebugState((prev) => ({
      ...prev,
      enabled: !prev.enabled,
    }));
  };

  const clearOperations = () => {
    setDebugState((prev) => ({
      ...prev,
      operations: [],
    }));
  };

  const checkBackendConnectivity = async () => {
    try {
      const response = await axiosClient.get('/health');
      setDebugState((prev) => ({
        ...prev,
        lastBackendPing: Date.now(),
        backendConnected: response.status >= 200 && response.status < 300,
      }));

      // Log connectivity check
      (window as DebugWindow).__voyadebug?.log({
        timestamp: Date.now(),
        operation: 'CONNECTIVITY',
        status: response.status >= 200 && response.status < 300 ? 'SUCCESS' : 'FAILURE',
        message: `Backend: ${response.status >= 200 && response.status < 300 ? 'Connected' : 'Disconnected'}`,
      });
    } catch (error) {
      setDebugState((prev) => ({
        ...prev,
        lastBackendPing: Date.now(),
        backendConnected: false,
      }));

      (window as DebugWindow).__voyadebug?.log({
        timestamp: Date.now(),
        operation: 'CONNECTIVITY',
        status: 'FAILURE',
        error: String(error),
      });
    }
  };

  if (!debugState.enabled) {
    return (
      <button
        className="debug-panel__toggle-button"
        onClick={toggleDebugMode}
        title="Enable debug mode"
      >
        🐛 Debug
      </button>
    );
  }

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    return `${ms.toFixed(0)}ms`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return '#10b981';
      case 'FAILURE':
        return '#ef4444';
      case 'IN_PROGRESS':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="debug-panel">
      <div className="debug-panel__header">
        <h3 className="debug-panel__title">🐛 Debug Console</h3>
        <div className="debug-panel__controls">
          <button
            className="debug-panel__button"
            onClick={checkBackendConnectivity}
            title="Check backend connectivity"
          >
            🔗 Ping
          </button>
          <button
            className="debug-panel__button"
            onClick={clearOperations}
            title="Clear operation history"
          >
            Clear
          </button>
          <button
            className="debug-panel__button"
            onClick={toggleDebugMode}
            title="Close debug panel"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="debug-panel__status">
        <div className="debug-panel__status-item">
          <span>Backend:</span>
          <span
            className="debug-panel__status-indicator"
            style={{
              backgroundColor: debugState.backendConnected ? '#10b981' : '#ef4444',
            }}
          >
            {debugState.backendConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        {debugState.lastBackendPing && (
          <div className="debug-panel__status-item">
            <span>Last Ping:</span>
            <span>{formatTime(debugState.lastBackendPing)}</span>
          </div>
        )}
        <div className="debug-panel__status-item">
          <span>Operations:</span>
          <span>{debugState.operations.length}</span>
        </div>
      </div>

      <div className="debug-panel__content">
        <div className="debug-panel__operations">
          {debugState.operations.length === 0 ? (
            <div className="debug-panel__empty">No operations recorded yet</div>
          ) : (
            debugState.operations.map((op, idx) => (
              <details key={idx} className="debug-panel__operation">
                <summary className="debug-panel__operation-summary">
                  <span
                    className="debug-panel__operation-status"
                    style={{ backgroundColor: getStatusColor(op.status) }}
                  >
                    {op.status}
                  </span>
                  <span className="debug-panel__operation-type">{op.operation}</span>
                  <span className="debug-panel__operation-time">
                    {formatTime(op.timestamp)}
                  </span>
                  {op.duration_ms && (
                    <span className="debug-panel__operation-duration">
                      {formatDuration(op.duration_ms)}
                    </span>
                  )}
                </summary>

                <div className="debug-panel__operation-details">
                  {op.session_id && (
                    <div className="debug-panel__detail-line">
                      <span className="debug-panel__detail-key">Session ID:</span>
                      <code className="debug-panel__detail-value">{op.session_id}</code>
                    </div>
                  )}
                  {op.job_id && (
                    <div className="debug-panel__detail-line">
                      <span className="debug-panel__detail-key">Job ID:</span>
                      <code className="debug-panel__detail-value">{op.job_id}</code>
                    </div>
                  )}
                  {op.message && (
                    <div className="debug-panel__detail-line">
                      <span className="debug-panel__detail-key">Message:</span>
                      <span className="debug-panel__detail-value">{op.message}</span>
                    </div>
                  )}
                  {op.error && (
                    <div className="debug-panel__detail-line debug-panel__detail-error">
                      <span className="debug-panel__detail-key">Error:</span>
                      <span className="debug-panel__detail-value">{op.error}</span>
                    </div>
                  )}
                  {op.response && (
                    <div className="debug-panel__detail-line">
                      <span className="debug-panel__detail-key">Response:</span>
                      <pre className="debug-panel__detail-json">
                        {JSON.stringify(op.response, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            ))
          )}
        </div>
      </div>

      <div className="debug-panel__footer">
        <small>Debug mode enabled. Keyboard: Shift+D to toggle</small>
      </div>
    </div>
  );
};

export default DebugPanel;

import type { Sample } from "../types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";

interface SessionPanelProps {
  sessionId: string;
  samples: Sample[];
  onFinish: () => void;
  onDelete: (id: number) => void;
}

export default function SessionPanel({ sessionId, samples, onFinish, onDelete }: SessionPanelProps) {
  const handleDelete = (id: number) => {
    if (confirm("Are you sure you want to delete this sample?")) {
      onDelete(id);
    }
  };

  const totalFrames = samples.reduce((sum, sample) => sum + (sample.frames || 0), 0);
  const avgFrames = samples.length > 0 ? (totalFrames / samples.length).toFixed(1) : 0;

  return (
    <div className="card card-compact">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div className="flex items-center">
          <div className="w-9 h-9 sm:w-10 sm:h-10 bg-indigo-100 rounded-xl flex items-center justify-center mr-3 shrink-0">
            <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-gray-900">Capture Session</h3>
            <div className="text-xs sm:text-sm text-gray-600">Manage your recorded samples</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="info" size="sm">
            {samples.length} samples
          </Badge>
          <Badge variant="default" size="sm">
            {totalFrames} frames
          </Badge>
        </div>
      </div>

      {/* Session Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-6 p-3 sm:p-4 bg-gray-50 rounded-xl">
        <div className="text-center">
          <div className="text-xl sm:text-2xl font-bold text-gray-900">{samples.length}</div>
          <div className="text-xs text-gray-600">Total Samples</div>
        </div>
        <div className="text-center">
          <div className="text-xl sm:text-2xl font-bold text-gray-900">{totalFrames}</div>
          <div className="text-xs text-gray-600">Total Frames</div>
        </div>
        <div className="text-center">
          <div className="text-xl sm:text-2xl font-bold text-gray-900">{avgFrames}</div>
          <div className="text-xs text-gray-600">Avg Frames</div>
        </div>
      </div>

      {/* Session ID */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between p-3 bg-indigo-50 rounded-lg mb-6">
        <div className="flex items-center">
          <svg className="w-4 h-4 text-indigo-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a.997.997 0 01-1.414 0l-7-7A1.997 1.997 0 013 12V7a4 4 0 014-4z" />
          </svg>
          <span className="text-sm font-medium text-indigo-900">Session ID</span>
        </div>
        <code className="block w-full sm:w-auto text-sm text-indigo-700 bg-indigo-100 px-2 py-1 rounded break-all">{sessionId}</code>
      </div>

      {samples.length === 0 ? (
        <div className="text-center py-10 sm:py-12 border-2 border-dashed border-gray-200 rounded-xl">
          <div className="w-14 h-14 sm:w-16 sm:h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <h4 className="text-lg font-medium text-gray-900 mb-2">No samples captured yet</h4>
          <p className="text-gray-600 text-sm">Start recording to see your samples appear here</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
          {samples.map((sample, idx) => (
            <div
              key={sample.id ?? idx}
              className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="flex items-start sm:items-center space-x-3 min-w-0 flex-1">
                <div className="w-9 h-9 sm:w-10 sm:h-10 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-gray-900">Sample #{sample.id ?? idx + 1}</span>
                    <Badge 
                      variant={sample.uploaded ? "success" : "warning"} 
                      size="sm"
                    >
                      {sample.uploaded ? "✓ Uploaded" : "⏳ Processing"}
                    </Badge>
                  </div>
                  <div className="text-sm text-gray-600">
                    {sample.frames || 0} frames • {sample.label || 'No label'}
                  </div>
                </div>
              </div>
              
              <button
                onClick={() => handleDelete(sample.id ?? idx)}
                className="p-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors self-end sm:self-auto"
                aria-label="Delete sample"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-6 pt-6 border-t border-gray-200">
        <Button 
          onClick={onFinish} 
          className="w-full py-3 text-sm sm:text-base font-medium"
          disabled={samples.length === 0}
          variant={samples.length > 0 ? "primary" : "secondary"}
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {samples.length > 0 ? `Complete Session (${samples.length} samples)` : 'No samples to finish'}
        </Button>
      </div>
    </div>
  );
}

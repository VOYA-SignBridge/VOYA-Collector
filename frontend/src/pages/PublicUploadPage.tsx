import { useState, useEffect } from 'react';
import Button from '../components/ui/Button';
import ErrorBanner from '../components/ErrorBanner';
import { uploadCamera } from '../api/upload';
import type { CameraUploadPayload } from '../types';
import { getRole } from '../utils/role';

type Feedback = {
  type: 'error' | 'warning' | 'info' | 'success';
  message: string;
};

export default function PublicUploadPage() {
  const [label, setLabel] = useState('');
  const [user, setUser] = useState('');
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [role, setRole] = useState(getRole());

  useEffect(() => {
    if (!feedback) return;
    if (feedback.type !== 'success' && feedback.type !== 'info') return;
    const timer = window.setTimeout(() => setFeedback(null), 2500);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  useEffect(() => {
    const onRole = () => setRole(getRole());
    window.addEventListener('voya:rolechange', onRole);
    return () => window.removeEventListener('voya:rolechange', onRole);
  }, []);

  const handleSubmit = async () => {
    if (!label || !user) {
      setFeedback({ type: 'warning', message: 'Vui lòng nhập đầy đủ tên và nhãn.' });
      return;
    }
    setLoading(true);
    setFeedback(null);

    // Minimal payload: front-end will let user upload via camera flow; here we send a tiny sample marker.
    const payload: CameraUploadPayload = {
      user,
      label,
      session_id: `public-${Date.now()}`,
      frames: [],
    };

    try {
      const res = await uploadCamera(payload);
      if (res.ok) {
        setFeedback({ type: 'success', message: 'Đã gửi mẫu thành công. Hệ thống đang xử lý.' });
        setLabel('');
        setUser('');
      } else {
        setFeedback({ type: 'error', message: res.error || 'Không thể tải lên.' });
      }
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card w-full max-w-xl mx-auto">
      <div className="p-4 sm:p-6">
        <h2 className="text-xl font-semibold mb-2">Community Upload</h2>
        <p className="text-sm text-gray-600 mb-4">Quickly submit a labeled sample. Advanced options are reserved for admins.</p>

        {feedback && (
          <div className="mb-4">
            <ErrorBanner
              message={feedback.message}
              type={feedback.type}
              autoClose={feedback.type === 'success' || feedback.type === 'info'}
              duration={2500}
              onClose={() => setFeedback(null)}
            />
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Your name</label>
            <input className="input w-full" value={user} onChange={(e) => setUser(e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Label</label>
            <input className="input w-full" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>

          <div className="flex flex-col gap-3 pt-4 border-t border-gray-200 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-gray-500">Role: <strong>{role}</strong></div>
            <Button className="w-full sm:w-auto" onClick={handleSubmit} loading={loading} disabled={loading || !label || !user}>Submit</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import Button from '../components/ui/Button';
import { uploadCamera } from '../api/upload';
import type { CameraUploadPayload } from '../types';
import { getRole } from '../utils/role';

export default function PublicUploadPage() {
  const [label, setLabel] = useState('');
  const [user, setUser] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [role, setRole] = useState(getRole());

  useEffect(() => {
    const onRole = () => setRole(getRole());
    window.addEventListener('voya:rolechange', onRole);
    return () => window.removeEventListener('voya:rolechange', onRole);
  }, []);

  const handleSubmit = async () => {
    if (!label || !user) {
      setMessage('Please fill both name and label');
      return;
    }
    setLoading(true);
    setMessage(null);

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
        setMessage('Thanks — your sample was queued for processing.');
        setLabel('');
        setUser('');
      } else {
        setMessage(res.error || 'Upload failed');
      }
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card max-w-xl mx-auto">
      <div className="p-6">
        <h2 className="text-lg font-semibold mb-2">Community Upload</h2>
        <p className="text-sm text-gray-600 mb-4">Quickly submit a labeled sample. Advanced options are reserved for admins.</p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Your name</label>
            <input className="input w-full" value={user} onChange={(e) => setUser(e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Label</label>
            <input className="input w-full" value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-gray-200">
            <div className="text-xs text-gray-500">Role: <strong>{role}</strong></div>
            <Button onClick={handleSubmit} loading={loading} disabled={loading || !label || !user}>Submit</Button>
          </div>

          {message && (
            <div className="mt-4 text-sm text-gray-700">{message}</div>
          )}
        </div>
      </div>
    </div>
  );
}

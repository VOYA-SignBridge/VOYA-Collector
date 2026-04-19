import type { Session } from "../../types";

export default function SessionList({ sessions }: { sessions: Session[] }) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <h3 className="font-semibold mb-3">📁 All Sessions</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left p-2">Session ID</th>
            <th className="text-left p-2">User</th>
            <th className="text-left p-2">Labels</th>
            <th className="text-left p-2">Samples</th>
            <th className="text-left p-2">Date</th>
            <th className="text-left p-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s: Session) => (
            <tr key={s.session_id} className="border-b hover:bg-gray-50">
              <td className="p-2 font-mono">{s.session_id}</td>
              <td className="p-2">{s.user}</td>
              <td className="p-2">{(s.labels || []).join(", ")}</td>
              <td className="p-2">{s.samples_count}</td>
              <td className="p-2">{s.created_at}</td>
              <td className="p-2">
                <button className="bg-blue-600 text-white px-2 py-1 rounded text-xs mr-2">
                  View
                </button>
                <button className="bg-green-500 text-white px-2 py-1 rounded text-xs">
                  Export
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

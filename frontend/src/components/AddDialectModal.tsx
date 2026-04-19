import { useState, useRef, useEffect } from 'react';

interface AddDialectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (dialectName: string) => void;
}

export default function AddDialectModal({ isOpen, onClose, onAdd }: AddDialectModalProps) {
  const [dialectName, setDialectName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = dialectName.trim();
    if (trimmedName) {
      onAdd(trimmedName);
      setDialectName('');
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div 
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        <div className="bg-gradient-to-r from-indigo-500 to-cyan-500 px-6 py-4">
          <h3 className="text-lg font-semibold text-white">Thêm bộ ngôn ngữ mới</h3>
          <p className="text-sm text-indigo-100 mt-1">
            Nhập tên bộ ngôn ngữ bạn muốn thêm vào danh sách
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tên bộ ngôn ngữ
            </label>
            <input
              ref={inputRef}
              type="text"
              value={dialectName}
              onChange={(e) => setDialectName(e.target.value)}
              placeholder="Ví dụ: Cần Thơ, Miền núi, v.v."
              className="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:ring-2 focus:ring-gray-500 transition-all"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={!dialectName.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-lg hover:from-indigo-600 hover:to-cyan-600 focus:ring-2 focus:ring-indigo-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Thêm mới
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

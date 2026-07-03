import React from 'react';
import Button from './Button';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages = [];
  const maxVisiblePages = 5;

  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
  let endPage = startPage + maxVisiblePages - 1;

  if (endPage > totalPages) {
    endPage = totalPages;
    startPage = Math.max(1, endPage - maxVisiblePages + 1);
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }

  const handleInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const val = parseInt(e.currentTarget.value, 10);
      if (!isNaN(val) && val >= 1 && val <= totalPages) {
        onPageChange(val);
        e.currentTarget.value = '';
      } else {
        alert(`Không tìm thấy trang bạn muốn kiếm! Vui lòng nhập từ 1 đến ${totalPages}.`);
      }
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-center gap-1 sm:gap-2 mt-4 text-sm sm:text-base">
      <Button
        variant="secondary"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-2 py-1"
      >
        &lt;
      </Button>

      {startPage > 1 && (
        <>
          <button
            onClick={() => onPageChange(1)}
            className="px-3 py-1 rounded hover:bg-gray-100 text-gray-700"
          >
            1
          </button>
          {startPage > 2 && <span className="text-gray-500 px-1">...</span>}
        </>
      )}

      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onPageChange(p)}
          className={`px-3 py-1 rounded transition-colors ${
            currentPage === p
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'hover:bg-gray-100 text-gray-700'
          }`}
        >
          {p}
        </button>
      ))}

      {endPage < totalPages && (
        <>
          {endPage < totalPages - 1 && <span className="text-gray-500 px-1">...</span>}
          <button
            onClick={() => onPageChange(totalPages)}
            className="px-3 py-1 rounded hover:bg-gray-100 text-gray-700"
          >
            {totalPages}
          </button>
        </>
      )}

      <Button
        variant="secondary"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-2 py-1"
      >
        &gt;
      </Button>

      <div className="flex items-center ml-2 border border-gray-300 rounded overflow-hidden">
        <input
          type="number"
          min={1}
          max={totalPages}
          placeholder="Đến trang..."
          className="w-24 px-2 py-1 outline-none text-sm"
          onKeyDown={handleInput}
        />
      </div>
    </div>
  );
}

import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

/**
 * Bộ dựng Markdown cho văn bản pháp lý.
 *
 * Hai nhóm khẳng định, và nhóm thứ hai là lý do bộ dựng này tự viết thay vì
 * dùng thư viện:
 *
 *   1. Cú pháp mà bốn văn bản thật sự dùng phải ra đúng thẻ.
 *   2. Nội dung do quản trị viên nhập KHÔNG được trở thành mã chạy được. Trang
 *      này công khai, nên một tài khoản quản trị bị chiếm sẽ có đường chạy
 *      script trong trình duyệt của mọi người đang đọc điều khoản.
 */

import Markdown from '../Markdown';

describe('Markdown — cú pháp dùng trong văn bản pháp lý', () => {
  it('dựng tiêu đề thành đúng cấp thẻ', () => {
    render(<Markdown text={'# Điều khoản\n\n## Mục 1'} />);

    expect(screen.getByRole('heading', { level: 1, name: 'Điều khoản' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Mục 1' })).toBeInTheDocument();
  });

  it('gom các dòng liền nhau thành một đoạn', () => {
    render(<Markdown text={'Dòng một\ndòng hai.'} />);

    expect(screen.getByText('Dòng một dòng hai.')).toBeInTheDocument();
  });

  it('dựng danh sách gạch đầu dòng thành các mục', () => {
    render(<Markdown text={'- một\n- hai\n- ba'} />);

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });

  it('dựng bảng thành thẻ table với đúng số dòng', () => {
    render(
      <Markdown
        text={'| Dữ liệu | Vì sao |\n|---|---|\n| Email | đăng nhập |\n| IP | chống lạm dụng |'}
      />,
    );

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Dữ liệu' })).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(3); // 1 tiêu đề + 2 dòng
  });

  it('dựng trích dẫn — khối cảnh báo "bản thảo" ở đầu mỗi văn bản', () => {
    render(<Markdown text={'> **Bản thảo kỹ thuật.** Chưa qua rà soát.'} />);

    expect(screen.getByText(/Chưa qua rà soát/)).toBeInTheDocument();
    expect(screen.getByText('Bản thảo kỹ thuật.').tagName).toBe('STRONG');
  });

  it('không nhầm đường kẻ ngang thành một mục danh sách', () => {
    // `---` cũng bắt đầu bằng `-`, nên thứ tự xét trong bộ dựng có ý nghĩa.
    const { container } = render(<Markdown text={'Đoạn.\n\n---\n\nĐoạn sau.'} />);

    expect(container.querySelector('hr')).toBeInTheDocument();
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
  });
});

describe('Markdown — nội dung không trở thành mã chạy được', () => {
  it('hiện thẻ script dưới dạng chữ, không dựng thành phần tử', () => {
    const { container } = render(
      <Markdown text={'Đoạn <script>alert(1)</script> tiếp theo.'} />,
    );

    expect(container.querySelector('script')).toBeNull();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
  });

  it('bỏ đường dẫn javascript: và chỉ giữ lại phần chữ', () => {
    // Tránh `innerHTML` không đủ: `href` là đường thứ hai để nhét mã vào trang.
    const { container } = render(
      <Markdown text={'[bấm vào đây](javascript:doHarm)'} />,
    );

    expect(container.querySelector('a')).toBeNull();
    expect(screen.getByText('bấm vào đây')).toBeInTheDocument();
  });

  it('bỏ đường dẫn data: — đường vòng quen thuộc khi javascript: bị chặn', () => {
    const { container } = render(
      <Markdown text={'[tải về](data:text/html;base64,PHNjcmlwdD4=)'} />,
    );

    expect(container.querySelector('a')).toBeNull();
  });

  it('bỏ đường dẫn giao thức tương đối //, vốn trỏ ra ngoài chứ không vào trong', () => {
    // `//evil.example` trông như đường nội bộ vì bắt đầu bằng `/`, nhưng trình
    // duyệt đọc nó là `https://evil.example`.
    const { container } = render(<Markdown text={'[trong nhà](//evil.example/x)'} />);

    expect(container.querySelector('a')).toBeNull();
  });

  it('giữ liên kết http và liên kết nội bộ', () => {
    render(<Markdown text={'[ra ngoài](https://ctu.edu.vn) và [vào trong](/legal/privacy)'} />);

    expect(screen.getByRole('link', { name: 'ra ngoài' })).toHaveAttribute(
      'href',
      'https://ctu.edu.vn',
    );
    expect(screen.getByRole('link', { name: 'vào trong' })).toHaveAttribute(
      'href',
      '/legal/privacy',
    );
  });

  it('gắn rel=noopener cho liên kết mở tab mới', () => {
    render(<Markdown text={'[ra ngoài](https://ctu.edu.vn)'} />);

    expect(screen.getByRole('link', { name: 'ra ngoài' })).toHaveAttribute(
      'rel',
      'noopener noreferrer',
    );
  });
});

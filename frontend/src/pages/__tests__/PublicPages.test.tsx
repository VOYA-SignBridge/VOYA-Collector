import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Ba trang công khai (Giới thiệu, Hỏi đáp, Liên hệ) và trình phát video có phụ đề.
 *
 * Điều đáng canh: người dùng chính là người khiếm thính, nên video LUÔN có hai
 * đường phụ đề + bản chữ; trang Liên hệ không bao giờ hiện một địa chỉ email bịa ra;
 * và khách thấy nút Đăng ký/Đăng nhập còn người đã đăng nhập thì không.
 */
const auth = vi.hoisted(() => ({ user: null as { id: string } | null }));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: auth.user }) }));

import AboutPage from '../AboutPage';
import FaqPage from '../FaqPage';
import ContactPage from '../ContactPage';
import CaptionedVideo from '../../components/guide/CaptionedVideo';
import { contactEmail } from '../../lib/publicConfig';

const CUES = {
  title: { vi: 'Hướng dẫn nhanh', en: 'Quick guide' },
  cues: [
    { start: 0, heading: { vi: 'Bước 1 · Đăng nhập', en: 'Step 1 · Sign in' }, line: { vi: 'Tạo tài khoản.', en: 'Create an account.' } },
    { start: 65, heading: { vi: 'Bước 2', en: 'Step 2' }, line: { vi: 'Chọn ký hiệu.', en: 'Choose a sign.' } },
  ],
};

const show = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

function setEnv(env: Record<string, string> | undefined) {
  (window as unknown as { __ENV__?: unknown }).__ENV__ = env;
}

beforeEach(() => {
  auth.user = null;
  setEnv(undefined);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => CUES }));
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('CaptionedVideo', () => {
  it('có phụ đề tiếng Việt và tiếng Anh, và đường dẫn tương đối để chạy dưới /voya/', () => {
    const { container } = show(<CaptionedVideo name="huong-dan" />);
    const tracks = [...container.querySelectorAll('track')];
    expect(tracks.map((t) => t.getAttribute('srclang'))).toEqual(['vi', 'en']);
    expect(tracks.every((t) => t.getAttribute('kind') === 'captions')).toBe(true);
    expect(tracks[0].getAttribute('src')).toBe('media/huong-dan.vi.vtt'); // không có "/" đầu
    expect(container.querySelector('source')!.getAttribute('src')).toBe('media/huong-dan.webm');
  });

  it('phụ đề mặc định theo ngôn ngữ giao diện (tiếng Việt)', () => {
    const { container } = show(<CaptionedVideo name="huong-dan" />);
    const [vi, en] = [...container.querySelectorAll('track')];
    expect(vi.hasAttribute('default')).toBe(true);
    expect(en.hasAttribute('default')).toBe(false);
  });

  it('dựng bản chữ từ tệp nguồn, kèm mốc thời gian', async () => {
    show(<CaptionedVideo name="huong-dan" />);
    await waitFor(() => expect(screen.getByText('Xem bản chữ của video')).toBeInTheDocument());
    expect(screen.getByText('Tạo tài khoản.')).toBeInTheDocument();
    expect(screen.getByText('0:00')).toBeInTheDocument();
    expect(screen.getByText('1:05')).toBeInTheDocument();
  });

  it('không tải được tệp nguồn thì video vẫn xem được, chỉ thiếu bản chữ', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')));
    const { container } = show(<CaptionedVideo name="huong-dan" />);
    await waitFor(() => expect(container.querySelector('video')).not.toBeNull());
    expect(screen.queryByText('Xem bản chữ của video')).toBeNull();
  });

  it('nói rõ video không có tiếng', () => {
    show(<CaptionedVideo name="huong-dan" />);
    expect(screen.getByText(/Video không có tiếng/)).toBeInTheDocument();
  });
});

describe('AboutPage', () => {
  it('khách thấy Đăng ký và Đăng nhập', () => {
    show(<AboutPage />);
    expect(screen.getByRole('link', { name: 'Đăng ký' })).toHaveAttribute('href', '/register');
    expect(screen.getByRole('link', { name: 'Đăng nhập' })).toHaveAttribute('href', '/login');
  });

  it('người đã đăng nhập không còn thấy lời mời đăng ký', () => {
    auth.user = { id: 'u1' };
    show(<AboutPage />);
    expect(screen.queryByRole('link', { name: 'Đăng ký' })).toBeNull();
  });

  it('trỏ tới ba việc chính và có video hướng dẫn', () => {
    const { container } = show(<AboutPage />);
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(expect.arrayContaining(['/learn', '/upload', '/realtime', '/faq', '/legal/terms', '/legal/privacy']));
    expect(container.querySelector('video')).not.toBeNull();
  });
});

describe('FaqPage', () => {
  it('mỗi câu hỏi là một <details> mở được bằng bàn phím, và có đường tới Liên hệ', () => {
    const { container } = show(<FaqPage />);
    const items = container.querySelectorAll('details');
    expect(items.length).toBeGreaterThanOrEqual(8);
    expect([...items].every((d) => d.querySelector('summary'))).toBe(true);
    expect(screen.getByRole('link', { name: 'Liên hệ' })).toHaveAttribute('href', '/contact');
  });

  it('không hứa điều hệ thống không làm: tên đăng nhập không đổi được', () => {
    show(<FaqPage />);
    expect(screen.getByText(/Tên đăng nhập gắn với dữ liệu bạn đã đóng góp nên không đổi được/)).toBeInTheDocument();
  });
});

describe('ContactPage', () => {
  it('chưa đặt email thì nói thẳng, không hiện địa chỉ nào', () => {
    show(<ContactPage />);
    expect(screen.getByText(/Địa chỉ email liên hệ chưa được thiết lập/)).toBeInTheDocument();
    expect(document.querySelector('a[href^="mailto:"]')).toBeNull();
  });

  it('đã đặt email thì hiện liên kết mailto', () => {
    setEnv({ VITE_CONTACT_EMAIL: 'ho-tro@ctu.edu.vn' });
    show(<ContactPage />);
    expect(screen.getByRole('link', { name: 'ho-tro@ctu.edu.vn' })).toHaveAttribute('href', 'mailto:ho-tro@ctu.edu.vn');
  });

  it('khách được chỉ đường về Quên mật khẩu; người đã đăng nhập được chỉ tới Hỗ trợ', () => {
    const { unmount } = show(<ContactPage />);
    expect(screen.getByRole('link', { name: 'Quên mật khẩu?' })).toHaveAttribute('href', '/forgot-password');
    unmount();
    auth.user = { id: 'u1' };
    show(<ContactPage />);
    expect(screen.getByRole('link', { name: 'Mở Hỗ trợ' })).toHaveAttribute('href', '/settings/support');
  });

  it('có địa chỉ đơn vị thực hiện', () => {
    show(<ContactPage />);
    const who = screen.getByRole('heading', { name: 'Đơn vị thực hiện' }).closest('section')!;
    expect(within(who).getByText(/Ninh Kiều, Cần Thơ/)).toBeInTheDocument();
  });
});

describe('contactEmail — giá trị đi thẳng vào mailto:', () => {
  it.each([
    ['ho-tro@ctu.edu.vn', 'ho-tro@ctu.edu.vn'],
    ['', ''],
    ['__VITE_CONTACT_EMAIL__', ''],
    ['không phải email', ''],
    ['a@b.vn" onmouseover="x', ''],
    ['javascript:alert(1)', ''],
  ])('%j -> %j', (input, expected) => {
    setEnv({ VITE_CONTACT_EMAIL: input });
    expect(contactEmail()).toBe(expected);
  });

  it('không có __ENV__ thì là rỗng', () => {
    setEnv(undefined);
    expect(contactEmail()).toBe('');
  });
});

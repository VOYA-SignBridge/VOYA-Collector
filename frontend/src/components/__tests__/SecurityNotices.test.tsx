import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import SecurityNotices from '../SecurityNotices';

/**
 * Proves the session-ended redirect stays UNDER the deployment's base path
 * (e.g. "/voya/") instead of jumping to the domain root — the exact bug the
 * user reported. Each test logs the ACTUAL href the button navigated to.
 *
 * jsdom throws on real navigation, so we replace window.location with a stub
 * that just records writes to `.href`.
 */

const originalLocation = Object.getOwnPropertyDescriptor(window, 'location');
let hrefWrites: string[] = [];

function stubLocation() {
  hrefWrites = [];
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      get href() {
        return hrefWrites[hrefWrites.length - 1] ?? '';
      },
      set href(v: string) {
        hrefWrites.push(v);
      },
    },
  });
}

function setBasePath(base: string) {
  (window as unknown as { __ENV__: Record<string, string> }).__ENV__ = {
    VITE_API_URL: '',
    VITE_BASE_PATH: base,
  };
}

describe('SecurityNotices — session-ended redirect stays under base path', () => {
  beforeEach(() => stubLocation());
  afterEach(() => {
    if (originalLocation) Object.defineProperty(window, 'location', originalLocation);
  });

  it('idle-logout under /voya returns to /voya/ (NOT domain root)', () => {
    setBasePath('/voya');
    render(<SecurityNotices />);
    act(() => {
      window.dispatchEvent(new CustomEvent('voya:idle-logout'));
    });
    fireEvent.click(screen.getByText('Đăng nhập lại'));

    console.log('[evidence] base="/voya", idle-logout redirect ->', window.location.href);
    expect(window.location.href).toBe('/voya/');
    expect(window.location.href).not.toBe('/login'); // the old buggy target
  });

  it('force-logout under /voya returns to /voya/', () => {
    setBasePath('/voya');
    render(<SecurityNotices />);
    act(() => {
      window.dispatchEvent(
        new CustomEvent('voya:forcelogout', { detail: { message: 'admin logged you out' } }),
      );
    });
    fireEvent.click(screen.getByText('Đăng nhập lại'));

    console.log('[evidence] base="/voya", force-logout redirect ->', window.location.href);
    expect(window.location.href).toBe('/voya/');
  });

  it('root deploy (this machine) still returns to "/" — unchanged', () => {
    setBasePath('/');
    render(<SecurityNotices />);
    act(() => {
      window.dispatchEvent(new CustomEvent('voya:idle-logout'));
    });
    fireEvent.click(screen.getByText('Đăng nhập lại'));

    console.log('[evidence] base="/", idle-logout redirect ->', window.location.href);
    expect(window.location.href).toBe('/');
  });
});

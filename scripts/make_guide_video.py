"""Dựng video hướng dẫn mẫu (WebM) và hai tệp phụ đề (WebVTT) từ một tệp nguồn.

    python scripts/make_guide_video.py            # ghi vào frontend/public/media/

Nguồn duy nhất là `frontend/public/media/huong-dan.cues.json`: mỗi mục có thời điểm,
tiêu đề bước và câu phụ đề (vi/en). Cùng tệp đó được trang web đọc để dựng bản chữ
(transcript), nên video, phụ đề và bản chữ không thể lệch nhau.

Đây là video MẪU dựng bằng hình vẽ, không có tiếng và không có người ký hiệu. Muốn
thay bằng video thật: giữ tên `huong-dan.webm` (hoặc đổi tên trong `GuidePage`) và
sửa thời điểm trong tệp cues cho khớp.

Chỉ cần Pillow, numpy và OpenCV (đã có trong môi trường backend). Mã hoá VP9/WebM
bằng OpenCV nên không cần ffmpeg.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "frontend" / "public" / "media"
W, H, FPS = 960, 540, 15

NAVY = (11, 42, 91)
BLUE = (30, 95, 180)
WHITE = (255, 255, 255)
SKY = (186, 230, 253)
RED = (220, 38, 38)
SKIN = (255, 214, 170)

_FONTS = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)
_REGULAR = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
)


def _font(candidates, size):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("Không tìm thấy phông chữ có tiếng Việt; cài DejaVu Sans hoặc chạy trên Windows.")


def _fit(draw, text, candidates, size, max_width):
    """Phông to nhất không quá `max_width`."""
    while size > 18:
        font = _font(candidates, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _font(candidates, size)


def _wrap(draw, text, size, max_width):
    """Tách `text` thành các dòng vừa `max_width` ở cỡ chữ `size`."""
    font = _font(_FONTS, size)
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def _gradient():
    top, bottom = np.array(NAVY, float), np.array(BLUE, float)
    ys = np.linspace(0, 1, H)[:, None, None]
    return (top * (1 - ys) + bottom * ys).repeat(W, axis=1).astype(np.uint8)


BACKGROUND = _gradient()


# ------------------------------------------------------------------ hình minh hoạ
def _hand(d, cx, cy, scale, wave, mirror=False):
    """Bàn tay cách điệu: lòng bàn tay + bốn ngón + ngón cái."""
    s = scale
    sign = -1 if mirror else 1
    palm = (cx - 38 * s, cy - 10 * s, cx + 38 * s, cy + 55 * s)
    d.rounded_rectangle(palm, radius=int(22 * s), fill=SKIN)
    for i, (dx, length) in enumerate(((-30, 62), (-10, 74), (10, 70), (30, 56))):
        x = cx + dx * s
        lift = math.sin(wave + i * 0.7) * 5 * s
        d.rounded_rectangle((x - 9 * s, cy - length * s + lift, x + 9 * s, cy), radius=int(9 * s), fill=SKIN)
    tx = cx + sign * 44 * s
    d.rounded_rectangle((tx - 9 * s, cy + 2 * s, tx + 9 * s, cy + 46 * s), radius=int(9 * s), fill=SKIN)


def _frame_brackets(d, x0, y0, x1, y1, color, w=6, n=42):
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line((x, y, x + sx * n, y), fill=color, width=w)
        d.line((x, y, x, y + sy * n), fill=color, width=w)


def _illustration(d, kind, t, dur):
    cx, cy = 690, 300
    if kind == "title":
        r = 105 + 6 * math.sin(t * 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=SKY, width=6)
        _hand(d, cx - 55, cy + 8, 1.15, t * 3)
        _hand(d, cx + 55, cy + 8, 1.15, t * 3 + 1, mirror=True)
    elif kind == "account":
        d.rounded_rectangle((cx - 150, cy - 125, cx + 150, cy + 125), radius=26, fill=WHITE)
        d.ellipse((cx - 42, cy - 92, cx + 42, cy - 8), fill=BLUE)
        d.pieslice((cx - 98, cy + 14, cx + 98, cy + 210), 180, 360, fill=BLUE)
    elif kind == "menu":
        labels = ("Đóng góp dữ liệu", "Thư viện nhãn", "Học ký hiệu", "Nhận dạng")
        font = _font(_REGULAR, 21)
        pulse = 4 + 3 * math.sin(t * 5)
        for i, text in enumerate(labels):
            x = cx - 175 + (i % 2) * 180
            y = cy - 105 + (i // 2) * 125
            hot = i == 0
            d.rounded_rectangle((x, y, x + 170, y + 110), radius=18, fill=WHITE,
                                outline=(245, 179, 1) if hot else None, width=int(pulse) if hot else 0)
            wlen = d.textlength(text, font=font)
            d.text((x + 85 - wlen / 2, y + 40), text, font=font, fill=NAVY)
    elif kind in ("camera", "record"):
        x0, y0, x1, y1 = cx - 205, cy - 150, cx + 205, cy + 150
        d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=(20, 33, 61))
        _frame_brackets(d, x0 + 14, y0 + 14, x1 - 14, y1 - 14, SKY)
        sway = math.sin(t * 2.2) * 8
        _hand(d, cx - 85, cy + 25 + sway, 1.25, t * 4)
        _hand(d, cx + 85, cy + 25 - sway, 1.25, t * 4 + 2, mirror=True)
        if kind == "record":
            if int(t * 2) % 2 == 0:
                d.ellipse((x0 + 26, y0 + 26, x0 + 48, y0 + 48), fill=RED)
            font = _font(_FONTS, 22)
            d.text((x0 + 58, y0 + 24), "ĐANG GHI", font=font, fill=WHITE)
            secs = int(t)
            d.text((x1 - 90, y0 + 24), f"00:0{min(secs, 9)}", font=font, fill=WHITE)
    elif kind == "send":
        r = 130
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE)
        progress = min(1.0, t / 1.2)
        p1, p2, p3 = (cx - 62, cy + 4), (cx - 18, cy + 50), (cx + 66, cy - 46)
        if progress > 0:
            seg1 = min(1.0, progress * 2)
            d.line((p1[0], p1[1], p1[0] + (p2[0] - p1[0]) * seg1, p1[1] + (p2[1] - p1[1]) * seg1), fill=(22, 163, 74), width=18)
        if progress > 0.5:
            seg2 = (progress - 0.5) * 2
            d.line((p2[0], p2[1], p2[0] + (p3[0] - p2[0]) * seg2, p2[1] + (p3[1] - p2[1]) * seg2), fill=(22, 163, 74), width=18)
    elif kind == "thanks":
        for i in range(5):
            ang = t * 0.9 + i * (2 * math.pi / 5)
            px, py = cx + math.cos(ang) * 120, cy + math.sin(ang) * 120
            d.polygon([(px, py - 22), (px + 8, py - 7), (px + 24, py - 5), (px + 12, py + 6),
                       (px + 15, py + 22), (px, py + 14), (px - 15, py + 22), (px - 12, py + 6),
                       (px - 24, py - 5), (px - 8, py - 7)], fill=(245, 179, 1))
        _hand(d, cx - 45, cy + 5, 1.0, t * 3)
        _hand(d, cx + 45, cy + 5, 1.0, t * 3 + 1, mirror=True)


# ------------------------------------------------------------------ dựng khung hình
def render(cue, t, dur, total_t, total, lang="vi"):
    img = Image.fromarray(BACKGROUND.copy())
    d = ImageDraw.Draw(img)

    d.text((48, 36), "CTU.SignBridge", font=_font(_FONTS, 26), fill=SKY)

    heading = cue["heading"][lang]
    big = cue["kind"] in ("title", "thanks")
    label, _, title = heading.partition(" · ")
    if not title:  # không có nhãn bước: cả chuỗi là tiêu đề
        label, title = "", heading
    y = 190 if not label else 150
    if label:
        d.text((48, y), label, font=_font(_FONTS, 30), fill=SKY)
        y += 52
    for line in _wrap(d, title, 64 if big else 46, 420):
        font = _fit(d, line, _FONTS, 64 if big else 46, 420)
        d.text((48, y), line, font=font, fill=WHITE)
        y += int(font.size * 1.25)

    if cue["kind"] == "title":
        sub = _font(_REGULAR, 28)
        d.text((48, 285), "Chỉ mất vài phút", font=sub, fill=SKY)

    _illustration(d, cue["kind"], t, dur)

    # thanh tiến độ toàn video
    d.rounded_rectangle((48, H - 36, W - 48, H - 28), radius=4, fill=(70, 110, 180))
    d.rounded_rectangle((48, H - 36, 48 + (W - 96) * (total_t / total), H - 28), radius=4, fill=WHITE)

    frame = np.array(img)
    fade = min(1.0, t / 0.4)  # hiện dần ở đầu mỗi cảnh
    if fade < 1.0:
        frame = (BACKGROUND * (1 - fade) + frame * fade).astype(np.uint8)
    return frame


def _stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_vtt(path: Path, cues, lang: str) -> None:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{_stamp(c['start'])} --> {_stamp(c['end'])}", c["line"][lang], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    data = json.loads((MEDIA / "huong-dan.cues.json").read_text(encoding="utf-8"))
    cues = data["cues"]
    total = cues[-1]["end"]

    out = MEDIA / "huong-dan.webm"
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"VP90"), FPS, (W, H))
    if not writer.isOpened():
        raise SystemExit("OpenCV không mở được bộ mã hoá VP9/WebM trên máy này.")
    n = int(total * FPS)
    poster_done = False
    for i in range(n):
        now = i / FPS
        cue = next(c for c in cues if c["start"] <= now < c["end"]) if now < total else cues[-1]
        frame = render(cue, now - cue["start"], cue["end"] - cue["start"], now, total)
        if not poster_done and now >= 1.0:
            Image.fromarray(frame).convert("RGB").save(MEDIA / "huong-dan.poster.jpg", quality=82)
            poster_done = True
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()

    for lang in ("vi", "en"):
        write_vtt(MEDIA / f"huong-dan.{lang}.vtt", cues, lang)

    size = out.stat().st_size / 1024
    print(f"đã ghi {out.name} ({n} khung, {total:.0f} giây, {size:.0f} KB), 2 tệp .vtt và ảnh bìa")
    return 0


if __name__ == "__main__":
    sys.exit(main())

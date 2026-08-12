import { describe, it, expect } from "vitest";
import { handLayout, wristSeparation, FRAME_DIM, DIMS_PER_HAND } from "../handData";

/**
 * Hai quy ước toạ độ cùng nằm trên đĩa, nên bố cục phải quyết theo TỪNG mẫu.
 *
 * - wrist-centred: bộ chuẩn hoá trừ đi cổ tay của chính mỗi bàn tay, nên cả hai
 *   cổ tay rơi vào gốc. Vẽ chung một khung bao là hai tay chồng lên nhau thành
 *   một khối rối, dính nhau ở giữa.
 * - image-coords (~11% số mẫu): giữ nguyên toạ độ ảnh, hai tay ĐÃ ở đúng vị trí
 *   tương đối và đúng tỉ lệ so với nhau.
 *
 * Ép tất cả vào hai cột thì sửa được nhóm đầu nhưng làm hỏng nhóm sau: nó dời
 * bàn tay vốn đã đúng chỗ và co giãn từng tay riêng, bịa ra một bố cục mà bản
 * ghi chưa bao giờ có.
 */

const zeroFrame = () => new Array<number>(FRAME_DIM).fill(0);

/** 21 điểm quanh gốc, cổ tay ghim đúng (0,0,0) — đúng như bộ chuẩn hoá tạo ra. */
function wristCentredFrame(seed: number): number[] {
  const frame = zeroFrame();
  for (const base of [0, DIMS_PER_HAND]) {
    for (let i = 0; i < 21; i++) {
      const t = seed + i + base;
      frame[base + i * 3] = i === 0 ? 0 : Math.sin(t) * 0.4;
      frame[base + i * 3 + 1] = i === 0 ? 0 : Math.cos(t) * 0.4;
      frame[base + i * 3 + 2] = i === 0 ? 0 : Math.sin(t * 2) * 0.1;
    }
  }
  return frame;
}

/** Toạ độ ảnh: tay trái quanh x=0.3, tay phải quanh x=0.7. */
function imageCoordsFrame(seed: number, rightScale = 1): number[] {
  const frame = zeroFrame();
  const spec: [number, number, number][] = [
    [0, 0.3, 1],
    [DIMS_PER_HAND, 0.7, rightScale],
  ];
  for (const [base, cx, scale] of spec) {
    for (let i = 0; i < 21; i++) {
      const t = seed + i;
      frame[base + i * 3] = cx + Math.sin(t) * 0.1 * scale;
      frame[base + i * 3 + 1] = 0.5 + Math.cos(t) * 0.1 * scale;
      frame[base + i * 3 + 2] = 0.02;
    }
  }
  return frame;
}

describe("wristSeparation — khoảng cách hai cổ tay theo kích thước bàn tay", () => {
  it("bằng 0 khi cả hai cổ tay nằm ở gốc", () => {
    const seq = [wristCentredFrame(1), wristCentredFrame(2), wristCentredFrame(3)];
    expect(wristSeparation(seq)).toBe(0);
  });

  it("lớn rõ rệt khi bản ghi giữ toạ độ ảnh", () => {
    const seq = [imageCoordsFrame(1), imageCoordsFrame(2)];
    expect(wristSeparation(seq)!).toBeGreaterThan(0.1);
  });

  it("trả null khi hai tay không bao giờ xuất hiện cùng khung", () => {
    const frame = zeroFrame();
    for (let i = 0; i < 21; i++) frame[i * 3] = 0.1 + i * 0.01;
    expect(wristSeparation([frame])).toBeNull();
  });
});

describe("handLayout — chọn bố cục theo dữ liệu, không mặc định", () => {
  it("tách hai cột khi hai cổ tay trùng nhau", () => {
    const seq = [wristCentredFrame(1), wristCentredFrame(2), wristCentredFrame(3)];
    const layout = handLayout(seq);
    expect(layout.mode).toBe("columns");
    // Mỗi tay nằm gọn trong nửa canvas của nó.
    const [lx] = layout.left.toUnit(0, 0);
    const [rx] = layout.right.toUnit(0, 0);
    expect(lx).toBeLessThan(0.5);
    expect(rx).toBeGreaterThan(0.5);
  });

  it("GIỮ NGUYÊN vị trí khi bản ghi đã có toạ độ thật", () => {
    const seq = [imageCoordsFrame(1), imageCoordsFrame(2), imageCoordsFrame(3)];
    const layout = handLayout(seq);
    expect(layout.mode).toBe("shared");
    // Dùng chung một phép biến đổi — đó là điều giữ được khoảng cách thật.
    expect(layout.left).toBe(layout.right);
  });

  it("giữ tỉ lệ tương đối giữa hai tay ở chế độ shared", () => {
    // Tay phải nhỏ bằng 40% tay trái; sau khi vẽ vẫn phải nhỏ hơn rõ rệt.
    const seq = [imageCoordsFrame(1, 0.4), imageCoordsFrame(2, 0.4)];
    const layout = handLayout(seq);
    expect(layout.mode).toBe("shared");

    const widthOf = (base: number) => {
      const xs: number[] = [];
      for (const frame of seq) {
        for (let i = 0; i < 21; i++) {
          xs.push(layout.left.toUnit(frame[base + i * 3], frame[base + i * 3 + 1])[0]);
        }
      }
      return Math.max(...xs) - Math.min(...xs);
    };
    expect(widthOf(0)).toBeGreaterThan(widthOf(DIMS_PER_HAND) * 1.5);
  });

  it("KHÔNG tách hai tay thật sự gần nhau", () => {
    // Ngưỡng cũ 0.05 trông an toàn với dữ liệu chuẩn hoá (điểm số đúng bằng 0),
    // nhưng trên landmark gốc mẫu gần nhau nhất chỉ 0.0154 — nó đã kéo hai bàn
    // tay đang chạm nhau về hai cột đối diện, bịa ra khoảng cách không có thật.
    const handAt = (wx: number, wy: number, base: number, frame: number[]) => {
      for (let i = 0; i < 21; i++) {
        frame[base + i * 3] = wx + (i === 0 ? 0 : 0.01 * i);
        frame[base + i * 3 + 1] = wy + (i === 0 ? 0 : 0.008 * i);
        frame[base + i * 3 + 2] = 0.01 * i;
      }
    };
    const frame = zeroFrame();
    handAt(0.4, 0.5, 0, frame);
    handAt(0.408, 0.5, DIMS_PER_HAND, frame);
    const seq = [frame, frame, frame];

    const sep = wristSeparation(seq)!;
    expect(sep).toBeGreaterThan(0.005);
    expect(sep).toBeLessThan(0.05);
    expect(handLayout(seq).mode).toBe("shared");
  });

  it("một bàn tay thì dùng trọn canvas, không chia cột", () => {
    const frame = zeroFrame();
    for (let i = 0; i < 21; i++) {
      frame[i * 3] = 0.2 + i * 0.01;
      frame[i * 3 + 1] = 0.3 + i * 0.01;
    }
    const layout = handLayout([frame, frame]);
    expect(layout.mode).toBe("shared");
    expect(layout.left).toBe(layout.right);
  });
});

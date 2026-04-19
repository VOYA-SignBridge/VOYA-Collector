declare module '@mediapipe/hands' {
  // Minimal ambient declaration to satisfy TypeScript when @mediapipe/hands types are not installed.
  export const HAND_CONNECTIONS: unknown;
  export class Hands {
    constructor(options?: unknown);
    setOptions(options: unknown): void;
    onResults(cb: (results: unknown) => void): void;
    send(input: unknown): Promise<void>;
    close(): void;
  }
  export default Hands;
}

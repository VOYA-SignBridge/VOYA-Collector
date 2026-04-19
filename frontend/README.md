# VOYA Motion Capture Frontend

A professional React + TypeScript application for collecting and processing motion capture data using MediaPipe Hands for real-time pose detection.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env

# Start development server
npm run dev

# Build for production
npm run build
```

## �️ Technical Stack

- **React 19.1.1** - Modern React with strict mode
- **TypeScript** - Full type safety and IntelliSense
- **Vite 7.1.9** - Fast build tool with HMR
- **Tailwind CSS v4** - Modern utility-first styling
- **MediaPipe Holistic** - AI-powered real-time pose detection
- **Axios** - HTTP client with retry logic and error handling

## ⚙️ Environment Configuration

Create a `.env` file from `.env.example`:

```env
# Backend API URL
VITE_API_URL=http://localhost:8000

# Environment
NODE_ENV=development
```

## 🎯 Core Features

### Motion Capture System

- **Fullscreen Capture Modal**: Immersive interface for professional data collection
- **Real-time Pose Detection**: MediaPipe integration for pose, face, and hand landmarks
- **Camera Management**: Automatic cleanup and error handling
- **Keyboard Shortcuts**: Space to start/stop, Escape to exit

### Data Management

- **Session Tracking**: Organized data collection with unique session IDs
- **Sample Management**: Track captures with metadata (user, label, frames)
- **Statistics Dashboard**: Real-time session statistics and progress tracking
- **Export Capabilities**: Data formatted for backend processing

### Professional UI/UX

- **Light Theme**: Clean, professional interface for data collection
- **Responsive Design**: Works across different screen sizes
- **Loading States**: Clear feedback during operations
- **Error Handling**: Comprehensive error messages and recovery

## � Backend API Integration

The frontend integrates with FastAPI backend using these endpoints:

### Video Upload

````typescript
POST /upload/video
Content-Type: multipart/form-data

FormData {
  file: File

## Backend (Docker)

If your backend runs inside Docker (local development or production), the frontend needs to know how to reach it. Below are common setups and what to set for `VITE_API_URL`.

- Backend container published to host port (common for local development)

  If your backend container maps port 8000 to the host (for example `-p 8000:8000`), use your host address. On Windows, browsers inside the host should use `localhost`:

  ```env
  VITE_API_URL=http://localhost:8000
````

If you run the frontend from the host machine and the backend is in Docker, this will reach the mapped port.

- Backend container accessed from frontend running on the host but Docker toolbox/VM users

  On some Windows setups (Docker Desktop, older toolbox, WSL differences), use the special DNS name `host.docker.internal` when containers need to talk to the host. Example when the frontend is running in a container and backend on host or another container:

  ```env
  VITE_API_URL=http://host.docker.internal:8000
  ```

- Backend + Frontend both in Docker Compose

  If you run both services in Docker Compose, services can reach each other by service name from inside containers. Example `docker-compose.yml` services `backend` and `frontend`:

  - From the frontend container use `http://backend:8000` as the API base URL.
  - For the host machine (your browser) use the published port: `http://localhost:8000`.

  Example compose snippet:

  ```yaml
  services:
    backend:
      build: ./backend
      ports:
        - "8000:8000"
    frontend:
      build: ./frontend
      ports:
        - "5173:5173"
      depends_on:
        - backend
  ```

- Health checks & quick verification

  Verify backend reachable from host:

  ```powershell
  curl http://localhost:8000/health
  ```

  If the frontend runs inside a container and cannot reach the host backend, try `host.docker.internal`:

  ```powershell
  curl http://host.docker.internal:8000/health
  ```

  - CORS and headers

  Make sure the backend includes correct CORS headers for your frontend origin during development (e.g., `http://localhost:5173`) or uses a permissive config for testing. FastAPI example:

  ```python
  from fastapi.middleware.cors import CORSMiddleware

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"]
  )
  ```

  user: string
  label: string
  }

````

### Camera Data Upload

```typescript
POST /upload/camera
Content-Type: application/json

{
  user: string,
  label: string,
  session_id: string,
  frames: Array<{
    timestamp: number,
    landmarks: {
      pose?: MediaPipeLandmark[],
      face?: MediaPipeLandmark[],
      left_hand?: MediaPipeLandmark[],
      right_hand?: MediaPipeLandmark[]
    }
  }>
}
````

### Response Format

```typescript
{
  success: boolean,
  task_id?: string,
  status?: string,
  filename?: string,
  total_frames?: number,
  detail?: string
}
```

## 🏗️ Project Structure

```
src/
├── components/           # React components
│   ├── ui/              # Reusable UI components
│   ├── dashboard/       # Dashboard-specific components
│   ├── CaptureCamera.tsx       # Main capture interface
│   ├── FullscreenCaptureModal.tsx  # Immersive capture modal
│   ├── SessionPanel.tsx        # Session management
│   └── ...
├── api/                 # API integration layer
│   ├── axiosClient.ts   # HTTP client configuration
│   ├── upload.ts        # Upload endpoints
│   ├── validators.ts    # Response validation
│   └── ...
├── pages/               # Page components
├── types.ts             # TypeScript type definitions
└── main.tsx            # Application entry point
```

## 🎮 Usage Guide

### Basic Data Collection Workflow

1. **Start Capture Session**

   ```typescript
   // Navigate to Capture Camera tab
   // Enter user name and label
   // Click "Start Fullscreen Capture"
   ```

2. **Record Motion Data**

   ```typescript
   // Position yourself in camera view
   // Press SPACE to start recording
   // Perform desired motion/action
   // Press SPACE to stop recording
   ```

3. **Data Processing**
   ```typescript
   // Data automatically uploaded to backend
   // Real-time landmarks extracted via MediaPipe
   // Session statistics updated
   ```

### Camera Capture Features

- **Real-time Preview**: Live camera feed with pose overlay
- **Landmark Detection**: Pose, face, and hand tracking
- **Session Management**: Organized data collection
- **Progress Tracking**: Frame count and timing statistics

## 🔧 Development

### Code Architecture

- **Component-based**: Modular React components with TypeScript
- **State Management**: React hooks for local state
- **API Layer**: Centralized HTTP client with error handling
- **Type Safety**: Full TypeScript coverage with strict mode

### Key Components

#### FullscreenCaptureModal

357-line comprehensive modal handling:

- MediaPipe Holistic integration
- Camera lifecycle management
- Real-time landmark detection
- Keyboard event handling
- Data collection and upload

#### CaptureCamera

Main interface component:

- Session management
- Backend API integration
- Loading states and error handling
- Statistics calculation

### Build System

- **Development**: `npm run dev` - Hot module replacement
- **Production**: `npm run build` - Optimized TypeScript compilation
- **Type Check**: `npm run type-check` - TypeScript validation
- **Linting**: ESLint configuration for code quality

## 🚀 Deployment

### Production Build

```bash
# Install dependencies
npm ci

# Build for production
npm run build

# Preview production build
npm run preview
```

## 🔔 Cập nhật & Thông tin bổ sung

### 🛠️ Tối ưu hoá thu dữ liệu (capture)

- Frame interval control: `FullscreenCaptureModal` hiện hỗ trợ điều chỉnh khoảng thời gian giữa 2 frame (ms) bằng slider và các preset (30/15/10/6/5/3 FPS). Mặc định là 100ms (~10 FPS).
- Real-time optimizations:
  - `modelComplexity` có thể giảm để tăng tốc inference khi cần.
  - `smoothLandmarks` có thể tắt để giảm lag hiển thị (phản hồi nhanh hơn khi người dùng di chuyển tay/chân).
  - Canvas rendering được schedule bằng `requestAnimationFrame` để tránh vẽ thừa và giảm jitter.
- Multi-capture flow: thu nhiều captures liên tiếp cùng label; upload không chặn UI/modal.

### 📐 Khuyến nghị thiết lập cho training

- Dynamic actions (ví dụ: walking, running): 10–15 FPS (67–100ms)
- Static poses (ví dụ: sitting, standing): 5–6 FPS (167–200ms)
- Gestures (waving, clapping): 15+ FPS (≈67ms)

Chú ý: sampling đều đặn (uniform sampling) giúp model học tốt hơn về đặc trưng thời gian của hành động.

### 🪄 Quick tips — khi capture bị lag hoặc lệch

- Kiểm tra quyền camera trong trình duyệt và đóng ứng dụng khác đang dùng camera.
- Tăng `frameInterval` để giảm số frame/giây nếu CPU bị quá tải.
- Tắt smoothing (nếu cần phản hồi real-time, trade-off: landmarks sẽ kém mượt hơn nhưng phản hồi nhanh hơn).
- Nếu preview đột ngột mất, mở DevTools và kiểm tra logs từ `FullscreenCaptureModal` (có logging frame counts, targetFrames, và progress).

### 🪄 Windows helper script

Có một script PowerShell hỗ trợ tại repo root: `dev.ps1`. Script này giúp chuẩn hoá workflow dev trên Windows:

- Sao chép `.env.example` → `.env` nếu `.env` không tồn tại
- Cài dependencies nếu `node_modules` chưa có
- Chạy `npm run dev`, `npm run build`, hoặc `npm run preview`

Sử dụng (PowerShell):

```powershell
# Start dev server via helper
.\dev.ps1

# Or via npm script
npm run dev:win
```

### 🧑‍💻 Ghi chú cho developer

- `src/components/FullscreenCaptureModal.tsx` là nơi chính cho các logic thu/đếm frame, xử lý multi-capture, và render landmarks.
- `src/components/CaptureCamera.tsx` quản lý session và trigger modal; upload được thực hiện không chặn UI.
- `README_ADDITIONS.md` cũng tồn tại nếu bạn muốn mở riêng phần helper nhanh.

---

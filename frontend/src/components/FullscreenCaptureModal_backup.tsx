import { useEffect, useRef, useState, useCallback } from "react";
import { Holistic, POSE_CONNECTIONS, HAND_CONNECTIONS } from "@mediapipe/holistic";
import { Camera } from "@mediapipe/camera_utils";
import * as drawing from "@mediapipe/drawing_utils";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import type { MediaPipeLandmark } from "../types";

interface FullscreenCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSampleCapture: (frames: Array<{
    pose: MediaPipeLandmark[];
    face: MediaPipeLandmark[];
    left_hand: MediaPipeLandmark[];
    right_hand: MediaPipeLandmark[];
  }>, label: string, user: string) => void;
  initialLabel?: string;
  initialUser?: string;
  targetFrames?: number;
  captureCount?: number;
}

export default function FullscreenCaptureModal({ 
  isOpen, 
  onClose, 
  onSampleCapture,
  initialLabel = "",
  initialUser = "",
  targetFrames = 60,
  captureCount = 1
}: FullscreenCaptureModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera | null>(null);
  
  const [recording, setRecording] = useState(false);
  const [frames, setFrames] = useState<Array<{
    pose: MediaPipeLandmark[];
    face: MediaPipeLandmark[];
    left_hand: MediaPipeLandmark[];
    right_hand: MediaPipeLandmark[];
  }>>([]);
  const [label, setLabel] = useState(initialLabel);
  const [user, setUser] = useState(initialUser);
  const [countdown, setCountdown] = useState(0);
  const [isReady, setIsReady] = useState(false);
  
  // New state for capture management
  const [currentCaptureIndex, setCurrentCaptureIndex] = useState(0);
  const [completedCaptures, setCompletedCaptures] = useState(0);
  const [showTips, setShowTips] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  
  // Refs to prevent stale closures
  const recordingRef = useRef(false);
  const framesRef = useRef<Array<{
    pose: MediaPipeLandmark[];
    face: MediaPipeLandmark[];
    left_hand: MediaPipeLandmark[];
    right_hand: MediaPipeLandmark[];
  }>>([]);
  // Hold-last-good for short missing periods and lightweight telemetry
  const lastGoodRef = useRef<{
    left: MediaPipeLandmark[] | null;
    right: MediaPipeLandmark[] | null;
    leftStreak: number;
    rightStreak: number;
  }>({ left: null, right: null, leftStreak: 0, rightStreak: 0 });
  const telemetryRef = useRef<{ framesProcessed: number; leftDetected: number; rightDetected: number }>({ framesProcessed: 0, leftDetected: 0, rightDetected: 0 });
  const labelRef = useRef(label);
  const userRef = useRef(user);
  const targetFramesRef = useRef(targetFrames);
  const captureCountRef = useRef(captureCount);
  const onSampleCaptureRef = useRef(onSampleCapture);
  const handleCloseRef = useRef<() => void>(() => {});

  const handleClose = useCallback(() => {
    setRecording(false);
    setFrames([]);
    setCountdown(0);
    setIsReady(false);
    setCurrentCaptureIndex(0);
    setCompletedCaptures(0);
    
    // Stop camera and close video stream
    if (cameraRef.current) {
      cameraRef.current.stop();
      cameraRef.current = null;
    }
    
    // Stop video tracks
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    
    onClose();
  }, [onClose]);
  
  // Update refs when state changes
  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);
  
  useEffect(() => {
    framesRef.current = frames;
  }, [frames]);

  useEffect(() => {
    labelRef.current = label;
  }, [label]);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

  useEffect(() => {
    targetFramesRef.current = targetFrames;
  }, [targetFrames]);

  useEffect(() => {
    captureCountRef.current = captureCount;
  }, [captureCount]);

  useEffect(() => {
    onSampleCaptureRef.current = onSampleCapture;
  }, [onSampleCapture]);

  useEffect(() => {
    handleCloseRef.current = handleClose;
  }, [handleClose]);

  // Quick labels for fast selection
  const quickLabels = [
    "walking", "running", "sitting", "standing", 
    "jumping", "waving", "pointing", "clapping",
    "dancing", "stretching", "exercising", "resting"
  ];

  // Handlers
  const handleQuickCapture = useCallback(() => {
    if (!labelRef.current || !userRef.current) return;
    // Reset capture state
    setFrames([]);
    framesRef.current = [];
    setCurrentCaptureIndex(0);
    setCompletedCaptures(0);
    setCountdown(3);
    
    setTimeout(() => {
      setRecording(true);
      recordingRef.current = true;
    }, 3000);
  }, []);

  const handleStop = useCallback(() => {
    setRecording(false);
    recordingRef.current = false;
    
    if (framesRef.current.length > 0) {
      onSampleCaptureRef.current(framesRef.current, labelRef.current, userRef.current);
      setFrames([]);
      framesRef.current = [];
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    const holistic = new Holistic({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/holistic/${file}`,
    });

    // Tune options for better responsiveness under fast motion:
    // - disable MediaPipe internal smoothing (we use short-hold + client-side smoothing instead)
    // - lower detection/tracking confidence slightly to increase recall on fast motion
    holistic.setOptions({
      modelComplexity: 1,
      smoothLandmarks: false,
      refineFaceLandmarks: false,
      minDetectionConfidence: 0.4,
      minTrackingConfidence: 0.3,
    });

    holistic.onResults((results) => {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      if (!canvas || !video) return;
      
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Always use fixed canvas size for consistency
      const canvasWidth = 1280;
      const canvasHeight = 720;
      
      if (canvas.width !== canvasWidth || canvas.height !== canvasHeight) {
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw the video frame first (this should always show the camera feed)
      try {
        if (video && video.readyState >= 2 && video.videoWidth > 0) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        } else if (results.image) {
          // Fallback to MediaPipe result image
          const img = results.image as HTMLImageElement | HTMLVideoElement;
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        } else {
          // Debug: show that we're not getting video data
          ctx.fillStyle = '#1a1a1a';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#ffffff';
          ctx.font = '24px Arial';
          ctx.textAlign = 'center';
          ctx.fillText('Waiting for camera...', canvas.width / 2, canvas.height / 2);
        }
      } catch (error) {
        console.warn('Failed to draw video frame:', error);
        // Show error state
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ff4444';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Camera Error', canvas.width / 2, canvas.height / 2);
      }

      // Draw pose landmarks and connections
      drawing.drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, { color: "#00FF88", lineWidth: 2 });
      drawing.drawLandmarks(ctx, results.poseLandmarks, { color: "#00FF88", radius: 3 });
      
      // Draw left hand with connections
      if (results.leftHandLandmarks) {
        drawing.drawConnectors(ctx, results.leftHandLandmarks, HAND_CONNECTIONS, { color: "#FF6B35", lineWidth: 2 });
        drawing.drawLandmarks(ctx, results.leftHandLandmarks, { color: "#FF6B35", radius: 4 });
      }
      
      // Draw right hand with connections  
      if (results.rightHandLandmarks) {
        drawing.drawConnectors(ctx, results.rightHandLandmarks, HAND_CONNECTIONS, { color: "#4ECDC4", lineWidth: 2 });
        drawing.drawLandmarks(ctx, results.rightHandLandmarks, { color: "#4ECDC4", radius: 4 });
      }

      // Use processFrameCapture for better performance - call directly without causing re-renders
      if (recordingRef.current) {
        // Lightweight temporal robustness: hold-last-good for a few frames when hands briefly disappear
        // This avoids throwing away very short dropouts while adding almost no latency.
        const HOLD_MAX = 3; // hold up to 3 frames of missing data

        const normalizeLandmarks = (arr: MediaPipeLandmark[] | undefined | null): MediaPipeLandmark[] =>
          arr && arr.length ? arr.map((p) => ({ x: p.x, y: p.y, z: p.z ?? 0, visibility: p.visibility ?? 1 })) : [];

        const leftRaw = normalizeLandmarks(results.leftHandLandmarks || []);
        const rightRaw = normalizeLandmarks(results.rightHandLandmarks || []);

        const leftPresent = leftRaw.length > 0 && leftRaw.some((p) => (p.visibility ?? 1) > 0.35);
        const rightPresent = rightRaw.length > 0 && rightRaw.some((p) => (p.visibility ?? 1) > 0.35);

        let leftToStore: MediaPipeLandmark[] = [];
        let rightToStore: MediaPipeLandmark[] = [];

        const lastGood = lastGoodRef.current;

        if (leftPresent) {
          leftToStore = leftRaw.map((p) => ({ ...p }));
          lastGood.left = leftToStore.map((p) => ({ ...p }));
          lastGood.leftStreak = 0;
        } else if (lastGood.left && lastGood.leftStreak < HOLD_MAX) {
          // hold last good for a few frames
          leftToStore = lastGood.left.map((p) => ({ ...p }));
          lastGood.leftStreak += 1;
        } else {
          leftToStore = [];
        }

        if (rightPresent) {
          rightToStore = rightRaw.map((p) => ({ ...p }));
          lastGood.right = rightToStore.map((p) => ({ ...p }));
          lastGood.rightStreak = 0;
        } else if (lastGood.right && lastGood.rightStreak < HOLD_MAX) {
          rightToStore = lastGood.right.map((p) => ({ ...p }));
          lastGood.rightStreak += 1;
        } else {
          rightToStore = [];
        }

        const landmarks = {
          pose: results.poseLandmarks || [],
          face: results.faceLandmarks || [],
          left_hand: leftToStore,
          right_hand: rightToStore,
          // include a tiny meta so uploader/consumer can decide what to do with held frames
          _meta: { leftPresent, rightPresent, ts: performance.now() },
        };

        // update lightweight telemetry counters (cheap)
        try {
          telemetryRef.current.framesProcessed += 1;
          if (leftPresent) telemetryRef.current.leftDetected += 1;
          if (rightPresent) telemetryRef.current.rightDetected += 1;
        } catch (e) {
          // ignore telemetry errors
        }

        // Directly update refs without causing state updates during recording
  framesRef.current.push(landmarks);
        
        // Only update state for UI display (throttled)
        if (framesRef.current.length % 5 === 0) {
          setFrames([...framesRef.current]);
        }

        // Check if target reached
        if (framesRef.current.length >= targetFramesRef.current) {
          recordingRef.current = false;
          setRecording(false);
          
          // Process current capture
          const capturedFrames = [...framesRef.current];
          
          setCompletedCaptures(prev => {
            const newCompleted = prev + 1;
            
            // Send capture data
            onSampleCaptureRef.current(capturedFrames, labelRef.current, userRef.current);
            
            if (newCompleted < captureCountRef.current) {
              // More captures needed - reset for next capture
              setCurrentCaptureIndex(newCompleted);
              setFrames([]);
              framesRef.current = [];
              
              // Auto-start next capture after 2 seconds
              setTimeout(() => {
                setCountdown(3);
                setTimeout(() => {
                  setRecording(true);
                  recordingRef.current = true;
                }, 3000);
              }, 2000);
            } else {
              // All captures completed, close modal
              setTimeout(() => {
                handleCloseRef.current?.();
              }, 1000);
            }
            return newCompleted;
          });
        }
      }
    });

    if (videoRef.current) {
      // Add video event listeners for debugging
      const video = videoRef.current;
      
      const onLoadedMetadata = () => {
        console.log('Video metadata loaded:', {
          videoWidth: video.videoWidth,
          videoHeight: video.videoHeight,
          readyState: video.readyState
        });
      };
      
      const onCanPlay = () => {
        console.log('Video can play:', {
          videoWidth: video.videoWidth,
          videoHeight: video.videoHeight,
          readyState: video.readyState
        });
      };

      video.addEventListener('loadedmetadata', onLoadedMetadata);
      video.addEventListener('canplay', onCanPlay);

      const camera = new Camera(videoRef.current, {
        onFrame: async () => {
          if (videoRef.current) {
            await holistic.send({ image: videoRef.current });
          }
        },
        width: 1280,
        height: 720,
      });
      
      cameraRef.current = camera;
      camera.start().then(() => {
        console.log('Camera started, video element:', {
          videoWidth: videoRef.current?.videoWidth,
          videoHeight: videoRef.current?.videoHeight,
          readyState: videoRef.current?.readyState,
          srcObject: !!videoRef.current?.srcObject
        });
        setIsReady(true);
      }).catch((error) => {
        console.error('Camera start failed:', error);
      });

      // Cleanup listeners
      return () => {
        video.removeEventListener('loadedmetadata', onLoadedMetadata);
        video.removeEventListener('canplay', onCanPlay);
        holistic.close();
        if (cameraRef.current) {
          cameraRef.current.stop();
          cameraRef.current = null;
        }
      };
    }

    return () => {
      holistic.close();
      if (cameraRef.current) {
        cameraRef.current.stop();
        cameraRef.current = null;
      }
    };
  }, [isOpen]); // Removed processFrameCapture dependency to prevent camera reset

  // Countdown effect
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (countdown === 0 && recording) {
      // Auto-stop after 5 seconds
      const timer = setTimeout(() => handleStop(), 5000);
      return () => clearTimeout(timer);
    }
  }, [countdown, recording, handleStop]);

  // Cleanup on unmount
  useEffect(() => {
    const currentCamera = cameraRef.current;
    const currentVideo = videoRef.current;
    
    return () => {
      // Cleanup when component unmounts
      if (currentCamera) {
        currentCamera.stop();
      }
      if (currentVideo && currentVideo.srcObject) {
        const stream = currentVideo.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyPress = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when user is typing in an input/textarea or editable element
      const active = document.activeElement as HTMLElement | null;
      if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) {
        return;
      }

      if (e.code === 'Enter') {
        e.preventDefault();
        if (!recordingRef.current && labelRef.current && userRef.current) {
          handleQuickCapture();
        } else if (recordingRef.current) {
          handleStop();
        }
      } else if (e.code === 'Escape') {
        handleCloseRef.current?.();
      }
    };

    document.addEventListener('keydown', handleKeyPress);
    return () => document.removeEventListener('keydown', handleKeyPress);
  }, [isOpen, handleQuickCapture, handleStop]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] bg-black">
      {/* Header Bar */}
      <div className="absolute top-0 left-0 right-0 z-10 bg-black/80 backdrop-blur-sm border-b border-gray-700">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-semibold text-white">🎬 Fullscreen Capture</h2>
            {isReady && (
              <Badge variant="success">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse mr-2"></span>
                Camera Ready
              </Badge>
            )}
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="text-white text-sm">
              Press <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Enter</kbd> to capture • <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Esc</kbd> to exit
            </div>
            <button
              onClick={() => setShowGuide(!showGuide)}
              className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center space-x-2"
            >
              <span>{showGuide ? '🙈' : '👁️'}</span>
              <span>{showGuide ? 'Hide Guide' : 'Show Guide'}</span>
            </button>
            <button
              onClick={handleClose}
              className="text-white hover:text-gray-300 p-2"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="h-full flex">
        {/* Camera Feed */}
        <div className="flex-1 relative flex items-center justify-center bg-gray-900">
          <video ref={videoRef} autoPlay muted className="hidden" />
          <canvas 
            ref={canvasRef} 
            width={1280} 
            height={720} 
            className="w-full h-full max-w-full max-h-full object-contain border border-gray-600 rounded-lg"
            style={{ minHeight: '400px' }}
          />
          
          {/* Toggle Guide Overlay - Only show when enabled and not recording/countdown */}
          {showGuide && !recording && countdown === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="relative">
                {/* Compact guide frame - just corner markers */}
                <div className="w-80 h-80 relative">
                  {/* Corner markers only */}
                  <div className="absolute top-0 left-0 w-8 h-8 border-l-4 border-t-4 border-green-400/80 rounded-tl-xl"></div>
                  <div className="absolute top-0 right-0 w-8 h-8 border-r-4 border-t-4 border-green-400/80 rounded-tr-xl"></div>
                  <div className="absolute bottom-0 left-0 w-8 h-8 border-l-4 border-b-4 border-green-400/80 rounded-bl-xl"></div>
                  <div className="absolute bottom-0 right-0 w-8 h-8 border-r-4 border-b-4 border-green-400/80 rounded-br-xl"></div>
                  
                  {/* Center crosshair */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-1 h-8 bg-green-400/60 rounded-full"></div>
                    <div className="absolute w-8 h-1 bg-green-400/60 rounded-full"></div>
                  </div>
                  
                  {/* Hand position indicators - small and subtle */}
                  <div className="absolute top-16 -left-6 w-8 h-8 border border-orange-400/60 rounded-full bg-orange-400/10 flex items-center justify-center">
                    <span className="text-orange-400 text-xs">L</span>
                  </div>
                  <div className="absolute top-16 -right-6 w-8 h-8 border border-teal-400/60 rounded-full bg-teal-400/10 flex items-center justify-center">
                    <span className="text-teal-400 text-xs">R</span>
                  </div>
                </div>
                
                {/* Minimal instruction */}
                <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-gray-800/80 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm font-medium">
                  🎯 Position yourself in frame
                </div>
                
                {/* Quality tip */}
                <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-800/70 backdrop-blur-sm text-white px-3 py-1 rounded-lg text-xs">
                  Upper body + hands visible
                </div>
              </div>
            </div>
          )}

          {/* Countdown Overlay */}
          {countdown > 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-8xl font-bold mb-4 animate-pulse">{countdown}</div>
                <div className="text-2xl mb-2">Get ready to perform:</div>
                <div className="text-3xl font-semibold text-green-400">{label}</div>
                {captureCount > 1 && (
                  <div className="text-lg mt-4 text-gray-300">
                    Capture {currentCaptureIndex + 1} of {captureCount}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Between Captures Overlay */}
          {!recording && !countdown && completedCaptures > 0 && completedCaptures < captureCount && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-4xl mb-4">🎉</div>
                <div className="text-2xl font-bold mb-2 text-green-400">Capture {completedCaptures} Complete!</div>
                <div className="text-xl mb-4">Preparing next capture...</div>
                <div className="text-lg text-gray-300">
                  Progress: {completedCaptures} / {captureCount}
                </div>
                <div className="w-64 bg-gray-700 rounded-full h-3 mt-4 mx-auto">
                  <div 
                    className="bg-green-500 h-3 rounded-full transition-all duration-500"
                    style={{ width: `${(completedCaptures / captureCount) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Completion Overlay */}
          {!recording && !countdown && completedCaptures > 0 && completedCaptures >= captureCount && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-6xl mb-4">✅</div>
                <div className="text-3xl font-bold mb-2 text-green-400">All Captures Complete!</div>
                <div className="text-xl mb-4">{completedCaptures} samples of "{label}" captured</div>
                <div className="text-lg text-gray-300">Closing modal...</div>
              </div>
            </div>
          )}

          {/* Recording Indicator */}
          {recording && (
            <div className="absolute top-24 left-6 flex items-center space-x-3 bg-red-500 text-white px-4 py-2 rounded-full shadow-lg">
              <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
              <span className="font-medium">RECORDING</span>
            </div>
          )}

          {/* Recording Progress */}
          {recording && (
            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-black/50 backdrop-blur-sm rounded-full px-6 py-2">
              <div className="text-white text-sm">
                📊 {frames.length} frames captured
              </div>
            </div>
          )}
        </div>

        {/* Control Panel */}
        <div className="w-80 bg-gray-900 border-l border-gray-700 flex flex-col">
          <div className="flex-1 p-6 space-y-6 overflow-y-auto">
            {/* Enhanced Form Fields with validation */}
            <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 rounded-xl p-5 border border-blue-500/20">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                <span className="w-3 h-3 bg-blue-400 rounded-full mr-3"></span>
                Capture Setup
              </h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-blue-300 mb-2">📝 Action Label *</label>
                  <input
                    type="text"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g., walking, jumping, waving"
                    className="w-full px-4 py-3 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200"
                    disabled={recording || countdown > 0}
                  />
                  {!label && (
                    <p className="text-xs text-yellow-400 mt-1">⚠️ Action label is required</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-blue-300 mb-2">👤 User ID *</label>
                  <input
                    type="text"
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                    placeholder="e.g., user001, john_doe"
                    className="w-full px-4 py-3 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200"
                    disabled={recording || countdown > 0}
                  />
                  {!user && (
                    <p className="text-xs text-yellow-400 mt-1">⚠️ User ID is required</p>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Labels */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">🏷️ Quick Labels</label>
              <div className="grid grid-cols-2 gap-2">
                {quickLabels.map((quickLabel) => (
                  <button
                    key={quickLabel}
                    onClick={() => setLabel(quickLabel)}
                    disabled={recording || countdown > 0}
                    className={`px-3 py-2 text-sm rounded-lg transition-colors ${
                      label === quickLabel
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    {quickLabel}
                  </button>
                ))}
              </div>
            </div>

            {/* Recording Stats */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-300 mb-3">📊 Capture Settings & Progress</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between text-gray-400">
                  <span>Target frames:</span>
                  <span className="text-white">{targetFrames}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Total captures:</span>
                  <span className="text-white">{captureCount}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Current capture:</span>
                  <span className="text-white">{currentCaptureIndex + 1}/{captureCount}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Completed:</span>
                  <span className="text-white">{completedCaptures}/{captureCount}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Current frames:</span>
                  <span className="text-white">{frames.length}/{targetFrames}</span>
                </div>
                {frames.length > 0 && (
                  <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min((frames.length / targetFrames) * 100, 100)}%` }}
                    />
                  </div>
                )}
                <div className="flex justify-between text-gray-400">
                  <span>Status:</span>
                  <Badge variant={recording ? "danger" : isReady ? "success" : "warning"} size="sm">
                    {recording ? "Recording" : isReady ? "Ready" : "Loading"}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="p-6 border-t border-gray-700 space-y-3">
            {countdown > 0 ? (
              <div className="w-full py-4 bg-yellow-600 text-white rounded-lg text-center font-medium">
                Starting in {countdown}...
              </div>
            ) : !recording ? (
              <Button
                onClick={handleQuickCapture}
                disabled={!label || !user || !isReady}
                className="w-full py-4 text-lg font-medium"
                variant="primary"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                {captureCount > 1 ? `Start Captures (${captureCount}x)` : 'Start Capture'} (Enter)
              </Button>
            ) : (
              <Button
                onClick={handleStop}
                className="w-full py-4 text-lg font-medium"
                variant="danger"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9h6v6H9z" />
                </svg>
                Stop Recording
              </Button>
            )}
            
            <Button
              onClick={handleClose}
              className="w-full"
              variant="secondary"
            >
              Exit Fullscreen
            </Button>
          </div>

          {/* Collapsible Tips Footer */}
          <div className="bg-gray-800 border-t border-gray-700 p-4">
            <button
              onClick={() => setShowTips(!showTips)}
              className="w-full flex items-center justify-between text-sm font-medium text-gray-300 hover:text-white transition-colors"
            >
              <span>💡 Quick Tips for Best Results</span>
              <span className="text-xs">{showTips ? '🔽' : '▶️'}</span>
            </button>
            
            {showTips && (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-400">
                <div>✨ Ensure good lighting and clear background</div>
                <div>🤲 Keep hands visible and fingers extended</div>
                <div>�️ Use "Show Guide" button for positioning help</div>
                <div>🔗 Watch hand connections for better tracking</div>
                <div>🎯 Stay centered in the camera view</div>
                <div>⚡ Move naturally for best results</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
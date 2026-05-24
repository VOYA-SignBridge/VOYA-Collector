# PHASE 1A Verification Guide

## Manual Testing Scenarios

### Scenario 1: Normal Capture (No Hand Loss)
**Expected Behavior**: Capture all 60 frames without interruption

```
Frame 1:   detectedCount=2 → initFrame=1, accept=false (warmup)
Frame 2:   detectedCount=2 → initFrame=2, accept=false (warmup)
Frame 3:   detectedCount=2 → initFrame=3, accept=false (warmup)
Frame 4:   detectedCount=2 → initFrame=4, accept=false (warmup)
Frame 5:   detectedCount=2 → majority vote 5/5=100%, expectedHands=2, initComplete=true
Frame 6:   detectedCount=2 → isMatching=true, accept=true ✓ (FIRST REAL FRAME)
...
Frame 65:  detectedCount=2 → accept=true ✓ (LAST FRAME)
         → framesRef.length >= 60, stop recording
```

**Verification**:
- [ ] Canvas shows 5 preview frames before counting starts
- [ ] Frame count shows "0/60" then "1/60" after frame 6
- [ ] All 60 frames have `initializationCompleteRef=true`

---

### Scenario 2: Brief Hand Loss (Within Grace Period)
**Expected Behavior**: Continue capturing, tolerate 1-2 frame mismatches

```
Frame 1-5:    Warmup (accept=false)
Frame 6-20:   Matching, accept=true ✓ (normal tracking)
Frame 21:     detectedCount=1 (one hand lost to motion blur)
            → isMatching=false, graceCounter=1 ≤ 2, accept=false
Frame 22:     detectedCount=1 (still lost)
            → isMatching=false, graceCounter=2 ≤ 2, accept=false
Frame 23:     detectedCount=2 (hands return!)
            → isMatching=true, graceCounter=0, accept=true ✓
            → Continue as normal
```

**Verification**:
- [ ] Capture does NOT pause during frames 21-22
- [ ] Frames 21-22 are not appended (are rejected)
- [ ] Frame 23 onwards resume normally
- [ ] Final frame count: 19 (6-20) + 1 (23) + 40 more = ~60 total

---

### Scenario 3: Extended Hand Loss (Grace Period Timeout → Recovery)
**Expected Behavior**: Pause capture, show recovery state, wait for hands

```
Frame 1-5:    Warmup (accept=false)
Frame 6-30:   Tracking, accept=true ✓ (25 frames appended)
Frame 31:     detectedCount=1 → graceCounter=1, accept=false
Frame 32:     detectedCount=1 → graceCounter=2, accept=false
Frame 33:     detectedCount=1 → graceCounter=3 (exceeded), ENTER RECOVERY
            → isRecovering=true, recoveryTimeout=0, recoveryConfirm=0, accept=false
Frame 34:     detectedCount=1 → recoveryTimeout=1, accept=false (waiting...)
Frame 35:     detectedCount=2 → recoveryConfirm=1, accept=false (1/3 matches)
Frame 36:     detectedCount=2 → recoveryConfirm=2, accept=false (2/3 matches)
Frame 37:     detectedCount=2 → recoveryConfirm=3, RESUME! accept=true ✓
            → Exit recovery, resume normal tracking
Frame 38-60:  Continue tracking normally, accept=true ✓
```

**Verification**:
- [ ] Frames 31-34 are rejected (no append)
- [ ] Frames 35-36 are rejected (recovery confirm in progress)
- [ ] Frame 37+ are accepted (recovery successful)
- [ ] Final frame count: 25 (6-30) + 24 (37-60) = 49 frames

---

### Scenario 4: Recovery Timeout (No Re-Detection)
**Expected Behavior**: Pause capture indefinitely until hands return or user restarts

```
Frame 1-5:    Warmup (accept=false)
Frame 6-20:   Tracking, accept=true ✓
Frame 21-23:  Grace period (graceCounter exceeded), ENTER RECOVERY
Frame 24:     recoveryTimeout=1, detectedCount=1 (still missing), accept=false
Frame 25:     recoveryTimeout=2, detectedCount=1 (still missing), accept=false
Frame 26:     recoveryTimeout=3 (TIMEOUT REACHED), detectedCount=1, accept=false
            → Recovery paused, awaiting hands
Frame 27:     recoveryTimeout=4, accept=false (waiting...)
            → User must click Restart or wait for hands to appear
```

**Verification**:
- [ ] Capture pauses at frame 26 (recovery timeout)
- [ ] No frames appended after frame 20
- [ ] Progress bar shows stuck at 15/60 frames
- [ ] User can restart to try again

---

### Scenario 5: Flicker During Recovery (Prevents False Resume)
**Expected Behavior**: Flicker resets recovery confirmation counter

```
Frame 1-5:    Warmup
Frame 6-15:   Tracking, accept=true ✓
Frame 16-18:  Grace period, enter recovery
Frame 19:     detectedCount=2 → recoveryConfirm=1 ✓
Frame 20:     detectedCount=2 → recoveryConfirm=2 ✓
Frame 21:     detectedCount=1 (FLICKER!) → recoveryConfirm=0 (RESET!)
Frame 22:     detectedCount=2 → recoveryConfirm=1 (restart from 0)
Frame 23:     detectedCount=2 → recoveryConfirm=2
Frame 24:     detectedCount=2 → recoveryConfirm=3, RESUME!
```

**Verification**:
- [ ] Frame 21 flicker resets the confirmation counter
- [ ] Frame 24 is the first resume (not frame 21)
- [ ] Prevents false resume from brief flicker

---

## Code-Level Verification

### Check 1: Initialization is Warmup-Only
```typescript
// Lines 721-738
if (initFrameCountRef.current < INIT_WINDOW) {
  accept = false;  // ✓ No append during warmup
} else if (initFrameCountRef.current === INIT_WINDOW) {
  // Calculate majority vote
  initializationCompleteRef.current = true;
  accept = false;  // ✓ Don't append init frame itself
}
```

### Check 2: Ring Buffer Guard
```typescript
// Lines 840-845
if (accept && initializationCompleteRef.current) {
  framesRef.current.push(frameEntry);  // ✓ Only append when initialized
  setFrames([...framesRef.current]);
}
```

### Check 3: Recovery Never Auto-Switches
```typescript
// Lines 802-807
if (recoveryTimeoutRef.current >= RECOVERY_TIMEOUT) {
  // DO NOT do: expectedHandsRef.current = currentHandCount;
  accept = false;  // ✓ Pause without switching
}
```

### Check 4: Consecutive-Only Grace Counting
```typescript
// Lines 749-772
if (isMatching) {
  graceCounterRef.current = 0;  // ✓ Reset on match
  accept = true;
} else if (!isRecoveringRef.current) {
  graceCounterRef.current++;  // ✓ Only increment on mismatch
}
```

### Check 5: Consecutive-Only Recovery Counting
```typescript
// Lines 781-812
if (currentHandCount === expectedHandsRef.current) {
  recoveryConfirmRef.current++;  // ✓ Increment on match
} else {
  recoveryConfirmRef.current = 0;  // ✓ Reset on mismatch
}
```

---

## Expected Frame Counts

| Scenario | Frames Appended | Notes |
|----------|-----------------|-------|
| Normal capture (no loss) | 60 | 5 warmup + 55 tracking |
| Brief loss (1-2 frames) | 58 | 2 frames rejected in grace period |
| Extended loss (recovery) | 49 | Frames 31-36 rejected during grace+recovery |
| Recovery timeout | 15 | Stopped when recovery timeout exceeded |
| Flicker in recovery | 49 | Extra 2 frames required for re-confirmation |

---

## Browser Console Debug Output

With `VITE_DEBUG_HANDS=1`, expected logs:

```
// Initialization
"Inferred expectedHands via majority vote = 2, agreement = 1"

// Grace period
"Grace period 1 / 2"
"Grace period 2 / 2"
"Grace period exceeded, entering recovery"

// Recovery progress
"Recovery progress 1 / 3"
"Recovery progress 2 / 3"
"Recovery successful, resuming capture"

// Recovery timeout
"Recovery timeout exceeded, waiting for hands to reappear"

// Flicker
"Grace period 1 / 2"  (when recovery interrupted)
```

---

## Performance Checks

- [ ] No memory leak in 10-minute capture
- [ ] Frame processing < 33ms per frame (30fps capable)
- [ ] React state updates: reduced to ~3-4 per 60 frames (not per-frame)
- [ ] No unbounded array growth

---

## Manual Test Procedure

1. **Open browser DevTools** (F12)
2. **Set environment variable**: `VITE_DEBUG_HANDS=1` before loading page
3. **Start capture in Auto Mode**
4. **Run through Scenarios 1-5** (above)
5. **Verify frame counts** match expected values
6. **Check console logs** for expected debug output
7. **Test on mobile** (iPhone 12, Android Pixel 5) for performance

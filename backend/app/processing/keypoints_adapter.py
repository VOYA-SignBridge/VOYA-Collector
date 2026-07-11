import cv2
import numpy as np
import mediapipe as mp
from typing import Tuple, Generator
from app.config import settings

# constants for hands only
N_HAND = 21

def detect_and_vectorize(frame: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Run MediaPipe Hands on a single frame and return (flattened 126-dim vector, has_hand flag).
    """
    mp_hands = mp.solutions.hands
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:
        if getattr(settings, "mirror_input", False):
            frame = cv2.flip(frame, 1)
        img_rgb = frame[:, :, ::-1]
        results = hands.process(img_rgb)
        kp_dict = extract_keypoints_from_results(results)
        vec = flatten_keypoints(kp_dict)
        has_hand = bool(np.any(vec != 0.0))
        return vec.astype(np.float32), has_hand


def extract_sequence_stream(frame_iter: Generator[Tuple[int, float, np.ndarray], None, None]) -> Generator[Tuple[int, int, np.ndarray, bool], None, None]:
    """
    Given a frame generator (idx, ts, frame), yield (idx, ts_idx, vector, has_hand) per frame.
    ts_idx is idx for now; caller can compute timestamps if needed.
    """
    mp_hands = mp.solutions.hands
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:
        for idx, ts, frame in frame_iter:
            if getattr(settings, "mirror_input", False):
                frame = cv2.flip(frame, 1)
            img_rgb = frame[:, :, ::-1]
            results = hands.process(img_rgb)
            kp_dict = extract_keypoints_from_results(results)
            vec = flatten_keypoints(kp_dict)
            has_hand = bool(np.any(vec != 0.0))
            yield idx, int(idx), vec.astype(np.float32), has_hand

def extract_keypoints_from_results(results):
    """
    Extract hand landmarks from MediaPipe Hands results
    Returns left and right hand keypoints (or zeros if not detected)
    """
    def lm_to_list(landmarks, expected_n):
        if not landmarks:
            return np.zeros((expected_n, 3), dtype=np.float32)
        coords = []
        for i in range(expected_n):
            if i < len(landmarks.landmark):
                lm = landmarks.landmark[i]
                coords.append([lm.x, lm.y, getattr(lm, "z", 0.0)])
            else:
                coords.append([0.0, 0.0, 0.0])
        return np.array(coords, dtype=np.float32)

    # Initialize hands as empty
    left_hand = np.zeros((N_HAND, 3), dtype=np.float32)
    right_hand = np.zeros((N_HAND, 3), dtype=np.float32)
    
    # Extract hand landmarks if detected
    if results.multi_hand_landmarks and results.multi_handedness:
        for i, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
            # Determine if it's left or right hand
            hand_label = handedness.classification[0].label  # "Left" or "Right"
            hand_keypoints = lm_to_list(hand_landmarks, N_HAND)
            
            if hand_label == "Left":
                left_hand = hand_keypoints
            elif hand_label == "Right":
                right_hand = hand_keypoints

    return {
        "left_hand": left_hand,
        "right_hand": right_hand
    }

def flatten_keypoints(kp_dict):
    """
    Flatten hand keypoints only
    Returns: vector of size 126 (2 hands * 21 landmarks * 3 coords)
    """
    left = kp_dict["left_hand"].flatten()   # 21 * 3 = 63
    right = kp_dict["right_hand"].flatten() # 21 * 3 = 63
    return np.concatenate([left, right], axis=0)  # Total: 126

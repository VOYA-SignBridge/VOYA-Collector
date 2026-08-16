"""Versioned feature builders, computed at load time from landmarks_raw.

Why this exists
---------------
The stored .npz keeps three things per sample: landmarks_raw, landmarks_normalized
and sequence, where sequence == landmarks_normalized. The training loader reads
`sequence`, so the features that reach the model were frozen when the sample was
ingested. Changing shared/normalization.py alone therefore changes nothing for
training, and recomputing every .npz would break the dataset manifest checksums
that the frozen research artefacts depend on.

Because landmarks_raw is kept in the same file, the fix is to rebuild features on
the fly from raw, selected by an explicit version string. Stored artefacts are
never touched, and any run records which version it used.

Versions
--------
v1    The stored `sequence`, byte for byte. Baseline; nothing is recomputed.
v2    Wrist-centred and scaled like v1, but the SAME per-hand scale is applied to
      all three axes instead of x and y only. In v1 the depth channel is passed
      through untouched: measured over 80 training samples, mean|z| = 0.046
      against mean|y| = 0.541, so depth carries about a twelfth of the magnitude
      of the other axes and is effectively ignored by the model.
v2g   v2 plus per-hand geometric descriptors (see geometric_features).

The v1 -> v2 gap matters for handshapes that differ only in depth or in palm
orientation. In the BiGRU run on root_strict_v13 those are exactly the classes
that collapsed: s was predicted as c 14 times out of 14, p as k 13 out of 15,
and r split between u and v on all 15.

Recovering depth without landmarks_raw
--------------------------------------
Only 90.9% of train, 50.6% of val and 37.9% of test rows of root_strict_v13 carry
landmarks_raw: the older samples were captured live and only the processed vector
was kept. Restricting the run to the rows that have it collapses the test set from
30 classes to 16 and from two test signers to one, so it cannot answer the
question.

Exact 3-D reconstruction is impossible for those rows. v1 stored
(xy_raw - wrist) / scale and left z alone, and `scale` is recorded nowhere -- not
in meta, not anywhere else -- so the metric unit that would put z back on the same
footing as x and y is simply gone.

It is not needed. The defect in v1 is not that depth is small, it is that depth
sits in a different reference frame: not wrist-centred, not scaled, so it drifts
with camera distance and hand position. Both can be repaired using only the stored
sequence, by re-referencing depth against itself:

    z_rel = (z - z_wrist) / max|z - z_wrist|      per hand, per frame

That is unit-free, needs no scale, and keeps what actually discriminates: which
finger sits in front of which. Measured over the split, old and new samples share
the same normalisation statistics (max span 1.137 vs 1.134, |x|/|z| 5.2 vs 6.1),
so the same transform applies to every row and the full split stays usable.

    v1z   stored xy, with z replaced by z_rel
    v1g   v1z plus 28 per-hand descriptors, in-plane plus depth ordering

v1z and v1g work on 100% of samples. v2 and v2g remain available for the subset
that kept landmarks_raw, as a metrically exact cross-check.
"""

import numpy as np

# MediaPipe Hands landmark indices.
WRIST = 0
TIPS = (4, 8, 12, 16, 20)
# (proximal, joint, distal) triplets; the flexion angle is measured at `joint`.
CURL_TRIPLETS = ((2, 3, 4), (5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))
INDEX_MCP = 5
PINKY_MCP = 17

GEOM_DIM_PER_HAND = 23          # 10 tip-tip + 5 wrist-tip + 5 curls + 3 normal
GEOM_DIM = 2 * GEOM_DIM_PER_HAND
BASE_DIM = 126


def normalize_single_hand_xyz(hand):
    """Wrist-centre and scale a (21, 3) hand, depth included.

    Identical to shared.normalization.normalize_single_hand except that the
    translation and the division are applied to all three axes. The scale is
    still the larger of the x and y spans, so a hand that is merely closer to
    the camera does not change the units of the depth channel.
    """
    h = hand.astype(np.float32).copy()
    if not np.any(h):
        return h

    h -= h[WRIST]

    valid = np.linalg.norm(h[:, :2], axis=1) > 1e-6
    if valid.any():
        pts = h[valid, :2]
        scale = max(pts[:, 0].max() - pts[:, 0].min(),
                    pts[:, 1].max() - pts[:, 1].min())
        if scale > 1e-6:
            h /= scale
    return h


def _unit(v, eps=1e-8):
    n = np.linalg.norm(v)
    return v / n if n > eps else np.zeros_like(v)


def geometric_features(hand):
    """Return 23 scale-invariant descriptors for one normalised (21, 3) hand.

    Raw coordinates say where each joint is; these say how the hand is shaped,
    which is what separates static fingerspelling letters.

      10  distances between the five fingertips  -- finger spread and crossing
       5  distances from the wrist to each tip   -- extension versus curl
       5  flexion angles at the middle joint     -- per-finger curl
       3  palm normal                            -- palm orientation

    The palm normal is the component that separates letters sharing a handshape
    but differing in wrist orientation; p and k are the clearest example, and in
    the baseline run p was predicted as k thirteen times out of fifteen.
    """
    out = np.zeros(GEOM_DIM_PER_HAND, dtype=np.float32)
    if not np.any(hand):
        return out

    k = 0
    for i in range(len(TIPS)):
        for j in range(i + 1, len(TIPS)):
            out[k] = np.linalg.norm(hand[TIPS[i]] - hand[TIPS[j]])
            k += 1

    for t in TIPS:
        out[k] = np.linalg.norm(hand[t] - hand[WRIST])
        k += 1

    for a, b, c in CURL_TRIPLETS:
        u, v = _unit(hand[a] - hand[b]), _unit(hand[c] - hand[b])
        out[k] = np.arccos(np.clip(float(np.dot(u, v)), -1.0, 1.0))
        k += 1

    normal = _unit(np.cross(hand[INDEX_MCP] - hand[WRIST],
                            hand[PINKY_MCP] - hand[WRIST]))
    out[k:k + 3] = normal
    return out


def rereference_depth(hand):
    """Put depth on a self-defined, unit-free footing: (z - z_wrist) / max|.|."""
    h = hand.astype(np.float32).copy()
    if not np.any(h):
        return h
    h[:, 2] -= h[WRIST, 2]
    m = np.abs(h[:, 2]).max()
    if m > 1e-8:
        h[:, 2] /= m
    return h


def geometric_features_planar(hand):
    """28 descriptors for one hand, using in-plane geometry plus depth order.

    The distances and angles are computed on x and y only, so they inherit the
    hand-span units v1 already established and need no `scale`. Depth enters only
    through z_rel, which is unit-free, and only where depth is what discriminates:
    the front-to-back order of the fingertips, which is what finger crossing looks
    like once the hand is projected onto the image plane.

      10  tip-tip distances (2-D)          5  wrist-tip distances (2-D)
       5  flexion angles (2-D)             5  z_rel at the fingertips
       3  in-plane palm orientation
    """
    out = np.zeros(28, dtype=np.float32)
    if not np.any(hand):
        return out

    xy = hand[:, :2]
    k = 0
    for i in range(len(TIPS)):
        for j in range(i + 1, len(TIPS)):
            out[k] = np.linalg.norm(xy[TIPS[i]] - xy[TIPS[j]])
            k += 1
    for t in TIPS:
        out[k] = np.linalg.norm(xy[t] - xy[WRIST])
        k += 1
    for a, b, c in CURL_TRIPLETS:
        u, v = _unit(xy[a] - xy[b]), _unit(xy[c] - xy[b])
        out[k] = np.arccos(np.clip(float(np.dot(u, v)), -1.0, 1.0))
        k += 1
    for t in TIPS:
        out[k] = hand[t, 2]
        k += 1

    axis = _unit(xy[9] - xy[WRIST])          # wrist -> middle-finger MCP
    out[k:k + 2] = axis
    k += 2
    a, b = _unit(xy[INDEX_MCP] - xy[WRIST]), _unit(xy[PINKY_MCP] - xy[WRIST])
    out[k] = np.arctan2(float(a[0] * b[1] - a[1] * b[0]), float(np.dot(a, b)))
    return out


def build_frame_from_normalized(vec126, version):
    """Build a frame from an already v1-normalised 126-dim vector."""
    v = np.asarray(vec126, dtype=np.float32)
    if v.size != BASE_DIM:
        return v

    hands = v.reshape(2, 21, 3)
    left = rereference_depth(hands[0])
    right = rereference_depth(hands[1])
    base = np.concatenate([left.reshape(-1), right.reshape(-1)])

    if version == "v1z":
        return base.astype(np.float32)
    if version == "v1g":
        return np.concatenate([
            base,
            geometric_features_planar(left),
            geometric_features_planar(right),
        ]).astype(np.float32)
    raise ValueError("unknown feature version: %r" % (version,))


def build_sequence_from_normalized(sequence, version):
    arr = np.asarray(sequence, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != BASE_DIM:
        return arr
    return np.stack([build_frame_from_normalized(arr[t], version)
                     for t in range(arr.shape[0])])


def append_geometry(seq126):
    """Append the per-hand descriptors to an already-built (T, 126) block.

    Kept separate from the base build so it can run AFTER augmentation. Mirroring
    or jittering the landmarks changes the geometry, so descriptors derived before
    augmentation would contradict the coordinates the model actually sees.
    """
    arr = np.asarray(seq126, dtype=np.float32)
    rows = []
    for t in range(arr.shape[0]):
        hands = arr[t].reshape(2, 21, 3)
        rows.append(np.concatenate([
            arr[t],
            geometric_features_planar(hands[0]),
            geometric_features_planar(hands[1]),
        ]))
    return np.stack(rows).astype(np.float32)


def has_geometry(version):
    return version in ("v1g", "v2g")


def needs_raw(version):
    """True when the version cannot be built from the stored `sequence`."""
    return version in ("v2", "v2g")


def build_frame(vec126, version):
    """Build one frame's feature vector from a raw 126-dim landmark vector."""
    v = np.asarray(vec126, dtype=np.float32)
    if v.size != BASE_DIM:
        return v

    hands = v.reshape(2, 21, 3)
    left = normalize_single_hand_xyz(hands[0])
    right = normalize_single_hand_xyz(hands[1])
    base = np.concatenate([left.reshape(-1), right.reshape(-1)])

    if version == "v2":
        return base.astype(np.float32)
    if version == "v2g":
        return np.concatenate([
            base,
            geometric_features(left),
            geometric_features(right),
        ]).astype(np.float32)
    raise ValueError("unknown feature version: %r" % (version,))


def build_sequence(landmarks_raw, version):
    """Build features for a (T, 126) raw sequence. `v1` is not handled here."""
    arr = np.asarray(landmarks_raw, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != BASE_DIM:
        return arr
    return np.stack([build_frame(arr[t], version) for t in range(arr.shape[0])])


def feature_dim(version):
    if version in ("v1", "v1z", "v2"):
        return BASE_DIM
    if version == "v1g":
        return BASE_DIM + 2 * 28
    if version == "v2g":
        return BASE_DIM + GEOM_DIM
    raise ValueError("unknown feature version: %r" % (version,))

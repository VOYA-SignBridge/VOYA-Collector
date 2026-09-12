from __future__ import annotations

import unittest

import numpy as np

try:
    from .preprocess_hands126 import (
        normalize_hands_sequence_126,
        normalize_hands_vector_126,
    )
except ImportError:
    from preprocess_hands126 import (
        normalize_hands_sequence_126,
        normalize_hands_vector_126,
    )


class Hands126V1Tests(unittest.TestCase):
    def test_two_hands_are_wrist_centered_and_scaled(self) -> None:
        raw = np.zeros((2, 21, 3), dtype=np.float32)
        raw[0, 0] = [0.4, 0.5, 0.1]
        raw[0, 1] = [0.6, 0.4, -0.2]
        raw[0, 2] = [0.8, 0.7, 0.2]
        raw[1, 0] = [0.7, 0.5, 0.3]
        raw[1, 1] = [0.9, 0.8, 0.4]
        raw[1, 2] = [0.8, 0.4, -0.4]

        got = normalize_hands_vector_126(raw.reshape(-1)).reshape(2, 21, 3)

        np.testing.assert_allclose(got[0, 0], [0.0, 0.0, 0.1], atol=1e-6)
        np.testing.assert_allclose(got[0, 1], [2/3, -1/3, -0.2], atol=1e-6)
        np.testing.assert_allclose(got[0, 2], [4/3, 2/3, 0.2], atol=1e-6)
        np.testing.assert_allclose(got[1, 0], [0.0, 0.0, 0.3], atol=1e-6)
        np.testing.assert_allclose(got[1, 1], [0.5, 0.75, 0.4], atol=1e-6)
        np.testing.assert_allclose(got[1, 2], [0.25, -0.25, -0.4], atol=1e-6)
        self.assertTrue(np.all(got[:, 3:] == 0.0))

    def test_missing_hand_remains_exactly_zero(self) -> None:
        raw = np.zeros((2, 21, 3), dtype=np.float32)
        raw[1, 0] = [0.2, 0.3, 0.05]
        raw[1, 5] = [0.4, 0.7, -0.1]
        raw[1, 9] = [0.6, 0.5, 0.2]

        got = normalize_hands_vector_126(raw.reshape(-1)).reshape(2, 21, 3)

        self.assertTrue(np.all(got[0] == 0.0))
        np.testing.assert_allclose(got[1, 0], [0.0, 0.0, 0.05], atol=1e-6)
        np.testing.assert_allclose(got[1, 5], [1.0, 2.0, -0.1], atol=1e-6)
        np.testing.assert_allclose(got[1, 9], [2.0, 1.0, 0.2], atol=1e-6)

    def test_sequence_transform_matches_per_frame_transform(self) -> None:
        rng = np.random.default_rng(42)
        seq = rng.normal(size=(3, 126)).astype(np.float32)
        seq[1] = 0.0
        expected = np.stack([normalize_hands_vector_126(x) for x in seq])
        np.testing.assert_allclose(normalize_hands_sequence_126(seq), expected)

    def test_invalid_feature_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "expects 126"):
            normalize_hands_vector_126(np.zeros((125,), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()

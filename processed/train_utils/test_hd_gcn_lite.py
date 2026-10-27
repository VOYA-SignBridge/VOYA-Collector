"""Run with: python -m unittest processed.train_utils.test_hd_gcn_lite -v.

PyTorch tests need no converter. The real conversion test is skipped until
litert-torch has been installed in a compatible environment. Mock tests below
check exporter orchestration only; they do NOT establish TFLite compatibility.
"""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch
import torch.nn.functional as F

from .export_tflite import export_tflite
from .models import get_model_class
from .models.hd_gcn import HandGCNModel
from .models.hd_gcn_lite import HandGCNLiteModel


class HandGCNLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        torch.manual_seed(7)
        cls.original = HandGCNModel(
            126, 4, gcn_channels=8, temporal_channels=16, dropout=0
        )
        cls.lite = HandGCNLiteModel.from_config(126, 4, cls.original.get_config())
        cls.lite.load_state_dict(cls.original.state_dict(), strict=True)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.old_threads)

    def test_original_weights_and_buffers_match_at_inference(self):
        original, lite = copy.deepcopy(self.original).eval(), copy.deepcopy(self.lite).eval()
        generator = torch.Generator().manual_seed(11)
        inputs = torch.randn(2, 60, 126, generator=generator)
        cases = [inputs, torch.zeros_like(inputs)]
        for start, end in ((0, 63), (63, 126)):
            missing_hand = inputs.clone()
            missing_hand[..., start:end] = 0
            cases.append(missing_hand)
        with torch.no_grad():
            for case in cases:
                torch.testing.assert_close(lite(case), original(case), atol=1e-5, rtol=1e-4)

    def test_training_gradients_and_batchnorm_match_original(self):
        original, lite = copy.deepcopy(self.original).train(), copy.deepcopy(self.lite).train()
        inputs = torch.randn(2, 6, 126)
        targets = torch.tensor([0, 3])
        for model in (original, lite):
            F.cross_entropy(model(inputs), targets).backward()
        for name, parameter in original.named_parameters():
            torch.testing.assert_close(
                dict(lite.named_parameters())[name].grad, parameter.grad,
                atol=1e-5, rtol=1e-4,
            )
        for name, buffer in original.named_buffers():
            torch.testing.assert_close(dict(lite.named_buffers())[name], buffer)

    def test_registry_config_roundtrip(self):
        cls = get_model_class("hdgcn_lite")
        rebuilt = cls.from_config(126, 4, self.lite.get_config())
        rebuilt.load_state_dict(self.lite.state_dict(), strict=True)
        self.assertEqual(rebuilt.get_config(), self.lite.get_config())

    def test_graph_can_be_captured_with_torch_export(self):
        model = copy.deepcopy(self.lite).eval()
        sample = torch.randn(1, 60, 126)
        exported = torch.export.export(model, (sample,)).module()
        with torch.no_grad():
            torch.testing.assert_close(exported(sample), model(sample))

    def test_unsupported_node_layout_is_rejected(self):
        with self.assertRaises(ValueError):
            HandGCNLiteModel(126, 4, num_nodes=21)

    def test_export_uses_memory_model_and_preserves_caller(self):
        model = copy.deepcopy(self.lite).train()
        model.attention.eval()  # Include mixed submodule modes in preservation check.
        before = {key: value.clone() for key, value in model.state_dict().items()}
        modes = {key: module.training for key, module in model.named_modules()}
        calls = []

        def convert(candidate, inputs):
            self.assertIsNot(candidate, model)
            self.assertFalse(any(module.training for module in candidate.modules()))
            self.assertEqual(tuple(inputs[0].shape), (1, 60, 126))
            calls.append(candidate)

            class FakeEdge:
                def __call__(self, value):
                    return candidate(value).detach().numpy()

                def export(self, path):
                    Path(path).write_bytes(b"\x00\x00\x00\x00TFL3test-only")

            return FakeEdge()

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "hand.tflite"
            with patch(
                "processed.train_utils.export_tflite.require_litert_torch",
                return_value=SimpleNamespace(convert=convert, __version__="test-double"),
            ), patch("torch.save", side_effect=AssertionError("No .pt serialization")), patch(
                "torch.load", side_effect=AssertionError("No checkpoint reload")
            ):
                self.assertEqual(export_tflite(model, path, metadata={"idx_to_label": {0: "A"}}), path)
            manifest = json.loads(path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["training_contract"]["idx_to_label"], {"0": "A"})
            self.assertEqual(manifest["output"]["semantics"], "logits")
            self.assertEqual(manifest["verification"]["cases"], 5)
            self.assertFalse(list(Path(directory).glob("*.pt")))
        self.assertEqual(len(calls), 1)
        for key, value in model.state_dict().items():
            torch.testing.assert_close(value, before[key], rtol=0, atol=0)
        self.assertEqual(modes, {key: module.training for key, module in model.named_modules()})

    def test_parity_failure_does_not_replace_existing_artifact(self):
        class BadEdge:
            def __call__(self, value):
                return np.full((1, 4), np.nan)

            def export(self, path):
                raise AssertionError("Must not serialize before parity passes")

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "hand.tflite"
            path.write_bytes(b"previous-artifact")
            with patch(
                "processed.train_utils.export_tflite.require_litert_torch",
                return_value=SimpleNamespace(convert=lambda *args: BadEdge()),
            ), self.assertRaisesRegex(RuntimeError, "Non-finite"):
                export_tflite(self.lite, path)
            self.assertEqual(path.read_bytes(), b"previous-artifact")
            self.assertFalse(path.with_suffix(".metadata.json").exists())

    def test_bare_state_dict_is_rejected(self):
        with self.assertRaises(TypeError):
            export_tflite(self.lite.state_dict(), "unused.tflite")

    @unittest.skipUnless(importlib.util.find_spec("litert_torch"), "LiteRT Torch environment not set up")
    def test_real_tflite_conversion_and_reload(self):
        import litert_torch

        model = copy.deepcopy(self.lite).eval()
        sample = torch.randn(1, 60, 126)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = export_tflite(model, Path(directory) / "hand.tflite", sample_input=sample)
            restored = litert_torch.load(str(path))
            with torch.no_grad():
                np.testing.assert_allclose(
                    restored(sample), model(sample).numpy(), atol=1e-5, rtol=1e-4
                )


if __name__ == "__main__":
    unittest.main()

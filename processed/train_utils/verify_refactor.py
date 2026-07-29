#!/usr/bin/env python
"""Verify refactoring: all models load correctly from registry"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_model_registry():
    """Verify model registry works"""
    try:
        from processed.train_utils.models import get_model_class, MODEL_REGISTRY

        print("[TEST] Model Registry")
        print(f"  Available models: {list(MODEL_REGISTRY.keys())}")

        expected = {"tcn", "cnn", "lstm", "bigru_attention", "handgcn", "hdgcn"}
        found = set(MODEL_REGISTRY.keys())

        if expected.issubset(found):
            print("  [OK] All expected models found")
            return True
        else:
            print(f"  [ERROR] Missing models: {expected - found}")
            return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def test_model_instantiation():
    """Test that all models can be instantiated"""
    try:
        from processed.train_utils.models import get_model_class

        print("\n[TEST] Model Instantiation")

        models_to_test = ["tcn", "cnn", "lstm", "bigru_attention", "handgcn"]
        results = {}

        for model_name in models_to_test:
            try:
                model_class = get_model_class(model_name)
                model = model_class.from_config(
                    input_dim=126,
                    output_dim=10,
                    config={
                        "channels": 32,
                        "levels": 2,
                        "kernel_size": 5,
                        "dropout": 0.3,
                    }
                )
                name = model.get_model_name()
                print(f"  [OK] {model_name:20} -> {name}")
                results[model_name] = True
            except Exception as e:
                print(f"  [ERROR] {model_name:20} -> {e}")
                results[model_name] = False

        return all(results.values())
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def test_train_tcn_imports():
    """Verify train_tcn.py can import and has no TCNClassifier reference"""
    try:
        print("\n[TEST] train_tcn.py Structure")

        train_tcn_path = Path(__file__).parent / "train_tcn.py"
        content = train_tcn_path.read_text()

        # Check that hardcoded classes are removed
        has_chomp1d = "class Chomp1d" in content
        has_temporal_block = "class TemporalBlock" in content
        has_tcn_classifier = "class TCNClassifier" in content

        if has_chomp1d:
            print("  [ERROR] Chomp1d still defined in train_tcn.py")
            return False
        print("  [OK] Chomp1d removed")

        if has_temporal_block:
            print("  [ERROR] TemporalBlock still defined in train_tcn.py")
            return False
        print("  [OK] TemporalBlock removed")

        if has_tcn_classifier:
            print("  [ERROR] TCNClassifier still defined in train_tcn.py")
            return False
        print("  [OK] TCNClassifier removed")

        # Check that get_model_class is used
        has_get_model_class = "get_model_class(args.model_type)" in content
        if not has_get_model_class:
            print("  [ERROR] get_model_class() not called in train_tcn.py")
            return False
        print("  [OK] Unified model loading with get_model_class()")

        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    print("=" * 60)
    print("REFACTORING VERIFICATION")
    print("=" * 60)

    tests = [
        ("Model Registry", test_model_registry),
        ("Model Instantiation", test_model_instantiation),
        ("train_tcn.py Structure", test_train_tcn_imports),
    ]

    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "[PASS]" if passed_test else "[FAIL]"
        print(f"{status} {test_name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n[OK] All refactoring checks passed!")
        return 0
    else:
        print("\n[ERROR] Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

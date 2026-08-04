"""C1-C14 fault-injection check — no training required.

Loads one real checkpoint (a fresh v13 matched-experiment run) via the SAME
loading path production auditing uses (torch.load on the .pt, not the
lightweight .json sidecar — the two carry different fields, and reading the
wrong one produces fake failures for reasons that have nothing to do with the
gate itself). Confirms the gate currently accepts it, then applies six
categories of deliberate corruption and confirms the gate rejects EACH ONE
for the correct reason. A gate that has only ever seen good input has not
been tested; this exercises the failure path directly, cheaply, and without
retraining anything.

    docker compose exec -T trainer sh -lc \
        'cd /workspace && python scripts/test_research_validity_fault_injection.py'
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from research_validity import evaluate_checkpoint  # noqa: E402

GOOD_CKPT_GLOB = "processed/train_utils/outputs/matched/**/protocol_A/*/seed_42/*_hoa_de_*.pt"


def find_good_checkpoint() -> dict:
    import torch
    candidates = sorted(REPO.glob(GOOD_CKPT_GLOB))
    if not candidates:
        raise SystemExit("Khong tim thay checkpoint mau — can it nhat mot ket qua "
                          "trong reports/matched_hoa_de_matched_leak_v13_raw.txt")
    return torch.load(candidates[0], map_location="cpu", weights_only=False)


def find_good_split_meta() -> dict:
    p = REPO / "processed/splits/versions/hoa_de_matched_leak_v13/test_S001/protocol_A/split_metadata.json"
    return json.loads(p.read_text(encoding="utf-8"))


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("baseline (khong sua gi) — PHAI qua")
def c_baseline(ckpt, split_meta):
    return ckpt, split_meta, True, None, True


@case("C5 sai manifest checksum")
def c_bad_checksum(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c["dataset_manifest_checksum"] = "0" * 64
    return c, split_meta, False, "C5", True


@case("C7 split bi ro ri nguoi ky (valid_for_research=False)")
def c_overlap(ckpt, split_meta):
    m = copy.deepcopy(split_meta)
    m["valid_for_research"] = False
    m["invalid_reasons"] = ["performer overlap between train and test detected"]
    return ckpt, m, False, "C7", True


@case("C6 checkpoint tro toi split khong ton tai tren dia")
def c_missing_split(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c["split_version"] = "khong_ton_tai/foo/bar"
    return c, None, False, "C6", True  # split_meta=None -> gate tu tra tu split_version gia


@case("C2 sai augmentation contract (mirror hong, chua fix)")
def c_bad_augmentation(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c["training_config"] = dict(c.get("training_config") or {})
    c["training_config"]["augmentation"] = {
        "augmentation_contract_version": "v1_broken_mirror",
        "enabled": True, "profile": "full", "p": 0.9, "mirror_prob": 0.5,
    }
    return c, split_meta, False, "C2", True


@case("C3 checkpoint thieu truong bat buoc (vocabulary_schema_version)")
def c_missing_field(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c.pop("vocabulary_schema_version", None)
    return c, split_meta, False, "C3", True


@case("C13 checkpoint khong phuc hoi tu best-val state")
def c_not_restored(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c["model_selection"] = {"restored_best_state": False}
    return c, split_meta, False, "C13", True


@case("C1 run_purpose khong phai 'research' (smoke test)")
def c_smoke(ckpt, split_meta):
    c = copy.deepcopy(ckpt)
    c["run_purpose"] = "smoke_test"  # khoa GOC — run_purpose_of() doc day truoc
    c["training_config"] = dict(c.get("training_config") or {})
    c["training_config"]["run_purpose"] = "smoke_test"
    return c, split_meta, False, "C1", True


def main() -> int:
    ckpt0 = find_good_checkpoint()
    split0 = find_good_split_meta()

    print(f"checkpoint mau: {ckpt0.get('model_type')} / {ckpt0.get('split_version')}")
    v0 = evaluate_checkpoint(ckpt0, split_meta=split0, check_manifest_checksum=True)
    print(f"  gate hien tai tren checkpoint that: valid={v0.valid}")
    if v0.valid is not True:
        print(f"  !! checkpoint mau khong sach — ly do: {v0.reasons}")
    print()

    passed = 0
    print(f"{'ca':<58} {'ky_vong':<8} {'thuc_te':<8} {'ket qua'}")
    print("-" * 100)
    for name, fn in CASES:
        ckpt, split_meta, should_pass, expect_code, check_sum = fn(ckpt0, split0)
        v = evaluate_checkpoint(ckpt, split_meta=split_meta, check_manifest_checksum=check_sum)
        actual_pass = v.valid is True
        ok = actual_pass == should_pass
        if ok and not should_pass and expect_code:
            hit = any(expect_code in r for r in v.reasons) or (
                v.criteria.get(next((k for k in v.criteria if k.startswith(expect_code)), ""), True) is False)
            ok = ok and hit
        passed += ok
        status = "OK" if ok else "** SAI **"
        print(f"{name:<58} {str(should_pass):<8} {str(actual_pass):<8} {status}")
        if not ok:
            print(f"    ly do gate tra ve: {v.reasons}")

    print()
    print(f"{passed}/{len(CASES)} ca dung nhu ky vong")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

# Checkpoint validity inventory
Generated: 2026-07-21T11:48:41

**No checkpoint was deleted or modified.** This report only classifies which artifacts may be cited as experimental results.

Broken-mirror window: `2026-05-14` .. `2026-07-21` (train-time `x -> 1-x` applied to wrist-centered storage).

| bucket | count |
|---|---|
| research_valid = true | 0 |
| research_valid = false | 5 |
| unverifiable (treat as not reportable) | 22 |
| **total** | **27** |

## research_valid = false

| checkpoint | profile | classes | epochs | test_acc | reason |
|---|---|---|---|---|---|
| `tcn_hoa_de_20260718_181853.pt` | hoa_de | 30 | 2 | 0.2034 | broken image-space mirror active: profile='full' p=0.9 mirror_prob=0.5 -> ~45% of training samples distorted |
| `tcn_hoa_de_20260718_182159.pt` | hoa_de | 30 | 2 | 0.2034 | broken image-space mirror active: profile='full' p=0.9 mirror_prob=0.5 -> ~45% of training samples distorted |
| `tcn_alphabet_20260719_132024.pt` | alphabet | 23 | 2 | 0.1889 | broken image-space mirror active: profile='full' p=0.9 mirror_prob=0.5 -> ~45% of training samples distorted |
| `tcn_hoa_de_20260719_132056.pt` | hoa_de | 7 | 2 | 0.5357 | broken image-space mirror active: profile='full' p=0.9 mirror_prob=0.5 -> ~45% of training samples distorted |
| `tcn_dialect-common_20260720_163129.pt` | - | 3 | 80 | 1.0000 | broken image-space mirror active: profile='full' p=0.9 mirror_prob=0.5 -> ~45% of training samples distorted |

## unverifiable

| checkpoint | profile | classes | epochs | test_acc | reason |
|---|---|---|---|---|---|
| `bigru_attention_dialect-hoa-de_20260705_051529.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `cnn_20260704_153856.pt` | - | 42 | - | 0.3109 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `handgcn_dialect-bang-chu-cai+hoa-de_20260705_135757.pt` | - | 30 | - | 0.5882 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `lstm_dialect-hoa-de_20260705_100936.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_20260704_153639.pt` | - | 42 | - | 0.0588 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_20260705_051052.pt` | - | 42 | - | 0.1092 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-bang-chu-cai_20260624_080546.pt` | - | 23 | - | 0.8000 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260526_210121.pt` | - | 7 | - | 0.9286 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260603_233544.pt` | - | 7 | - | 0.6071 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_043750.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_044719.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_055832.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_060805.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_061347.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_061954.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_065001.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260701_090448.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260702_064538.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260705_054829.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260708_061459.pt` | - | 7 | - | 0.9655 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-bang-chu-cai_20260607_130922.pt` | - | 23 | - | 0.9145 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |
| `tcn_dialect-hoa-de_20260515_131050.pt` | - | 6 | - | 0.9565 | no training_config.augmentation recorded (pre-contract checkpoint); trained via train_tcn.py, which has applied the broken mirror by default since 2026-05-14 — assume affected |

## research_valid = true

_(none)_

## Required action

Every row above that is not `research_valid = true` must be re-trained after the 2026-07-21 stabilization patch before it can appear in a paper table. Re-trained runs are stamped `training_config.augmentation.augmentation_contract_version = 'v2_wrist_centered_mirror'`, which this script recognises automatically.

# Label Metadata Pipeline Audit Report

**Date**: 2026-05-18  
**Status**: 🔴 **ROOT CAUSE IDENTIFIED**  
**Severity**: 🟡 **MEDIUM** (functional but metadata incomplete)

---

## Executive Summary

The system is displaying `label_key` instead of `label_original` for newly added classes because:

1. **Checkpoint contains incomplete metadata**: `idx_to_label` only has string values (label_keys), not enriched objects
2. **External enrichment file missing**: `processed/analysis/index_to_label.json` doesn't exist
3. **Fallback to label_key**: Normalization function correctly falls back to label_key when enrichment unavailable
4. **Older classes work**: They were likely added with enriched metadata in the checkpoint itself

---

## CHECKPOINT AUDIT FINDINGS

### Current Checkpoint Structure

**File**: `realtime_service/config/checkpoints/tcn_dialect-hoa-de_20260515_131050.pt`

**idx_to_label Type**: `dict` (not list)

**Structure**:
```python
{
    "0": "vn/hoa-de/rang-muoi",
    "1": "vn/hoa-de/tom",
    "2": "vn/hoa-de/lot-da-ca",
    "3": "vn/hoa-de/lot-vo-tom",
    "4": "vn/hoa-de/cat-ky",
    "5": "vn/hoa-de/danh-vay-ca",
}
```

**Critical Issue**: Values are **strings only** — no label metadata objects:
- ❌ NO `label_original` field
- ❌ NO `label_slug` field
- ❌ NO `language` field
- ❌ NO `dialect` field
- ✅ Only has label_key

### Data Format Evolution

The new checkpoint format changed from previous structure where labels might have been dicts:

```python
# OLD (example - what would work)
{
    "0": {
        "label_key": "vn/hoa-de/rang-muoi",
        "label_original": "Rang Mười",
        "label_slug": "rang-muoi",
        "language": "vn",
        "dialect": "hoa-de"
    }
}

# NEW (what we have)
{
    "0": "vn/hoa-de/rang-muoi"  # String only
}
```

---

## LABEL NORMALIZATION AUDIT

### Code Path: `normalize_idx_to_label()` 

**File**: `realtime_service/app/model_loader.py:278-330`

#### When checkpoint value is a STRING (our case):

```python
def normalize_idx_to_label(...):
    for _, raw_value in _sorted_idx_items(raw_idx_to_label):
        
        # Line 288-299: Check if dict — NO, it's a string
        if isinstance(raw_value, dict):
            # ... skipped for our case
        else:
            # Line 300-307: STRING case (THIS IS EXECUTED)
            label_key = str(raw_value or "").strip()
            # label_key = "vn/hoa-de/rang-muoi"
            
            # Try to look up enrichment from external file
            lookup = _label_lookup_by_key(label_lookup, label_key)
            # lookup = {} because file doesn't exist
            
            # FALLBACK: Use label_key as label_original
            label_original = str(lookup.get("label_original") or label_key).strip()
            # Result: label_original = "vn/hoa-de/rang-muoi" (NOT HUMAN READABLE)
        
        # Lines 309-315: Optional second enrichment pass (also fails)
        lookup = _label_lookup_by_key(label_lookup, label_key)
        if lookup:
            label_original = str(lookup.get("label_original") or label_original).strip()
        # lookup still empty, so no update
        
        # Line 324: FINAL RESULT
        normalized.append({
            "label_key": label_key,
            "label_slug": ...,
            "label_original": label_original or label_key,  # ⚠️ FALLBACK HAPPENS HERE
            "language": ...,
            "dialect": ...
        })
```

### The Fallback Chain

```
checkpoint string "vn/hoa-de/rang-muoi"
  ↓
normalize_idx_to_label() with empty label_lookup
  ↓
lookup.get("label_original") → None (empty dict)
  ↓
Fallback: label_original = label_key = "vn/hoa-de/rang-muoi"
  ↓
Result: label_original = "vn/hoa-de/rang-muoi"
```

### Why External Lookup is Empty

**File**: `realtime_service/app/startup.py:40-65`

```python
def _resolve_optional_path(path_value: str) -> Path | None:
    # Walks up directory tree from CWD
    # Returns None if file not found
    
def _load_label_lookup(label_index_path: str) -> Dict[str, Dict[str, Any]]:
    resolved = _resolve_optional_path(label_index_path)
    if resolved is None:
        logger.warning("[STARTUP] label index not found path=%s", label_index_path)
        return {}  # ⚠️ RETURNS EMPTY DICT
    # ... loads JSON if file exists
```

**Expected path**: `processed/analysis/index_to_label.json`  
**Actual existence**: ❌ FILE DOES NOT EXIST

```bash
$ find . -name "index_to_label.json"
# (no results)
```

---

## BACKEND DECODE PATH AUDIT

### Prediction Response Encoding

**File**: `realtime_service/app/predict.py:122-144`

```python
# Line 123: Index into normalized idx_to_label (list of dicts)
label_obj = bundle.idx_to_label[pred_idx]

# label_obj example:
# {
#     "label_key": "vn/hoa-de/rang-muoi",
#     "label_original": "vn/hoa-de/rang-muoi",  # ← FALLBACK VALUE (string only, not human readable)
#     "label_slug": "rang-muoi",
#     "language": "vn",
#     "dialect": "hoa-de"
# }

# Lines 124-128: Extract fields
label_spec = {
    "label_original": str(label_obj.get("label_original", "")),
    "label_key": str(label_obj.get("label_key", "")),
    "confidence": float(probs[pred_idx]),
}

# Line 136: Send label_original in response
response = PredictResponse(
    label=label_spec["label_original"],  # ← This is the fallback value
    confidence=label_spec["confidence"],
    label_key=label_spec["label_key"],
)
```

### API Response Structure

**Type**: `PredictResponse` (from `realtime_service/app/schemas.py`)

```python
{
    "label": "vn/hoa-de/rang-muoi",  # ← Should be human-readable like "Rang Mười"
    "confidence": 0.95,
    "label_key": "vn/hoa-de/rang-muoi"
}
```

**Issue**: `label` field contains label_key format, not human-readable label_original.

---

## FRONTEND RENDERING AUDIT

### Data Flow

```
Backend API Response
├── label: "vn/hoa-de/rang-muoi"  ← Should be human-readable
├── confidence: 0.95
└── label_key: "vn/hoa-de/rang-muoi"

↓ (frontend/src/components/realtime/RealtimeRuntime.tsx:333)

PredictionSmoother
└── pushPrediction(label, confidence)

↓ (frontend/src/components/realtime/RealtimeRuntime.tsx:332-348)

setPrediction({
    label: "vn/hoa-de/rang-muoi",  ← Wrong value (machine format)
    confidence: 0.95,
    samples: N,
    labelKey: "vn/hoa-de/rang-muoi"
})

↓ (rendered in UI)

Display shows: "vn/hoa-de/rang-muoi" instead of "Rang Mười"
```

### Frontend is Correctly Passing Through

✅ Frontend correctly extracts `response.label` (line 333 in RealtimeRuntime.tsx)  
✅ Frontend correctly renders `prediction.label` (consistent with backend)  
❌ **Issue is upstream** — backend is sending wrong value

---

## ROOT CAUSE SUMMARY

### Why Some Classes Show label_key Instead of label_original

| Factor | Old Classes | New Classes |
|--------|------------|-------------|
| Checkpoint idx_to_label format | Likely dict with objects | String-only dict |
| Has label_original in checkpoint | ✅ YES (in object) | ❌ NO (strings only) |
| External enrichment file | ❌ Missing | ❌ Missing |
| Fallback activated | No | **YES** |
| Display result | Human-readable | Machine format (label_key) |

### The Three-Layer Failure

1. **Layer 1 - Checkpoint**: Missing `label_original` metadata
   - New labels added as strings only
   - Old labels had enriched objects

2. **Layer 2 - Enrichment**: External file missing
   - `processed/analysis/index_to_label.json` doesn't exist
   - Would provide `label_original` → "Rang Mười"
   - But file path resolution can't find it

3. **Layer 3 - Fallback**: Normalization accepts fallback
   - Code correctly falls back to label_key
   - But result is machine format, not human readable
   - This is working as designed, but with incomplete data

---

## EXACTLY WHERE SEMANTIC DOWNGRADE HAPPENS

### Code Location
**File**: `realtime_service/app/model_loader.py:303`

```python
label_original = str(lookup.get("label_original") or label_key).strip()
```

When:
- `lookup` is empty dict (file not found)
- `lookup.get("label_original")` returns `None`
- Python's `or` operator activates
- **Result**: `label_original = label_key = "vn/hoa-de/rang-muoi"`

This is correct fallback logic, but the fallback value is machine format, not human-readable.

---

## VERIFICATION: EXPECTED vs ACTUAL

### What Should Happen (if metadata complete)

```python
checkpoint = {"0": "vn/hoa-de/rang-muoi"}
label_lookup = {
    "vn/hoa-de/rang-muoi": {
        "label_original": "Rang Mười",
        "label_slug": "rang-muoi"
    }
}

# normalize_idx_to_label result:
{
    "label_key": "vn/hoa-de/rang-muoi",
    "label_original": "Rang Mười",  ← HUMAN-READABLE
    "label_slug": "rang-muoi"
}

# predict.py response:
{
    "label": "Rang Mười",  ← Display this
    "label_key": "vn/hoa-de/rang-muoi"
}

# Frontend displays: "Rang Mười" ✅
```

### What Actually Happens (metadata incomplete)

```python
checkpoint = {"0": "vn/hoa-de/rang-muoi"}
label_lookup = {}  # File not found

# normalize_idx_to_label result:
{
    "label_key": "vn/hoa-de/rang-muoi",
    "label_original": "vn/hoa-de/rang-muoi",  # ← FALLBACK (machine format)
    "label_slug": "rang-muoi"
}

# predict.py response:
{
    "label": "vn/hoa-de/rang-muoi",  # ← Machine format
    "label_key": "vn/hoa-de/rang-muoi"
}

# Frontend displays: "vn/hoa-de/rang-muoi" ❌
```

---

## SEVERITY ASSESSMENT

### 🟡 MEDIUM

**Why not CRITICAL**:
- System is functionally working
- Predictions are correct
- Fallback is deterministic and consistent
- No data loss or corruption

**Why not LOW**:
- User-facing display degraded
- New labels appear in wrong format
- Inconsistent with older labels
- Poor UX for end users

---

## CONCLUSION

**Root Cause**: Checkpoint metadata incomplete + external enrichment file missing

**Actual Failure Point**: `model_loader.py:303` — label_original falls back to label_key

**Why It Works This Way**: Robust fallback chain, but fallback value is machine format

**Fix Approach**: Must provide either:
1. **Checkpoint with enriched label objects** (not strings), OR
2. **Create label index file** with mappings, OR
3. **Both** (most robust)

---

## NEXT STEPS

**Do NOT change**:
- ✅ Fallback logic (it's correct)
- ✅ Normalization (it's correct)
- ✅ Runtime architecture (it's working)

**Must address**:
- Provide complete label metadata (either in checkpoint or external file)
- Ensure label_original is human-readable, not machine format

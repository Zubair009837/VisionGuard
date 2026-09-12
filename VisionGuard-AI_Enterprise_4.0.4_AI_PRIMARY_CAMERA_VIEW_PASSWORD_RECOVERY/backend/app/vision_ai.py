# ==========================================================
# VisionGuard AI - Semantic Scene Understanding
# ==========================================================
"""
Optional local AI confirmation layer for CCTV scene changes.

Uses OpenAI CLIP through Hugging Face Transformers.
The model is downloaded on first use and cached locally.

This is the primary camera-view decision layer.
- A persistent baseline image represents the normal camera view.
- CLIP compares baseline and current scene semantics/embeddings.
- PTZ values and ORB/homography are deliberately not required for an alert.
- It identifies semantic conditions such as wall, window, table/furniture,
  ceiling/floor, obstruction, lens blockage, or a radically different view.
"""

import os
import threading
import hashlib
from typing import Dict, Any

import cv2
import numpy as np

_LOCK = threading.Lock()
_MODEL = None
_PROCESSOR = None
_LOAD_ERROR = None
_CACHE = {}
_CACHE_MAX = 128

MODEL_NAME = os.getenv("VISION_AI_MODEL", "openai/clip-vit-base-patch32")
SEMANTIC_DISTANCE_THRESHOLD = float(
    os.getenv("VISION_AI_DISTANCE_THRESHOLD", "0.105")
)
LABEL_CHANGE_THRESHOLD = float(
    os.getenv("VISION_AI_LABEL_CHANGE_THRESHOLD", "0.16")
)
HIGH_RISK_LABEL_THRESHOLD = float(
    os.getenv("VISION_AI_HIGH_RISK_THRESHOLD", "0.42")
)

# Prompts are deliberately concrete CCTV descriptions.
LABELS = [
    "a normal CCTV view of the expected room or area",
    "a CCTV camera pointed at a close wall",
    "a wall is blocking most of the CCTV camera view",
    "a CCTV view dominated by a window",
    "a CCTV view dominated by a table or furniture",
    "a CCTV camera pointed at the ceiling",
    "a CCTV camera pointed at the floor",
    "a CCTV camera view is blocked or covered by an object",
    "an object is very close to the CCTV camera lens",
    "a CCTV camera has a radically different viewpoint",
]

RISK_LABELS = {
    1: "close wall / wall obstruction",
    2: "wall obstruction",
    3: "window-dominated scene",
    4: "table / furniture-dominated scene",
    5: "ceiling view",
    6: "floor view",
    7: "camera view blocked by object",
    8: "object very close to lens",
    9: "radically different viewpoint",
}


def _load():
    global _MODEL, _PROCESSOR, _LOAD_ERROR

    if _MODEL is not None:
        return _MODEL, _PROCESSOR

    with _LOCK:
        if _MODEL is not None:
            return _MODEL, _PROCESSOR
        if _LOAD_ERROR is not None:
            return None, None

        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            print(
                f"🤖 VISION AI | Loading semantic model: {MODEL_NAME}"
            )

            processor = CLIPProcessor.from_pretrained(MODEL_NAME)
            model = CLIPModel.from_pretrained(MODEL_NAME)
            model.eval()

            _PROCESSOR = processor
            _MODEL = model

            print("✅ VISION AI | Semantic model ready")
            return _MODEL, _PROCESSOR

        except Exception as exc:
            _LOAD_ERROR = str(exc)
            print(
                "⚠️ VISION AI | Model unavailable. "
                f"Semantic confirmation disabled: {exc}"
            )
            return None, None


def is_available() -> bool:
    model, processor = _load()
    return model is not None and processor is not None


def _prepare(frame):
    if frame is None or getattr(frame, "size", 0) == 0:
        return None
    # CLIP processor accepts numpy RGB images.
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _image_key(image):
    small = cv2.resize(image, (224, 224), interpolation=cv2.INTER_AREA)
    return hashlib.sha1(small.tobytes()).hexdigest()


def _cached_encode(image):
    key = _image_key(image)
    cached = _CACHE.get(("embedding", key))
    if cached is not None:
        return cached
    value = _encode(image)
    if value is not None:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[("embedding", key)] = value
    return value


def _cached_labels(image):
    key = _image_key(image)
    cached = _CACHE.get(("labels", key))
    if cached is not None:
        return cached
    value = _label_scores(image)
    if value:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[("labels", key)] = value
    return value


def _encode(image):
    model, processor = _load()
    if model is None:
        return None

    import torch

    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = features / features.norm(
            p=2, dim=-1, keepdim=True
        )
    return features.cpu().numpy()[0]


def _label_scores(image):
    model, processor = _load()
    if model is None:
        return {}

    import torch

    inputs = processor(
        text=LABELS,
        images=image,
        return_tensors="pt",
        padding=True,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits_per_image[0]
        probs = torch.softmax(logits, dim=0).cpu().numpy()

    return {
        idx: float(prob)
        for idx, prob in enumerate(probs)
    }


def analyze_scene_change(
    baseline,
    current,
    *,
    enabled=True,
) -> Dict[str, Any]:
    """
    Returns a semantic decision.

    AI is intentionally conservative. It confirms a change when:
      1) image embedding distance is large AND a semantic label changed, OR
      2) a high-risk obstruction/scene label is strongly dominant.

    If the model is unavailable, changed=False and available=False.
    The caller can continue using the existing ORB detector.
    """
    if not enabled:
        return {
            "available": False,
            "changed": False,
            "reason": "disabled",
        }

    base = _prepare(baseline)
    curr = _prepare(current)

    if base is None or curr is None:
        return {
            "available": False,
            "changed": False,
            "reason": "invalid_frame",
        }

    try:
        base_embedding = _cached_encode(base)
        current_embedding = _cached_encode(curr)

        if base_embedding is None or current_embedding is None:
            return {
                "available": False,
                "changed": False,
                "reason": _LOAD_ERROR or "model_unavailable",
            }

        cosine = float(
            np.clip(
                np.dot(base_embedding, current_embedding),
                -1.0,
                1.0,
            )
        )
        distance = 1.0 - cosine

        if distance < SEMANTIC_DISTANCE_THRESHOLD:
            return {
                "available": True,
                "changed": False,
                "distance": round(distance, 4),
                "reason": "semantic embedding stable",
            }

        base_labels = _cached_labels(base)
        current_labels = _cached_labels(curr)

        if not base_labels or not current_labels:
            return {
                "available": True,
                "changed": distance >= SEMANTIC_DISTANCE_THRESHOLD,
                "distance": round(distance, 4),
                "reason": "embedding change",
            }

        deltas = {
            idx: current_labels.get(idx, 0.0)
            - base_labels.get(idx, 0.0)
            for idx in range(len(LABELS))
        }

        strongest_idx = max(
            current_labels,
            key=current_labels.get,
        )
        strongest_prob = current_labels[strongest_idx]
        strongest_delta = deltas[strongest_idx]

        risk_candidates = []
        for idx, label in RISK_LABELS.items():
            prob = current_labels.get(idx, 0.0)
            delta = deltas.get(idx, 0.0)
            if (
                prob >= HIGH_RISK_LABEL_THRESHOLD
                and delta >= LABEL_CHANGE_THRESHOLD
            ):
                risk_candidates.append(
                    (prob, delta, label)
                )

        risk_candidates.sort(reverse=True)
        risk = risk_candidates[0] if risk_candidates else None

        semantic_changed = (
            distance >= SEMANTIC_DISTANCE_THRESHOLD
            and (
                strongest_delta >= LABEL_CHANGE_THRESHOLD
                or bool(risk)
            )
        )

        # A very strong obstruction signal is sufficient even when
        # the embedding distance is slightly below the general threshold.
        if risk and risk[0] >= 0.55:
            semantic_changed = True

        top_label = LABELS[strongest_idx]

        if risk:
            reason = risk[2]
        elif semantic_changed:
            reason = "semantic scene changed"
        else:
            reason = "semantic scene stable"

        return {
            "available": True,
            "changed": bool(semantic_changed),
            "distance": round(distance, 4),
            "top_label": top_label,
            "top_probability": round(float(strongest_prob), 4),
            "top_delta": round(float(strongest_delta), 4),
            "reason": reason,
            "risk": (
                {
                    "label": risk[2],
                    "probability": round(float(risk[0]), 4),
                    "delta": round(float(risk[1]), 4),
                }
                if risk
                else None
            ),
        }

    except Exception as exc:
        print(f"⚠️ VISION AI | Analysis error: {exc}")
        return {
            "available": False,
            "changed": False,
            "reason": f"analysis_error:{exc}",
        }

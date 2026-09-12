# VisionGuard AI - Semantic Camera View Detection

This version adds an optional local AI confirmation layer to the existing camera-angle monitor.

## What it detects

The AI compares the stored baseline image with the current CCTV frame using CLIP image embeddings and zero-shot scene descriptions.

It can identify meaningful changes such as:

- close wall / wall obstruction
- window becoming dominant
- table/furniture becoming dominant
- ceiling view
- floor view
- object blocking the camera
- object very close to the lens
- radically different camera viewpoint

## How alerts work

1. Existing ORB/homography detector checks physical viewpoint movement.
2. When AI is enabled, CLIP checks whether the scene meaning changed.
3. If `VISION_AI_CONFIRM_ONLY = True`, both geometry and semantic evidence are required.
4. If the AI model cannot load, the existing ORB detector remains active as a fail-safe.
5. The existing VisionGuard email function is reused, so the AI explanation is included in the angle alert details.

## First run

From the backend directory:

```text
pip install -r requirements.txt
```

The first AI analysis downloads `openai/clip-vit-base-patch32` from Hugging Face and caches it locally. Internet access is required for that first model download.

After that, the model is loaded from the local Hugging Face cache.

## Important

AI detection does not repair an SMTP/Gmail authentication problem. If SMTP login is failing, the terminal will still show the mail failure. The AI event itself will be visible in the terminal and alert history, and once SMTP is fixed it will use the same email pipeline.

For CPU-only servers, CLIP is intentionally used as a confirmation layer rather than running full semantic inference on every frame.


## AI-PRIMARY CAMERA VIEW DETECTION (4.0.4)

The camera-view alert decision is now made by the local CLIP semantic scene engine.
PTZ pan/tilt/preset values are not used for the decision, and ORB/homography is
retained only as diagnostic information.

### Behavior
- The first valid frame becomes the persistent normal-view baseline.
- Subsequent frames are compared against that baseline semantically.
- The engine looks for major scene changes such as wall, window, table/furniture,
  ceiling, floor, close object/lens obstruction, or radically different viewpoint.
- Existing consecutive-reading confirmation prevents one-frame false alarms.
- If the AI model cannot load, camera-view alerts are suppressed rather than
  silently falling back to PTZ/ORB decisions.

### Install
Run from the `backend` directory:

```bat
pip install -r requirements.txt
```

The first AI analysis downloads `openai/clip-vit-base-patch32` and caches it locally.
Internet access is required for that first model download.

### Test
Start the backend and look for:

`VISION AI | Semantic model ready`

Then move one camera so its view changes substantially. The terminal should show
`VISION_AI_PRIMARY=CHANGED`. The email pipeline will use the same camera-angle event.


## AI-PRIMARY CAMERA VIEW DETECTION (4.0.4)

Camera-view alerts are decided by the local CLIP semantic scene engine. PTZ
pan/tilt/preset values are not used for the decision. ORB/homography is retained
only as diagnostic information.

The first valid frame becomes the persistent normal-view baseline. Later frames
are compared against it for major semantic changes such as wall, window,
table/furniture, ceiling, floor, close object/lens obstruction, or radically
different viewpoint. Existing consecutive-reading confirmation remains active.

If the AI model cannot load, camera-view alerts are suppressed rather than
silently falling back to PTZ/ORB decisions.

Run from the backend directory:

    pip install -r requirements.txt

The first AI analysis downloads and caches openai/clip-vit-base-patch32.
Look for: VISION AI | Semantic model ready
Then move a camera substantially and look for VISION_AI_PRIMARY=CHANGED.

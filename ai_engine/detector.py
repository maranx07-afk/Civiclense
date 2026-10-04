import os
import json
import gc
from pathlib import Path

from ultralytics import YOLO
from huggingface_hub import hf_hub_download


# ============================================================
# CIVICLENS AI CONFIGURATION
# ============================================================

MODEL_REPO = "nsr51324/Road_Damage_Object_Detection"
MODEL_FILENAME = "runs/detect/yolov8_road/weights/best.pt"

# Reduced from 640 to 512 to lower RAM usage on Render
IMAGE_SIZE = 512

CONFIDENCE_THRESHOLD = 0.30
IOU_THRESHOLD = 0.45

# Maximum number of detections we need for a road-damage report
MAX_DETECTIONS = 20


# ============================================================
# MODEL PATHS
# ============================================================

LOCAL_BASE_DIR = Path(
    os.getenv(
        "CIVICLENS_BASE_DIR",
        r"D:\CivicLens"
    )
)

MODEL_FOLDER = Path(
    os.getenv(
        "CIVICLENS_MODEL_DIR",
        str(LOCAL_BASE_DIR / "ai_models")
    )
)

MODEL_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

LOCAL_MODEL_PATH = MODEL_FOLDER / "road_damage_best.pt"


# ============================================================
# DOWNLOAD MODEL IF NEEDED
# ============================================================

def get_model_path():
    """
    Use the local model if available.

    On Render/cloud deployment, download the model from
    Hugging Face if it isn't already present.
    """

    if LOCAL_MODEL_PATH.exists():
        return str(LOCAL_MODEL_PATH)

    print("Downloading CivicLens AI model...")

    downloaded_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILENAME
    )

    return downloaded_path


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():
    """
    Load YOLO model once during application startup.
    """

    model_path = get_model_path()

    print(f"Loading CivicLens AI model from: {model_path}")

    model = YOLO(model_path)

    print("CivicLens AI model loaded successfully.")

    return model


# ============================================================
# ANALYZE IMAGE
# ============================================================

def analyze_image(image_path, model):
    """
    Detect road damage from an image.

    Memory-optimized for Render's limited RAM.
    """

    if model is None:
        return {
            "damage_detected": False,
            "damage_count": 0,
            "damage_types": [],
            "highest_confidence": 0,
            "detections": [],
            "error": "AI model is not loaded"
        }

    results_generator = None
    result = None

    try:

        # --------------------------------------------------------
        # STREAM YOLO RESULTS
        # --------------------------------------------------------

        results_generator = model.predict(
            source=image_path,

            # Smaller inference resolution
            imgsz=IMAGE_SIZE,

            # Detection thresholds
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,

            # CPU inference
            device="cpu",

            # Reduce memory/output generation
            max_det=MAX_DETECTIONS,
            augment=False,
            save=False,
            show=False,
            verbose=False,

            # IMPORTANT:
            # stream=True prevents YOLO from building a large
            # list of results in memory.
            stream=True
        )

        # We only analyze one uploaded image.
        result = next(results_generator, None)

        if result is None:
            return {
                "damage_detected": False,
                "damage_count": 0,
                "damage_types": [],
                "highest_confidence": 0,
                "detections": []
            }

        # --------------------------------------------------------
        # CLASS NAMES
        # --------------------------------------------------------

        names = result.names

        detections = []
        damage_types = []
        highest_confidence = 0.0

        # --------------------------------------------------------
        # PROCESS DETECTIONS
        # --------------------------------------------------------

        if result.boxes is not None:

            for box in result.boxes:

                confidence = float(
                    box.conf[0]
                )

                class_id = int(
                    box.cls[0]
                )

                # Get class name safely
                if isinstance(names, dict):
                    class_name = names.get(
                        class_id,
                        str(class_id)
                    )
                else:
                    class_name = str(
                        names[class_id]
                    )

                # Bounding box
                xyxy = box.xyxy[0].tolist()

                x1, y1, x2, y2 = [
                    round(float(value), 2)
                    for value in xyxy
                ]

                # Store detection
                detections.append({
                    "class": class_name,
                    "confidence": round(
                        confidence * 100,
                        2
                    ),
                    "bbox": [
                        x1,
                        y1,
                        x2,
                        y2
                    ]
                })

                if class_name not in damage_types:
                    damage_types.append(
                        class_name
                    )

                if confidence > highest_confidence:
                    highest_confidence = confidence

        # --------------------------------------------------------
        # FINAL RESULT
        # --------------------------------------------------------

        damage_count = len(detections)

        return {
            "damage_detected": damage_count > 0,

            "damage_count": damage_count,

            "damage_types": damage_types,

            "highest_confidence": round(
                highest_confidence * 100,
                2
            ),

            "detections": detections
        }

    except Exception as e:

        print(
            f"CivicLens AI inference error: {e}"
        )

        return {
            "damage_detected": False,
            "damage_count": 0,
            "damage_types": [],
            "highest_confidence": 0,
            "detections": [],
            "error": str(e)
        }

    finally:

        # --------------------------------------------------------
        # EXPLICIT MEMORY CLEANUP
        # --------------------------------------------------------

        try:
            if results_generator is not None:
                results_generator.close()
        except Exception:
            pass

        result = None
        results_generator = None

        gc.collect()
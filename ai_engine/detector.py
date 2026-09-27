import os
import json
from pathlib import Path

from ultralytics import YOLO
from huggingface_hub import hf_hub_download


# ============================================================
# CIVICLENS ROAD DAMAGE AI
# ============================================================

MODEL_REPO = "nsr51324/Road_Damage_Object_Detection"
MODEL_FILENAME = "runs/detect/yolov8_road/weights/best.pt"

IMAGE_SIZE = 640
CONFIDENCE_THRESHOLD = 0.30
IOU_THRESHOLD = 0.45

LOCAL_BASE_DIR = Path(
    os.getenv("CIVICLENS_BASE_DIR", r"D:\CivicLens")
)

MODEL_FOLDER = Path(
    os.getenv(
        "CIVICLENS_MODEL_DIR",
        str(LOCAL_BASE_DIR / "ai_models")
    )
)

MODEL_FOLDER.mkdir(parents=True, exist_ok=True)

LOCAL_MODEL_PATH = MODEL_FOLDER / "road_damage_best.pt"


# ============================================================
# DOWNLOAD MODEL
# ============================================================

def get_model_path():
    """
    Local PC:
        Uses D:\CivicLens\ai_models\road_damage_best.pt
        when that file already exists.

    Cloud:
        If the local file does not exist, downloads the
        official trained checkpoint from Hugging Face.
    """

    if LOCAL_MODEL_PATH.exists():
        print(f"Using local CivicLens model: {LOCAL_MODEL_PATH}")
        return str(LOCAL_MODEL_PATH)

    print("\n========================================")
    print("CIVICLENS AI MODEL DOWNLOAD")
    print("========================================")
    print("Local model not found.")
    print("Downloading road-damage YOLOv8 model...")
    print(f"Repository: {MODEL_REPO}")

    downloaded_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILENAME,
        cache_dir=str(MODEL_FOLDER)
    )

    print(f"Model downloaded successfully:")
    print(downloaded_path)
    print("========================================\n")

    return downloaded_path


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():
    """
    Load the CivicLens road-damage YOLO model.

    The returned object is compatible with main.py.
    """

    model_path = get_model_path()

    print("Loading CivicLens YOLO model...")
    model = YOLO(model_path)

    print("CivicLens YOLO model ready!")

    return model


# ============================================================
# ANALYZE IMAGE
# ============================================================

def analyze_image(image_path, model):
    """
    Analyze a road image and return the result in the format
    expected by CivicLens backend.
    """

    try:
        print("\n----------------------------------------")
        print("CIVICLENS AI IMAGE ANALYSIS")
        print("----------------------------------------")
        print(f"Image: {image_path}")
        print(f"Image size: {IMAGE_SIZE}")
        print(f"Confidence: {CONFIDENCE_THRESHOLD}")
        print(f"IoU: {IOU_THRESHOLD}")

        results = model.predict(
            source=image_path,
            imgsz=IMAGE_SIZE,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            augment=False,
            verbose=False
        )

        if not results:
            return {
                "success": True,
                "damage_detected": False,
                "damage_count": 0,
                "damage_types": [],
                "highest_confidence": 0,
                "detections": [],
                "ai_status": "No detections"
            }

        result = results[0]

        detections = []
        damage_types = []
        highest_confidence = 0.0

        names = result.names

        if result.boxes is not None:
            for box in result.boxes:
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])

                if isinstance(names, dict):
                    class_name = names.get(
                        class_id,
                        str(class_id)
                    )
                else:
                    class_name = names[class_id]

                class_name = str(class_name)

                # Bounding box
                xyxy = box.xyxy[0].tolist()

                x1 = round(float(xyxy[0]), 2)
                y1 = round(float(xyxy[1]), 2)
                x2 = round(float(xyxy[2]), 2)
                y2 = round(float(xyxy[3]), 2)

                detection = {
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(
                        confidence * 100,
                        2
                    ),
                    "bbox": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    }
                }

                detections.append(detection)

                if class_name not in damage_types:
                    damage_types.append(class_name)

                highest_confidence = max(
                    highest_confidence,
                    confidence * 100
                )

        damage_count = len(detections)
        damage_detected = damage_count > 0

        if damage_detected:
            ai_status = "Damage detected"
        else:
            ai_status = "No road damage detected"

        result_data = {
            "success": True,
            "damage_detected": damage_detected,
            "damage_count": damage_count,
            "damage_types": damage_types,
            "highest_confidence": round(
                highest_confidence,
                2
            ),
            "detections": detections,
            "ai_status": ai_status
        }

        print("\nAI RESULT:")
        print(json.dumps(result_data, indent=2))

        print("----------------------------------------\n")

        return result_data

    except Exception as error:
        print("\nCIVICLENS AI ERROR:")
        print(error)

        return {
            "success": False,
            "damage_detected": False,
            "damage_count": 0,
            "damage_types": [],
            "highest_confidence": 0,
            "detections": [],
            "ai_status": f"AI error: {error}"
        }
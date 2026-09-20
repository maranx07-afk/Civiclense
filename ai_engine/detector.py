import os
from pathlib import Path

from ultralytics import YOLO


# ============================================================
# CIVICLENS ROAD DAMAGE AI
# ============================================================

BASE_DIR = Path(r"D:\CivicLens")

MODEL_PATH = (
    BASE_DIR
    / "ai_models"
    / "road_damage_best.pt"
)

RESULTS_DIR = BASE_DIR / "ai_results"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)


print("========================================")
print("CIVICLENS ROAD DAMAGE AI")
print("========================================")


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():
    print("\nLoading road-damage AI model...")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"AI model not found:\n{MODEL_PATH}\n\n"
            "Copy the downloaded best.pt model to this location "
            "and rename it to road_damage_best.pt"
        )

    model = YOLO(str(MODEL_PATH))

    print("Road-damage AI model loaded successfully!")

    return model


# ============================================================
# ANALYZE IMAGE
# ============================================================

def analyze_image(image_path, model):
    image_path = str(image_path).strip().strip('"')

    if not os.path.exists(image_path):
        return {
            "success": False,
            "error": "Image file not found"
        }

    try:
        print("\nAI is analyzing image...")
        print(f"Image: {image_path}")

        results = model.predict(
            source=image_path,
            imgsz=320,
            conf=0.25,
            save=True,
            project=str(RESULTS_DIR),
            name="detections",
            exist_ok=True,
            verbose=False
        )

        result = results[0]

        detections = []

        if result.boxes is not None and len(result.boxes) > 0:

            boxes = result.boxes

            for i in range(len(boxes)):

                class_id = int(boxes.cls[i].item())
                confidence = float(boxes.conf[i].item())

                label = result.names.get(
                    class_id,
                    f"class_{class_id}"
                )

                xyxy = boxes.xyxy[i].tolist()

                detections.append({
                    "damage_type": label,
                    "confidence": round(confidence * 100, 2),
                    "bounding_box": {
                        "x1": round(xyxy[0], 2),
                        "y1": round(xyxy[1], 2),
                        "x2": round(xyxy[2], 2),
                        "y2": round(xyxy[3], 2)
                    }
                })

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        damage_count = len(detections)

        if damage_count > 0:

            highest_confidence = max(
                item["confidence"]
                for item in detections
            )

            damage_types = sorted(
                set(
                    item["damage_type"]
                    for item in detections
                )
            )

            ai_status = "Damage detected"

        else:

            highest_confidence = 0

            damage_types = []

            ai_status = "No road damage detected"

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        return {
            "success": True,
            "damage_detected": damage_count > 0,
            "damage_count": damage_count,
            "damage_types": damage_types,
            "highest_confidence": highest_confidence,
            "detections": detections,
            "ai_status": ai_status,
            "result_image": str(
                RESULTS_DIR / "detections"
            )
        }

    except Exception as error:

        return {
            "success": False,
            "error": str(error)
        }


# ============================================================
# TEST MODE
# ============================================================

if __name__ == "__main__":

    try:

        model = load_model()

        image_path = input(
            "\nEnter image path: "
        ).strip().strip('"')

        result = analyze_image(
            image_path,
            model
        )

        print("\n========================================")
        print("AI RESULT")
        print("========================================")

        print("\n")

        print(result)

    except Exception as error:

        print("\n========================================")
        print("AI ENGINE ERROR")
        print("========================================")

        print(error)
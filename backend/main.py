import os
import json
import shutil
import sqlite3
import uuid
import math
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.detector import load_model, analyze_image


# ============================================================
# CIVICLENS CONFIGURATION
# ============================================================

BASE_DIR = Path(r"D:\CivicLens")

DATABASE_PATH = BASE_DIR / "database" / "civiclens.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
AI_RESULTS_FOLDER = BASE_DIR / "ai_results"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
AI_RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="CivicLens",
    description="Crowdsourced Infrastructure Auditor",
    version="1.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_FOLDER)),
    name="uploads"
)

app.mount(
    "/ai-results",
    StaticFiles(directory=str(AI_RESULTS_FOLDER)),
    name="ai-results"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# AI MODEL
# ============================================================

AI_MODEL = None


@app.on_event("startup")
def startup_event():
    global AI_MODEL

    print("\n========================================")
    print("CIVICLENS STARTING")
    print("========================================")

    print("Loading AI model...")

    try:
        AI_MODEL = load_model()
        print("AI model loaded successfully!")

    except Exception as error:
        print("AI MODEL ERROR:")
        print(error)
        AI_MODEL = None

    print("========================================")
    print("CIVICLENS READY")
    print("========================================\n")


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "project": "CivicLens",
        "description": "The Crowdsourced Infrastructure Auditor",
        "status": "running",
        "ai_available": AI_MODEL is not None
    }


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance_km(lat1, lon1, lat2, lon2):

    earth_radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius * c


# ============================================================
# FIND NEAREST ROAD
# ============================================================

def find_nearest_road(latitude, longitude):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            r.*,
            a.name AS authority_name,
            a.department AS authority_department,
            a.contact_email AS authority_email,
            a.contact_phone AS authority_phone
        FROM roads r
        LEFT JOIN authorities a
            ON r.authority_id = a.id
    """)

    roads = cursor.fetchall()

    connection.close()

    if not roads:
        print("No roads exist in database.")
        return None

    nearest_road = None
    nearest_distance_km = float("inf")

    print("\nGPS received:")
    print(f"Latitude:  {latitude}")
    print(f"Longitude: {longitude}")

    print("\nChecking roads...")

    for road in roads:

        if road["latitude"] is None or road["longitude"] is None:
            continue

        distance_km = calculate_distance_km(
            latitude,
            longitude,
            float(road["latitude"]),
            float(road["longitude"])
        )

        print(
            f"Road: {road['road_name']} | "
            f"Distance: {distance_km:.3f} km"
        )

        # matching_radius in database is treated as degrees
        # 0.01 degrees is approximately 1.1 km
        matching_radius = road["matching_radius"]

        if matching_radius is None:
            matching_radius = 0.01

        try:
            matching_radius_km = float(matching_radius) * 111.0
        except:
            matching_radius_km = 1.11

        if (
            distance_km <= matching_radius_km
            and distance_km < nearest_distance_km
        ):

            nearest_distance_km = distance_km
            nearest_road = road

    if nearest_road:

        print(
            f"\nRoad matched successfully: "
            f"{nearest_road['road_name']}"
        )

        print(
            f"Distance: "
            f"{nearest_distance_km:.3f} km"
        )

    else:

        print("\nNo matching road found.")

    return nearest_road


# ============================================================
# REPORT ISSUE
# ============================================================

@app.post("/report-issue")
async def report_issue(
    issue_type: str = Form(...),
    description: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    image: UploadFile = File(None)
):

    connection = None

    try:

        # ----------------------------------------------------
        # CHECK AI
        # ----------------------------------------------------

        if AI_MODEL is None:

            return {
                "success": False,
                "error": "AI model is not available"
            }


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        image_path = None
        ai_result = None

        if image is not None:

            extension = Path(
                image.filename
            ).suffix.lower()

            if extension not in [
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ]:

                return {
                    "success": False,
                    "error": "Unsupported image format"
                }

            filename = f"{uuid.uuid4()}{extension}"

            image_path = UPLOAD_FOLDER / filename

            with open(image_path, "wb") as buffer:

                shutil.copyfileobj(
                    image.file,
                    buffer
                )


            # ------------------------------------------------
            # AI ANALYSIS
            # ------------------------------------------------

            print("\n========================================")
            print("RUNNING CIVICLENS AI")
            print("========================================")

            ai_result = analyze_image(
                str(image_path),
                AI_MODEL
            )

            print("\nAI RESULT:")
            print(ai_result)

        else:

            ai_result = {
                "success": True,
                "damage_detected": False,
                "damage_count": 0,
                "damage_types": [],
                "highest_confidence": 0,
                "detections": [],
                "ai_status": "No image provided"
            }


        # ----------------------------------------------------
        # GPS ROAD MATCHING
        # ----------------------------------------------------

        road = find_nearest_road(
            latitude,
            longitude
        )

        road_id = None

        if road:

            road_id = road["id"]

        else:

            print(
                "Issue will be stored without road match."
            )


        # ----------------------------------------------------
        # DATABASE INSERT
        # ----------------------------------------------------

        connection = get_db()
        cursor = connection.cursor()


        ai_damage_detected = int(
            bool(
                ai_result.get(
                    "damage_detected",
                    False
                )
            )
        )

        ai_damage_count = int(
            ai_result.get(
                "damage_count",
                0
            )
        )

        ai_damage_types = json.dumps(
            ai_result.get(
                "damage_types",
                []
            )
        )

        ai_highest_confidence = float(
            ai_result.get(
                "highest_confidence",
                0
            )
        )

        ai_status = ai_result.get(
            "ai_status",
            "AI analysis unavailable"
        )

        ai_detections = json.dumps(
            ai_result.get(
                "detections",
                []
            )
        )


        cursor.execute("""
            INSERT INTO road_issues (
                issue_type,
                description,
                latitude,
                longitude,
                image_path,
                status,
                road_id,
                ai_damage_detected,
                ai_damage_count,
                ai_damage_types,
                ai_highest_confidence,
                ai_status,
                ai_detections
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            issue_type,
            description,
            latitude,
            longitude,
            str(image_path)
            if image_path
            else None,
            "Reported",
            road_id,
            ai_damage_detected,
            ai_damage_count,
            ai_damage_types,
            ai_highest_confidence,
            ai_status,
            ai_detections
        ))


        issue_id = cursor.lastrowid

        connection.commit()


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        image_url = None

        if image_path:

            image_url = (
                "http://127.0.0.1:8000/"
                f"uploads/{image_path.name}"
            )


        return {

            "success": True,

            "message":
                "Road issue reported successfully",

            "issue_id":
                issue_id,

            "road_id":
                road_id,

            "matched_road":
                road["road_name"]
                if road
                else None,

            "status":
                "Reported",

            "image_url":
                image_url,

            "ai_analysis": {

                "damage_detected":
                    bool(ai_damage_detected),

                "damage_count":
                    ai_damage_count,

                "damage_types":
                    ai_result.get(
                        "damage_types",
                        []
                    ),

                "highest_confidence":
                    ai_highest_confidence,

                "status":
                    ai_status,

                "detections":
                    ai_result.get(
                        "detections",
                        []
                    )
            }
        }


    except Exception as error:

        if connection:

            connection.rollback()

        print("\nREPORT ERROR:")
        print(error)

        return {
            "success": False,
            "error": str(error)
        }


    finally:

        if connection:

            connection.close()


# ============================================================
# GET ALL ISSUES
# ============================================================

@app.get("/issues")
def get_issues():

    connection = None

    try:

        connection = get_db()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                ri.*,
                r.road_name,
                r.road_type,
                r.area AS road_area
            FROM road_issues ri
            LEFT JOIN roads r
                ON ri.road_id = r.id
            ORDER BY ri.id DESC
        """)

        rows = cursor.fetchall()

        issues = []

        for row in rows:

            item = dict(row)

            if item.get("image_path"):

                filename = Path(
                    item["image_path"]
                ).name

                item["image_url"] = (
                    "http://127.0.0.1:8000/"
                    f"uploads/{filename}"
                )

            else:

                item["image_url"] = None


            if item.get("ai_damage_types"):

                try:

                    item["ai_damage_types"] = json.loads(
                        item["ai_damage_types"]
                    )

                except:

                    pass


            if item.get("ai_detections"):

                try:

                    item["ai_detections"] = json.loads(
                        item["ai_detections"]
                    )

                except:

                    pass


            issues.append(item)


        return {
            "success": True,
            "total_issues": len(issues),
            "issues": issues
        }


    except Exception as error:

        print("\nGET ISSUES ERROR:")
        print(error)

        return {
            "success": False,
            "error": str(error),
            "total_issues": 0,
            "issues": []
        }


    finally:

        if connection:

            connection.close()


# ============================================================
# ISSUE TRANSPARENCY REPORT
# ============================================================

@app.get("/issue-transparency/{issue_id}")
def issue_transparency(issue_id: int):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            ri.id AS issue_id,
            ri.issue_type,
            ri.description,
            ri.latitude,
            ri.longitude,
            ri.image_path,
            ri.status AS issue_status,
            ri.created_at,

            ri.ai_damage_detected,
            ri.ai_damage_count,
            ri.ai_damage_types,
            ri.ai_highest_confidence,
            ri.ai_status,
            ri.ai_detections,

            r.id AS road_id,
            r.road_name,
            r.road_type,
            r.area,

            a.name AS authority_name,
            a.department AS authority_department,
            a.contact_email AS authority_email,
            a.contact_phone AS authority_phone,

            rp.tender_number,
            rp.project_cost,
            rp.work_description,
            rp.start_date,
            rp.expected_completion,
            rp.warranty_period,
            rp.project_status,

            c.name AS contractor_name,
            c.company_email AS contractor_email,
            c.company_phone AS contractor_phone

        FROM road_issues ri

        LEFT JOIN roads r
            ON ri.road_id = r.id

        LEFT JOIN authorities a
            ON r.authority_id = a.id

        LEFT JOIN road_projects rp
            ON r.id = rp.road_id

        LEFT JOIN contractors c
            ON rp.contractor_id = c.id

        WHERE ri.id = ?

        LIMIT 1

    """, (issue_id,))

    row = cursor.fetchone()

    connection.close()


    if not row:

        return {
            "success": False,
            "error": "Issue not found"
        }


    report = dict(row)


    if report.get("image_path"):

        filename = Path(
            report["image_path"]
        ).name

        report["image_url"] = (
            "http://127.0.0.1:8000/"
            f"uploads/{filename}"
        )

    else:

        report["image_url"] = None


    if report.get("ai_damage_types"):

        try:

            report["ai_damage_types"] = json.loads(
                report["ai_damage_types"]
            )

        except:

            pass


    if report.get("ai_detections"):

        try:

            report["ai_detections"] = json.loads(
                report["ai_detections"]
            )

        except:

            pass


    return {
        "success": True,
        "complete_transparency_report": report
    }


# ============================================================
# ROAD TRANSPARENCY
# ============================================================

@app.get("/road-transparency/{road_id}")
def road_transparency(road_id: int):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            r.id AS road_id,
            r.road_name,
            r.road_type,
            r.area,
            r.latitude,
            r.longitude,

            a.name AS authority_name,
            a.department AS authority_department,
            a.contact_email AS authority_email,
            a.contact_phone AS authority_phone,

            rp.tender_number,
            rp.project_cost,
            rp.work_description,
            rp.start_date,
            rp.expected_completion,
            rp.warranty_period,
            rp.project_status,

            c.name AS contractor_name,
            c.company_email AS contractor_email,
            c.company_phone AS contractor_phone

        FROM roads r

        LEFT JOIN authorities a
            ON r.authority_id = a.id

        LEFT JOIN road_projects rp
            ON r.id = rp.road_id

        LEFT JOIN contractors c
            ON rp.contractor_id = c.id

        WHERE r.id = ?

    """, (road_id,))


    row = cursor.fetchone()

    connection.close()


    if not row:

        return {
            "success": False,
            "error": "Road not found"
        }


    return {
        "success": True,
        "road_transparency_report": dict(row)
    }


# ============================================================
# AI STATUS
# ============================================================

@app.get("/ai-status")
def ai_status():

    return {

        "ai_available":
            AI_MODEL is not None,

        "model":
            "Road Damage YOLO",

        "status":
            "ready"
            if AI_MODEL is not None
            else "unavailable"
    }
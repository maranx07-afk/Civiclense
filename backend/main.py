import os
import json
import math
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.detector import load_model, analyze_image


# ============================================================
# CIVICLENS CONFIGURATION
# ============================================================

BASE_DIR = Path(r"D:\CivicLens")

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

SUPABASE_STORAGE_BUCKET = os.getenv(
    "SUPABASE_STORAGE_BUCKET",
    "civiclense-images"
)


# ============================================================
# CHECK REQUIRED CONFIGURATION
# ============================================================

if not DATABASE_URL:
    print("WARNING: DATABASE_URL is missing from .env")

if not SUPABASE_URL:
    print("WARNING: SUPABASE_URL is missing from .env")

if not SUPABASE_SERVICE_KEY:
    print("WARNING: SUPABASE_SERVICE_KEY is missing from .env")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="CivicLens",
    description="The Crowdsourced Infrastructure Auditor",
    version="2.0"
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
# AI MODEL
# ============================================================

AI_MODEL = None


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing from .env"
        )

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


# ============================================================
# SUPABASE STORAGE
# ============================================================

def get_storage_object_path(filename: str) -> str:

    return f"issues/{filename}"


def get_public_storage_url(object_path: str):

    if not SUPABASE_URL:
        return None

    encoded_path = quote(
        object_path,
        safe="/"
    )

    return (
        f"{SUPABASE_URL.rstrip('/')}"
        f"/storage/v1/object/public/"
        f"{SUPABASE_STORAGE_BUCKET}/"
        f"{encoded_path}"
    )


def upload_to_supabase_storage(
    file_bytes: bytes,
    original_filename: str,
    content_type: str | None
):

    """
    Upload image directly to Supabase Storage REST API.

    This intentionally does NOT use:

    because the installed storage client produced:
        'dict' object has no attribute 'text'

    The REST API is more reliable for this deployment.
    """

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is missing from .env"
        )

    if not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_KEY is missing from .env"
        )

    if not SUPABASE_STORAGE_BUCKET:
        raise RuntimeError(
            "SUPABASE_STORAGE_BUCKET is missing from .env"
        )


    # --------------------------------------------------------
    # FILE EXTENSION
    # --------------------------------------------------------

    extension = Path(
        original_filename or ""
    ).suffix.lower()

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    }

    if extension not in allowed_extensions:
        extension = ".jpg"


    # --------------------------------------------------------
    # UNIQUE STORAGE NAME
    # --------------------------------------------------------

    filename = (
        f"{uuid.uuid4()}"
        f"{extension}"
    )

    object_path = get_storage_object_path(
        filename
    )


    # --------------------------------------------------------
    # STORAGE URL
    # --------------------------------------------------------

    encoded_path = quote(
        object_path,
        safe="/"
    )

    upload_url = (
        f"{SUPABASE_URL.rstrip('/')}"
        f"/storage/v1/object/"
        f"{SUPABASE_STORAGE_BUCKET}/"
        f"{encoded_path}"
    )


    # --------------------------------------------------------
    # CONTENT TYPE
    # --------------------------------------------------------

    if not content_type:

        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }

        content_type = content_type_map.get(
            extension,
            "application/octet-stream"
        )


    # --------------------------------------------------------
    # HTTP REQUEST
    # --------------------------------------------------------

    request = Request(
        upload_url,
        data=file_bytes,
        method="POST"
    )

    request.add_header(
        "Authorization",
        f"Bearer {SUPABASE_SERVICE_KEY}"
    )

    request.add_header(
        "apikey",
        SUPABASE_SERVICE_KEY
    )

    request.add_header(
        "Content-Type",
        content_type
    )

    request.add_header(
        "x-upsert",
        "false"
    )


    try:

        with urlopen(
            request,
            timeout=60
        ) as response:

            response_data = response.read()

            print(
                "Supabase Storage upload HTTP status:",
                response.status
            )

            print(
                "Supabase Storage upload successful."
            )

    except HTTPError as error:

        error_body = ""

        try:
            error_body = error.read().decode(
                "utf-8",
                errors="replace"
            )
        except Exception:
            pass

        raise RuntimeError(
            "Supabase Storage upload failed: "
            f"HTTP {error.code} - {error_body}"
        )

    except URLError as error:

        raise RuntimeError(
            "Could not connect to Supabase Storage: "
            f"{error}"
        )

    except Exception as error:

        raise RuntimeError(
            "Supabase Storage upload error: "
            f"{error}"
        )


    # --------------------------------------------------------
    # PUBLIC URL
    # --------------------------------------------------------

    public_url = get_public_storage_url(
        object_path
    )

    return {
        "object_path": object_path,
        "public_url": public_url
    }


# ============================================================
# IMAGE URL HELPER
# ============================================================

def get_image_url(image_path):

    if not image_path:
        return None


    image_path = str(image_path)


    # Already a URL
    if image_path.startswith(
        "http://"
    ) or image_path.startswith(
        "https://"
    ):
        return image_path


    # New Supabase Storage object path
    if image_path.startswith("issues/"):

        return get_public_storage_url(
            image_path
        )


    # Old local Windows path
    if "\\" in image_path:

        filename = Path(
            image_path
        ).name

        return None


    return None


# ============================================================
# DATABASE TEST
# ============================================================

def test_database_connection():

    connection = None

    try:

        connection = get_db()

        cursor = connection.cursor()

        cursor.execute(
            "SELECT NOW() AS database_time"
        )

        row = cursor.fetchone()

        print(
            "SUPABASE DATABASE CONNECTION SUCCESS"
        )

        print(
            "Database time:",
            row["database_time"]
        )

        return True

    except Exception as error:

        print(
            "SUPABASE DATABASE ERROR:"
        )

        print(error)

        return False

    finally:

        if connection:

            connection.close()


# ============================================================
# FASTAPI STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():

    global AI_MODEL


    print()
    print("========================================")
    print("CIVICLENS STARTING")
    print("========================================")


    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    print()
    print("Testing Supabase Database...")

    test_database_connection()


    # --------------------------------------------------------
    # STORAGE
    # --------------------------------------------------------

    print()
    print("Supabase Storage configuration:")

    print(
        "Bucket:",
        SUPABASE_STORAGE_BUCKET
    )

    print(
        "Storage startup test skipped."
    )

    print(
        "Images will be tested during upload."
    )


    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    print()
    print("Loading AI model...")


    try:

        AI_MODEL = load_model()

        print(
            "AI model loaded successfully!"
        )

    except Exception as error:

        print(
            "AI MODEL ERROR:"
        )

        print(error)

        AI_MODEL = None


    print()
    print("========================================")
    print("CIVICLENS READY")
    print("========================================")
    print()


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {

        "project":
            "CivicLens",

        "description":
            "The Crowdsourced Infrastructure Auditor",

        "status":
            "running",

        "database":
            "Supabase PostgreSQL",

        "storage":
            SUPABASE_STORAGE_BUCKET,

        "ai_available":
            AI_MODEL is not None
    }


# ============================================================
# DISTANCE CALCULATION
# ============================================================

def calculate_distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

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
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )


    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


    return earth_radius * c


# ============================================================
# FIND NEAREST ROAD
# ============================================================

def find_nearest_road(
    latitude,
    longitude
):

    connection = None


    try:

        connection = get_db()

        cursor = connection.cursor()


        cursor.execute(
            """
            SELECT
                r.*,

                a.name AS authority_name,
                a.department AS authority_department,
                a.contact_email AS authority_email,
                a.contact_phone AS authority_phone

            FROM roads r

            LEFT JOIN authorities a
                ON r.authority_id = a.id
            """
        )


        roads = cursor.fetchall()


    finally:

        if connection:
            connection.close()


    if not roads:

        print(
            "No roads exist in database."
        )

        return None


    nearest_road = None

    nearest_distance_km = float(
        "inf"
    )


    print()
    print("GPS received:")

    print(
        f"Latitude:  {latitude}"
    )

    print(
        f"Longitude: {longitude}"
    )


    print()
    print("Checking roads...")


    for road in roads:

        if (
            road["latitude"] is None
            or
            road["longitude"] is None
        ):
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


        matching_radius = (
            road["matching_radius"]
        )


        if matching_radius is None:

            matching_radius = 0.01


        try:

            matching_radius_km = (
                float(matching_radius)
                * 111.0
            )

        except Exception:

            matching_radius_km = 1.11


        if (
            distance_km <= matching_radius_km
            and
            distance_km < nearest_distance_km
        ):

            nearest_distance_km = (
                distance_km
            )

            nearest_road = road


    if nearest_road:

        print()

        print(
            "Road matched successfully:",
            nearest_road["road_name"]
        )

        print(
            f"Distance: "
            f"{nearest_distance_km:.3f} km"
        )

    else:

        print()
        print(
            "No matching road found."
        )


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

    temp_image_path = None


    try:

        # ----------------------------------------------------
        # AI CHECK
        # ----------------------------------------------------

        if AI_MODEL is None:

            return {
                "success": False,
                "error":
                    "AI model is not available"
            }


        # ----------------------------------------------------
        # IMAGE VARIABLES
        # ----------------------------------------------------

        image_url = None

        image_storage_path = None

        ai_result = None


        # ----------------------------------------------------
        # IMAGE PROCESSING
        # ----------------------------------------------------

        if image is not None:


            extension = Path(
                image.filename or ""
            ).suffix.lower()


            allowed_extensions = [
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ]


            if extension not in allowed_extensions:

                return {
                    "success": False,
                    "error":
                        "Unsupported image format. "
                        "Use JPG, JPEG, PNG or WEBP."
                }


            # ------------------------------------------------
            # READ IMAGE
            # ------------------------------------------------

            image_bytes = await image.read()


            if not image_bytes:

                return {
                    "success": False,
                    "error":
                        "Uploaded image is empty"
                }


            print()
            print("========================================")
            print("IMAGE RECEIVED")
            print("========================================")

            print(
                "Filename:",
                image.filename
            )

            print(
                "Size:",
                len(image_bytes),
                "bytes"
            )


            # ------------------------------------------------
            # TEMP FILE FOR AI
            # ------------------------------------------------

            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=extension
            )

            temp_image_path = Path(
                temp_file.name
            )

            temp_file.write(
                image_bytes
            )

            temp_file.close()


            # ------------------------------------------------
            # AI ANALYSIS
            # ------------------------------------------------

            print()
            print("========================================")
            print("RUNNING CIVICLENS AI")
            print("========================================")


            ai_result = analyze_image(
                str(temp_image_path),
                AI_MODEL
            )


            print()
            print("AI RESULT:")

            print(
                ai_result
            )


            # ------------------------------------------------
            # SUPABASE STORAGE UPLOAD
            # ------------------------------------------------

            print()
            print("========================================")
            print("UPLOADING IMAGE TO SUPABASE STORAGE")
            print("========================================")


            storage_result = (
                upload_to_supabase_storage(
                    image_bytes,
                    image.filename,
                    image.content_type
                )
            )


            image_storage_path = (
                storage_result["object_path"]
            )


            image_url = (
                storage_result["public_url"]
            )


            print(
                "Storage path:",
                image_storage_path
            )

            print(
                "Public image URL:",
                image_url
            )


        else:

            # ------------------------------------------------
            # NO IMAGE
            # ------------------------------------------------

            ai_result = {

                "success": True,

                "damage_detected": False,

                "damage_count": 0,

                "damage_types": [],

                "highest_confidence": 0,

                "detections": [],

                "ai_status":
                    "No image provided"
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
                "Issue will be stored "
                "without road match."
            )


        # ----------------------------------------------------
        # AI VALUES
        # ----------------------------------------------------

        ai_damage_detected = bool(
            ai_result.get(
                "damage_detected",
                False
            )
        )


        ai_damage_count = int(
            ai_result.get(
                "damage_count",
                0
            )
        )


        ai_damage_types = (
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


        ai_detections = (
            ai_result.get(
                "detections",
                []
            )
        )


        # ----------------------------------------------------
        # DATABASE INSERT
        # ----------------------------------------------------

        connection = get_db()

        cursor = connection.cursor()


        cursor.execute(
            """
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

            VALUES (

                %s,
                %s,

                %s,
                %s,

                %s,

                %s,
                %s,

                %s,
                %s,
                %s,
                %s,
                %s,
                %s

            )

            RETURNING id
            """,

            (

                issue_type,

                description,

                latitude,

                longitude,

                image_storage_path,

                "Reported",

                road_id,

                ai_damage_detected,

                ai_damage_count,

                Jsonb(
                    ai_damage_types
                ),

                ai_highest_confidence,

                ai_status,

                Jsonb(
                    ai_detections
                )
            )
        )


        result = cursor.fetchone()


        issue_id = result["id"]


        connection.commit()


        # ----------------------------------------------------
        # SUCCESS RESPONSE
        # ----------------------------------------------------

        print()
        print("========================================")
        print("CIVICLENS REPORT CREATED")
        print("========================================")

        print(
            "Issue ID:",
            issue_id
        )

        print(
            "Road:",
            road["road_name"]
            if road
            else "No matching road"
        )

        print(
            "Image:",
            image_url
            if image_url
            else "None"
        )


        return {

            "success": True,

            "message":
                "Road issue reported "
                "and stored successfully",

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
                    ai_damage_detected,

                "damage_count":
                    ai_damage_count,

                "damage_types":
                    ai_damage_types,

                "highest_confidence":
                    ai_highest_confidence,

                "status":
                    ai_status,

                "detections":
                    ai_detections
            }
        }


    except Exception as error:

        if connection:

            connection.rollback()


        print()
        print("========================================")
        print("REPORT ERROR")
        print("========================================")

        print(error)


        return {

            "success": False,

            "error":
                str(error)
        }


    finally:

        # ----------------------------------------------------
        # CLOSE DATABASE
        # ----------------------------------------------------

        if connection:

            connection.close()


        # ----------------------------------------------------
        # DELETE TEMP AI IMAGE
        # ----------------------------------------------------

        if temp_image_path:

            try:

                if temp_image_path.exists():

                    temp_image_path.unlink()

            except Exception as cleanup_error:

                print(
                    "Temporary image cleanup error:",
                    cleanup_error
                )


# ============================================================
# GET ALL ISSUES
# ============================================================

@app.get("/issues")
def get_issues():

    connection = None


    try:

        connection = get_db()

        cursor = connection.cursor()


        cursor.execute(
            """
            SELECT

                ri.*,

                r.road_name,
                r.road_type,
                r.area AS road_area

            FROM road_issues ri

            LEFT JOIN roads r
                ON ri.road_id = r.id

            ORDER BY ri.id DESC
            """
        )


        rows = cursor.fetchall()


        issues = []


        for row in rows:

            item = dict(row)


            # ------------------------------------------------
            # IMAGE URL
            # ------------------------------------------------

            item["image_url"] = (
                get_image_url(
                    item.get("image_path")
                )
            )


            # ------------------------------------------------
            # JSONB SAFETY
            # ------------------------------------------------

            if isinstance(
                item.get("ai_damage_types"),
                str
            ):

                try:

                    item["ai_damage_types"] = (
                        json.loads(
                            item["ai_damage_types"]
                        )
                    )

                except Exception:
                    pass


            if isinstance(
                item.get("ai_detections"),
                str
            ):

                try:

                    item["ai_detections"] = (
                        json.loads(
                            item["ai_detections"]
                        )
                    )

                except Exception:
                    pass


            issues.append(item)


        return {

            "success": True,

            "total_issues":
                len(issues),

            "issues":
                issues
        }


    except Exception as error:

        print()
        print(
            "GET ISSUES ERROR:"
        )

        print(error)


        return {

            "success": False,

            "error":
                str(error),

            "total_issues":
                0,

            "issues":
                []
        }


    finally:

        if connection:

            connection.close()


# ============================================================
# ISSUE TRANSPARENCY REPORT
# ============================================================

@app.get(
    "/issue-transparency/{issue_id}"
)
def issue_transparency(
    issue_id: int
):

    connection = None


    try:

        connection = get_db()

        cursor = connection.cursor()


        cursor.execute(
            """
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

            WHERE ri.id = %s

            LIMIT 1
            """,
            (issue_id,)
        )


        row = cursor.fetchone()


        if not row:

            return {

                "success": False,

                "error":
                    "Issue not found"
            }


        report = dict(row)


        # ----------------------------------------------------
        # IMAGE URL
        # ----------------------------------------------------

        report["image_url"] = (
            get_image_url(
                report.get("image_path")
            )
        )


        # ----------------------------------------------------
        # JSONB
        # ----------------------------------------------------

        if isinstance(
            report.get("ai_damage_types"),
            str
        ):

            try:

                report["ai_damage_types"] = (
                    json.loads(
                        report["ai_damage_types"]
                    )
                )

            except Exception:
                pass


        if isinstance(
            report.get("ai_detections"),
            str
        ):

            try:

                report["ai_detections"] = (
                    json.loads(
                        report["ai_detections"]
                    )
                )

            except Exception:
                pass


        return {

            "success": True,

            "complete_transparency_report":
                report
        }


    except Exception as error:

        print(
            "ISSUE TRANSPARENCY ERROR:"
        )

        print(error)


        return {

            "success": False,

            "error":
                str(error)
        }


    finally:

        if connection:

            connection.close()


# ============================================================
# ROAD TRANSPARENCY
# ============================================================

@app.get(
    "/road-transparency/{road_id}"
)
def road_transparency(
    road_id: int
):

    connection = None


    try:

        connection = get_db()

        cursor = connection.cursor()


        cursor.execute(
            """
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

            WHERE r.id = %s
            """,
            (road_id,)
        )


        row = cursor.fetchone()


        if not row:

            return {

                "success": False,

                "error":
                    "Road not found"
            }


        return {

            "success": True,

            "road_transparency_report":
                dict(row)
        }


    except Exception as error:

        print(
            "ROAD TRANSPARENCY ERROR:"
        )

        print(error)


        return {

            "success": False,

            "error":
                str(error)
        }


    finally:

        if connection:

            connection.close()


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


# ============================================================
# STORAGE STATUS
# ============================================================

@app.get("/storage-status")
def storage_status():

    configured = (
        bool(SUPABASE_URL)
        and
        bool(SUPABASE_SERVICE_KEY)
        and
        bool(SUPABASE_STORAGE_BUCKET)
    )


    return {

        "storage_configured":
            configured,

        "bucket":
            SUPABASE_STORAGE_BUCKET,

        "method":
            "Supabase Storage REST API",

        "status":
            "ready"
            if configured
            else "not_configured"
    }
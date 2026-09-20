import sqlite3

DATABASE_PATH = "database/civiclens.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_connection()
    cursor = connection.cursor()

    # Government Authorities Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS authorities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        area TEXT
    )
    """)

    # Contractors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contractors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company_email TEXT,
        company_phone TEXT
    )
    """)

    # Roads Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        road_name TEXT NOT NULL,
        road_type TEXT,
        area TEXT,
        authority_id INTEGER,
        latitude REAL,
        longitude REAL,
        matching_radius REAL DEFAULT 0.01,

        FOREIGN KEY (authority_id) REFERENCES authorities(id)
    )
    """)

    # Road Projects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS road_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        road_id INTEGER,
        contractor_id INTEGER,
        tender_number TEXT,
        project_cost REAL,
        work_description TEXT,
        start_date TEXT,
        expected_completion TEXT,
        warranty_period TEXT,
        project_status TEXT DEFAULT 'Active',

        FOREIGN KEY (road_id) REFERENCES roads(id),
        FOREIGN KEY (contractor_id) REFERENCES contractors(id)
    )
    """)

    # Road Issues Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS road_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_type TEXT NOT NULL,
        description TEXT,
        latitude REAL,
        longitude REAL,
        image_path TEXT,
        status TEXT DEFAULT 'Reported',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    connection.commit()
    connection.close()

    print("CivicLens database tables created successfully!")


def add_column_if_missing(table_name, column_name, column_type):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")

    columns = [column[1] for column in cursor.fetchall()]

    if column_name not in columns:

        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )

        connection.commit()

        print(f"{column_name} column added successfully!")

    else:
        print(f"{column_name} column already exists!")

    connection.close()


def update_existing_database():

    # Road Issues
    add_column_if_missing(
        "road_issues",
        "road_id",
        "INTEGER"
    )

    # AI Analysis Fields
    add_column_if_missing(
        "road_issues",
        "ai_damage_detected",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        "road_issues",
        "ai_damage_count",
        "INTEGER DEFAULT 0"
    )

    add_column_if_missing(
        "road_issues",
        "ai_damage_types",
        "TEXT"
    )

    add_column_if_missing(
        "road_issues",
        "ai_highest_confidence",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        "road_issues",
        "ai_status",
        "TEXT"
    )

    add_column_if_missing(
        "road_issues",
        "ai_detections",
        "TEXT"
    )

    # Roads GPS Location
    add_column_if_missing(
        "roads",
        "latitude",
        "REAL"
    )

    add_column_if_missing(
        "roads",
        "longitude",
        "REAL"
    )

    add_column_if_missing(
        "roads",
        "matching_radius",
        "REAL DEFAULT 0.01"
    )


if __name__ == "__main__":

    create_database()

    update_existing_database()

    print("CivicLens database update completed successfully!")
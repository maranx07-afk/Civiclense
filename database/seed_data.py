import sqlite3

DATABASE_PATH = "database/civiclens.db"


def add_sample_data():

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    # Add Government Authority
    cursor.execute("""
        INSERT INTO authorities
        (name, department, contact_email, contact_phone, area)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "Salem City Municipal Corporation",
        "Roads and Infrastructure Department",
        "roads@salem.gov.in",
        "0000000000",
        "Salem"
    ))

    authority_id = cursor.lastrowid


    # Add Contractor
    cursor.execute("""
        INSERT INTO contractors
        (name, company_email, company_phone)
        VALUES (?, ?, ?)
    """, (
        "Sample Infrastructure Pvt Ltd",
        "contact@example.com",
        "0000000000"
    ))

    contractor_id = cursor.lastrowid


    # Add Road
    cursor.execute("""
        INSERT INTO roads
        (road_name, road_type, area, authority_id)
        VALUES (?, ?, ?, ?)
    """, (
        "Sample Main Road",
        "City Road",
        "Salem",
        authority_id
    ))

    road_id = cursor.lastrowid


    # Add Road Project
    cursor.execute("""
        INSERT INTO road_projects
        (
            road_id,
            contractor_id,
            tender_number,
            project_cost,
            work_description,
            start_date,
            expected_completion,
            warranty_period,
            project_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        road_id,
        contractor_id,
        "TN-DEMO-ROAD-2026-001",
        25000000,
        "Road resurfacing and drainage improvement",
        "2026-01-15",
        "2026-12-31",
        "5 Years",
        "Active"
    ))

    connection.commit()
    connection.close()

    print("Sample CivicLens data added successfully!")


if __name__ == "__main__":
    add_sample_data()
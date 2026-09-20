import sqlite3


DATABASE_PATH = "database/civiclens.db"


def update_road_location():

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE roads
        SET latitude = ?,
            longitude = ?,
            matching_radius = ?
        WHERE id = ?
    """, (
        11.6643,
        78.1460,
        0.01,
        1
    ))

    connection.commit()

    print("Road location updated successfully!")
    print("Road ID: 1")
    print("Latitude: 11.6643")
    print("Longitude: 78.1460")
    print("Matching Radius: 0.01")

    connection.close()


if __name__ == "__main__":
    update_road_location()
import sqlite3

def init_db():
    conn = sqlite3.connect("wedding.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weddings (
        wedding_id TEXT PRIMARY KEY,
        collection_id TEXT,
        status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faces (
        face_id TEXT PRIMARY KEY,
        wedding_id TEXT,
        filename TEXT
    )
    """)

    conn.commit()
    conn.close()

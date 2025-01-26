import sqlite3

def inspect_database(db_path):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in {db_path}:\n")
        for table in tables:
            print(f"- {table[0]}")

        # Inspect the first 5 rows of each table
        for table in tables:
            table_name = table[0]
            print(f"\nSchema for table '{table_name}':")
            cursor.execute(f"PRAGMA table_info({table_name});")
            schema = cursor.fetchall()
            for column in schema:
                print(f"  {column[1]} ({column[2]})")

            print(f"\nFirst 5 rows of table '{table_name}':")
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            rows = cursor.fetchall()
            for row in rows:
                print(row)

        conn.close()
    except sqlite3.Error as e:
        print(f"Error while accessing the database: {e}")

# Replace with the path to your database
db_path = r'C:\Workspace\abbreviator\db.sqlite3'
inspect_database(db_path)
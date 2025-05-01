import json
import sqlite3

from lib.lib_yeoul import uni_log_debug


# ---------------------------------------------------------------------------- #
class ObjectStorage:
    def __init__(self, db_name="user_data.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor: sqlite3.Cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS json_objects (id INTEGER PRIMARY KEY, name TEXT UNIQUE, object TEXT)"""
        )
        self.conn.commit()

    def save_json_object(self, data, name="user_data"):
        json_data = json.dumps(data)
        self.cursor.execute(
            """ INSERT INTO json_objects (name, object) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET object = ? """,
            (name, json_data, json_data),
        )
        self.conn.commit()

    def load_json_object(self, name="user_data"):
        self.cursor.execute("""SELECT object FROM json_objects WHERE name = ?""", (name,))
        result = self.cursor.fetchone()
        uni_log_debug(f"load_json_object {result=}")
        return json.loads(result[0]) if result else None

    def close(self):
        self.conn.close()

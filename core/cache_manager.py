import sqlite3
import os
import json

class CacheManager:
    def __init__(self, db_path=os.path.expanduser("~/.config/tray-ai/models_cache.db")):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    size_gb REAL,
                    mtime REAL,
                    arch TEXT,
                    quant TEXT,
                    max_context INTEGER,
                    total_layers INTEGER,
                    has_mtp INTEGER,
                    has_thinking INTEGER,
                    has_tools INTEGER,
                    has_vision INTEGER,
                    extra_meta TEXT
                )
            """)
            conn.commit()

    def get_model(self, path, current_mtime):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path = ? AND mtime = ?", (path, current_mtime))
            row = cursor.fetchone()
            if row:
                return {
                    "path": row[0],
                    "filename": row[1],
                    "size_gb": row[2],
                    "mtime": row[3],
                    "arch": row[4],
                    "quant": row[5],
                    "max_context": row[6],
                    "total_layers": row[7],
                    "has_mtp": bool(row[8]),
                    "has_thinking": bool(row[9]),
                    "has_tools": bool(row[10]),
                    "has_vision": bool(row[11]),
                    "extra_meta": json.loads(row[12]) if row[12] else {}
                }
        return None

    def save_model(self, info):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info["path"], info["filename"], info["size_gb"], info["mtime"],
                info["arch"], info["quant"], info["max_context"], info["total_layers"],
                int(info["has_mtp"]), int(info["has_thinking"]), int(info["has_tools"]),
                int(info["has_vision"]), json.dumps(info.get("extra_meta", {}))
            ))
            conn.commit()

    def get_all_by_folder(self, folder):
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path LIKE ?", (f"{folder}%",))
            for row in cursor.fetchall():
                results.append({
                    "path": row[0],
                    "filename": row[1],
                    "size_gb": row[2],
                    "mtime": row[3],
                    "arch": row[4],
                    "quant": row[5],
                    "max_context": row[6],
                    "total_layers": row[7],
                    "has_mtp": bool(row[8]),
                    "has_thinking": bool(row[9]),
                    "has_tools": bool(row[10]),
                    "has_vision": bool(row[11]),
                    "extra_meta": json.loads(row[12]) if row[12] else {}
                })
        return results

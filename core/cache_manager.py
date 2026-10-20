import sqlite3
import os
import json

CACHE_SCHEMA_VERSION = 3

class CacheManager:
    def __init__(self, db_path=os.path.expanduser("~/.config/tray-ai/models_cache.db")):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version")
            ver = cursor.fetchone()[0]
            if ver != CACHE_SCHEMA_VERSION:
                cursor.execute("DROP TABLE IF EXISTS models")
                cursor.execute(f"PRAGMA user_version = {CACHE_SCHEMA_VERSION}")

            cursor.execute("""
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

    def _row_to_dict(self, row):
        extra = json.loads(row[12]) if row[12] else {}
        return {
            "path": row[0],
            "filename": row[1],
            "size_gb": row[2],
            "mtime": row[3],
            "arch": row[4],
            "quant": row[5],
            "max_context": row[6],
            "base_context": extra.get("base_context", row[6]),
            "total_layers": row[7],
            "has_mtp": bool(row[8]),
            "mtp_layers": extra.get("mtp_layers", 1 if row[8] else 0),
            "has_yarn": extra.get("has_yarn", False),
            "has_thinking": bool(row[9]),
            "has_tools": bool(row[10]),
            "has_vision": bool(row[11]),
            "publisher": extra.get("publisher", "Bilinmiyor"),
            "recommended_temp": extra.get("recommended_temp", 0.70),
            "recommended_topp": extra.get("recommended_topp", 0.90),
            "recommended_minp": extra.get("recommended_minp", 0.05),
            " recommended_top_k": extra.get("recommended_top_k", 40),
            "extra_meta": extra
        }

    def get_model(self, path, current_mtime):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path = ? AND mtime = ?", (path, current_mtime))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def save_model(self, info):
        extra = info.get("extra_meta", {}).copy()
        extra["publisher"] = info.get("publisher", "Bilinmiyor")
        extra["base_context"] = info.get("base_context", info.get("max_context", 4096))
        extra["mtp_layers"] = info.get("mtp_layers", 0)
        extra["has_yarn"] = info.get("has_yarn", False)
        extra["recommended_temp"] = info.get("recommended_temp", 0.70)
        extra["recommended_topp"] = info.get("recommended_topp", 0.90)
        extra["recommended_minp"] = info.get("recommended_minp", 0.05)
        extra["recommended_top_k"] = info.get("recommended_top_k", 40)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info["path"], info["filename"], info["size_gb"], info["mtime"],
                info["arch"], info["quant"], info["max_context"], info["total_layers"],
                int(info["has_mtp"]), int(info["has_thinking"]), int(info["has_tools"]),
                int(info["has_vision"]), json.dumps(extra)
            ))
            conn.commit()

    def get_all_by_folder(self, folder):
        results = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path LIKE ?", (f"{folder}%",))
            for row in cursor.fetchall():
                results.append(self._row_to_dict(row))
        return results

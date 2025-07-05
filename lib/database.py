import json
import sqlite3
import threading
from typing import Any, Dict, Optional

from lib.lib_yeoul import log_error

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.05"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Database:
    """
    Database는 SQLite 데이터베이스를 사용하여 키-값 쌍을 저장하는 클래스입니다.
    - 데이터는 JSON 형식으로 저장됩니다.
    - 데이터베이스는 database 테이블을 사용합니다.
    - 각 키는 고유하며, 값은 JSON 문자열로 저장됩니다.
    - 데이터베이스는 WAL(Write-Ahead Logging) 모드로 설정되어 동시성을 지원합니다.
    - 외래키 제약 조건이 활성화되어 데이터 무결성을 보장합니다
    - 동기화 모드는 NORMAL로 설정되어 성능과 안전성의 균형을 맞춥니다.
    - 캐시 크기는 10,000으로 설정되어 성능을 향상시킵니다.
    - 데이터베이스 파일은 기본적으로 "database.db"로 설정되어 있으며, 필요에 따라 변경할 수 있습니다.
    - 데이터베이스 연결은 쓰레드 안전하게 처리됩니다.
    - 기본값을 설정할 수 있는 load 메서드가 있습니다.
    - 데이터베이스에 저장된 모든 키를 나열할 수 있는 list_keys 메서드가 있습니다.
    - 특정 키가 존재하는지 확인할 수 있는 exists 메서드가 있습니다.
    - 데이터베이스를 비우는 clear_all 메서드가 있습니다.
    - 데이터베이스는 기본적으로 3초의 타임아웃을 가지며, 필요에 따라 변경할 수 있습니다.
    """

    def __init__(self, db_path="database.db", timeout: float = 3.0):
        self.db_path = db_path
        self.timeout = timeout
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            with self._lock:
                with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")  # WAL 모드로 설정 (더 나은 동시성 지원)
                    conn.execute("PRAGMA foreign_keys=ON")  # 외래키 제약 조건 활성화
                    conn.execute("PRAGMA synchronous=NORMAL")  # 동기화 모드 설정 (성능과 안전성 균형)
                    conn.execute("PRAGMA cache_size=10000")  # 캐시 크기 설정
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS database (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """
                    )
                    conn.commit()
        except Exception as e:
            log_error(f"{self.db_path} _init_db() 에러 : {e}")

    def save(self, key: str, data: Any) -> bool:
        try:
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO database (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, json_data),
                )
                conn.commit()
                return True
        except Exception as e:
            log_error(f"{self.db_path} save() 에러 : {e}")
            return False

    def load(self, key: str, default: Any) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT value FROM database WHERE key = ?""", (key,))
                result = cursor.fetchone()
                if result:
                    data = json.loads(result[0])
                    return data
                self.save(key, default)  # 기본값이 없으면 저장
                return default
        except Exception as e:
            log_error(f"{self.db_path} load() 에러 {default=}: {e}")
            self.save(key, default)  # 기본값이 없으면 저장
            return default

    def list_keys(self) -> list:
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT key, created_at, updated_at FROM database ORDER BY key""")
                results = cursor.fetchall()
                keys = []
                for key, created, updated in results:
                    keys.append({"key": key, "created_at": created, "updated_at": updated})
                return keys
        except Exception:
            return []

    def exists(self, key: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM database WHERE key = ?", (key,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception:
            return False

    def clear_all(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM database")
                conn.commit()
            return True
        except Exception as e:
            log_error(f"{self.db_path} clear_all() 에러 : {e}")
            return False

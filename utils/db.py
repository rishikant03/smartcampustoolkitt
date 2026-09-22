import os
import sys
import re
import sqlite3

# Export standard sqlite3 attributes so app.py works seamlessly
Row = sqlite3.Row
DatabaseError = sqlite3.DatabaseError
ProgrammingError = sqlite3.ProgrammingError

# Try to import psycopg2; if missing (e.g. local machine or build step), fall back cleanly
try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_PSYCOPG2 = True
    IntegrityError = psycopg2.IntegrityError
    Error = psycopg2.Error
    OperationalError = psycopg2.OperationalError
except ImportError:
    HAS_PSYCOPG2 = False
    IntegrityError = sqlite3.IntegrityError
    Error = sqlite3.Error
    OperationalError = sqlite3.OperationalError


def get_sqlite_path():
    # If in Vercel or AWS Lambda, root filesystem is read-only, so use /tmp
    is_serverless = bool(
        os.getenv("VERCEL") 
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME") 
        or os.getenv("LAMBDA_TASK_ROOT")
        or (os.name != 'nt' and os.path.exists("/tmp"))
    )
    if is_serverless:
        target_path = "/tmp/smartcampus.db"
        if not os.path.exists(target_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            source_path = os.path.join(base_dir, "smartcampus.db")
            if os.path.exists(source_path):
                import shutil
                try:
                    shutil.copy2(source_path, target_path)
                except Exception:
                    pass
        return target_path
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "smartcampus.db")


class PgCursor:
    def __init__(self, pg_cursor):
        self._cursor = pg_cursor
        self.lastrowid = None
        self._last_row = None

    def execute(self, query, params=()):
        q = query
        # Replace SQLite ? with Postgres %s
        if '?' in q and '%s' not in q:
            q = q.replace('?', '%s')
            
        # SQLite's INSERT OR IGNORE -> Postgres ON CONFLICT DO NOTHING
        if "INSERT OR IGNORE INTO user_profiles (user_id)" in q:
            q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            q += " ON CONFLICT (user_id) DO NOTHING"
        elif "INSERT OR IGNORE INTO user_profiles (user_id, full_name)" in q:
            q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            q += " ON CONFLICT (user_id) DO NOTHING"

        is_returning = "RETURNING id" in q.upper()

        self._cursor.execute(q, params)
        
        if is_returning:
            row = self._cursor.fetchone()
            self._last_row = row
            if row:
                self.lastrowid = row['id']
                
        return self

    def fetchone(self):
        if self._last_row is not None:
            r = self._last_row
            self._last_row = None
            return r
        try:
            return self._cursor.fetchone()
        except Exception:
            return None

    def fetchall(self):
        try:
            return self._cursor.fetchall()
        except Exception:
            return []
            
    @property
    def rowcount(self):
        return self._cursor.rowcount


class PgConnection:
    def __init__(self, db_url):
        self.conn = psycopg2.connect(db_url)
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._row_factory = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

    def execute(self, query, params=()):
        cur = self.conn.cursor(cursor_factory=DictCursor)
        pg_cursor = PgCursor(cur)
        return pg_cursor.execute(query, params)
        
    def commit(self):
        self.conn.commit()
        
    def close(self):
        self.conn.close()


class SqliteCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = cursor.lastrowid

    def execute(self, query, params=()):
        q = query
        # Convert Postgres SERIAL PRIMARY KEY to SQLite INTEGER PRIMARY KEY AUTOINCREMENT
        if "SERIAL PRIMARY KEY" in q.upper():
            q = re.sub(r'\bSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', q, flags=re.IGNORECASE)
            
        # Convert Postgres %s to SQLite ?
        if '%s' in q and '?' not in q:
            q = q.replace('%s', '?')

        # Strip RETURNING id for SQLite so SQLite doesn't leave unconsumed statement cursors
        q = re.sub(r'\s+RETURNING\s+id\b', '', q, flags=re.IGNORECASE)

        self._cursor.execute(q, params)
        self.lastrowid = self._cursor.lastrowid
        return self

    def fetchone(self):
        try:
            return self._cursor.fetchone()
        except Exception:
            return None

    def fetchall(self):
        try:
            return self._cursor.fetchall()
        except Exception:
            return []

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    @property
    def rowcount(self):
        return self._cursor.rowcount


class SqliteConnection:
    def __init__(self, db_path=None):
        if not db_path:
            db_path = get_sqlite_path()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._cursors = []

    @property
    def row_factory(self):
        return self.conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.conn.row_factory = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for c in self._cursors:
            try:
                c.close()
            except Exception:
                pass
        self._cursors.clear()

        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
        finally:
            try:
                self.conn.close()
            except Exception:
                pass

    def execute(self, query, params=()):
        c = self.conn.cursor()
        self._cursors.append(c)
        cur = SqliteCursor(c)
        return cur.execute(query, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def connect(*args, **kwargs):
    db_url = (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "").strip()
    
    if db_url and HAS_PSYCOPG2:
        try:
            cleaned_url = db_url
            if cleaned_url.startswith("postgres://"):
                cleaned_url = cleaned_url.replace("postgres://", "postgresql://", 1)
            if "localhost" not in cleaned_url and "127.0.0.1" not in cleaned_url and "sslmode=" not in cleaned_url:
                separator = "&" if "?" in cleaned_url else "?"
                cleaned_url += f"{separator}sslmode=require"
            return PgConnection(cleaned_url)
        except Exception as e:
            print(f"[Database Warning] PostgreSQL connection failed ({e}). Falling back to SQLite.", flush=True)
            return SqliteConnection()
            
    # Default fallback: SQLite
    return SqliteConnection()

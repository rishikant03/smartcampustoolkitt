import os
import psycopg2
from psycopg2.extras import DictCursor

# Map exceptions for compatibility with existing sqlite3 exception handling
IntegrityError = psycopg2.IntegrityError
Error = psycopg2.Error
OperationalError = psycopg2.OperationalError

class PgCursor:
    def __init__(self, pg_cursor):
        self._cursor = pg_cursor
        self.lastrowid = None

    def execute(self, query, params=()):
        # Replace SQLite ? with Postgres %s (naive replace)
        q = query
        if '?' in q and '%s' not in q:
            # Avoid replacing ? inside strings by just doing basic replace for now, 
            # since most of our queries use ? as standalone parameters.
            q = q.replace('?', '%s')
            
        # SQLite's INSERT OR IGNORE -> Postgres ON CONFLICT DO NOTHING
        if "INSERT OR IGNORE INTO user_profiles (user_id)" in q:
            q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            q += " ON CONFLICT (user_id) DO NOTHING"
        elif "INSERT OR IGNORE INTO user_profiles (user_id, full_name)" in q:
            q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            q += " ON CONFLICT (user_id) DO NOTHING"

        # Check if it has RETURNING id for lastrowid
        is_returning = "RETURNING id" in q.upper()

        self._cursor.execute(q, params)
        
        if is_returning:
            row = self._cursor.fetchone()
            if row:
                self.lastrowid = row['id']
                
        return self

    def fetchone(self):
        try:
            return self._cursor.fetchone()
        except psycopg2.ProgrammingError:
            return None

    def fetchall(self):
        try:
            return self._cursor.fetchall()
        except psycopg2.ProgrammingError:
            return []
            
    @property
    def rowcount(self):
        return self._cursor.rowcount

class PgConnection:
    def __init__(self, db_url):
        self.conn = psycopg2.connect(db_url)
        # We don't need row_factory since DictCursor already behaves like a dict
        self.row_factory = None

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

def connect(*args, **kwargs):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL environment variable is required")
    return PgConnection(db_url)

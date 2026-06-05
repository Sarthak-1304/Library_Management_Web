"""
database.py
═══════════
Single source of truth for all SQLite operations.
Schema creation, seeding, and query helpers live here.
"""

import hashlib
import datetime
import sqlite3
import os

from config import DATABASE, DEFAULT_ISSUE_DAYS, FINE_PER_DAY


# ── tiny helpers ─────────────────────────────────────────────
def _hash(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def today() -> datetime.date:
    return datetime.date.today()


def due_date(days: int = DEFAULT_ISSUE_DAYS) -> datetime.date:
    return today() + datetime.timedelta(days=days)


def calc_fine(due) -> float:
    if isinstance(due, str):
        due = datetime.date.fromisoformat(str(due))
    overdue = (today() - due).days
    return round(max(overdue, 0) * FINE_PER_DAY, 2)


# ── Database class ───────────────────────────────────────────
class Database:
    """Thin wrapper around sqlite3."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DATABASE
        self.conn = None
        self._connect()
        self._init_schema()

    # ── connection ──────────────────────────────────────────
    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # dict-like rows
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def _cursor(self):
        return self.conn.cursor()

    # ── generic helpers ─────────────────────────────────────
    def execute(self, sql, params=None, many=False):
        cur = self._cursor()
        if many:
            cur.executemany(sql, params or [])
        else:
            cur.execute(sql, params or ())
        self.conn.commit()
        return cur

    def fetchall(self, sql, params=None) -> list:
        cur = self._cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        # Convert sqlite3.Row to dict for template access
        return [dict(r) for r in rows]

    def fetchone(self, sql, params=None):
        cur = self._cursor()
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return dict(row) if row else None

    def close(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    # ── audit logging ───────────────────────────────────────
    def log(self, actor: str, action: str, details: str):
        self.execute(
            "INSERT INTO audit_log (actor, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (actor, action, details, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    # ── schema ──────────────────────────────────────────────
    def _init_schema(self):
        statements = [
            """CREATE TABLE IF NOT EXISTS admins (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL,
                password   TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now'))
            )""",

            """CREATE TABLE IF NOT EXISTS students (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT    UNIQUE NOT NULL,
                name       TEXT    NOT NULL,
                password   TEXT    NOT NULL DEFAULT '',
                email      TEXT,
                phone      TEXT,
                created_at TEXT    DEFAULT (datetime('now'))
            )""",

            """CREATE TABLE IF NOT EXISTS books (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn         TEXT    UNIQUE NOT NULL,
                title        TEXT    NOT NULL,
                author       TEXT    NOT NULL,
                category     TEXT,
                total_copies INTEGER DEFAULT 1,
                available    INTEGER DEFAULT 1,
                added_at     TEXT    DEFAULT (datetime('now'))
            )""",

            """CREATE TABLE IF NOT EXISTS issued_books (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT    NOT NULL,
                book_isbn   TEXT    NOT NULL,
                issued_at   TEXT    DEFAULT (datetime('now')),
                due_date    TEXT    NOT NULL,
                returned_at TEXT,
                fine        REAL    DEFAULT 0.00,
                status      TEXT    DEFAULT 'issued' CHECK(status IN ('issued','returned')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (book_isbn)  REFERENCES books(isbn)
            )""",

            """CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                actor     TEXT,
                action    TEXT,
                details   TEXT,
                timestamp TEXT    DEFAULT (datetime('now'))
            )""",
        ]
        for stmt in statements:
            self.execute(stmt)
        self._seed()

    # ── seed data ───────────────────────────────────────────
    def _seed(self):
        # Default admin (password: admin123)
        if not self.fetchone("SELECT id FROM admins WHERE username='admin'"):
            self.execute(
                "INSERT INTO admins (username, password) VALUES (?, ?)",
                ("admin", _hash("admin123"))
            )

        # Default demo student (password: student123)
        if not self.fetchone("SELECT id FROM students WHERE student_id='STU2024001'"):
            self.execute(
                "INSERT INTO students (student_id, name, password, email, phone) VALUES (?, ?, ?, ?, ?)",
                ("STU2024001", "Demo Student", _hash("student123"), "demo@student.edu", "+91 9876543210")
            )

        # 20 sample books across diverse categories
        if not self.fetchone("SELECT id FROM books LIMIT 1"):
            books = [
                ("978-0-13-235088-4", "The Pragmatic Programmer",       "David Thomas & Andrew Hunt",   "Programming",       20, 20),
                ("978-0-13-468599-1", "Clean Code",                     "Robert C. Martin",             "Programming",       15, 15),
                ("978-0-13-110362-7", "The C Programming Language",     "Kernighan & Ritchie",          "Programming",       12, 12),
                ("978-0-596-51774-8", "Python Cookbook",                 "David Beazley",                "Python",            18, 18),
                ("978-1-49-195016-0", "Fluent Python",                  "Luciano Ramalho",              "Python",            14, 14),
                ("978-0-13-468599-9", "Introduction to Python",         "Bill Lubanovic",               "Python",            20, 20),
                ("978-0-201-63361-0", "Design Patterns",                "Gang of Four",                 "Architecture",      10, 10),
                ("978-0-07-352188-0", "Data Structures & Algorithms",   "Mark Allen Weiss",             "CS Theory",         20, 20),
                ("978-0-26-253428-3", "Introduction to Algorithms",     "Cormen, Leiserson et al.",     "CS Theory",         16, 16),
                ("978-0-13-235088-2", "Discrete Mathematics",           "Kenneth Rosen",                "Mathematics",       18, 18),
                ("978-0-13-235088-0", "Operating System Concepts",      "Silberschatz & Galvin",        "Operating Systems", 25, 25),
                ("978-0-13-597444-5", "Computer Networks",              "Andrew Tanenbaum",             "Networks",          22, 22),
                ("978-0-13-468599-3", "Computer Organization",          "Patterson & Hennessy",         "Systems",           15, 15),
                ("978-0-13-468599-5", "Database System Concepts",       "Silberschatz et al.",          "Databases",         20, 20),
                ("978-1-49-194516-6", "Learning SQL",                   "Alan Beaulieu",                "Databases",         16, 16),
                ("978-1-49-195016-2", "JavaScript: The Good Parts",     "Douglas Crockford",            "Web Dev",           14, 14),
                ("978-1-49-195016-4", "You Don't Know JS",              "Kyle Simpson",                 "Web Dev",           12, 12),
                ("978-1-49-195016-6", "Hands-On Machine Learning",      "Aurélien Géron",               "AI/ML",             15, 15),
                ("978-1-49-195016-8", "Deep Learning",                  "Goodfellow, Bengio & Courville","AI/ML",            10, 10),
                ("978-0-13-468599-7", "The Mythical Man-Month",         "Frederick P. Brooks Jr.",      "Software Engg",     10, 10),
            ]
            self.execute(
                "INSERT INTO books (isbn, title, author, category, total_copies, available) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                books, many=True
            )

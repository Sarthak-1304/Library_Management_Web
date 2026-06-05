"""
app.py
══════
Flask web application — routes, authentication, API endpoints.
Replaces the desktop CustomTkinter interface.
"""

import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)

from config import SECRET_KEY, FINE_PER_DAY, DEFAULT_ISSUE_DAYS
from database import Database, _hash, today, due_date, calc_fine

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = datetime.timedelta(hours=8)

# ── Database singleton ───────────────────────────────────────
db = Database()


# ── Auth decorators ──────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session or session.get("role") != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session or session.get("role") != "student":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Context processor ────────────────────────────────────────
@app.context_processor
def inject_globals():
    return {
        "today": today(),
        "role": session.get("role"),
        "user": session.get("user"),
        "FINE_PER_DAY": FINE_PER_DAY,
    }


# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "user" in session:
        if session["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "admin").lower()
        uid = request.form.get("username", "").strip()
        pw = request.form.get("password", "").strip()

        if not uid:
            return render_template("login.html", error="Please enter your ID or username.", role=role)
        if not pw:
            return render_template("login.html", error="Please enter your password.", role=role)

        if role == "admin":
            row = db.fetchone(
                "SELECT id FROM admins WHERE username=? AND password=?",
                (uid, _hash(pw))
            )
            if row:
                session.permanent = True
                session["user"] = uid
                session["role"] = "admin"
                return redirect(url_for("admin_dashboard"))
            return render_template("login.html", error="Incorrect username or password.", role=role)
        else:
            row = db.fetchone(
                "SELECT id FROM students WHERE student_id=? AND password=?",
                (uid, _hash(pw))
            )
            if row:
                session.permanent = True
                session["user"] = uid
                session["role"] = "student"
                return redirect(url_for("student_dashboard"))
            return render_template("login.html",
                                   error="Invalid Student ID or password. Ask an admin to register you first.",
                                   role=role)

    return render_template("login.html", error=None, role="admin")


@app.route("/demo-login/<role>")
def demo_login(role):
    """Quick demo login for recruiters."""
    if role == "admin":
        session.permanent = True
        session["user"] = "admin"
        session["role"] = "admin"
        return redirect(url_for("admin_dashboard"))
    elif role == "student":
        session.permanent = True
        session["user"] = "STU2024001"
        session["role"] = "student"
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    total = db.fetchone("SELECT SUM(total_copies) AS n FROM books")["n"] or 0
    avail = db.fetchone("SELECT SUM(available) AS n FROM books")["n"] or 0
    stus = db.fetchone("SELECT COUNT(*) AS n FROM students")["n"] or 0
    issued = db.fetchone("SELECT COUNT(*) AS n FROM issued_books WHERE status='issued'")["n"] or 0
    overdue = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books WHERE status='issued' AND due_date < ?",
        (str(today()),)
    )["n"] or 0

    logs = db.fetchall(
        "SELECT actor, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 7"
    )

    return render_template("admin/dashboard.html",
                           total=total, avail=avail, stus=stus,
                           issued=issued, overdue=overdue, logs=logs,
                           active="dashboard")


@app.route("/admin/books")
@admin_required
def admin_books():
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    rows = db.fetchall(
        "SELECT isbn, title, author, category, total_copies, available "
        "FROM books WHERE title LIKE ? OR author LIKE ? OR category LIKE ? ORDER BY title",
        (like, like, like)
    )
    return render_template("admin/books.html", books=rows, query=q, active="books")


@app.route("/admin/books/add", methods=["POST"])
@admin_required
def admin_add_book():
    isbn = request.form.get("isbn", "").strip()
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    category = request.form.get("category", "").strip()
    copies = request.form.get("copies", "").strip()

    if not all([isbn, title, author, category, copies]):
        flash("All fields are required.", "error")
        return redirect(url_for("admin_books"))

    try:
        copies = int(copies)
        assert copies > 0
    except (ValueError, AssertionError):
        flash("Copies must be a positive integer.", "error")
        return redirect(url_for("admin_books"))

    try:
        db.execute(
            "INSERT INTO books (isbn, title, author, category, total_copies, available) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (isbn, title, author, category, copies, copies)
        )
        db.log(session["user"], "ADD_BOOK", f"{title} (ISBN {isbn})")
        flash(f"'{title}' added successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")

    return redirect(url_for("admin_books"))


@app.route("/admin/students")
@admin_required
def admin_students():
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    rows = db.fetchall(
        "SELECT student_id, name, email, phone, created_at FROM students "
        "WHERE student_id LIKE ? OR name LIKE ? ORDER BY name",
        (like, like)
    )
    return render_template("admin/students.html", students=rows, query=q, active="students")


@app.route("/admin/students/register", methods=["POST"])
@admin_required
def admin_register_student():
    sid = request.form.get("student_id", "").strip()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip() or None
    phone = request.form.get("phone", "").strip() or None

    if not sid or not name:
        flash("Student ID and Full Name are required.", "error")
        return redirect(url_for("admin_students"))
    if not password:
        flash("Password is required.", "error")
        return redirect(url_for("admin_students"))

    try:
        db.execute(
            "INSERT INTO students (student_id, name, password, email, phone) VALUES (?, ?, ?, ?, ?)",
            (sid, name, _hash(password), email, phone)
        )
        db.log(session["user"], "REGISTER", f"{name} ({sid})")
        flash(f"Student '{name}' registered successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")

    return redirect(url_for("admin_students"))


@app.route("/admin/issue", methods=["GET", "POST"])
@admin_required
def admin_issue():
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        isbn = request.form.get("book_isbn", "").strip()
        days = request.form.get("days", str(DEFAULT_ISSUE_DAYS)).strip()

        try:
            days = int(days)
            assert days > 0
        except (ValueError, AssertionError):
            flash("Loan period must be a positive number.", "error")
            return redirect(url_for("admin_issue"))

        if not sid or not isbn:
            flash("Please select both a student and a book.", "error")
            return redirect(url_for("admin_issue"))

        # Check availability
        bk = db.fetchone("SELECT title, available FROM books WHERE isbn=?", (isbn,))
        if not bk or bk["available"] <= 0:
            flash("This book has no available copies right now.", "error")
            return redirect(url_for("admin_issue"))

        # Check already issued
        already = db.fetchone(
            "SELECT id FROM issued_books WHERE student_id=? AND book_isbn=? AND status='issued'",
            (sid, isbn)
        )
        if already:
            flash("This student already has this book issued.", "error")
            return redirect(url_for("admin_issue"))

        due = str(today() + datetime.timedelta(days=days))
        db.execute(
            "INSERT INTO issued_books (student_id, book_isbn, due_date) VALUES (?, ?, ?)",
            (sid, isbn, due)
        )
        db.execute("UPDATE books SET available = available - 1 WHERE isbn=?", (isbn,))

        stu = db.fetchone("SELECT name FROM students WHERE student_id=?", (sid,))
        db.log(session["user"], "ISSUE", f"'{bk['title']}' → {stu['name']} (due {due})")
        flash(f"'{bk['title']}' issued to {stu['name']}. Due: {due}", "success")
        return redirect(url_for("admin_issue"))

    students = db.fetchall("SELECT student_id, name FROM students ORDER BY name")
    books = db.fetchall(
        "SELECT isbn, title, author, available FROM books ORDER BY title"
    )
    return render_template("admin/issue.html",
                           students=students, books=books,
                           default_days=DEFAULT_ISSUE_DAYS,
                           active="issue")


@app.route("/admin/return", methods=["GET", "POST"])
@admin_required
def admin_return():
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        isbn = request.form.get("book_isbn", "").strip()

        if not sid or not isbn:
            flash("Please select a student and a book.", "error")
            return redirect(url_for("admin_return"))

        rec = db.fetchone(
            "SELECT id, due_date FROM issued_books "
            "WHERE student_id=? AND book_isbn=? AND status='issued'",
            (sid, isbn)
        )
        if not rec:
            flash("No active issue record found.", "error")
            return redirect(url_for("admin_return"))

        fine = calc_fine(rec["due_date"])
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE issued_books SET returned_at=?, fine=?, status='returned' WHERE id=?",
            (now, fine, rec["id"])
        )
        db.execute("UPDATE books SET available = available + 1 WHERE isbn=?", (isbn,))
        bk = db.fetchone("SELECT title FROM books WHERE isbn=?", (isbn,))
        db.log(session["user"], "RETURN", f"'{bk['title']}' by {sid} | fine=₹{fine}")

        if fine > 0:
            flash(f"'{bk['title']}' returned. Fine charged: ₹{fine:.2f}", "warning")
        else:
            flash(f"'{bk['title']}' returned on time — no fine!", "success")
        return redirect(url_for("admin_return"))

    students = db.fetchall("SELECT student_id, name FROM students ORDER BY name")
    return render_template("admin/return.html", students=students, active="return")


@app.route("/admin/issued-list")
@admin_required
def admin_issued_list():
    rows = db.fetchall(
        """SELECT ib.id, s.name, s.student_id, b.title, b.isbn,
                  ib.issued_at, ib.due_date,
                  CAST(julianday(?) - julianday(ib.due_date) AS INTEGER) AS overdue_days
           FROM issued_books ib
           JOIN students s ON s.student_id = ib.student_id
           JOIN books b    ON b.isbn        = ib.book_isbn
           WHERE ib.status = 'issued'
           ORDER BY ib.due_date""",
        (str(today()),)
    )
    return render_template("admin/issued_list.html", records=rows, active="issued_list")


@app.route("/admin/fines")
@admin_required
def admin_fines():
    rows = db.fetchall(
        """SELECT s.name, s.student_id, b.title,
                  ib.due_date, ib.returned_at, ib.fine, ib.status
           FROM issued_books ib
           JOIN students s ON s.student_id = ib.student_id
           JOIN books b    ON b.isbn        = ib.book_isbn
           WHERE ib.fine > 0
              OR (ib.status='issued' AND ib.due_date < ?)
           ORDER BY ib.due_date""",
        (str(today()),)
    )
    # Calculate live fines for still-issued books
    for r in rows:
        if r["status"] == "issued":
            r["live_fine"] = calc_fine(r["due_date"])
        else:
            r["live_fine"] = float(r["fine"]) if r["fine"] else 0
    return render_template("admin/fines.html", records=rows, active="fines")


@app.route("/admin/audit-log")
@admin_required
def admin_audit_log():
    rows = db.fetchall(
        "SELECT actor, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 300"
    )
    return render_template("admin/audit_log.html", logs=rows, active="audit_log")


# ══════════════════════════════════════════════════════════════
#  STUDENT ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    actor = session["user"]
    stu = db.fetchone("SELECT name FROM students WHERE student_id=?", (actor,))
    name = stu["name"] if stu else actor

    issued = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books WHERE student_id=? AND status='issued'",
        (actor,)
    )["n"] or 0

    overdue = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books "
        "WHERE student_id=? AND status='issued' AND due_date < ?",
        (actor, str(today()))
    )["n"] or 0

    avail = db.fetchone("SELECT SUM(available) AS n FROM books")["n"] or 0

    current_books = db.fetchall(
        """SELECT b.title, ib.due_date,
                  CAST(julianday(?) - julianday(ib.due_date) AS INTEGER) AS overdue_days
           FROM issued_books ib
           JOIN books b ON b.isbn = ib.book_isbn
           WHERE ib.student_id=? AND ib.status='issued'
           ORDER BY ib.due_date""",
        (str(today()), actor)
    )

    return render_template("student/dashboard.html",
                           name=name, issued=issued, overdue=overdue,
                           avail=avail, current_books=current_books,
                           active="dashboard")


@app.route("/student/issue", methods=["GET", "POST"])
@student_required
def student_issue():
    actor = session["user"]

    if request.method == "POST":
        isbn = request.form.get("book_isbn", "").strip()

        if not isbn:
            flash("Please select a book first.", "error")
            return redirect(url_for("student_issue"))

        # Check availability
        bk = db.fetchone("SELECT title, available FROM books WHERE isbn=?", (isbn,))
        if not bk or bk["available"] <= 0:
            flash("That book is currently out of stock.", "error")
            return redirect(url_for("student_issue"))

        # Check already issued
        already = db.fetchone(
            "SELECT id FROM issued_books WHERE student_id=? AND book_isbn=? AND status='issued'",
            (actor, isbn)
        )
        if already:
            flash("You already have this book issued.", "error")
            return redirect(url_for("student_issue"))

        due = str(today() + datetime.timedelta(days=DEFAULT_ISSUE_DAYS))
        db.execute(
            "INSERT INTO issued_books (student_id, book_isbn, due_date) VALUES (?, ?, ?)",
            (actor, isbn, due)
        )
        db.execute("UPDATE books SET available = available - 1 WHERE isbn=?", (isbn,))

        stu = db.fetchone("SELECT name FROM students WHERE student_id=?", (actor,))
        db.log(actor, "ISSUE", f"'{bk['title']}' issued to {stu['name']} (due {due})")
        flash(f"'{bk['title']}' has been issued to you. Due date: {due}", "success")
        return redirect(url_for("student_issue"))

    # GET — show book catalogue
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    books = db.fetchall(
        "SELECT isbn, title, author, category, total_copies, available FROM books "
        "WHERE title LIKE ? OR author LIKE ? OR category LIKE ? ORDER BY title",
        (like, like, like)
    )
    return render_template("student/issue.html", books=books, query=q, active="issue")


@app.route("/student/my-books")
@student_required
def student_my_books():
    actor = session["user"]
    rows = db.fetchall(
        """SELECT b.title, b.author, b.category, ib.issued_at, ib.due_date,
                  CAST(julianday(?) - julianday(ib.due_date) AS INTEGER) AS overdue_days
           FROM issued_books ib
           JOIN books b ON b.isbn = ib.book_isbn
           WHERE ib.student_id=? AND ib.status='issued'
           ORDER BY ib.due_date""",
        (str(today()), actor)
    )
    for r in rows:
        od = r["overdue_days"] or 0
        r["fine"] = od * FINE_PER_DAY if od > 0 else 0
        r["status_text"] = f"Overdue {od}d (₹{r['fine']:.0f} fine)" if od > 0 else "On time"
    return render_template("student/my_books.html", books=rows, active="my_books")


# ══════════════════════════════════════════════════════════════
#  API ENDPOINTS (for AJAX)
# ══════════════════════════════════════════════════════════════

@app.route("/api/student-books/<sid>")
@admin_required
def api_student_books(sid):
    """Return books currently issued to a student (for Return tab dropdown)."""
    rows = db.fetchall(
        """SELECT b.isbn, b.title, ib.due_date
           FROM issued_books ib
           JOIN books b ON b.isbn = ib.book_isbn
           WHERE ib.student_id=? AND ib.status='issued'
           ORDER BY b.title""",
        (sid,)
    )
    return jsonify(rows)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)

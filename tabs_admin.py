"""
tabs_admin.py
═════════════
All admin tab UI builders (Dashboard, Books, Students,
Issue, Return, Issued-List, Fines, Audit Log).
Each function receives:
    parent  – the CTkFrame to populate
    db      – Database instance
    actor   – logged-in admin's username
    refresh – callable to re-draw a tab by key (provided by LibraryApp)
"""

import datetime
from tkinter import messagebox

import customtkinter as ctk

from database import Database, today, due_date, calc_fine
from config import DEFAULT_ISSUE_DAYS, FINE_PER_DAY
from ui_helpers import (
    COLORS, FONTS,
    card, label, entry_widget, btn, divider, stat_card,
    build_table, SearchableDropdown,
)


# ══════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════
def build_dashboard(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    label(parent, "Dashboard Overview", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, f"Welcome back, {actor}  •  {today().strftime('%A, %d %B %Y')}",
          "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=14)

    # ── stat cards ──
    sf = ctk.CTkFrame(parent, fg_color="transparent")
    sf.pack(fill="x", padx=24)
    for i in range(4):
        sf.columnconfigure(i, weight=1)

    total   = db.fetchone("SELECT SUM(total_copies) AS n FROM books")["n"] or 0
    avail   = db.fetchone("SELECT SUM(available) AS n FROM books")["n"] or 0
    stus    = db.fetchone("SELECT COUNT(*) AS n FROM students")["n"] or 0
    issued  = db.fetchone("SELECT COUNT(*) AS n FROM issued_books WHERE status='issued'")["n"] or 0
    overdue = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books WHERE status='issued' AND due_date < %s",
        (today(),))["n"] or 0

    stat_card(sf, "Total Copies",    total,   col=0, color="accent")
    stat_card(sf, "Available",       avail,   col=1, color="success")
    stat_card(sf, "Students",        stus,    col=2, color="accent2")
    stat_card(sf, "Currently Issued",issued,  col=3, color="warning")

    # ── overdue banner ──
    if overdue:
        af = ctk.CTkFrame(parent, fg_color="#1f151d",  # danger at ~12% on dark bg
                           corner_radius=10, border_width=1,
                           border_color=COLORS["danger"])
        af.pack(fill="x", padx=32, pady=10)
        ctk.CTkLabel(
            af,
            text=f"⚠   {overdue} book(s) are overdue — check the Issued List tab.",
            text_color=COLORS["danger"], font=FONTS["body"]
        ).pack(pady=10, padx=16)

    # ── recent activity ──
    label(parent, "Recent Activity", "sub").pack(anchor="w", padx=32, pady=(18, 6))
    logs = db.fetchall(
        "SELECT actor, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 7"
    )
    lf = card(parent)
    lf.pack(fill="x", padx=32, pady=2)
    if not logs:
        label(lf, "No activity yet.", color="muted").pack(pady=20)
    for lg in logs:
        row = ctk.CTkFrame(lf, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(row, text=f"[{lg['action']}]", font=FONTS["mono"],
                     text_color=COLORS["accent"], width=110, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=str(lg["details"])[:65], font=FONTS["small"],
                     text_color=COLORS["text"]).pack(side="left", padx=8)
        ctk.CTkLabel(row, text=str(lg["timestamp"])[:16], font=FONTS["small"],
                     text_color=COLORS["muted"]).pack(side="right")


# ══════════════════════════════════════════════
#  BOOKS
# ══════════════════════════════════════════════
def build_books(parent: ctk.CTkFrame, db: Database, actor: str, refresh, **_):
    label(parent, "Book Catalogue", "heading").pack(anchor="w", padx=32, pady=(28, 2))

    # toolbar
    tb = ctk.CTkFrame(parent, fg_color="transparent")
    tb.pack(fill="x", padx=32, pady=10)

    search_var = ctk.StringVar()
    se = ctk.CTkEntry(
        tb, textvariable=search_var,
        placeholder_text="🔍  Search by title, author or category…",
        width=340, height=38, corner_radius=8,
        fg_color=COLORS["input"], border_color=COLORS["border"],
        text_color=COLORS["text"], font=FONTS["body"],
    )
    se.pack(side="left")

    table_frame = ctk.CTkFrame(parent, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=32, pady=4)

    def _refresh_table(*_):
        for w in table_frame.winfo_children():
            w.destroy()
        q = search_var.get().strip()
        like = f"%{q}%"
        rows = db.fetchall(
            "SELECT isbn, title, author, category, total_copies, available "
            "FROM books WHERE title LIKE %s OR author LIKE %s OR category LIKE %s ORDER BY title",
            (like, like, like)
        )
        data = [(r["isbn"], r["title"], r["author"], r["category"],
                 r["total_copies"], r["available"]) for r in rows]
        build_table(table_frame,
                    ["ISBN", "Title", "Author", "Category", "Total", "Available"],
                    data, [140, 240, 170, 110, 60, 80])

    se.bind("<KeyRelease>", _refresh_table)
    _refresh_table()

    btn(tb, "+ Add Book", lambda: _add_book_dialog(parent, db, actor, lambda: _refresh_table()),
        width=130).pack(side="right")


def _add_book_dialog(parent, db, actor, on_done):
    d = ctk.CTkToplevel(parent)
    d.title("Add New Book")
    d.geometry("440x560")
    d.configure(fg_color=COLORS["bg"])
    d.grab_set()

    label(d, "Add New Book", "heading").pack(pady=(24, 14))

    fields = [
        ("ISBN",     "e.g. 978-0-13-…"),
        ("Title",    "Book title"),
        ("Author",   "Author name(s)"),
        ("Category", "e.g. Python, Networks…"),
        ("Copies",   "Number of copies"),
    ]
    entries = {}
    for lbl, ph in fields:
        ctk.CTkLabel(d, text=lbl, font=FONTS["small"],
                     text_color=COLORS["muted"]).pack(anchor="w", padx=28)
        e = entry_widget(d, ph, width=384)
        e.pack(padx=28, pady=(3, 10))
        entries[lbl] = e

    err = ctk.CTkLabel(d, text="", text_color=COLORS["danger"], font=FONTS["small"])
    err.pack()

    def _save():
        vals = {k: v.get().strip() for k, v in entries.items()}
        if not all(vals.values()):
            err.configure(text="All fields are required.")
            return
        try:
            copies = int(vals["Copies"])
            assert copies > 0
        except (ValueError, AssertionError):
            err.configure(text="Copies must be a positive integer.")
            return
        try:
            db.execute(
                "INSERT INTO books (isbn,title,author,category,total_copies,available) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (vals["ISBN"], vals["Title"], vals["Author"], vals["Category"], copies, copies)
            )
            db.log(actor, "ADD_BOOK", f"{vals['Title']} (ISBN {vals['ISBN']})")
            messagebox.showinfo("Success", f"'{vals['Title']}' added.", parent=d)
            d.destroy()
            on_done()
        except Exception as exc:
            err.configure(text=f"Error: {exc}")

    btn(d, "Add Book", _save, width=384).pack(padx=28, pady=8)


# ══════════════════════════════════════════════
#  STUDENTS
# ══════════════════════════════════════════════
def build_students(parent: ctk.CTkFrame, db: Database, actor: str, refresh, **_):
    label(parent, "Student Registry", "heading").pack(anchor="w", padx=32, pady=(28, 2))

    tb = ctk.CTkFrame(parent, fg_color="transparent")
    tb.pack(fill="x", padx=32, pady=10)

    search_var = ctk.StringVar()
    se = ctk.CTkEntry(
        tb, textvariable=search_var,
        placeholder_text="🔍  Search by name or student ID…",
        width=340, height=38, corner_radius=8,
        fg_color=COLORS["input"], border_color=COLORS["border"],
        text_color=COLORS["text"], font=FONTS["body"],
    )
    se.pack(side="left")

    table_frame = ctk.CTkFrame(parent, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=32, pady=4)

    def _refresh(*_):
        for w in table_frame.winfo_children():
            w.destroy()
        q = search_var.get().strip()
        like = f"%{q}%"
        rows = db.fetchall(
            "SELECT student_id, name, email, phone, created_at FROM students "
            "WHERE student_id LIKE %s OR name LIKE %s ORDER BY name",
            (like, like)
        )
        data = [(r["student_id"], r["name"], r["email"] or "—",
                 r["phone"] or "—", str(r["created_at"])[:10]) for r in rows]
        build_table(table_frame,
                    ["Student ID", "Name", "Email", "Phone", "Registered On"],
                    data, [110, 170, 190, 110, 110])

    se.bind("<KeyRelease>", _refresh)
    _refresh()

    btn(tb, "+ Register Student",
        lambda: _register_student_dialog(parent, db, actor, _refresh),
        width=160).pack(side="right")


def _register_student_dialog(parent, db, actor, on_done):
    d = ctk.CTkToplevel(parent)
    d.title("Register Student")
    d.geometry("440x560")
    d.configure(fg_color=COLORS["bg"])
    d.grab_set()

    label(d, "Register New Student", "heading").pack(pady=(24, 14))

    fields = [
        ("Student ID", "e.g. STU2024001", ""),
        ("Full Name",  "Full name",        ""),
        ("Password",   "Set a password",   "•"),
        ("Email",      "student@email.com  (optional)", ""),
        ("Phone",      "+91 …  (optional)", ""),
    ]
    entries = {}
    for lbl, ph, show in fields:
        ctk.CTkLabel(d, text=lbl, font=FONTS["small"],
                     text_color=COLORS["muted"]).pack(anchor="w", padx=28)
        e = entry_widget(d, ph, show=show, width=384)
        e.pack(padx=28, pady=(3, 10))
        entries[lbl] = e

    err = ctk.CTkLabel(d, text="", text_color=COLORS["danger"], font=FONTS["small"])
    err.pack()

    def _save():
        vals = {k: v.get().strip() for k, v in entries.items()}
        if not vals["Student ID"] or not vals["Full Name"]:
            err.configure(text="Student ID and Full Name are required.")
            return
        if not vals["Password"]:
            err.configure(text="Password is required.")
            return
        try:
            from database import _hash
            db.execute(
                "INSERT INTO students (student_id,name,password,email,phone) VALUES (%s,%s,%s,%s,%s)",
                (vals["Student ID"], vals["Full Name"], _hash(vals["Password"]),
                 vals["Email"] or None, vals["Phone"] or None)
            )
            db.log(actor, "REGISTER", f"{vals['Full Name']} ({vals['Student ID']})")
            messagebox.showinfo("Registered", "Student registered successfully!", parent=d)
            d.destroy()
            on_done()
        except Exception as exc:
            err.configure(text=f"Error: {exc}")

    btn(d, "Register", _save, width=384).pack(padx=28, pady=8)


# ══════════════════════════════════════════════
#  ISSUE BOOK
# ══════════════════════════════════════════════
def build_issue(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    label(parent, "Issue a Book", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, "Search and select the student and book — no ISBN memorisation needed.",
          "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=14)

    f = card(parent)
    f.pack(padx=32, pady=4, fill="x")

    # ── Student picker ──────────────────────────────────────
    label(f, "Student", "small", color="muted").pack(anchor="w", padx=24, pady=(16, 4))

    stu_items = _load_student_items(db)
    stu_dd = SearchableDropdown(
        f, stu_items,
        placeholder="Click to browse all students, or type to filter…",
        on_select=None,
        width=460,
    )
    stu_dd.pack(padx=24, pady=(0, 14))

    label(f, "Book  (click to browse all, or type to filter)", "small", color="muted").pack(
        anchor="w", padx=24, pady=(0, 4))

    book_items = _load_book_items(db)
    book_dd = SearchableDropdown(
        f, book_items,
        placeholder="Click here to browse all books…",
        on_select=None,
        width=460,
    )
    book_dd.pack(padx=24, pady=(0, 14))

    # ── Loan period ─────────────────────────────────────────
    label(f, f"Loan Period (days, default = {DEFAULT_ISSUE_DAYS})",
          "small", color="muted").pack(anchor="w", padx=24, pady=(0, 4))
    days_ent = entry_widget(f, str(DEFAULT_ISSUE_DAYS), width=460)
    days_ent.pack(padx=24, pady=(0, 14))

    err_lbl = ctk.CTkLabel(f, text="", text_color=COLORS["danger"], font=FONTS["small"])
    err_lbl.pack(pady=2)

    def _issue():
        sid   = stu_dd.get_value()
        isbn  = book_dd.get_value()
        s_txt = stu_dd.get_text().strip()
        b_txt = book_dd.get_text().strip()

        if not s_txt:
            err_lbl.configure(text="Please select a student.")
            return
        if not b_txt:
            err_lbl.configure(text="Please select a book.")
            return
        if sid is None:
            err_lbl.configure(text="No matching student found — check spelling.")
            return
        if isbn is None:
            err_lbl.configure(text="That book is currently out of stock — cannot issue.")
            return

        try:
            days = int(days_ent.get().strip() or DEFAULT_ISSUE_DAYS)
            assert days > 0
        except (ValueError, AssertionError):
            err_lbl.configure(text="Loan period must be a positive number.")
            return

        # availability check
        bk = db.fetchone("SELECT title, available FROM books WHERE isbn=%s", (isbn,))
        if not bk or bk["available"] <= 0:
            err_lbl.configure(text="This book has no available copies right now.")
            return

        # already issued check
        already = db.fetchone(
            "SELECT id FROM issued_books WHERE student_id=%s AND book_isbn=%s AND status='issued'",
            (sid, isbn)
        )
        if already:
            err_lbl.configure(text="This student already has this book issued.")
            return

        due = today() + datetime.timedelta(days=days)
        db.execute(
            "INSERT INTO issued_books (student_id, book_isbn, due_date) VALUES (%s,%s,%s)",
            (sid, isbn, due)
        )
        db.execute("UPDATE books SET available = available - 1 WHERE isbn=%s", (isbn,))

        stu = db.fetchone("SELECT name FROM students WHERE student_id=%s", (sid,))
        db.log(actor, "ISSUE", f"'{bk['title']}' → {stu['name']} (due {due})")
        err_lbl.configure(text="")
        stu_dd.clear()
        book_dd.clear()
        days_ent.delete(0, "end")
        days_ent.insert(0, str(DEFAULT_ISSUE_DAYS))
        messagebox.showinfo(
            "Book Issued ✔",
            f"'{bk['title']}' issued to {stu['name']}.\n\nDue date:  {due}"
        )

    btn(f, "✔  Issue Book", _issue, width=460, height=42).pack(padx=24, pady=(4, 20))


def _load_student_items(db) -> list:
    rows = db.fetchall("SELECT student_id, name FROM students ORDER BY name")
    return [(f"{r['name']}  ({r['student_id']})", r["student_id"]) for r in rows]


def _load_book_items(db) -> list:
    """
    Returns (label, isbn, badge_text, badge_color) tuples for the dropdown.
    Badge colour:  green  >= 5 copies
                   orange  1-4 copies
                   red     0 copies  (value=None blocks issuing)
    """
    rows = db.fetchall(
        "SELECT isbn, title, author, category, available FROM books ORDER BY title"
    )
    items = []
    for r in rows:
        avail = r["available"]
        lbl   = f"{r['title']}  ·  {r['author']}"
        if avail >= 5:
            badge_col = COLORS["success"]
        elif avail >= 1:
            badge_col = COLORS["warning"]
        else:
            badge_col = COLORS["danger"]
        badge_txt = f"{avail} available" if avail > 0 else "Out of stock"
        isbn = r["isbn"] if avail > 0 else None
        items.append((lbl, isbn, badge_txt, badge_col))
    return items


# ══════════════════════════════════════════════
#  RETURN BOOK
# ══════════════════════════════════════════════
def build_return(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    label(parent, "Return a Book", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, "Select a student — their issued books will appear automatically.",
          "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=14)

    f = card(parent)
    f.pack(padx=32, pady=4, fill="x")

    # isbn map: display string → isbn  (populated when student selected)
    _isbn_map: dict = {}

    # Book dropdown (defined before student dd so the callback can reference it)
    label(f, "Book to Return  (select student first)", "small", color="muted").pack(
        anchor="w", padx=24, pady=(14, 4))
    book_var  = ctk.StringVar(value="— select a student above —")
    book_menu = ctk.CTkOptionMenu(
        f, variable=book_var,
        values=["— select a student above —"],
        fg_color=COLORS["input"],
        button_color=COLORS["accent"],
        button_hover_color=COLORS["accent"],
        text_color=COLORS["text"],
        font=FONTS["body"],
        width=460, height=40,
    )

    def _on_student_selected(_label_text, sid):
        """Called by the student SearchableDropdown on selection."""
        rows = db.fetchall(
            """SELECT b.isbn, b.title, ib.due_date
               FROM issued_books ib
               JOIN books b ON b.isbn = ib.book_isbn
               WHERE ib.student_id=%s AND ib.status='issued'
               ORDER BY b.title""",
            (sid,)
        )
        _isbn_map.clear()
        if not rows:
            book_menu.configure(values=["No books currently issued"])
            book_var.set("No books currently issued")
            return
        options = []
        for r in rows:
            display = f"{r['title']}  (due {r['due_date']})"
            _isbn_map[display] = r["isbn"]
            options.append(display)
        book_menu.configure(values=options)
        book_var.set(options[0])

    # Student dropdown — pass on_select at construction time
    label(f, "Student", "small", color="muted").pack(anchor="w", padx=24, pady=(16, 4))
    stu_items = _load_student_items(db)
    stu_dd = SearchableDropdown(
        f, stu_items,
        placeholder="Click to browse all students, or type to filter…",
        on_select=_on_student_selected,
        width=460,
    )
    stu_dd.pack(padx=24, pady=(0, 4))

    book_menu.pack(padx=24, pady=(0, 14))

    err_lbl = ctk.CTkLabel(f, text="", text_color=COLORS["danger"], font=FONTS["small"])
    err_lbl.pack(pady=2)

    def _return():
        sid       = stu_dd.get_value()
        book_disp = book_var.get()
        isbn      = _isbn_map.get(book_disp)

        if not sid:
            err_lbl.configure(text="Please select a student.")
            return
        if not isbn:
            err_lbl.configure(text="Please select a valid book to return.")
            return

        rec = db.fetchone(
            "SELECT id, due_date FROM issued_books "
            "WHERE student_id=%s AND book_isbn=%s AND status='issued'",
            (sid, isbn)
        )
        if not rec:
            err_lbl.configure(text="No active issue record found.")
            return

        fine = calc_fine(rec["due_date"])
        db.execute(
            "UPDATE issued_books SET returned_at=%s, fine=%s, status='returned' WHERE id=%s",
            (datetime.datetime.now(), fine, rec["id"])
        )
        db.execute("UPDATE books SET available = available + 1 WHERE isbn=%s", (isbn,))
        bk = db.fetchone("SELECT title FROM books WHERE isbn=%s", (isbn,))
        db.log(actor, "RETURN", f"'{bk['title']}' by {sid} | fine=₹{fine}")
        err_lbl.configure(text="")
        stu_dd.clear()
        book_menu.configure(values=["— select a student above —"])
        book_var.set("— select a student above —")
        _isbn_map.clear()

        fine_msg = f"\n\nFine charged:  ₹{fine:.2f}" if fine else "\n\nReturned on time — no fine! ✔"
        messagebox.showinfo("Returned ✔", f"'{bk['title']}' returned successfully.{fine_msg}")

    btn(f, "↩  Return Book", _return, color="success", width=460, height=42
        ).pack(padx=24, pady=(4, 20))


# ══════════════════════════════════════════════
#  ISSUED LIST
# ══════════════════════════════════════════════
def build_issued_list(parent: ctk.CTkFrame, db: Database, **_):
    label(parent, "Currently Issued Books", "heading").pack(anchor="w", padx=32, pady=(28, 2))

    rows = db.fetchall(
        """SELECT ib.id, s.name, s.student_id, b.title, b.isbn,
                  ib.issued_at, ib.due_date,
                  DATEDIFF(%s, ib.due_date) AS overdue_days
           FROM issued_books ib
           JOIN students s ON s.student_id = ib.student_id
           JOIN books b    ON b.isbn        = ib.book_isbn
           WHERE ib.status = 'issued'
           ORDER BY ib.due_date""",
        (today(),)
    )
    data = []
    for r in rows:
        od = r["overdue_days"] or 0
        data.append((
            r["id"], r["name"], r["student_id"],
            r["title"][:32], r["isbn"],
            str(r["issued_at"])[:10], str(r["due_date"]),
            f"⚠ {od}d overdue" if od > 0 else "✔ On time"
        ))

    p = ctk.CTkFrame(parent, fg_color="transparent")
    p.pack(fill="both", expand=True, padx=32, pady=12)
    build_table(p,
                ["#", "Student", "ID", "Book", "ISBN", "Issued", "Due", "Status"],
                data, [40, 130, 100, 210, 130, 90, 90, 110])


# ══════════════════════════════════════════════
#  FINES  (admin view)
# ══════════════════════════════════════════════
def build_fines_admin(parent: ctk.CTkFrame, db: Database, **_):
    label(parent, "Fines Overview", "heading").pack(anchor="w", padx=32, pady=(28, 2))

    rows = db.fetchall(
        """SELECT s.name, s.student_id, b.title,
                  ib.due_date, ib.returned_at, ib.fine, ib.status
           FROM issued_books ib
           JOIN students s ON s.student_id = ib.student_id
           JOIN books b    ON b.isbn        = ib.book_isbn
           WHERE ib.fine > 0
              OR (ib.status='issued' AND ib.due_date < %s)
           ORDER BY ib.due_date""",
        (today(),)
    )
    data = []
    for r in rows:
        fine = float(r["fine"]) if r["fine"] else calc_fine(r["due_date"])
        data.append((
            r["name"], r["student_id"], r["title"][:32],
            str(r["due_date"]),
            str(r["returned_at"])[:10] if r["returned_at"] else "—",
            f"₹ {fine:.2f}", r["status"]
        ))

    p = ctk.CTkFrame(parent, fg_color="transparent")
    p.pack(fill="both", expand=True, padx=32, pady=12)
    build_table(p,
                ["Student", "ID", "Book", "Due Date", "Returned", "Fine", "Status"],
                data, [130, 100, 200, 90, 90, 80, 80])


# ══════════════════════════════════════════════
#  AUDIT LOG
# ══════════════════════════════════════════════
def build_audit_log(parent: ctk.CTkFrame, db: Database, **_):
    label(parent, "Audit Log", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, "Every action taken in the system is recorded here.",
          "small", color="muted").pack(anchor="w", padx=32, pady=(0, 12))

    rows = db.fetchall(
        "SELECT actor, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 300"
    )
    data = [(r["actor"], r["action"], str(r["details"])[:70],
             str(r["timestamp"])[:19]) for r in rows]

    p = ctk.CTkFrame(parent, fg_color="transparent")
    p.pack(fill="both", expand=True, padx=32, pady=4)
    build_table(p, ["Actor", "Action", "Details", "Timestamp"],
                data, [110, 100, 400, 160])

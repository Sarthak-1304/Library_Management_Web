"""
tabs_student.py
═══════════════
Student portal tabs:
  - Dashboard      : quick summary of issued books
  - Browse & Issue : browse all books and issue one via dropdown
  - My Books       : currently issued books with due dates
"""

import datetime
from tkinter import messagebox

import customtkinter as ctk

from database import Database, today, calc_fine
from config import DEFAULT_ISSUE_DAYS, FINE_PER_DAY
from ui_helpers import (
    COLORS, FONTS,
    card, label, divider, btn, stat_card,
    build_table, SearchableDropdown,
)


# ══════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════
def build_dashboard(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    stu  = db.fetchone("SELECT name FROM students WHERE student_id=%s", (actor,))
    name = stu["name"] if stu else actor

    label(parent, f"Welcome, {name}", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, today().strftime("%A, %d %B %Y"), "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=16)

    sf = ctk.CTkFrame(parent, fg_color="transparent")
    sf.pack(fill="x", padx=24)
    sf.columnconfigure(0, weight=1)
    sf.columnconfigure(1, weight=1)
    sf.columnconfigure(2, weight=1)

    issued  = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books WHERE student_id=%s AND status='issued'",
        (actor,))["n"] or 0
    overdue = db.fetchone(
        "SELECT COUNT(*) AS n FROM issued_books "
        "WHERE student_id=%s AND status='issued' AND due_date < %s",
        (actor, today()))["n"] or 0
    avail = db.fetchone("SELECT SUM(available) AS n FROM books")["n"] or 0

    stat_card(sf, "Books I Have",     issued,  col=0, color="accent")
    stat_card(sf, "Overdue",          overdue, col=1, color="danger")
    stat_card(sf, "Books in Library", avail,   col=2, color="success")

    if overdue:
        af = ctk.CTkFrame(parent, fg_color="#1f151d",  # danger at ~12% on dark bg
                          corner_radius=10, border_width=1, border_color=COLORS["danger"])
        af.pack(fill="x", padx=32, pady=12)
        ctk.CTkLabel(af,
                     text=f"You have {overdue} overdue book(s) — please return them soon.",
                     text_color=COLORS["danger"], font=FONTS["body"]).pack(pady=10, padx=16)

    label(parent, "My Current Books", "sub").pack(anchor="w", padx=32, pady=(18, 6))
    rows = db.fetchall(
        """SELECT b.title, ib.due_date, DATEDIFF(%s, ib.due_date) AS overdue_days
           FROM issued_books ib
           JOIN books b ON b.isbn = ib.book_isbn
           WHERE ib.student_id=%s AND ib.status='issued'
           ORDER BY ib.due_date""",
        (today(), actor)
    )
    lf = card(parent)
    lf.pack(fill="x", padx=32, pady=2)
    if not rows:
        label(lf, "No books currently issued. Go to 'Issue Book' to get one!", color="muted").pack(pady=20)
    for r in rows:
        od  = r["overdue_days"] or 0
        row = ctk.CTkFrame(lf, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(row, text=r["title"], font=FONTS["body"],
                     text_color=COLORS["text"]).pack(side="left")
        col = COLORS["danger"] if od > 0 else COLORS["success"]
        txt = f"⚠ {od}d overdue" if od > 0 else f"due {r['due_date']}"
        ctk.CTkLabel(row, text=txt, font=FONTS["small"], text_color=col).pack(side="right")


# ══════════════════════════════════════════════
#  ISSUE BOOK
# ══════════════════════════════════════════════
def build_issue(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    label(parent, "Issue a Book", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, "Click the dropdown to see all books, or type to search.",
          "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=14)

    f = card(parent)
    f.pack(padx=32, pady=4, fill="x")

    label(f, "Select a Book", "small", color="muted").pack(anchor="w", padx=24, pady=(18, 4))

    book_dd = SearchableDropdown(
        f,
        items=_book_items(db),
        placeholder="Click here to browse all books…",
        on_select=None,
        width=500,
    )
    book_dd.pack(padx=24, pady=(0, 18))

    err_lbl = ctk.CTkLabel(f, text="", text_color=COLORS["danger"], font=FONTS["small"])
    err_lbl.pack(pady=(0, 4))

    def _issue():
        isbn  = book_dd.get_value()
        b_txt = book_dd.get_text().strip()

        if not b_txt:
            err_lbl.configure(text="Please select a book first.")
            return
        if isbn is None:
            err_lbl.configure(text="That book is currently out of stock.")
            return

        already = db.fetchone(
            "SELECT id FROM issued_books WHERE student_id=%s AND book_isbn=%s AND status='issued'",
            (actor, isbn)
        )
        if already:
            err_lbl.configure(text="You already have this book issued.")
            return

        bk  = db.fetchone("SELECT title FROM books WHERE isbn=%s", (isbn,))
        stu = db.fetchone("SELECT name FROM students WHERE student_id=%s", (actor,))
        due = today() + datetime.timedelta(days=DEFAULT_ISSUE_DAYS)

        db.execute(
            "INSERT INTO issued_books (student_id, book_isbn, due_date) VALUES (%s,%s,%s)",
            (actor, isbn, due)
        )
        db.execute("UPDATE books SET available = available - 1 WHERE isbn=%s", (isbn,))
        db.log(actor, "ISSUE", f"'{bk['title']}' issued to {stu['name']} (due {due})")

        err_lbl.configure(text="")
        book_dd.clear()
        messagebox.showinfo(
            "Book Issued",
            f"'{bk['title']}' has been issued to you.\n\nDue date:  {due}"
        )

    btn(f, "Issue This Book", _issue, width=500, height=42).pack(padx=24, pady=(0, 20))

    # ── full catalogue below ──
    label(parent, "All Books", "sub").pack(anchor="w", padx=32, pady=(16, 4))

    search_var = ctk.StringVar()
    ctk.CTkEntry(
        parent, textvariable=search_var,
        placeholder_text="Search title, author or category…",
        width=360, height=36, corner_radius=8,
        fg_color=COLORS["input"], border_color=COLORS["border"],
        text_color=COLORS["text"], font=FONTS["body"],
    ).pack(anchor="w", padx=32, pady=(0, 6))

    table_frame = ctk.CTkFrame(parent, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=32, pady=4)

    def _refresh(*_):
        for w in table_frame.winfo_children():
            w.destroy()
        q    = search_var.get().strip()
        like = f"%{q}%"
        rows = db.fetchall(
            "SELECT title, author, category, total_copies, available FROM books "
            "WHERE title LIKE %s OR author LIKE %s OR category LIKE %s ORDER BY title",
            (like, like, like)
        )
        build_table(table_frame,
                    ["Title", "Author", "Category", "Total", "Available"],
                    [(r["title"], r["author"], r["category"], r["total_copies"], r["available"])
                     for r in rows],
                    [280, 180, 120, 70, 90])

    search_var.trace_add("write", _refresh)
    _refresh()


def _book_items(db) -> list:
    rows = db.fetchall(
        "SELECT isbn, title, author, available FROM books ORDER BY title"
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
        items.append((lbl, r["isbn"] if avail > 0 else None, badge_txt, badge_col))
    return items


# ══════════════════════════════════════════════
#  MY BOOKS
# ══════════════════════════════════════════════
def build_my_books(parent: ctk.CTkFrame, db: Database, actor: str, **_):
    label(parent, "My Issued Books", "heading").pack(anchor="w", padx=32, pady=(28, 2))
    label(parent, "All books currently issued to you.", "small", color="muted").pack(anchor="w", padx=32)
    divider(parent).pack(fill="x", padx=32, pady=14)

    rows = db.fetchall(
        """SELECT b.title, b.author, b.category, ib.issued_at, ib.due_date,
                  DATEDIFF(%s, ib.due_date) AS overdue_days
           FROM issued_books ib
           JOIN books b ON b.isbn = ib.book_isbn
           WHERE ib.student_id=%s AND ib.status='issued'
           ORDER BY ib.due_date""",
        (today(), actor)
    )

    p = ctk.CTkFrame(parent, fg_color="transparent")
    p.pack(fill="both", expand=True, padx=32, pady=4)

    if not rows:
        label(p, "You have no books currently issued.", color="muted").pack(pady=40)
        return

    data = []
    for r in rows:
        od   = r["overdue_days"] or 0
        fine = od * FINE_PER_DAY
        st   = f"Overdue {od}d  (₹{fine:.0f} fine)" if od > 0 else "On time"
        data.append((r["title"], r["author"], r["category"],
                     str(r["issued_at"])[:10], str(r["due_date"]), st))

    build_table(p,
                ["Title", "Author", "Category", "Issued On", "Due Date", "Status"],
                data, [220, 140, 100, 90, 90, 190])

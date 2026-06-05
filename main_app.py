"""
main_app.py
═══════════
Main application window — sidebar navigation, tab routing.
Imports tab builders from tabs_admin and tabs_student.
"""

from functools import partial
import customtkinter as ctk

from database import Database 
from ui_helpers import COLORS, FONTS, divider
import tabs_admin   as adm
import tabs_student as stu


class LibraryApp(ctk.CTk):
    """Main window shown after successful login."""

    _ADMIN_TABS = [
        ("dashboard",   "🏠", "Dashboard",    adm.build_dashboard),
        ("books",       "📚", "Books",         adm.build_books),
        ("students",    "👤", "Students",      adm.build_students),
        ("issue",       "📤", "Issue Book",    adm.build_issue),
        ("return",      "📥", "Return Book",   adm.build_return),
        ("issued_list", "📋", "Issued List",   adm.build_issued_list),
        ("fines",       "💰", "Fines",         adm.build_fines_admin),
        ("logs",        "🗒", "Audit Log",     adm.build_audit_log),
    ]

    _STUDENT_TABS = [
        ("dashboard", "🏠", "Dashboard",   stu.build_dashboard),
        ("issue",     "📤", "Issue Book",  stu.build_issue),
        ("my_books",  "📋", "My Books",    stu.build_my_books),
    ]

    def __init__(self, db: Database, role: str, actor: str):
        super().__init__()
        self.db    = db
        self.role  = role
        self.actor = actor

        self.title(
            "Library MS — Admin Panel"
            if role == "admin"
            else "Library MS — Student Portal"
        )
        self.geometry("1220x760")
        self.minsize(960, 620)
        self.configure(fg_color=COLORS["bg"])

        self._tabs       = self._ADMIN_TABS if role == "admin" else self._STUDENT_TABS
        self._tab_btns   = {}
        self._active_key = None
        self._content_frame = None

        self._build_sidebar()
        self._show_tab("dashboard")

    # ── sidebar ──────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, fg_color=COLORS["sidebar"], corner_radius=0)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Logo
        ctk.CTkLabel(sb, text="📚", font=("Helvetica", 36)).pack(pady=(28, 2))
        ctk.CTkLabel(sb, text="Library MS", font=FONTS["sub"],
                     text_color=COLORS["text"]).pack()
        ctk.CTkLabel(sb, text=f"{self.role.capitalize()}  ·  {self.actor}",
                     font=FONTS["small"], text_color=COLORS["muted"]).pack(pady=(2, 18))
        divider(sb).pack(fill="x", padx=18)

        # Nav buttons
        for key, icon, lbl, _ in self._tabs:
            b = ctk.CTkButton(
                sb,
                text=f"  {icon}   {lbl}",
                anchor="w",
                fg_color="transparent",
                hover_color=COLORS["card2"],
                text_color=COLORS["muted"],
                font=FONTS["body"],
                corner_radius=8,
                height=40,
                command=partial(self._show_tab, key),
            )
            b.pack(fill="x", padx=12, pady=2)
            self._tab_btns[key] = b

        # Spacer + logout
        ctk.CTkFrame(sb, fg_color="transparent").pack(expand=True, fill="both")
        divider(sb).pack(fill="x", padx=18, pady=8)
        ctk.CTkButton(
            sb,
            text="  ⬅   Logout",
            anchor="w",
            fg_color="transparent",
            hover_color="#35151e",  # danger at ~19% on dark bg
            text_color=COLORS["danger"],
            font=FONTS["body"],
            corner_radius=8,
            height=40,
            command=self._logout,
        ).pack(fill="x", padx=12, pady=(0, 20))

    # ── tab routing ──────────────────────────────────────────
    def _show_tab(self, key: str):
        # Update button highlights
        for k, b in self._tab_btns.items():
            b.configure(
                fg_color=COLORS["card2"] if k == key else "transparent",
                text_color=COLORS["accent"] if k == key else COLORS["muted"],
            )
        self._active_key = key

        # Destroy old content
        if self._content_frame:
            self._content_frame.destroy()
        self._content_frame = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self._content_frame.pack(side="left", fill="both", expand=True)

        # Find and call builder
        builder = next((b for (k, _, _, b) in self._tabs if k == key), None)
        if builder:
            builder(
                self._content_frame,
                db=self.db,
                actor=self.actor,
                refresh=self._show_tab,
            )

    def _logout(self):
        self.destroy()
        _run_login(self.db)


# ── entry helpers ─────────────────────────────────────────────
def _run_login(db: Database):
    from login_window import LoginWindow
    win = LoginWindow(db)
    win.mainloop()
    if win.result:
        role, actor = win.result
        app = LibraryApp(db, role, actor)
        app.mainloop()


def main():
    db = Database()
    _run_login(db)
    db.close()


if __name__ == "__main__":
    main()

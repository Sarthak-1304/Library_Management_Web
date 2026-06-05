"""
login_window.py
═══════════════
Role-based login screen (Admin / Student).
"""

import hashlib
import customtkinter as ctk

from database import Database, _hash
from ui_helpers import COLORS, FONTS, card, label, entry_widget, btn, divider


class LoginWindow(ctk.CTk):
    """
    Standalone login window.
    After successful auth, `.result` = ("admin"|"student", actor_id).
    """

    def __init__(self, db: Database):
        super().__init__()
        self.db     = db
        self.result = None

        self.title("Library MS — Sign In")
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])

        self._build()

    # ── build UI ─────────────────────────────────────────────
    def _build(self):
        # ── logo area ──
        ctk.CTkLabel(self, text="📚", font=("Helvetica", 52)).pack(pady=(48, 4))
        label(self, "Library Management System", "heading").pack()
        label(self, "Sign in to your account", "small", color="muted").pack(pady=(4, 24))

        # ── form card ──
        f = card(self)
        f.pack(padx=48, fill="x", pady=4)

        # Role toggle
        self._role = ctk.StringVar(value="Admin")
        seg = ctk.CTkSegmentedButton(
            f, values=["Admin", "Student"],
            variable=self._role,
            command=self._toggle_role,
            font=FONTS["sub"],
            fg_color=COLORS["card2"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent"],
            unselected_color=COLORS["card2"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        seg.pack(pady=(20, 18), padx=24, fill="x")

        # ID / Username
        self._lbl_id = label(f, "Username", "small", color="muted")
        self._lbl_id.pack(anchor="w", padx=24)
        self._ent_id = entry_widget(f, "Enter username", width=368)
        self._ent_id.pack(padx=24, pady=(4, 10))

        # Password (in a container so show/hide keeps correct order)
        self._pw_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._pw_frame.pack(fill="x")
        label(self._pw_frame, "Password", "small", color="muted").pack(anchor="w", padx=24)
        self._ent_pw = entry_widget(self._pw_frame, "Enter password", show="•", width=368)
        self._ent_pw.pack(padx=24, pady=(4, 0))
        self._ent_pw.bind("<Return>", lambda _: self._login())

        # Error
        self._err = ctk.CTkLabel(f, text="", text_color=COLORS["danger"],
                                  font=FONTS["small"])
        self._err.pack(pady=(8, 4))

        # Sign-in button
        btn(f, "Sign In →", self._login, width=368, height=42).pack(padx=24, pady=(0, 20))



    # ── role toggle ──────────────────────────────────────────
    def _toggle_role(self, val: str):
        if val == "Admin":
            self._lbl_id.configure(text="Username")
            self._ent_id.configure(placeholder_text="Enter username")
        else:
            self._lbl_id.configure(text="Student ID")
            self._ent_id.configure(placeholder_text="e.g. STU2024001")
        self._err.configure(text="")

    # ── auth ─────────────────────────────────────────────────
    def _login(self):
        role = self._role.get()
        uid  = self._ent_id.get().strip()
        pw   = self._ent_pw.get().strip()

        if not uid:
            self._err.configure(text="⚠  Please enter your ID or username.")
            return
        if not pw:
            self._err.configure(text="⚠  Please enter your password.")
            return

        if role == "Admin":
            row = self.db.fetchone(
                "SELECT id FROM admins WHERE username=%s AND password=%s",
                (uid, _hash(pw))
            )
            if row:
                self.result = ("admin", uid)
                self.destroy()
            else:
                self._err.configure(text="⚠  Incorrect username or password.")

        else:   # Student
            row = self.db.fetchone(
                "SELECT id FROM students WHERE student_id=%s AND password=%s",
                (uid, _hash(pw))
            )
            if row:
                self.result = ("student", uid)
                self.destroy()
            else:
                self._err.configure(
                    text="⚠  Invalid Student ID or password.\n   Ask an admin to register you first."
                )
"""
ui_helpers.py
═════════════
Shared theme constants and reusable widget factory functions.
"""

import customtkinter as ctk
from tkinter import ttk
import tkinter as tk

# ── theme ─────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":      "#0d0f18",
    "sidebar": "#13161f",
    "card":    "#181b27",
    "card2":   "#1e2235",
    "input":   "#1a1e2e",
    "border":  "#272c42",
    "accent":  "#4b8cf5",
    "accent2": "#6d5ef7",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger":  "#ef4444",
    "text":    "#dde3f0",
    "muted":   "#5a6380",
    "white":   "#ffffff",
}

FONTS = {
    "title":   ("Georgia",     24, "bold"),
    "heading": ("Georgia",     15, "bold"),
    "sub":     ("Helvetica",   12, "bold"),
    "body":    ("Helvetica",   12),
    "small":   ("Helvetica",   10),
    "mono":    ("Courier New", 11),
    "tag":     ("Helvetica",   10, "bold"),
}


# ── widget factories ──────────────────────────────────────────

def card(parent, **kw):
    defaults = dict(fg_color=COLORS["card"], corner_radius=14)
    defaults.update(kw)
    return ctk.CTkFrame(parent, **defaults)


def label(parent, text, style="body", color="text", **kw):
    return ctk.CTkLabel(parent, text=text,
                        font=FONTS[style], text_color=COLORS[color], **kw)


def entry_widget(parent, placeholder="", show="", width=320):
    kw = dict(
        placeholder_text=placeholder,
        width=width, height=38, corner_radius=8,
        fg_color=COLORS["input"], border_color=COLORS["border"],
        border_width=1, text_color=COLORS["text"],
        placeholder_text_color=COLORS["muted"], font=FONTS["body"],
    )
    if show:
        kw["show"] = show
    return ctk.CTkEntry(parent, **kw)


def btn(parent, text, command, color="accent", width=160, height=38, **kw):
    bg = COLORS.get(color, color)
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=bg, hover_color=_darken(bg),
        font=FONTS["sub"], corner_radius=8,
        width=width, height=height, **kw
    )


def _darken(hex_color, factor=0.75):
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(int(r*factor), int(g*factor), int(b*factor))


def divider(parent, **kw):
    return ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"], **kw)


def stat_card(parent, title, value, col=0, row=0, color="accent"):
    f = ctk.CTkFrame(parent, fg_color=COLORS["card2"], corner_radius=12)
    f.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
    ctk.CTkLabel(f, text=title,     font=FONTS["small"],          text_color=COLORS["muted"]).pack(pady=(16, 2), padx=16)
    ctk.CTkLabel(f, text=str(value),font=("Georgia", 26, "bold"), text_color=COLORS[color]).pack(pady=(0, 16), padx=16)
    return f


# ── Treeview table ────────────────────────────────────────────

def build_table(parent, columns, rows, col_widths=None):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Lib.Treeview",
        background=COLORS["card2"], foreground=COLORS["text"],
        rowheight=32, fieldbackground=COLORS["card2"],
        borderwidth=0, font=FONTS["body"])
    style.configure("Lib.Treeview.Heading",
        background=COLORS["card"], foreground=COLORS["accent"],
        font=FONTS["sub"], relief="flat", padding=(8, 6))
    style.map("Lib.Treeview",
        background=[("selected", "#183055")],  # accent at ~27% on dark bg
        foreground=[("selected", COLORS["white"])])

    wrapper = ctk.CTkFrame(parent, fg_color="transparent")
    wrapper.pack(fill="both", expand=True)

    sb = ttk.Scrollbar(wrapper, orient="vertical")
    sb.pack(side="right", fill="y")

    tv = ttk.Treeview(wrapper, columns=columns, show="headings",
                      style="Lib.Treeview", yscrollcommand=sb.set)
    sb.config(command=tv.yview)

    for i, col in enumerate(columns):
        w = col_widths[i] if col_widths else 150
        tv.heading(col, text=col)
        tv.column(col, width=w, anchor="center", minwidth=40)

    for row_data in rows:
        tv.insert("", "end", values=row_data)

    tv.pack(fill="both", expand=True)
    return tv


# ── SearchableDropdown ────────────────────────────────────────

class SearchableDropdown(ctk.CTkFrame):
    """
    Reliable search-as-you-type combobox.

    Uses a plain tk.Listbox placed via place() on the nearest
    CTk root/toplevel — no separate Toplevel window, no flicker.

    items : list of (label, value)
          or (label, value, badge_text, badge_color)
    """

    ROW_H          = 18    # listbox line height (pixels, approximate)
    MAX_SHOW       = 10    # max visible rows before scroll
    _ANIM_OPEN_MS  = 150   # slide-down duration  (ms)
    _ANIM_CLOSE_MS = 80    # slide-up duration    (ms)
    _ANIM_FRAMES   = 8     # number of animation frames

    def __init__(self, parent, items, placeholder="Search…",
                 on_select=None, width=380, **kw):
        super().__init__(parent, fg_color="transparent", **kw)

        self._all_items      = items          # full list
        self._on_select      = on_select
        self._selected_value = None
        self._suppress_trace = False          # guard against re-entry

        # ── text entry ────────────────────────────────────
        self._var = ctk.StringVar()

        self._entry = ctk.CTkEntry(
            self, textvariable=self._var,
            placeholder_text=placeholder,
            width=width, height=40, corner_radius=8,
            fg_color=COLORS["input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"], font=FONTS["body"],
        )
        self._entry.pack()

        # Bind AFTER packing so winfo calls work
        self._entry.bind("<FocusIn>",  self._on_focus)
        self._entry.bind("<FocusOut>", self._on_blur)
        self._entry.bind("<Escape>",   lambda e: self._hide())
        self._entry.bind("<Return>",   self._on_return)
        self._entry.bind("<Down>",     self._on_down)
        self._var.trace_add("write",   self._on_type)

        # ── listbox (created once, shown/hidden) ──────────
        self._lb_frame = None   # tk.Frame holding listbox + scrollbar
        self._lb       = None   # tk.Listbox
        self._visible  = False

        # Store badge data separately (can't put in listbox)
        self._badge_data = []   # parallel list to _all_items

        # Animation state
        self._anim_after_id    = None
        self._type_debounce_id = None
        self._anim_step        = 0
        self._target_h         = 0
        self._place_x          = 0
        self._place_y          = 0
        self._place_w          = 0

    # ── public ────────────────────────────────────────────
    def get_value(self):
        return self._selected_value

    def get_text(self):
        return self._var.get()

    def set_items(self, items):
        self._all_items = items
        if self._visible:
            self._populate(items)

    def clear(self):
        self._suppress_trace = True
        self._var.set("")
        self._suppress_trace = False
        self._selected_value = None
        self._hide()

    # ── events ────────────────────────────────────────────
    def _on_focus(self, _e=None):
        self._show_filtered()

    def _on_blur(self, _e=None):
        # 150 ms lets a listbox click register first
        self.after(150, self._hide)

    def _on_type(self, *_):
        if self._suppress_trace:
            return
        # Debounce rapid keystrokes for smoother filtering
        if self._type_debounce_id is not None:
            self.after_cancel(self._type_debounce_id)
        self._type_debounce_id = self.after(40, self._debounced_filter)

    def _debounced_filter(self):
        self._type_debounce_id = None
        self._show_filtered()

    def _on_return(self, _e=None):
        if self._lb and self._visible:
            sel = self._lb.curselection()
            if sel:
                self._pick(sel[0])

    def _on_down(self, _e=None):
        """Move focus into the listbox on Down arrow."""
        if self._lb and self._visible:
            self._lb.focus_set()
            if not self._lb.curselection():
                self._lb.selection_set(0)

    # ── filtering & display ───────────────────────────────
    def _show_filtered(self):
        q = self._var.get().lower().strip()
        filtered = [it for it in self._all_items if q in it[0].lower()] if q else self._all_items[:]
        if filtered:
            self._show(filtered)
        else:
            self._hide()

    def _show(self, items):
        self._ensure_listbox()
        self._populate(items)

        # Cancel any running animation
        if self._anim_after_id is not None:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        # Position: get coords of the entry relative to the root window
        self._entry.update_idletasks()
        root = self._get_root()

        self._place_x = self._entry.winfo_rootx() - root.winfo_rootx()
        ey = self._entry.winfo_rooty() - root.winfo_rooty()
        self._place_w = self._entry.winfo_width()
        eh = self._entry.winfo_height()
        self._place_y = ey + eh + 2

        n_rows = min(len(items), self.MAX_SHOW)
        self._target_h = n_rows * 22 + 6

        if self._visible:
            # Already open — just resize, skip animation
            self._lb_frame.place(x=self._place_x, y=self._place_y,
                                 width=self._place_w, height=self._target_h)
            self._lb_frame.lift()
        else:
            # Slide-down open animation
            self._visible = True
            self._anim_step = 0
            self._animate_open()

    def _animate_open(self):
        """Ease-out cubic slide-down."""
        self._anim_step += 1
        t = self._anim_step / self._ANIM_FRAMES
        eased = 1 - (1 - t) ** 3
        h = max(1, int(self._target_h * eased))

        self._lb_frame.place(x=self._place_x, y=self._place_y,
                             width=self._place_w, height=h)
        self._lb_frame.lift()

        if self._anim_step < self._ANIM_FRAMES:
            ms = self._ANIM_OPEN_MS // self._ANIM_FRAMES
            self._anim_after_id = self.after(ms, self._animate_open)
        else:
            self._anim_after_id = None

    def _populate(self, items):
        self._lb.delete(0, tk.END)
        self._badge_data = items
        for item in items:
            display = item[0]
            # Append badge text inline for readability
            if len(item) > 2 and item[2]:
                display = f"{item[0]}    [{item[2]}]"
            self._lb.insert(tk.END, display)

    def _hide(self):
        # Cancel any running animation
        if self._anim_after_id is not None:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        if self._lb_frame and self._visible:
            self._visible = False
            self._anim_step = self._ANIM_FRAMES
            self._animate_close()
        elif self._lb_frame:
            self._lb_frame.place_forget()
            self._visible = False
        else:
            self._visible = False

    def _animate_close(self):
        """Ease-in quadratic slide-up."""
        self._anim_step -= 1
        if self._anim_step <= 0:
            self._lb_frame.place_forget()
            self._anim_after_id = None
            return

        t = self._anim_step / self._ANIM_FRAMES
        eased = t ** 2
        h = max(1, int(self._target_h * eased))

        self._lb_frame.place(x=self._place_x, y=self._place_y,
                             width=self._place_w, height=h)

        ms = self._ANIM_CLOSE_MS // self._ANIM_FRAMES
        self._anim_after_id = self.after(ms, self._animate_close)

    # ── listbox construction ──────────────────────────────
    def _ensure_listbox(self):
        if self._lb_frame is not None:
            return

        root = self._get_root()

        # Outer frame placed on the root window
        self._lb_frame = tk.Frame(
            root,
            bg=COLORS["card2"],
            bd=1, relief="solid",
            highlightthickness=1,
            highlightbackground=COLORS["accent"],
        )

        sb = tk.Scrollbar(self._lb_frame, orient="vertical")
        sb.pack(side="right", fill="y")

        self._lb = tk.Listbox(
            self._lb_frame,
            yscrollcommand=sb.set,
            bg=COLORS["card2"],
            fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["white"],
            font=FONTS["body"],
            bd=0,
            highlightthickness=0,
            activestyle="none",
            cursor="hand2",
        )
        sb.config(command=self._lb.yview)
        self._lb.pack(side="left", fill="both", expand=True)

        self._lb.bind("<ButtonRelease-1>", self._on_lb_click)
        self._lb.bind("<Return>",          self._on_lb_enter)
        self._lb.bind("<FocusOut>",        lambda e: self.after(150, self._hide))

    def _on_lb_click(self, _e=None):
        sel = self._lb.curselection()
        if sel:
            self._pick(sel[0])

    def _on_lb_enter(self, _e=None):
        sel = self._lb.curselection()
        if sel:
            self._pick(sel[0])

    def _pick(self, index):
        item = self._badge_data[index]
        label_text = item[0]
        value      = item[1]
        self._suppress_trace = True
        self._var.set(label_text)
        self._suppress_trace = False
        self._selected_value = value
        self._hide()
        self._entry.focus_set()
        if self._on_select:
            self._on_select(label_text, value)

    def _get_root(self):
        """Walk up widget tree to find the root CTk window."""
        w = self
        while w.master is not None:
            w = w.master
        return w

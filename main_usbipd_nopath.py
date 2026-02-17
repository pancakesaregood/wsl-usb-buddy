# WSL USB Buddy (Public-Safe / Stateless) - usbipd v4 compatible + "Open WSL as root"
# -------------------------------------------------------------------
# Public-safe design:
# - NO config file
# - NO profiles
# - NO persistent storage of BUSIDs, device names, window size, etc.
# - All state is in-memory only for the current session
#
# Added:
# - Top-right button: "Open WSL as root" (launches: wsl.exe -u root)
#
# Requires: usbipd-win v4+ on Windows, Python 3, Tkinter (included with standard Python)
# Recommended: Run as Administrator for bind/attach/detach/unbind.

import threading
import subprocess
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox


# ---- usbipd.exe resolver (no PATH required) ----
def resolve_usbipd_exe():
    """
    Returns an absolute path to usbipd.exe if we can find it, otherwise returns 'usbipd'
    (so PATH still works as a fallback).
    Resolution order:
      1) USBIPD_EXE environment variable (full path)
      2) usbipd.exe in the same folder as this script
      3) Common install paths for usbipd-win
      4) Fallback: 'usbipd' (requires PATH)
    """
    env = os.environ.get("USBIPD_EXE", "").strip().strip('"')
    if env:
        if os.path.isfile(env):
            return env
        # If user set a folder, try appending usbipd.exe
        cand = os.path.join(env, "usbipd.exe")
        if os.path.isfile(cand):
            return cand

    try:
        here = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(here, "usbipd.exe")
        if os.path.isfile(cand):
            return cand
    except Exception:
        pass

    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "usbipd-win", "usbipd.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "usbipd-win", "usbipd.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Programs", "usbipd-win", "usbipd.exe"),
    ]
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand

    return "usbipd"


USBIPD_EXE = resolve_usbipd_exe()
try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None

# ---- "acceptable devices" filter (in-memory only) ----
ALLOW_VIDPID_PREFIXES = ["1050:"]  # Yubico vendor ID
ALLOW_DEVICE_KEYWORDS = ["yubico", "yubikey", "security key", "fido"]
TRAY_POLL_INTERVAL_SECONDS = 3
UI_FONT_FAMILY = "Bahnschrift"
UI_COLORS = {
    "app_bg": "#eef2f7",
    "hero_bg": "#0f172a",
    "hero_fg": "#f8fafc",
    "text": "#0b1220",
    "muted": "#52607a",
    "card_bg": "#ffffff",
    "border": "#d8e0ec",
    "primary": "#0d9488",
    "primary_active": "#0f766e",
    "neutral_btn": "#e6edf7",
    "neutral_btn_active": "#d7e4f5",
}
TREE_COLUMN_WEIGHTS = {
    "busid": 11,
    "vidpid": 15,
    "device": 54,
    "state": 20,
}
TREE_COLUMN_MIN_WIDTHS = {
    "busid": 90,
    "vidpid": 120,
    "device": 300,
    "state": 140,
}
TREE_MIN_VISIBLE_ROWS = 6
TREE_MAX_VISIBLE_ROWS = 18
AUTO_ATTACH_RETRY_SECONDS = 30


def is_security_key_device(dev):
    vidpid = (dev.get("vidpid") or "").strip().lower()
    device = (dev.get("device") or "").strip().lower()

    for pref in ALLOW_VIDPID_PREFIXES:
        if vidpid.startswith(pref.lower()):
            return True
    for kw in ALLOW_DEVICE_KEYWORDS:
        if kw and kw.lower() in device:
            return True
    return False


def is_wsl_attached_state(state_text):
    state = (state_text or "").strip().lower()
    return "attached" in state and "not attached" not in state


def get_security_key_state(devices):
    keys = [d for d in devices if is_security_key_device(d)]
    if not keys:
        return "red", "Security key: not detected on host"

    if any(is_wsl_attached_state(d.get("state")) for d in keys):
        return "green", "Security key: attached to WSL"

    return "blue", "Security key: detected on host (not attached to WSL)"


def run_cmd(cmd, timeout=25):
    try:
        # If caller used "usbipd" without PATH, replace with resolved exe.
        if cmd and str(cmd[0]).lower() == "usbipd":
            cmd = [USBIPD_EXE] + list(cmd[1:])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]} (resolved usbipd path: {USBIPD_EXE})"
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out."
    except Exception as e:
        return 1, "", str(e)


def usbipd_list():
    rc, out, err = run_cmd(["usbipd", "list"], timeout=20)
    if rc != 0:
        raise RuntimeError(err or out or "usbipd list failed")

    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    results = []
    for ln in lines[1:]:
        # Split by 2+ spaces so "DEVICE" can contain spaces
        parts = [p for p in ln.split("  ") if p.strip()]
        parts = [p.strip() for p in parts]
        if len(parts) < 4:
            continue

        busid = parts[0]
        vidpid = parts[1]
        state = parts[-1]
        device = "  ".join(parts[2:-1]).strip() if len(parts) > 4 else parts[2]

        results.append({
            "busid": busid,
            "vidpid": vidpid,
            "device": device,
            "state": state
        })
    return results


def usbipd_bind(busid):
    rc, out, err = run_cmd(["usbipd", "bind", "--busid", busid], timeout=30)
    if rc != 0 and "already bound" not in (out + err).lower():
        raise RuntimeError(err or out or f"Bind (enable sharing) failed for {busid}")
    return out or "Sharing enabled (bind OK)."


def usbipd_unbind(busid):
    rc, out, err = run_cmd(["usbipd", "unbind", "--busid", busid], timeout=30)
    if rc != 0:
        raise RuntimeError(err or out or f"Unbind (disable sharing) failed for {busid}")
    return out or "Sharing disabled (unbind OK)."


def usbipd_attach(busid):
    usbipd_bind(busid)
    rc, out, err = run_cmd(["usbipd", "attach", "--wsl", "--busid", busid], timeout=30)
    if rc != 0:
        raise RuntimeError(err or out or f"Attach failed for {busid}")
    return out or "Attach OK."


def usbipd_detach(busid):
    rc, out, err = run_cmd(["usbipd", "detach", "--busid", busid], timeout=30)
    if rc != 0:
        raise RuntimeError(err or out or f"Detach failed for {busid}")
    return out or "Detach OK."


class SecurityKeyTray:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self._icons = {}
        self._last_state = None
        self._last_title = None
        self._stop_evt = threading.Event()
        self._icon_thread = None
        self._poll_thread = None

    def start(self):
        if pystray is None or Image is None or ImageDraw is None:
            self.app.log_line("Tray disabled: install pystray + Pillow to enable token status icon.")
            return False

        self._icons = {
            "red": self._build_icon("#cc2f2f"),
            "blue": self._build_icon("#2b72d6"),
            "green": self._build_icon("#2e9d48"),
        }

        self.icon = pystray.Icon("wsl-usb-buddy")
        self.icon.icon = self._icons["red"]
        self.icon.title = "Security key: checking..."
        self.icon.menu = pystray.Menu(
            pystray.MenuItem("Show Window", self._on_show_window),
            pystray.MenuItem("Refresh Devices", self._on_refresh_devices),
            pystray.MenuItem("Exit", self._on_exit),
        )

        self._icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        self._icon_thread.start()

        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        return True

    def stop(self):
        self._stop_evt.set()
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

    def _build_icon(self, fill_color):
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, size - 8, size - 8), fill=fill_color, outline="#202020", width=4)
        return img

    def _poll_loop(self):
        while not self._stop_evt.is_set():
            try:
                devices = usbipd_list()
                state, title = get_security_key_state(devices)
            except Exception as e:
                state, title = "red", f"Security key: status error ({e})"
            self._apply_state(state, title)
            self._stop_evt.wait(TRAY_POLL_INTERVAL_SECONDS)

    def _apply_state(self, state, title):
        if self.icon is None:
            return
        if state == self._last_state and title == self._last_title:
            return
        self._last_state = state
        self._last_title = title
        try:
            self.app.gui_queue.put((self.app._set_token_status_chip, (state, title)))
        except Exception:
            pass
        try:
            self.icon.icon = self._icons.get(state, self._icons["red"])
            self.icon.title = title
        except Exception:
            pass

    def _on_show_window(self, icon, item):
        self.app.gui_queue.put((self.app.show_window, ()))

    def _on_refresh_devices(self, icon, item):
        self.app.gui_queue.put((self.app.refresh_devices, ()))

    def _on_exit(self, icon, item):
        self.app.gui_queue.put((self.app.on_close_clicked, ()))


class App:
    def __init__(self):
        self.gui_queue = queue.Queue()
        self._closing = False
        self._last_tree_width = 0
        self._auto_attach_retry_until = {}
        self._auto_attach_blocked_busids = set()

        self.root = tk.Tk()
        self.root.title("WSL USB Buddy (Public-Safe / Stateless)")
        self.root.geometry("1000x660")
        self.root.minsize(900, 580)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_clicked)
        self.root.bind("<Unmap>", self._on_root_unmap)

        self._build_styles()
        self._build_ui()
        self.root.after(100, self._process_gui_queue)

        self.tray = SecurityKeyTray(self)
        if self.tray.start():
            self.log_line("Tray utility started: red=absent, blue=host, green=WSL.")
        else:
            self.btn_hide_to_tray.configure(state="disabled")

        self.refresh_devices()

    def _build_styles(self):
        self.root.configure(bg=UI_COLORS["app_bg"])
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=(UI_FONT_FAMILY, 10), foreground=UI_COLORS["text"], background=UI_COLORS["app_bg"])
        style.configure("App.TFrame", background=UI_COLORS["app_bg"])
        style.configure("Hero.TFrame", background=UI_COLORS["hero_bg"])
        style.configure("Card.TFrame", background=UI_COLORS["card_bg"], relief="flat")
        style.configure("Title.TLabel", font=(UI_FONT_FAMILY, 20, "bold"), foreground=UI_COLORS["hero_fg"], background=UI_COLORS["hero_bg"])
        style.configure("HeroText.TLabel", font=(UI_FONT_FAMILY, 10), foreground="#cbd5e1", background=UI_COLORS["hero_bg"])
        style.configure("Muted.TLabel", font=(UI_FONT_FAMILY, 10), foreground=UI_COLORS["muted"], background=UI_COLORS["app_bg"])
        style.configure("StatValue.TLabel", font=(UI_FONT_FAMILY, 18, "bold"), foreground=UI_COLORS["text"], background=UI_COLORS["card_bg"])
        style.configure("StatLabel.TLabel", font=(UI_FONT_FAMILY, 10), foreground=UI_COLORS["muted"], background=UI_COLORS["card_bg"])

        style.configure("Card.TLabelframe", background=UI_COLORS["card_bg"], bordercolor=UI_COLORS["border"], relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", font=(UI_FONT_FAMILY, 10, "bold"), foreground=UI_COLORS["text"], background=UI_COLORS["card_bg"])

        style.configure("TCheckbutton", background=UI_COLORS["hero_bg"], foreground="#dbe6ff")
        style.map("TCheckbutton", foreground=[("active", "#ffffff"), ("disabled", "#7a8ea8")])

        style.configure(
            "Primary.TButton",
            font=(UI_FONT_FAMILY, 10, "bold"),
            background=UI_COLORS["primary"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
        )
        style.map(
            "Primary.TButton",
            background=[("active", UI_COLORS["primary_active"]), ("disabled", "#a8c7c3")],
            foreground=[("disabled", "#e8f1ef")],
        )

        style.configure(
            "Action.TButton",
            font=(UI_FONT_FAMILY, 10),
            background=UI_COLORS["neutral_btn"],
            foreground=UI_COLORS["text"],
            borderwidth=0,
            focusthickness=0,
            padding=(12, 9),
        )
        style.map(
            "Action.TButton",
            background=[("active", UI_COLORS["neutral_btn_active"]), ("disabled", "#edf2f9")],
            foreground=[("disabled", "#9ca8be")],
        )

        style.configure(
            "Modern.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground=UI_COLORS["text"],
            rowheight=30,
            borderwidth=0,
        )
        style.map("Modern.Treeview", background=[("selected", "#d6f5ef")], foreground=[("selected", "#07261f")])
        style.configure(
            "Modern.Treeview.Heading",
            font=(UI_FONT_FAMILY, 10, "bold"),
            background="#f2f6fc",
            foreground="#1f2a3a",
            relief="flat",
            borderwidth=0,
        )
        style.map("Modern.Treeview.Heading", background=[("active", "#e4edf9")])

    def _build_ui(self):
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(16, 16, 16, 12))
        shell.pack(fill="both", expand=True)

        hero = ttk.Frame(shell, style="Hero.TFrame", padding=(18, 16))
        hero.pack(fill="x")

        hero_top = ttk.Frame(hero, style="Hero.TFrame")
        hero_top.pack(fill="x")
        ttk.Label(hero_top, text="WSL USB Buddy", style="Title.TLabel").pack(side="left", anchor="w")

        self.token_status_chip = tk.Label(
            hero_top,
            text="Token status: checking...",
            font=(UI_FONT_FAMILY, 10, "bold"),
            padx=12,
            pady=6,
            bd=0,
            relief="flat",
        )
        self.token_status_chip.pack(side="right")

        ttk.Label(
            hero,
            text="Stateless public-safe utility for usbipd and WSL security token passthrough.",
            style="HeroText.TLabel",
        ).pack(anchor="w", pady=(8, 0))

        controls = ttk.Frame(hero, style="Hero.TFrame")
        controls.pack(fill="x", pady=(12, 0))

        self.show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls,
            text="Show all devices for troubleshooting",
            variable=self.show_all_var,
            command=self.refresh_devices,
        ).pack(side="left")

        self.auto_attach_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls,
            text="Auto-attach known devices",
            variable=self.auto_attach_var,
            command=self._on_auto_attach_toggle,
        ).pack(side="left", padx=(14, 0))

        self.btn_hide_to_tray = ttk.Button(controls, text="Hide to Tray", style="Action.TButton", command=self.hide_window_to_tray)
        self.btn_hide_to_tray.pack(side="right")
        ttk.Button(controls, text="Open WSL as root", style="Action.TButton", command=self.open_wsl_as_root).pack(side="right", padx=(0, 8))

        self.total_devices_var = tk.StringVar(value="--")
        self.visible_devices_var = tk.StringVar(value="--")
        self.hidden_devices_var = tk.StringVar(value="--")

        summary = ttk.Frame(shell, style="App.TFrame", padding=(0, 12, 0, 8))
        summary.pack(fill="x")

        self._build_stat_card(summary, "USB devices", self.total_devices_var).pack(side="left", fill="x", expand=True)
        self._build_stat_card(summary, "Visible", self.visible_devices_var).pack(side="left", fill="x", expand=True, padx=10)
        self._build_stat_card(summary, "Hidden", self.hidden_devices_var).pack(side="left", fill="x", expand=True)

        list_frame = ttk.LabelFrame(shell, text="Device List", style="Card.TLabelframe", padding=12)
        list_frame.pack(fill="x", expand=False)

        cols = ("busid", "vidpid", "device", "state")
        self.tree = ttk.Treeview(
            list_frame,
            columns=cols,
            show="headings",
            height=TREE_MIN_VISIBLE_ROWS,
            style="Modern.Treeview",
        )
        self.tree.heading("busid", text="BUSID")
        self.tree.heading("vidpid", text="VID:PID")
        self.tree.heading("device", text="Device")
        self.tree.heading("state", text="State")

        self.tree.column("busid", width=90, minwidth=TREE_COLUMN_MIN_WIDTHS["busid"], anchor="w", stretch=True)
        self.tree.column("vidpid", width=120, minwidth=TREE_COLUMN_MIN_WIDTHS["vidpid"], anchor="w", stretch=True)
        self.tree.column("device", width=620, minwidth=TREE_COLUMN_MIN_WIDTHS["device"], anchor="w", stretch=True)
        self.tree.column("state", width=140, minwidth=TREE_COLUMN_MIN_WIDTHS["state"], anchor="w", stretch=True)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Configure>", self._on_tree_resize)
        vsb.pack(side="right", fill="y")
        self.root.after(0, lambda: self._apply_tree_column_scaling(self.tree.winfo_width()))

        btns = ttk.Frame(shell, style="App.TFrame", padding=(0, 10, 0, 0))
        btns.pack(fill="x")

        self.btn_refresh = ttk.Button(btns, text="Refresh", style="Action.TButton", command=self.refresh_devices)
        self.btn_refresh.pack(side="left")

        self.btn_share_on = ttk.Button(btns, text="Enable Sharing", style="Action.TButton", command=self.bind_selected)
        self.btn_share_on.pack(side="left", padx=8)

        self.btn_share_off = ttk.Button(btns, text="Disable Sharing", style="Action.TButton", command=self.unbind_selected)
        self.btn_share_off.pack(side="left")

        self.btn_attach = ttk.Button(btns, text="Attach to WSL", style="Primary.TButton", command=self.attach_selected)
        self.btn_attach.pack(side="left", padx=8)

        self.btn_detach = ttk.Button(btns, text="Detach from WSL", style="Action.TButton", command=self.detach_selected)
        self.btn_detach.pack(side="left")

        log_frame = ttk.LabelFrame(shell, text="Session Log", style="Card.TLabelframe", padding=10)
        log_frame.pack(fill="both", expand=False, pady=(10, 0))

        self.log = tk.Text(log_frame, height=8, wrap="word")
        self.log.configure(
            bg="#0f172a",
            fg="#dbe7ff",
            insertbackground="#dbe7ff",
            bd=0,
            padx=10,
            pady=10,
            highlightthickness=1,
            highlightbackground=UI_COLORS["border"],
            relief="flat",
            font=("Consolas", 10),
        )
        self.log.pack(fill="both", expand=True)

        ttk.Label(
            shell,
            text="Reminder: This build writes nothing to disk. Avoid sharing screenshots with sensitive host details.",
            style="Muted.TLabel",
            padding=(0, 8, 0, 0),
        ).pack(anchor="w")

        self._set_token_status_chip("red", "Security key: not detected on host")

    def _build_stat_card(self, parent, label_text, value_var):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        ttk.Label(card, textvariable=value_var, style="StatValue.TLabel").pack(anchor="w")
        ttk.Label(card, text=label_text, style="StatLabel.TLabel").pack(anchor="w", pady=(2, 0))
        return card

    def _set_token_status_chip(self, state, title):
        color_map = {
            "red": ("Token not detected", "#fde3e3", "#8f1f1f"),
            "blue": ("Token on host", "#dfeafe", "#1f4d8a"),
            "green": ("Token attached to WSL", "#dff5e6", "#1f6a3a"),
        }
        chip_text, bg_color, fg_color = color_map.get(state, ("Token status unknown", "#f3f4f6", "#334155"))
        self.token_status_chip.configure(text=chip_text, bg=bg_color, fg=fg_color)
        self.token_status_chip_tooltip = title

    def _on_auto_attach_toggle(self):
        state = "enabled" if self.auto_attach_var.get() else "disabled"
        if self.auto_attach_var.get():
            self._auto_attach_blocked_busids.clear()
        self.log_line(f"Auto-attach known devices {state}.")
        self.refresh_devices()

    def _is_allowed_device(self, dev, show_all=None):
        if show_all is None:
            show_all = bool(self.show_all_var.get())
        if show_all:
            return True
        return is_security_key_device(dev)

    def log_line(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")

    def _process_gui_queue(self):
        try:
            while True:
                fn, args = self.gui_queue.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.root.after(100, self._process_gui_queue)

    def _ui_set_busy(self, busy=True):
        state = "disabled" if busy else "normal"
        for b in (self.btn_refresh, self.btn_share_on, self.btn_share_off, self.btn_attach, self.btn_detach):
            b.configure(state=state)

    def _selected_busid(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0]).get("values", [])
        return str(vals[0]).strip() if vals else None

    def _on_tree_resize(self, event):
        width = int(getattr(event, "width", 0) or 0)
        if width <= 0:
            return
        if abs(width - self._last_tree_width) < 4:
            return
        self._last_tree_width = width
        self._apply_tree_column_scaling(width)

    def _apply_tree_column_scaling(self, width):
        if width <= 0:
            return

        min_total = sum(TREE_COLUMN_MIN_WIDTHS.values())
        usable_width = max(width - 6, min_total)
        total_weight = sum(TREE_COLUMN_WEIGHTS.values()) or 1

        new_widths = {}
        for col, weight in TREE_COLUMN_WEIGHTS.items():
            scaled = int((usable_width * weight) / total_weight)
            new_widths[col] = max(TREE_COLUMN_MIN_WIDTHS[col], scaled)

        overflow = sum(new_widths.values()) - usable_width
        if overflow > 0:
            for col in ("device", "state", "vidpid", "busid"):
                floor = TREE_COLUMN_MIN_WIDTHS[col]
                reducible = max(0, new_widths[col] - floor)
                take = min(overflow, reducible)
                new_widths[col] -= take
                overflow -= take
                if overflow <= 0:
                    break

        extra = usable_width - sum(new_widths.values())
        if extra > 0:
            new_widths["device"] += extra

        for col in ("busid", "vidpid", "device", "state"):
            self.tree.column(col, width=new_widths[col], minwidth=TREE_COLUMN_MIN_WIDTHS[col], stretch=True)

    def _fit_tree_rows(self, visible_count):
        rows = max(TREE_MIN_VISIBLE_ROWS, min(TREE_MAX_VISIBLE_ROWS, int(visible_count or 0)))
        self.tree.configure(height=rows)

    def _auto_attach_known_devices(self, devices):
        logs = []
        changed = False
        now = time.time()

        for d in devices:
            if not is_security_key_device(d):
                continue
            if is_wsl_attached_state(d.get("state")):
                continue

            busid = (d.get("busid") or "").strip()
            if not busid:
                continue
            if busid in self._auto_attach_blocked_busids:
                continue

            retry_until = self._auto_attach_retry_until.get(busid, 0)
            if retry_until > now:
                continue

            try:
                usbipd_attach(busid)
                changed = True
                self._auto_attach_retry_until.pop(busid, None)
                logs.append(f"Auto-attach OK: {busid}.")
            except Exception as e:
                self._auto_attach_retry_until[busid] = now + AUTO_ATTACH_RETRY_SECONDS
                logs.append(f"Auto-attach failed for {busid}: {e}")

        return changed, logs

    def show_window(self):
        if self._closing:
            return
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def hide_window_to_tray(self):
        if self._closing:
            return
        try:
            self.root.withdraw()
            self.log_line("Window hidden to tray.")
        except Exception:
            pass

    def _on_root_unmap(self, event):
        if self._closing:
            return
        try:
            has_tray = bool(getattr(self, "tray", None) and self.tray.icon is not None)
            if has_tray and self.root.state() == "iconic":
                # Convert normal minimize into tray-only mode (no taskbar button).
                self.root.after(0, self.hide_window_to_tray)
        except Exception:
            pass

    # ---- WSL root launcher ----
    def open_wsl_as_root(self):
        try:
            # Open default distro as root in a new console window
            subprocess.Popen(["wsl.exe", "-u", "root"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.log_line("Opened WSL as root (wsl.exe -u root).")
        except Exception as e:
            messagebox.showerror("Failed to open WSL", str(e))

    # ---- refresh ----
    def refresh_devices(self):
        if self._closing:
            return
        self._ui_set_busy(True)
        self.log_line("Refreshing device list...")
        auto_attach_enabled = bool(self.auto_attach_var.get())
        show_all_enabled = bool(self.show_all_var.get())
        threading.Thread(
            target=self._refresh_worker,
            args=(auto_attach_enabled, show_all_enabled),
            daemon=True,
        ).start()

    def _refresh_worker(self, auto_attach_enabled, show_all_enabled):
        try:
            devs = usbipd_list()
            auto_logs = []

            if auto_attach_enabled:
                changed, auto_logs = self._auto_attach_known_devices(devs)
                if changed:
                    devs = usbipd_list()

            shown = [d for d in devs if self._is_allowed_device(d, show_all=show_all_enabled)]
            token_state, token_title = get_security_key_state(devs)
            self.gui_queue.put((
                self._refresh_ui,
                (shown, len(devs), len(shown), token_state, token_title, auto_logs, show_all_enabled),
            ))
        except Exception as e:
            self.gui_queue.put((self._error_ui, ("Refresh failed", str(e))))

    def _refresh_ui(self, devs, total, shown, token_state, token_title, auto_logs, show_all_enabled):
        for x in self.tree.get_children():
            self.tree.delete(x)
        for d in devs:
            self.tree.insert("", "end", values=(d["busid"], d["vidpid"], d["device"], d["state"]))

        self._fit_tree_rows(shown)
        self.total_devices_var.set(str(total))
        self.visible_devices_var.set(str(shown))
        self.hidden_devices_var.set(str(max(0, total - shown)))
        self._set_token_status_chip(token_state, token_title)
        for line in auto_logs:
            self.log_line(line)

        self._ui_set_busy(False)
        if show_all_enabled:
            self.log_line(f"Showing ALL devices: {shown}/{total}.")
        else:
            self.log_line(f"Showing acceptable devices: {shown}/{total}. Hidden: {total - shown}.")

    def _error_ui(self, title, msg):
        self._ui_set_busy(False)
        self._set_token_status_chip("red", "Security key: status unavailable")
        self.log_line(f"ERROR: {title}: {msg}")
        messagebox.showerror(title, msg)

    # ---- operations ----
    def bind_selected(self):
        busid = self._selected_busid()
        if not busid:
            messagebox.showinfo("Pick a device", "Select a USB device first.")
            return
        self._ui_set_busy(True)
        self.log_line(f"Enabling sharing for {busid} (bind)...")
        threading.Thread(target=self._bind_worker, args=(busid,), daemon=True).start()

    def _bind_worker(self, busid):
        try:
            msg = usbipd_bind(busid)
            self.gui_queue.put((self._op_ok_ui, (f"Sharing enabled for {busid}", msg)))
        except Exception as e:
            self.gui_queue.put((self._error_ui, ("Enable sharing failed", str(e))))

    def unbind_selected(self):
        busid = self._selected_busid()
        if not busid:
            messagebox.showinfo("Pick a device", "Select a USB device first.")
            return
        self._ui_set_busy(True)
        self.log_line(f"Disabling sharing for {busid} (unbind)...")
        threading.Thread(target=self._unbind_worker, args=(busid,), daemon=True).start()

    def _unbind_worker(self, busid):
        try:
            msg = usbipd_unbind(busid)
            self._auto_attach_blocked_busids.add(busid)
            self.gui_queue.put((self._op_ok_ui, (f"Sharing disabled for {busid}", msg)))
        except Exception as e:
            self.gui_queue.put((self._error_ui, ("Disable sharing failed", str(e))))

    def attach_selected(self):
        busid = self._selected_busid()
        if not busid:
            messagebox.showinfo("Pick a device", "Select a USB device first.")
            return
        self._ui_set_busy(True)
        self.log_line(f"Attaching {busid} to WSL (bind + attach)...")
        threading.Thread(target=self._attach_worker, args=(busid,), daemon=True).start()

    def _attach_worker(self, busid):
        try:
            msg = usbipd_attach(busid)
            self._auto_attach_blocked_busids.discard(busid)
            self._auto_attach_retry_until.pop(busid, None)
            self.gui_queue.put((self._op_ok_ui, (f"Attach OK: {busid}", msg)))
        except Exception as e:
            self.gui_queue.put((self._error_ui, ("Attach failed", str(e))))

    def detach_selected(self):
        busid = self._selected_busid()
        if not busid:
            messagebox.showinfo("Pick a device", "Select a USB device first.")
            return
        self._ui_set_busy(True)
        self.log_line(f"Detaching {busid} from WSL...")
        threading.Thread(target=self._detach_worker, args=(busid,), daemon=True).start()

    def _detach_worker(self, busid):
        try:
            msg = usbipd_detach(busid)
            self._auto_attach_blocked_busids.add(busid)
            self.gui_queue.put((self._op_ok_ui, (f"Detach OK: {busid}", msg)))
        except Exception as e:
            self.gui_queue.put((self._error_ui, ("Detach failed", str(e))))

    def _op_ok_ui(self, title, details):
        self._ui_set_busy(False)
        self.log_line(title)
        if details:
            self.log_line(details)
        self.refresh_devices()

    def on_close_clicked(self):
        if self._closing:
            return
        self._closing = True
        try:
            if getattr(self, "tray", None):
                self.tray.stop()
        finally:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

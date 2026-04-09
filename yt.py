#!/usr/bin/env python3
"""
YouTube Video Downloader - GUI App
Yêu cầu: pip install yt-dlp
         pip install pillow  (để hiện thumbnail)
Chạy:    python youtube_downloader.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import re
import json
import subprocess
import time
from datetime import datetime

# ── Kiểm tra yt-dlp ──────────────────────────────────────────────
try:
    import yt_dlp
except ImportError:
    print("[Lỗi] Chưa cài yt-dlp. Chạy: pip install yt-dlp")
    sys.exit(1)

# ── Thử import Pillow để hiện thumbnail (tuỳ chọn) ───────────────
try:
    from PIL import Image, ImageTk
    import urllib.request
    import io
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

# ── Kiểm tra ffmpeg (để cắt video) ──────────────────────────────
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    FFMPEG_OK = True
except (FileNotFoundError, subprocess.CalledProcessError):
    FFMPEG_OK = False
    print("[⚠ Cảnh báo] ffmpeg chưa cài. Cắt video sẽ bị vô hiệu. Cài đặt: pip install ffmpeg-python hoặc tải từ ffmpeg.org")


# ══════════════════════════════════════════════════════════════════
#  MÀU SẮC & STYLE
# ══════════════════════════════════════════════════════════════════
COLORS = {
    "bg":        "#0f0f0f",
    "surface":   "#1a1a1a",
    "surface2":  "#242424",
    "border":    "#2e2e2e",
    "red":       "#FF0000",
    "red_dark":  "#CC0000",
    "text":      "#f1f1f1",
    "muted":     "#aaaaaa",
    "success":   "#1ed760",
    "warning":   "#ffb800",
    "error":     "#ff4444",
}

FONTS = {
    "title":   ("Segoe UI", 13, "bold"),
    "body":    ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "mono":    ("Consolas", 9),
    "heading": ("Segoe UI", 11, "bold"),
}


# ══════════════════════════════════════════════════════════════════
#  TIỆN ÍCH
# ══════════════════════════════════════════════════════════════════
def fmt_size(n):
    """Định dạng bytes → KB/MB/GB."""
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def fmt_time(s):
    """Giây → mm:ss hoặc hh:mm:ss."""
    if s is None:
        return "?"
    s = int(s)
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def sanitize(name):
    """Xoá ký tự không hợp lệ trong tên file."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)

def parse_time_to_seconds(time_str):
    """Chuyển mm:ss hoặc hh:mm:ss thành giây."""
    if not time_str or not time_str.strip():
        return None
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])  # mm:ss
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])  # hh:mm:ss
        else:
            return int(float(time_str))  # Giây trực tiếp
    except (ValueError, AttributeError):
        return None


# ══════════════════════════════════════════════════════════════════
#  WIDGET PHỤ TRỢ
# ══════════════════════════════════════════════════════════════════
class RoundedButton(tk.Canvas):
    """Nút bo góc tự vẽ."""
    def __init__(self, parent, text, command=None, bg=None, fg="#fff",
                 width=120, height=32, radius=6, font=None, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=COLORS["surface"], highlightthickness=0, **kwargs)
        self.command = command
        self.bg_normal = bg or COLORS["red"]
        self.bg_hover  = COLORS["red_dark"] if bg == COLORS["red"] else bg
        self.fg = fg
        self.radius = radius
        self.font = font or FONTS["body"]
        self._text = text
        self._draw(self.bg_normal)
        self.bind("<Enter>",    lambda e: self._draw(self.bg_hover))
        self.bind("<Leave>",    lambda e: self._draw(self.bg_normal))
        self.bind("<Button-1>", lambda e: self._click())

    def _draw(self, color):
        self.delete("all")
        r = self.radius
        w = int(self["width"])
        h = int(self["height"])
        self.create_polygon(
            r, 0, w-r, 0, w, r, w, h-r, w-r, h, r, h, 0, h-r, 0, r,
            smooth=True, fill=color, outline="")
        self.create_text(w//2, h//2, text=self._text,
                         fill=self.fg, font=self.font)

    def _click(self):
        if self.command:
            self.command()

    def config_text(self, text):
        self._text = text
        self._draw(self.bg_normal)


class Separator(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, height=1,
                         bg=COLORS["border"], **kw)


class Section(tk.LabelFrame):
    def __init__(self, parent, title, **kw):
        super().__init__(parent, text=f"  {title}  ",
                         bg=COLORS["surface"],
                         fg=COLORS["muted"],
                         font=FONTS["small"],
                         bd=1, relief="flat",
                         highlightbackground=COLORS["border"],
                         highlightthickness=1,
                         padx=10, pady=8, **kw)


# ══════════════════════════════════════════════════════════════════
#  CỬA SỔ CHÍNH
# ══════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("700x850")
        self.minsize(620, 750)
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)

        # Trạng thái
        self._dl_thread   = None
        self._cancelled   = False
        self._info        = None
        self._save_dir    = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self._url_var     = tk.StringVar()
        self._quality_var = tk.StringVar(value="720")
        self._format_var  = tk.StringVar(value="mp4")
        self._playlist    = tk.BooleanVar(value=False)
        self._subtitles   = tk.BooleanVar(value=False)
        self._sub_lang    = tk.StringVar(value="vi")
        self._speed_var   = tk.StringVar(value="0")  # 0 = không giới hạn
        # ── Cắt video ────────────────────────────────────────────
        self._trim_enabled = tk.BooleanVar(value=False)
        self._trim_start   = tk.StringVar(value="")
        self._trim_end     = tk.StringVar(value="")
        self._last_file    = None  # Lưu file vừa tải
        # ── Cắt video có sẵn ────────────────────────────────────────
        self._trim_file_var     = tk.StringVar(value="")
        self._trim_file_start   = tk.StringVar(value="")
        self._trim_file_end     = tk.StringVar(value="")
        self._trim_file_output_name = tk.StringVar(value="")

        self._build_ui()
        self._log("Sẵn sàng. Dán link YouTube và nhấn Phân tích.")

    # ── BUILD UI ────────────────────────────────────────────────
    def _build_ui(self):
        C = COLORS
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self, bg="#1a0000", pady=14)
        header.pack(fill="x")

        tk.Label(header, text="▶  YouTube Downloader",
                 bg="#1a0000", fg=C["text"],
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
        tk.Label(header, text="powered by yt-dlp",
                 bg="#1a0000", fg=C["muted"],
                 font=FONTS["small"]).pack(side="right", padx=20)

        # ── Scrollable body ─────────────────────────────────────
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=10)

        # ── URL ─────────────────────────────────────────────────
        url_sec = Section(body, "Link YouTube / Playlist")
        url_sec.pack(fill="x", pady=(0, 8))

        url_row = tk.Frame(url_sec, bg=C["surface"])
        url_row.pack(fill="x")

        self._url_entry = tk.Entry(
            url_row, textvariable=self._url_var,
            bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
            relief="flat", font=FONTS["body"], bd=6)
        self._url_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._url_entry.bind("<Return>", lambda e: self._analyze())

        self._btn_paste = RoundedButton(
            url_row, "Dán", command=self._paste,
            bg=C["surface2"], fg=C["muted"], width=54, height=34)
        self._btn_paste.pack(side="left", padx=(4, 0))

        self._btn_analyze = RoundedButton(
            url_row, "Phân tích  ▶", command=self._analyze,
            width=110, height=34)
        self._btn_analyze.pack(side="left", padx=(6, 0))

        # ── Thông tin video ─────────────────────────────────────
        self._info_sec = Section(body, "Thông tin video")
        self._info_sec.pack(fill="x", pady=(0, 8))

        info_inner = tk.Frame(self._info_sec, bg=C["surface"])
        info_inner.pack(fill="x")

        # Thumbnail
        self._thumb_lbl = tk.Label(
            info_inner, bg=C["surface2"],
            width=16, height=5, relief="flat",
            text="[ thumbnail ]", fg=C["muted"], font=FONTS["small"])
        self._thumb_lbl.pack(side="left", padx=(0, 12))

        meta = tk.Frame(info_inner, bg=C["surface"])
        meta.pack(side="left", fill="x", expand=True)

        self._title_lbl = tk.Label(
            meta, text="—", bg=C["surface"],
            fg=C["text"], font=FONTS["heading"],
            anchor="w", wraplength=420, justify="left")
        self._title_lbl.pack(fill="x")

        self._channel_lbl = tk.Label(
            meta, text="", bg=C["surface"],
            fg=C["muted"], font=FONTS["small"], anchor="w")
        self._channel_lbl.pack(fill="x", pady=(2, 0))

        stats = tk.Frame(meta, bg=C["surface"])
        stats.pack(fill="x", pady=(4, 0))
        self._dur_lbl  = self._badge(stats, "Thời lượng: —")
        self._size_lbl = self._badge(stats, "Kích thước: —")
        self._views_lbl= self._badge(stats, "")

        # ── Tùy chọn tải ────────────────────────────────────────
        opt_sec = Section(body, "Tùy chọn tải xuống")
        opt_sec.pack(fill="x", pady=(0, 8))

        row1 = tk.Frame(opt_sec, bg=C["surface"])
        row1.pack(fill="x", pady=(0, 6))

        self._add_label(row1, "Chất lượng:")
        self._quality_cb = self._combo(
            row1, self._quality_var,
            ["Tốt nhất", "4320 (8K)", "2160 (4K)", "1440 (2K)",
             "1080", "720", "480", "360", "240", "144"],
            width=14)
        self._quality_var.set("720")

        self._add_label(row1, "  Định dạng:")
        self._format_cb = self._combo(
            row1, self._format_var,
            ["mp4", "webm", "mkv", "mp3", "m4a", "opus", "flac"],
            width=8)

        self._add_label(row1, "  Tốc độ tối đa:")
        self._speed_cb = self._combo(
            row1, self._speed_var,
            ["Không giới hạn", "10M", "5M", "2M", "1M", "500K", "200K"],
            width=13)

        row2 = tk.Frame(opt_sec, bg=C["surface"])
        row2.pack(fill="x")

        self._add_label(row2, "Thư mục lưu:")
        dir_entry = tk.Entry(
            row2, textvariable=self._save_dir,
            bg=C["surface2"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", font=FONTS["body"], bd=4, width=30)
        dir_entry.pack(side="left", ipady=3, padx=(0, 4))

        RoundedButton(row2, "Duyệt...", command=self._browse,
                      bg=C["surface2"], fg=C["muted"],
                      width=64, height=28).pack(side="left")

        row3 = tk.Frame(opt_sec, bg=C["surface"])
        row3.pack(fill="x", pady=(8, 0))

        self._ck_playlist = self._checkbox(row3, "Tải cả playlist", self._playlist)
        self._ck_subs     = self._checkbox(row3, "Tải phụ đề", self._subtitles)

        sub_inner = tk.Frame(row3, bg=C["surface"])
        sub_inner.pack(side="left", padx=(4, 0))
        self._add_label(sub_inner, "Ngôn ngữ:")
        self._sub_cb = self._combo(sub_inner, self._sub_lang,
                                   ["vi", "en", "zh", "ja", "ko", "fr", "de"],
                                   width=6)

        # ── Cắt video ────────────────────────────────────────────
        if FFMPEG_OK:
            trim_sec = Section(body, "Cắt video (sau khi tải)")
            trim_sec.pack(fill="x", pady=(0, 8))

            trim_row = tk.Frame(trim_sec, bg=C["surface"])
            trim_row.pack(fill="x")

            self._ck_trim = self._checkbox(trim_row, "Kích hoạt cắt video", self._trim_enabled)

            trim_inner = tk.Frame(trim_sec, bg=C["surface"])
            trim_inner.pack(fill="x", pady=(4, 0))

            self._add_label(trim_inner, "Bắt đầu (mm:ss hoặc hh:mm:ss):")
            self._trim_start_entry = tk.Entry(
                trim_inner, textvariable=self._trim_start,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=12)
            self._trim_start_entry.pack(side="left", ipady=3, padx=(0, 12))

            self._add_label(trim_inner, "Kết thúc (mm:ss hoặc hh:mm:ss):")
            self._trim_end_entry = tk.Entry(
                trim_inner, textvariable=self._trim_end,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=12)
            self._trim_end_entry.pack(side="left", ipady=3)

            trim_hint = tk.Label(
                trim_sec, text="💡 Để trống để cắt từ đầu/đến cuối. VD: 00:15 - 01:30",
                bg=C["surface"], fg=C["muted"], font=FONTS["small"], justify="left")
            trim_hint.pack(fill="x", pady=(4, 0))

            # ── Cắt video có sẵn ────────────────────────────────────
            existing_sec = Section(body, "Cắt video có sẵn")
            existing_sec.pack(fill="x", pady=(0, 8))

            file_row = tk.Frame(existing_sec, bg=C["surface"])
            file_row.pack(fill="x", pady=(0, 6))

            self._add_label(file_row, "File video:")
            self._file_entry = tk.Entry(
                file_row, textvariable=self._trim_file_var,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=40)
            self._file_entry.pack(side="left", ipady=3, padx=(0, 4))

            RoundedButton(file_row, "Chọn file...", command=self._browse_video_file,
                          bg=C["surface2"], fg=C["muted"],
                          width=90, height=28).pack(side="left")

            time_row = tk.Frame(existing_sec, bg=C["surface"])
            time_row.pack(fill="x", pady=(0, 6))

            self._add_label(time_row, "Bắt đầu:")
            self._trim_file_start_entry = tk.Entry(
                time_row, textvariable=self._trim_file_start,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=12)
            self._trim_file_start_entry.pack(side="left", ipady=3, padx=(0, 12))

            self._add_label(time_row, "Kết thúc:")
            self._trim_file_end_entry = tk.Entry(
                time_row, textvariable=self._trim_file_end,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=12)
            self._trim_file_end_entry.pack(side="left", ipady=3, padx=(0, 12))

            output_row = tk.Frame(existing_sec, bg=C["surface"])
            output_row.pack(fill="x", pady=(0, 6))

            self._add_label(output_row, "Tên file output:")
            self._trim_file_output_entry = tk.Entry(
                output_row, textvariable=self._trim_file_output_name,
                bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                relief="flat", font=FONTS["body"], bd=4, width=40)
            self._trim_file_output_entry.pack(side="left", ipady=3, padx=(0, 4))

            hint_lbl = tk.Label(
                existing_sec, text="💡 Để trống để sử dụng tên mặc định (thêm _trimmed)",
                bg=C["surface"], fg=C["muted"], font=FONTS["small"])
            hint_lbl.pack(fill="x", pady=(0, 6))

            RoundedButton(existing_sec, "🎬 Cắt video", command=self._trim_existing_video,
                          bg="#008000", fg="#fff",
                          width=120, height=32).pack(pady=(4, 0))

        # ── Progress ─────────────────────────────────────────────
        prog_sec = Section(body, "Tiến độ tải")
        prog_sec.pack(fill="x", pady=(0, 8))

        self._prog_lbl = tk.Label(
            prog_sec, text="Chờ...",
            bg=C["surface"], fg=C["muted"], font=FONTS["small"], anchor="w")
        self._prog_lbl.pack(fill="x")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Red.Horizontal.TProgressbar",
                         troughcolor=C["surface2"],
                         background=C["red"],
                         bordercolor=C["surface2"],
                         lightcolor=C["red"],
                         darkcolor=C["red"])
        self._pbar = ttk.Progressbar(
            prog_sec, style="Red.Horizontal.TProgressbar",
            maximum=100, value=0, length=600)
        self._pbar.pack(fill="x", pady=(4, 6))

        self._speed_lbl = tk.Label(
            prog_sec, text="",
            bg=C["surface"], fg=C["muted"], font=FONTS["small"], anchor="w")
        self._speed_lbl.pack(fill="x")

        # ── Nút tải / hủy ───────────────────────────────────────
        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(fill="x", pady=(0, 8))

        self._btn_dl = RoundedButton(
            btn_row, "⬇  Tải xuống", command=self._start_download,
            width=140, height=38, font=FONTS["heading"])
        self._btn_dl.pack(side="left", padx=(0, 8))

        self._btn_cancel = RoundedButton(
            btn_row, "✕  Hủy", command=self._cancel,
            bg=C["surface2"], fg=C["muted"], width=90, height=38)
        self._btn_cancel.pack(side="left", padx=(0, 8))

        RoundedButton(
            btn_row, "↗  Mở thư mục", command=self._open_dir,
            bg=C["surface2"], fg=C["muted"], width=110, height=38
        ).pack(side="left")

        # ── Log ─────────────────────────────────────────────────
        log_sec = Section(body, "Nhật ký")
        log_sec.pack(fill="both", expand=True)

        self._log_text = tk.Text(
            log_sec, height=7, state="disabled",
            bg=C["bg"], fg=C["muted"], font=FONTS["mono"],
            relief="flat", wrap="word",
            insertbackground=C["muted"],
            selectbackground=C["surface2"])
        scroll = tk.Scrollbar(log_sec, command=self._log_text.yview,
                               bg=C["surface2"], troughcolor=C["bg"],
                               relief="flat", width=8)
        self._log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)

        # ── Status bar ──────────────────────────────────────────
        status = tk.Frame(self, bg=C["surface2"], pady=4)
        status.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(
            status, text="  yt-dlp ready",
            bg=C["surface2"], fg=C["muted"], font=FONTS["small"], anchor="w")
        self._status_lbl.pack(side="left", padx=8)
        tk.Label(status, text=f"  yt-dlp {yt_dlp.version.__version__}",
                 bg=C["surface2"], fg=C["border"],
                 font=FONTS["small"]).pack(side="right", padx=8)

    # ── HELPER WIDGETS ──────────────────────────────────────────
    def _badge(self, parent, text):
        lbl = tk.Label(parent, text=text,
                       bg=COLORS["surface2"], fg=COLORS["muted"],
                       font=FONTS["small"], padx=6, pady=2,
                       relief="flat")
        lbl.pack(side="left", padx=(0, 4))
        return lbl

    def _add_label(self, parent, text):
        tk.Label(parent, text=text,
                 bg=COLORS["surface"], fg=COLORS["muted"],
                 font=FONTS["small"]).pack(side="left")

    def _combo(self, parent, var, values, width=12):
        style = ttk.Style()
        style.configure("Dark.TCombobox",
                         fieldbackground=COLORS["surface2"],
                         background=COLORS["surface2"],
                         foreground=COLORS["text"],
                         arrowcolor=COLORS["muted"],
                         selectforeground=COLORS["text"],
                         selectbackground=COLORS["surface2"])
        cb = ttk.Combobox(parent, textvariable=var, values=values,
                          width=width, state="readonly",
                          font=FONTS["small"], style="Dark.TCombobox")
        cb.pack(side="left", padx=(4, 0))
        return cb

    def _checkbox(self, parent, text, var):
        ck = tk.Checkbutton(
            parent, text=text, variable=var,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"],
            font=FONTS["small"])
        ck.pack(side="left", padx=(0, 8))
        return ck

    # ── LOG / STATUS ────────────────────────────────────────────
    def _log(self, msg, color=None):
        now = datetime.now().strftime("%H:%M:%S")
        self._log_text.configure(state="normal")
        tag = f"c{id(msg)}"
        self._log_text.insert("end", f"[{now}] {msg}\n", tag)
        if color:
            self._log_text.tag_configure(tag, foreground=color)
        self._log_text.configure(state="disabled")
        self._log_text.see("end")

    def _set_status(self, text):
        self._status_lbl.configure(text=f"  {text}")

    # ── ACTIONS ─────────────────────────────────────────────────
    def _paste(self):
        try:
            clip = self.clipboard_get()
            self._url_var.set(clip.strip())
        except Exception:
            pass

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._save_dir.get())
        if d:
            self._save_dir.set(d)

    def _open_dir(self):
        d = self._save_dir.get()
        if os.path.isdir(d):
            if sys.platform == "win32":
                os.startfile(d)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])

    def _browse_video_file(self):
        """Chọn file video để cắt."""
        filetypes = [
            ("Video files", "*.mp4 *.mkv *.webm *.avi *.mov *.flv *.wmv *.m4v"),
            ("Tất cả file", "*.*")
        ]
        f = filedialog.askopenfilename(
            initialdir=self._save_dir.get(),
            filetypes=filetypes,
            title="Chọn file video để cắt")
        if f:
            self._trim_file_var.set(f)
            self._log(f"✔ Chọn file: {os.path.basename(f)}", COLORS["success"])

    # ── PHÂN TÍCH VIDEO ─────────────────────────────────────────
    def _analyze(self):
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thiếu link", "Vui lòng dán link YouTube.")
            return
        self._log(f"Đang phân tích: {url}")
        self._set_status("Đang tải thông tin video...")
        threading.Thread(target=self._fetch_info, args=(url,), daemon=True).start()

    def _fetch_info(self, url):
        opts = {"quiet": True, "no_warnings": True,
                "skip_download": True, "noplaylist": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self._info = info
            self.after(0, self._show_info, info)
        except Exception as e:
            self.after(0, self._log, f"Lỗi phân tích: {e}", COLORS["error"])
            self.after(0, self._set_status, "Lỗi phân tích")

    def _show_info(self, info):
        title   = info.get("title", "Không rõ")
        channel = info.get("channel") or info.get("uploader", "")
        dur     = fmt_time(info.get("duration"))
        views   = info.get("view_count")
        views_s = f"{views:,}" if views else "?"

        self._title_lbl.configure(text=title)
        self._channel_lbl.configure(text=f"📺  {channel}")
        self._dur_lbl.configure(text=f"⏱  {dur}")
        self._views_lbl.configure(text=f"👁  {views_s} lượt xem")

        # Ước tính kích thước
        formats = info.get("formats", [])
        tbr = info.get("tbr") or 0
        approx = (tbr * 1000 / 8 * info.get("duration", 0)) if tbr else None
        self._size_lbl.configure(text=f"💾  ~{fmt_size(approx)}")

        # Thumbnail (nếu có Pillow)
        if PILLOW_OK:
            thumb_url = info.get("thumbnail")
            if thumb_url:
                threading.Thread(target=self._load_thumb,
                                 args=(thumb_url,), daemon=True).start()

        self._log(f"✔  {title}", COLORS["success"])
        self._log(f"   Kênh: {channel}  |  Thời lượng: {dur}  |  Views: {views_s}")
        self._set_status(f"Sẵn sàng tải: {title[:60]}...")

    def _load_thumb(self, url):
        try:
            req = urllib.request.urlopen(url, timeout=8)
            data = req.read()
            img  = Image.open(io.BytesIO(data))
            img  = img.resize((128, 72), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.after(0, lambda: (
                self._thumb_lbl.configure(image=photo, text="",
                                          width=128, height=72),
                setattr(self._thumb_lbl, "_photo", photo)
            ))
        except Exception:
            pass

    # ── TẢI XUỐNG ───────────────────────────────────────────────
    def _build_format_str(self):
        q   = self._quality_var.get()
        fmt = self._format_var.get()

        # Chỉ âm thanh
        if fmt in ("mp3", "m4a", "opus", "flac"):
            return "bestaudio/best"

        # Video
        if "Tốt nhất" in q:
            return f"bestvideo[ext={fmt}]+bestaudio/bestvideo+bestaudio/best"

        h = re.sub(r"\D.*", "", q)  # lấy số đầu
        if h:
            return (f"bestvideo[height<={h}][ext={fmt}]+bestaudio"
                    f"/bestvideo[height<={h}]+bestaudio"
                    f"/best[height<={h}]/best")
        return "best"

    def _build_ydl_opts(self):
        fmt    = self._format_var.get()
        savedir= self._save_dir.get()
        outtmpl= os.path.join(savedir, "%(title)s.%(ext)s")
        speed  = self._speed_var.get()

        post_proc = []
        if fmt in ("mp3", "m4a", "opus", "flac"):
            post_proc.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": "0",
            })
        else:
            post_proc.append({"key": "FFmpegVideoConvertor",
                               "preferedformat": fmt})

        opts = {
            "format":           self._build_format_str(),
            "outtmpl":          outtmpl,
            "noplaylist":       not self._playlist.get(),
            "writesubtitles":   self._subtitles.get(),
            "subtitleslangs":   [self._sub_lang.get()],
            "subtitlesformat":  "srt",
            "postprocessors":   post_proc,
            "merge_output_format": fmt if fmt not in ("mp3","m4a","opus","flac") else None,
            "progress_hooks":   [self._progress_hook],
            "quiet":            True,
            "no_warnings":      False,
            # ── Fix for HTTP 416 errors ──────────────────────────
            "socket_timeout":   30,
            "http_headers":     {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            "retries":          5,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            # ─────────────────────────────────────────────────────
        }

        if speed and speed != "Không giới hạn" and speed != "0":
            opts["ratelimit"] = speed

        return opts

    def _start_download(self):
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thiếu link", "Vui lòng nhập link YouTube.")
            return
        if self._dl_thread and self._dl_thread.is_alive():
            messagebox.showinfo("Đang tải", "Đang có tác vụ tải, vui lòng chờ.")
            return
        if not os.path.isdir(self._save_dir.get()):
            try:
                os.makedirs(self._save_dir.get())
            except Exception as e:
                messagebox.showerror("Lỗi thư mục", str(e))
                return

        self._cancelled = False
        self._pbar["value"] = 0
        self._prog_lbl.configure(text="Đang chuẩn bị...")
        self._speed_lbl.configure(text="")
        self._log(f"▶ Bắt đầu tải: {url}")
        self._set_status("Đang tải...")

        self._dl_thread = threading.Thread(
            target=self._download_worker, args=(url,), daemon=True)
        self._dl_thread.start()

    def _download_worker(self, url):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries and not self._cancelled:
            try:
                opts = self._build_ydl_opts()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                if not self._cancelled:
                    # Sau khi tải xong, kiểm tra xem có cắt video không
                    if FFMPEG_OK and self._trim_enabled.get() and self._last_file:
                        self.after(0, self._trim_video, self._last_file)
                    else:
                        self.after(0, self._on_done)
                return  # Success
            except yt_dlp.utils.DownloadCancelled:
                self.after(0, self._on_cancelled)
                return
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                
                # Check if error is retriable
                is_network_error = any(err in error_msg.lower() 
                                      for err in ["416", "connection", "timeout", "reset"])
                
                if is_network_error and retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff: 2s, 4s, 8s
                    self.after(0, self._log, 
                              f"⚠ Lỗi tạm thời ({retry_count}/{max_retries}). Thử lại sau {wait_time}s...",
                              COLORS["warning"])
                    time.sleep(wait_time)
                else:
                    self.after(0, self._on_error, error_msg)
                    return

    def _progress_hook(self, d):
        if self._cancelled:
            raise yt_dlp.utils.DownloadCancelled()

        status = d.get("status")
        if status == "downloading":
            total     = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded= d.get("downloaded_bytes", 0)
            speed     = d.get("speed") or 0
            eta       = d.get("eta") or 0
            pct       = (downloaded / total * 100) if total else 0
            filename  = os.path.basename(d.get("filename", ""))
            speed_s   = f"{fmt_size(speed)}/s" if speed else "—"
            eta_s     = fmt_time(eta) if eta else "—"

            self.after(0, lambda: (
                self._pbar.configure(value=pct),
                self._prog_lbl.configure(
                    text=f"{pct:.1f}%  —  {fmt_size(downloaded)} / {fmt_size(total) if total else '?'}  —  {filename[:50]}"),
                self._speed_lbl.configure(
                    text=f"Tốc độ: {speed_s}   ETA: {eta_s}")
            ))

        elif status == "finished":
            filename = os.path.basename(d.get("filename", ""))
            filepath = d.get("filename", "")
            # Store the file path for potential trimming
            if filepath:
                self._last_file = filepath
            self.after(0, lambda: (
                self._pbar.configure(value=100),
                self._prog_lbl.configure(
                    text=f"Đang xử lý hậu kỳ... {filename[:50]}"),
                self._log(f"⬇ Đã tải xong: {filename}", COLORS["success"])
            ))

    def _on_done(self):
        self._pbar["value"] = 100
        if self._trim_enabled.get():
            self._prog_lbl.configure(
                text="✔ Tải và cắt hoàn tất!", fg=COLORS["success"])
            self._log("✔ Tài và cắt video hoàn tất!", COLORS["success"])
            message = f"Tải xuống và cắt video thành công!\n\nĐã lưu vào:\n{self._save_dir.get()}"
        else:
            self._prog_lbl.configure(
                text="✔ Tải hoàn tất!", fg=COLORS["success"])
            self._log("✔ Tất cả đã tải xong!", COLORS["success"])
            message = f"Đã lưu vào:\n{self._save_dir.get()}"
        self._set_status("Hoàn tất")
        messagebox.showinfo("Xong!", message)

    def _on_cancelled(self):
        self._prog_lbl.configure(text="✕ Đã hủy", fg=COLORS["warning"])
        self._log("✕ Đã hủy tải xuống", COLORS["warning"])
        self._set_status("Đã hủy")

    def _on_error(self, msg):
        # Analyze error and provide helpful suggestions
        error_lower = msg.lower()
        suggestion = ""
        
        if "416" in msg or "range not satisfiable" in error_lower:
            suggestion = "\n[💡 Gợi ý] Lỗi phạm vi. Thử tải lại hoặc kiểm tra URL."
        elif "10054" in msg or "connection was forcibly closed" in error_lower:
            suggestion = "\n[💡 Gợi ý] Kết nối bị ngắt. Đợi vài giây rồi thử lại."
        elif "age-restricted" in error_lower:
            suggestion = "\n[💡 Gợi ý] Video bị giới hạn độ tuổi. Đăng nhập YouTube hoặc thử video khác."
        elif "not available" in error_lower or "removed" in error_lower:
            suggestion = "\n[💡 Gợi ý] Video không khả dụng hoặc đã bị xóa."
        elif "403" in msg or "forbidden" in error_lower:
            suggestion = "\n[💡 Gợi ý] Truy cập bị từ chối. Video có thể bị địa phương hóa hoặc yêu cầu đăng nhập."
        
        self._prog_lbl.configure(text=f"Lỗi: {msg[:80]}", fg=COLORS["error"])
        self._log(f"✗ Lỗi: {msg}{suggestion}", COLORS["error"])
        self._set_status("Lỗi")

    def _trim_existing_video(self):
        """Cắt video từ file có sẵn."""
        if not FFMPEG_OK:
            messagebox.showerror("Lỗi", "ffmpeg chưa cài. Không thể cắt video.")
            return
        
        filepath = self._trim_file_var.get().strip()
        if not filepath or not os.path.isfile(filepath):
            messagebox.showwarning("Thiếu file", "Vui lòng chọn file video hợp lệ.")
            return
        
        self._pbar["value"] = 0
        self._prog_lbl.configure(text="⏱ Đang cắt video...", fg=COLORS["warning"])
        self._log(f"🎬 Bắt đầu cắt video: {os.path.basename(filepath)}", COLORS["warning"])
        self._set_status("Đang cắt video...")
        
        self._dl_thread = threading.Thread(
            target=self._trim_existing_worker, args=(filepath,), daemon=True)
        self._dl_thread.start()

    def _trim_video(self, filepath):
        """Cắt video bằng ffmpeg (chạy trong thread)."""
        self._prog_lbl.configure(text="⏱ Đang cắt video...", fg=COLORS["warning"])
        self._log(f"🎬 Bắt đầu cắt video: {os.path.basename(filepath)}", COLORS["warning"])
        self._set_status("Đang cắt video...")
        
        self._dl_thread = threading.Thread(
            target=self._trim_worker, args=(filepath,), daemon=True)
        self._dl_thread.start()

    def _trim_existing_worker(self, filepath):
        """Worker function cho cắt video từ file có sẵn."""
        try:
            start_sec = parse_time_to_seconds(self._trim_file_start.get())
            end_sec   = parse_time_to_seconds(self._trim_file_end.get())
            self._perform_trim(filepath, start_sec, end_sec, is_from_download=False)
        except Exception as e:
            self.after(0, self._on_error, f"Lỗi cắt video: {str(e)}")

    def _trim_worker(self, filepath):
        """Worker function cho việc cắt video."""
        try:
            start_sec = parse_time_to_seconds(self._trim_start.get())
            end_sec   = parse_time_to_seconds(self._trim_end.get())
            self._perform_trim(filepath, start_sec, end_sec, is_from_download=True)
            self._perform_trim(filepath, start_sec, end_sec, is_from_download=True)
        except Exception as e:
            self.after(0, self._on_error, f"Lỗi cắt video: {str(e)}")

    def _perform_trim(self, filepath, start_sec, end_sec, is_from_download=False):
        """Thực hiện cắt video (dùng chung cho cả 2 hàm trim)."""
        if start_sec is None and end_sec is None:
            self.after(0, self._log, "⚠ Không có thời gian bắt đầu/kết thúc. Bỏ qua cắt video.", COLORS["warning"])
            if is_from_download:
                self.after(0, self._on_done)
            return
        
        # Tạo file output
        base, ext = os.path.splitext(filepath)
        custom_name = self._trim_file_output_name.get().strip() if not is_from_download else ""
        
        if custom_name:
            # Nếu người dùng nhập tên tùy chỉnh
            if not custom_name.endswith(ext):
                output_path = os.path.join(os.path.dirname(filepath), custom_name + ext)
            else:
                output_path = os.path.join(os.path.dirname(filepath), custom_name)
        else:
            # Tên mặc định
            output_path = f"{base}_trimmed{ext}"
        
        # Build ffmpeg command
        cmd = ["ffmpeg", "-i", filepath]
        
        # Add start time if specified
        if start_sec is not None:
            cmd.extend(["-ss", str(start_sec)])
        
        # Add end time / duration
        if end_sec is not None and start_sec is not None:
            duration = end_sec - start_sec
            cmd.extend(["-t", str(duration)])
        elif end_sec is not None:
            cmd.extend(["-to", str(end_sec)])
        
        # Copy codecs without re-encoding (faster)
        cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        cmd.extend(["-y", output_path])  # -y to overwrite without asking
        
        self.after(0, self._log, f"🔧 Sử dụng ffmpeg...", COLORS["muted"])
        
        # Run ffmpeg
        result = subprocess.run(cmd, capture_output=True, text=True, 
                               encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            # Success - delete original and rename trimmed
            try:
                os.remove(filepath)
                os.rename(output_path, filepath)
                self.after(0, self._log, f"✔ Cắt video thành công!", COLORS["success"])
                if is_from_download:
                    self.after(0, self._on_done)
                else:
                    messagebox.showinfo("Thành công", f"File đã cắt và lưu tại:\n{filepath}")
                    self.after(0, self._set_status, "Hoàn tất")
                    self.after(0, lambda: self._trim_file_output_name.set(""))  # Xóa tên output
            except Exception as e:
                self.after(0, self._log, f"✗ Lỗi xóa/đổi tên file: {e}", COLORS["error"])
                self.after(0, self._log, f"(File đã cắt: {output_path})", COLORS["muted"])
                if is_from_download:
                    self.after(0, self._on_done)
        else:
            # FFmpeg error
            error_msg = result.stderr or result.stdout
            self.after(0, self._log, f"✗ Lỗi FFmpeg: {error_msg[:200]}", COLORS["error"])
            self.after(0, self._on_error, f"Cắt video thất bại: {error_msg[:100]}")

    def _cancel(self):
        if self._dl_thread and self._dl_thread.is_alive():
            self._cancelled = True
            self._log("Đang hủy...", COLORS["warning"])
        else:
            self._log("Không có tác vụ nào đang chạy.")


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
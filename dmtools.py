import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance
from screeninfo import get_monitors
import shutil
import platform
import subprocess
from pathlib import Path

BASE_DIR = "%sbattle-maps"%(os.path.dirname(os.path.abspath(__file__))).split('dmtools')[0]
THUMB_SIZE = (90, 160)

subprocess.run(["git","pull"], cwd=Path(__file__).resolve().parent.parent / "battle-maps")


class MapViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Map Control")

        self.current_dir = BASE_DIR
        self.image_cache = {}
        self.current_image = None

        self.zoom = 1.0

        self.grid_state = tk.IntVar(value=0)
        self.grid_enabled = tk.BooleanVar(value=False)

        self.image_offset_x = tk.IntVar(value=0)
        self.image_offset_y = tk.IntVar(value=0)

        self.setup_ui()
        self.setup_viewer()
        self.load_directory()
        self.selected_image_path = None
        self.is_fullscreen = False
        self.watch_job = None
        self.watching_path = None

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            self.viewer.attributes("-fullscreen", True)
        else:
            self.viewer.attributes("-fullscreen", False)

    def setup_viewer(self):
        self.viewer = tk.Toplevel(self.root)
        self.viewer.configure(bg="black")

        self.viewer.update_idletasks()

        # default fallback = full screen
        screen_w = self.viewer.winfo_screenwidth()
        screen_h = self.viewer.winfo_screenheight()

        x_offset = 0
        y_offset = 0

        try:
            from screeninfo import get_monitors
            monitors = get_monitors()

            if len(monitors) > 1:
                # pick second monitor if available
                m = sorted(monitors, key=lambda m: m.x)[1]
                x_offset = m.x
                y_offset = m.y
                screen_w = m.width
                screen_h = m.height

        except:
            pass  # fallback stays primary screen

        self.view_offset_x = x_offset
        self.view_offset_y = y_offset
        self.view_w = screen_w
        self.view_h = screen_h

        self.viewer.geometry(f"{screen_w}x{screen_h}+{x_offset}+{y_offset}")
        self.viewer.overrideredirect(True)

        self.canvas = tk.Canvas(self.viewer, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def setup_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x")

        ttk.Button(top, text="Up", command=self.go_up).pack(side="left", padx=5, pady=5)

        self.grid_btn = tk.Button(top, text="GRID OFF", bg="red", fg="white",
                                  command=self.cycle_grid, height=2)
        self.grid_btn.pack(side="left", padx=10)

        # Grid controls
        grid_controls = ttk.Frame(self.root)
        grid_controls.pack(fill="x")

        ttk.Button(top, text="Fullscreen", command=self.toggle_fullscreen).pack(side="left", padx=5, pady=5)

        button = tk.Button(top, text="Edit Copy", command=self.copy_and_open_image).pack(side="left", padx=5, pady=5)

        # Zoom controls
        zf = ttk.Frame(grid_controls)
        zf.pack(side="left", padx=10)
        ttk.Label(zf, text="Zoom").pack()
        tk.Button(zf, text="+", command=lambda: self.change_zoom(1.1), width=3, height=2).pack()
        tk.Button(zf, text="-", command=lambda: self.change_zoom(1/1.1), width=3, height=2).pack()
        tk.Button(zf, text="1", command=lambda: self.change_zoom(99), width=3, height=2).pack()

        # Image position offset controls
        of = ttk.Frame(grid_controls)
        of.pack(side="left", padx=10)
        ttk.Label(of, text="Image X Offset").pack()
        tk.Button(of, text="+", command=lambda: self.change_image_offset(10, 0), width=3, height=2).pack()
        tk.Button(of, text="-", command=lambda: self.change_image_offset(-10, 0), width=3, height=2).pack()
        tk.Button(of, text="0", command=lambda: self.change_image_offset(99, 0), width=3, height=2).pack()

        ofy = ttk.Frame(grid_controls)
        ofy.pack(side="left", padx=10)
        ttk.Label(ofy, text="Image Y Offset").pack()
        tk.Button(ofy, text="+", command=lambda: self.change_image_offset(0, 10), width=3, height=2).pack()
        tk.Button(ofy, text="-", command=lambda: self.change_image_offset(0, -10), width=3, height=2).pack()
        tk.Button(ofy, text="0", command=lambda: self.change_image_offset(0, 99), width=3, height=2).pack()

        # Scrollable file view
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        self.scroll_canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.scroll_canvas.yview)

        self.inner_frame = ttk.Frame(self.scroll_canvas)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        )

        self.scroll_canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)

        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def copy_and_open_image(self):
        src_path = self.selected_image_path

        if not src_path:
            print("No image selected")
            return

        if not os.path.exists(src_path):
            print("File not found:", src_path)
            return

        filename = os.path.basename(src_path)

        if "fuckedwith" in filename.lower():
            dst = src_path

        else:
            parent_dir = os.path.dirname(src_path)
            fw_dir = os.path.join(parent_dir, "fuckedwith")

            os.makedirs(fw_dir, exist_ok=True)

            name, ext = os.path.splitext(filename)
            timestamp = time.strftime("%Y%m%d-%H%M")

            new_name = f"{name}-fuckedwith-{timestamp}{ext}"
            dst = os.path.join(fw_dir, new_name)

            shutil.copy2(src_path, dst)

            # switch viewer to new copy
            self.selected_image_path = dst
            self.load_image(dst)
            self.load_directory()

        self.watch_file(dst)

        system = platform.system()

        try:
            subprocess.Popen(["kolourpaint", dst])
        except Exception as e:
            print("Editor launch failed:", e)

        return dst

    def watch_file(self, path):
        if hasattr(self, "watch_job") and self.watch_job:
            self.root.after_cancel(self.watch_job)

        try:
            self.last_mtime = os.path.getmtime(path)
        except:
            return

        self.watching_path = path

        def check():
            try:
                if self.selected_image_path != self.watching_path:
                    return

                mtime = os.path.getmtime(path)
                if mtime != self.last_mtime:
                    self.last_mtime = mtime
                    self.load_image(path)
                    self.load_directory()

            except FileNotFoundError:
                pass

            self.watch_job = self.root.after(1000, check)

        check()

    def cycle_grid(self):
        val = (self.grid_state.get() + 1) % 5
        self.grid_state.set(val)
        if val == 0:
            self.grid_btn.config(text="GRID", bg="red")
        elif val == 1:
            self.grid_btn.config(text="SQR1", bg="grey")
        elif val == 2:
            self.grid_btn.config(text="SQR2", bg="black")
        elif val == 3:
            self.grid_btn.config(text="HEX1", bg="grey")
        else:
            self.grid_btn.config(text="HEX2", bg="black")
        self.redraw()

    def change_zoom(self, factor):
        if factor == 99: self.zoom = 1 
        else:
            self.zoom = max(0.1, min(10.0, self.zoom * factor))
        self.redraw()

    def change_image_offset(self, dx, dy):
        if dx == 99: self.image_offset_x.set(0) 
        elif dy == 99: self.image_offset_y.set(0)
        else:
            self.image_offset_x.set(self.image_offset_x.get() + dx)
            self.image_offset_y.set(self.image_offset_y.get() + dy)
        self.redraw()

    def go_up(self):
        parent = os.path.dirname(self.current_dir)
        if os.path.commonpath([parent, BASE_DIR]) == BASE_DIR:
            self.current_dir = parent
            self.load_directory()

    def enter_dir(self, path):
        self.current_dir = path
        self.load_directory()

    def select_image(self, path):
        self.selected_image_path = path
        self.load_image(path)

    def load_directory(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        items = sorted(os.listdir(self.current_dir))
        ignored = [".git",".gitignore","readme.md","img-convert.py"]
        items = [i for i in items if not any(sub in i.lower() for sub in ignored)]

        row = 0
        col = 0

        for item in items:
            full_path = os.path.join(self.current_dir, item)

            if os.path.isdir(full_path):
                btn = tk.Button(self.inner_frame, text=f"[{item}]",
                                command=lambda p=full_path: self.enter_dir(p),
                                width=13, height=2)
                btn.grid(row=row, column=col, padx=5, pady=5)

                col += 1
                if col > 4:
                    col = 0
                    row += 1

        for item in items:
            full_path = os.path.join(self.current_dir, item)

            if item.lower().endswith((".png", ".jpg", ".jpeg")):
                thumb = self.get_thumbnail(full_path)

                btn = tk.Button(self.inner_frame, image=thumb,
                                command=lambda p=full_path: self.select_image(p))
                btn.image = thumb
                btn.grid(row=row, column=col, padx=5, pady=5)

                col += 1
                if col > 4:
                    col = 0
                    row += 1

    def get_thumbnail(self, path):
        if path in self.image_cache:
            return self.image_cache[path]

        img = Image.open(path)
        img.thumbnail(THUMB_SIZE)
        tk_img = ImageTk.PhotoImage(img)

        self.image_cache[path] = tk_img
        return tk_img

    def load_image(self, path):
        self.current_image = Image.open(path)

        self.redraw()

    def toggle_grid(self):
        val = not self.grid_enabled.get()
        self.grid_enabled.set(val)

        self.grid_btn.config(
            text="GRID ON" if val else "GRID OFF",
            bg="green" if val else "red"
        )
        self.redraw()

    # ------------------------
    # DRAW
    # ------------------------

    def redraw(self):
        if not self.current_image:
            return

        img = self.current_image.copy()
        canvas_w = self.view_w
        canvas_h = self.view_h

        if canvas_w < 10 or canvas_h < 10:
            self.root.after(50, self.redraw)
            return

        imgW, imgH = img.size
        scale = min(canvas_w / imgW, canvas_h / imgH)
        scale *= self.zoom
        newW = max(1, int(imgW * scale))
        newH = max(1, int(imgH * scale))
        img = img.resize((newW, newH), resample=Image.LANCZOS)

        paste_x = (canvas_w - newW) // 2 + self.image_offset_x.get()
        paste_y = (canvas_h - newH) // 2 + self.image_offset_y.get()

        gs_val = self.grid_state.get()

        if gs_val != 0:
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            size = 45 
            ox = 0 
            oy = 0

            # linear grid variants (light/dark)
            if gs_val in (1, 2):
                if gs_val == 1:
                    v = 40
                else:
                    v = 120

                for x in range(ox, canvas_w, size):
                    draw.line((x, 0, x, canvas_h), fill=(255, 255, 255, v))
                for y in range(oy, canvas_h, size):
                    draw.line((0, y, canvas_w, y), fill=(255, 255, 255, v))

            # hex grid variants
            else:
                if gs_val == 3:
                    v = 50
                else:
                    v = 100

                hex_h = size+10
                s = max(3, hex_h // 2)
                horiz = int(1.5 * s)
                vert = int(s * (3**0.5))
                if vert <= 0:
                    vert = s

                start_x = ox - s * 4
                start_y = oy - hex_h * 4

                cols = (canvas_w // horiz) + 6
                rows = (canvas_h // vert) + 6

                def hex_points(cx, cy, s):
                    return [
                        (cx + s, cy),
                        (cx + s/2, cy + s * 0.8660254),
                        (cx - s/2, cy + s * 0.8660254),
                        (cx - s, cy),
                        (cx - s/2, cy - s * 0.8660254),
                        (cx + s/2, cy - s * 0.8660254),
                    ]

                for r in range(-2, rows):
                    for c in range(-2, cols):
                        cx = start_x + c * horiz
                        cy = start_y + r * vert
                        if c % 2:
                            cy += vert // 2
                        pts = hex_points(cx, cy, s)
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        if max(xs) < 0 or min(xs) > canvas_w or max(ys) < 0 or min(ys) > canvas_h:
                            continue
                        draw.line(pts + [pts[0]], fill=(255, 255, 255, v), width=1)

            # paste the resized image onto a black canvas of canvas size at paste_x/paste_y
            bg_mode = "RGBA" if img.mode == "RGBA" else "RGB"
            bg = Image.new(bg_mode, (canvas_w, canvas_h), (0, 0, 0))
            if img.mode == "RGBA":
                bg.paste(img, (paste_x, paste_y), img)
            else:
                bg.paste(img, (paste_x, paste_y))
            # composite grid overlay on top
            img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            newW, newH = canvas_w, canvas_h
            paste_x, paste_y = 0, 0
        else:
            # no grid: paste image onto black canvas so borders exist when zoom < fit
            bg_mode = "RGBA" if img.mode == "RGBA" else "RGB"
            bg = Image.new(bg_mode, (canvas_w, canvas_h), (0, 0, 0))
            if img.mode == "RGBA":
                bg.paste(img, (paste_x, paste_y), img)
                img = bg.convert("RGB")
            else:
                bg.paste(img, (paste_x, paste_y))
                img = bg

        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")


# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()

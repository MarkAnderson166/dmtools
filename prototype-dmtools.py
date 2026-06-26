#!/usr/bin/env python3

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMB_SIZE = (140, 140)


class MapViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("DM Control")

        self.current_dir = BASE_DIR
        self.image_cache = {}
        self.current_image = None

        # Transform state
        self.rotation = 0
        self.mirrored = False
        self.zoom = 1.0            # 1.0 == fullscreen fit
        self.brightness = 1.0      # 1.0 == normal

        # Grid: 0=off,1=light,2=dark
        self.grid_state = tk.IntVar(value=0)
        # Grid state
        self.grid_enabled = tk.BooleanVar(value=False)
        self.grid_size = tk.IntVar(value=45)
        self.grid_offset_x = tk.IntVar(value=0)
        self.grid_offset_y = tk.IntVar(value=0)

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

    # ------------------------
    # SECOND SCREEN
    # ------------------------
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
                m = sorted(monitors, key=lambda m: m.x)[-1]
                x_offset = m.x
                y_offset = m.y
                screen_w = m.width
                screen_h = m.height

        except:
            pass  # fallback stays primary screen

        # store for rendering offsets (IMPORTANT)
        self.view_offset_x = x_offset
        self.view_offset_y = y_offset
        self.view_w = screen_w
        self.view_h = screen_h

        self.viewer.geometry(f"{screen_w}x{screen_h}+{x_offset}+{y_offset}")
        self.viewer.overrideredirect(True)

        self.canvas = tk.Canvas(self.viewer, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    # ------------------------
    # UI
    # ------------------------
    def setup_ui(self):
        # Top controls
        top = ttk.Frame(self.root)
        top.pack(fill="x")

        ttk.Button(top, text="Up", command=self.go_up).pack(side="left", padx=5, pady=5)
        ttk.Button(top, text="Refresh", command=self.load_directory).pack(side="left", padx=5, pady=5)

        ttk.Button(top, text="Rotate", command=self.rotate_image).pack(side="left", padx=5)
        ttk.Button(top, text="Mirror", command=self.mirror_image).pack(side="left", padx=5)

        self.grid_btn = tk.Button(top, text="GRID OFF", bg="red", fg="white",
                                  command=self.cycle_grid, height=2)
        self.grid_btn.pack(side="left", padx=10)

        # Grid controls
        grid_controls = ttk.Frame(self.root)
        grid_controls.pack(fill="x")

        ttk.Button(top, text="Fullscreen", command=self.toggle_fullscreen
        ).pack(side="left", padx=5, pady=5)

        button = tk.Button(
            top,
            text="Edit Copy",
            command=self.copy_and_open_image
        ).pack(side="left", padx=5, pady=5)

        # Zoom controls
        zf = ttk.Frame(grid_controls)
        zf.pack(side="left", padx=10)
        ttk.Label(zf, text="Zoom").pack()
        tk.Button(zf, text="+", command=lambda: self.change_zoom(1.1), width=3, height=2).pack()
        tk.Button(zf, text="-", command=lambda: self.change_zoom(1/1.1), width=3, height=2).pack()

        # Brightness controls
        bf = ttk.Frame(grid_controls)
        bf.pack(side="left", padx=10)
        ttk.Label(bf, text="Brightness").pack()
        tk.Button(bf, text="+", command=lambda: self.change_brightness(1.1), width=3, height=2).pack()
        tk.Button(bf, text="-", command=lambda: self.change_brightness(1/1.1), width=3, height=2).pack()


        def make_adjuster(label, var, step=5):
            frame = ttk.Frame(grid_controls)
            frame.pack(side="left", padx=10)

            ttk.Label(frame, text=label).pack()

            def inc():
                var.set(var.get() + step)
                self.redraw()

            def dec():
                var.set(var.get() - step)
                self.redraw()

            tk.Button(frame, text="+", command=inc, width=3, height=2).pack()
            tk.Button(frame, text="-", command=dec, width=3, height=2).pack()

        make_adjuster("Size", self.grid_size, 3)
        make_adjuster("Offset X", self.grid_offset_x, 6)
        make_adjuster("Offset Y", self.grid_offset_y, 6)

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

        # --- CASE 1: already edited → just open ---
        if "fuckedwith" in filename.lower():
            dst = src_path

        else:
            # --- CASE 2: original → copy into subfolder ---
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

        # --- start watcher ---
        self.watch_file(dst)

        # --- open editor ---
        system = platform.system()

        try:
            if system == "Windows":
                subprocess.Popen(["mspaint", dst])

            elif system == "Linux":
                for editor in ["kolourpaint", "drawing", "mtpaint" ]:
                    try:
                        subprocess.Popen([editor, dst])
                        break
                    except FileNotFoundError:
                        continue

            elif system == "Darwin":
                subprocess.Popen(["open", dst])

        except Exception as e:
            print("Editor launch failed:", e)

        return dst


    def watch_file(self, path):
        # cancel previous watcher if it exists
        if hasattr(self, "watch_job") and self.watch_job:
            self.root.after_cancel(self.watch_job)

        try:
            self.last_mtime = os.path.getmtime(path)
        except:
            return

        self.watching_path = path

        def check():
            try:
                # ignore if user switched images
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
        val = (self.grid_state.get() + 1) % 3
        self.grid_state.set(val)
        if val == 0:
            self.grid_btn.config(text="GRID OFF", bg="red")
        elif val == 1:
            self.grid_btn.config(text="GRID LIGHT", bg="grey")
        else:
            self.grid_btn.config(text="GRID DARK", bg="black")
        self.redraw()

    def change_zoom(self, factor):
        # multiply zoom, clamp between 0.1 and 10
        self.zoom = max(0.1, min(10.0, self.zoom * factor))
        self.redraw()

    def change_brightness(self, factor):
        self.brightness = max(0.1, min(5.0, self.brightness * factor))
        self.redraw()


    # ------------------------
    # DIRECTORY
    # ------------------------
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
        ignored = [".git",".gitignore","readme.md","dndmapcontroller","2.py"]
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
                if col > 2:
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
                if col > 2:
                    col = 0
                    row += 1

    # ------------------------
    # IMAGES
    # ------------------------
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

        self.rotation = 0
        self.mirrored = False

        self.redraw()

    # ------------------------
    # CONTROLS
    # ------------------------
    def toggle_grid(self):
        val = not self.grid_enabled.get()
        self.grid_enabled.set(val)

        self.grid_btn.config(
            text="GRID ON" if val else "GRID OFF",
            bg="green" if val else "red"
        )
        self.redraw()

    def rotate_image(self):
        self.rotation = (self.rotation + 90) % 360
        self.redraw()

    def mirror_image(self):
        self.mirrored = not self.mirrored
        self.redraw()

    # ------------------------
    # DRAW
    # ------------------------

    def redraw(self):
        if not self.current_image:
            return

        img = self.current_image.copy()

        # Apply transforms
        if self.rotation:
            img = img.rotate(self.rotation, expand=True)

        if self.mirrored:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        # Brightness
        if self.brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(self.brightness)

        canvas_w = self.view_w
        canvas_h = self.view_h

        if canvas_w < 10 or canvas_h < 10:
            self.root.after(50, self.redraw)
            return

        # Fit to canvas, then apply zoom
        imgW, imgH = img.size
        scale = min(canvas_w / imgW, canvas_h / imgH)
        # when zoom == 1.0 use scale; otherwise multiply
        scale *= self.zoom
        newW = max(1, int(imgW * scale))
        newH = max(1, int(imgH * scale))
        img = img.resize((newW, newH), resample=Image.LANCZOS)

        # Grid: draw on an overlay of canvas size, then paste centered so grid aligns to canvas
        if self.grid_state.get() != 0:
            # create full-size overlay
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            size = max(5, self.grid_size.get())
            ox = self.grid_offset_x.get()
            oy = self.grid_offset_y.get()

            # color depending on state
            if self.grid_state.get() == 1:
                v = 40   # light grey alpha
            else:
                v = 120  # dark grey alpha

            for x in range(ox, canvas_w, size):
                draw.line((x, 0, x, canvas_h), fill=(255, 255, 255, v))
            for y in range(oy, canvas_h, size):
                draw.line((0, y, canvas_w, y), fill=(255, 255, 255, v))

            # paste the resized image onto a black canvas of canvas size centered
            bg_mode = "RGBA" if img.mode == "RGBA" else "RGB"
            bg = Image.new(bg_mode, (canvas_w, canvas_h), (0, 0, 0))
            paste_x = (canvas_w - newW) // 2
            paste_y = (canvas_h - newH) // 2
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
            paste_x = (canvas_w - newW) // 2
            paste_y = (canvas_h - newH) // 2
            if img.mode == "RGBA":
                bg.paste(img, (paste_x, paste_y), img)
                img = bg.convert("RGB")
            else:
                bg.paste(img, (paste_x, paste_y))
                img = bg

        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        # place at 0,0 since img already full canvas when grid on; otherwise anchored at paste_x,paste_y earlier
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")


# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()

#!/usr/bin/env python3

import os
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
from screeninfo import get_monitors

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

        # Grid state
        self.grid_enabled = tk.BooleanVar(value=False)
        self.grid_size = tk.IntVar(value=45)
        self.grid_offset_x = tk.IntVar(value=0)
        self.grid_offset_y = tk.IntVar(value=0)

        self.setup_ui()
        self.setup_viewer()
        self.load_directory()

    # ------------------------
    # SECOND SCREEN
    # ------------------------
    def setup_viewer(self):
        monitors = get_monitors()

        if len(monitors) > 1:
            m = monitors[1]
        else:
            print("only 1 monitor detected - going to sys.exit()")
            sys.exit()
            m = monitors[0]

        self.viewer = tk.Toplevel(self.root)
        self.viewer.overrideredirect(True)
        self.viewer.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
        self.viewer.configure(bg="black")

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
                                  command=self.toggle_grid, height=2)
        self.grid_btn.pack(side="left", padx=10)

        # Grid controls
        grid_controls = ttk.Frame(self.root)
        grid_controls.pack(fill="x")

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
                                command=lambda p=full_path: self.load_image(p))
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

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 10 or canvas_h < 10:
            self.root.after(50, self.redraw)
            return

        # Stretch to fullscreen
        imgW, imgH = img.size
        scale = min(canvas_w / imgW, canvas_h / imgH)
        newW = max(1, int(imgW * scale))
        newH = max(1, int(imgH * scale))
        img = img.resize((newW, newH))

        # Grid
        if self.grid_enabled.get():
            draw = ImageDraw.Draw(img)

            size = max(5, self.grid_size.get())
            ox = self.grid_offset_x.get()
            oy = self.grid_offset_y.get()

            for x in range(ox, canvas_w, size):
                draw.line((x, 0, x, canvas_h), fill=(255, 255, 255, 10))

            for y in range(oy, canvas_h, size):
                draw.line((0, y, canvas_w, y), fill=(255, 255, 255, 2))

        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(((canvas_w-newW)//2),((canvas_h - newH )//2), image=self.tk_img, anchor="nw")


# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()

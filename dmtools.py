import math
import os
import sys
import time
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance
import shutil
import platform
import subprocess
from pathlib import Path

BASE_DIR = "%sbattle-maps"%os.path.dirname(os.path.abspath(__file__)).split('dmtools')[0]
THUMB_SIZE = (90, 160)

subprocess.run(["git","pull"], cwd=Path(__file__).resolve().parent.parent / "battle-maps")


class MapViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Map Control")
        self.root.geometry("570x600")
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

        self.highlight_mode = tk.StringVar(value="square")
        self.highlights = []
        self._dragging = False
        self._drag_start = None
        self._drag_preview = None

        self.canvas.bind("<Button-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<Button-3>", self.on_right_click)

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

        screen_w = self.viewer.winfo_screenwidth()
        screen_h = self.viewer.winfo_screenheight()

        x_offset = 0
        y_offset = 0

        try:
            from screeninfo import get_monitors
            monitors = get_monitors()
            if len(monitors) > 1:
                # pick second monitor if available
                m = sorted(monitors, key=lambda m: m.x)[0]
                x_offset = m.x
                y_offset = m.y
                screen_w = m.height#width
                screen_h = m.width#height
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

        # Zoom and offset  controls
        adj_frame = tk.Frame(self.root)
        adj_frame.pack(side = "left", padx=10, pady=10)
        tk.Button(adj_frame, text="Z+", command=lambda: self.change_zoom(1.1), width=3, height=2).pack()
        tk.Button(adj_frame, text="Z-", command=lambda: self.change_zoom(1/1.1), width=3, height=2).pack()
        tk.Button(adj_frame, text="Z=", command=lambda: self.change_zoom(99), width=3, height=2).pack()
        tk.Button(adj_frame, text="X+", command=lambda: self.change_image_offset(10, 0), width=3, height=2).pack()
        tk.Button(adj_frame, text="X-", command=lambda: self.change_image_offset(-10, 0), width=3, height=2).pack()
        tk.Button(adj_frame, text="X=", command=lambda: self.change_image_offset(99, 0), width=3, height=2).pack()
        tk.Button(adj_frame, text="Y+", command=lambda: self.change_image_offset(0, 10), width=3, height=2).pack()
        tk.Button(adj_frame, text="Y-", command=lambda: self.change_image_offset(0, -10), width=3, height=2).pack()
        tk.Button(adj_frame, text="Y=", command=lambda: self.change_image_offset(0, 99), width=3, height=2).pack()

        # System controls
        butt_frame = tk.Frame(self.root)
        butt_frame.pack(pady=10)

        tk.Button(butt_frame, text="Back", command=self.go_up, width=10, height=2).pack(padx=5, pady=5, side="left")
        self.grid_btn = tk.Button(butt_frame, text="Grid", command=self.cycle_grid, width=4, height=2)
        self.grid_btn.pack(padx=5, pady=5, side="left")

        tk.Button(butt_frame,text="Fullscreen",command=self.toggle_fullscreen,width=7,height=2).pack(padx=5,pady=5, side="left")
        tk.Button(butt_frame,text="Edit",command=self.copy_and_open_image,width=4,height=2).pack(padx=5,pady=5, side="left")

        self.shape_btn = tk.Button(butt_frame, text="Square", command=self.cycle_highlight_mode, width=7, height=2)
        self.shape_btn.pack(padx=5, pady=5, side="left")
        self.shape_btn.config(text="[]", bg="yellow")

        # Scrollable file view
        container = tk.Frame(self.root)
        container.pack(side="right", fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.scroll_canvas.yview)
        self.inner_frame = tk.Frame(self.scroll_canvas)
        self.inner_frame.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))
        self.scroll_canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        scrollbar.configure(width=20)

    def cycle_highlight_mode(self):
        order = ["square", "circle", "cone"]
        cur = order.index(self.highlight_mode.get())
        nxt = order[(cur + 1) % len(order)]
        if nxt=="square":self.shape_btn.config(text="[]", bg="yellow")
        if nxt=="circle":self.shape_btn.config(text="O", bg="red")
        if nxt=="cone":self.shape_btn.config(text="V", bg="teal")
        self.highlight_mode.set(nxt)

        self.redraw()

    def on_left_down(self, event):
        self._dragging = True
        self._drag_start = (event.x, event.y)
        self._drag_preview = self._make_shape_preview(
            shape_type=self.highlight_mode.get(),
            start_xy=self._drag_start,
            end_xy=(event.x, event.y)
        )
        self.redraw()

    def on_left_drag(self, event):
        if not self._dragging:
            return
        end_xy = (event.x, event.y)
        self._drag_preview = self._make_shape_preview(
            shape_type=self.highlight_mode.get(),
            start_xy=self._drag_start,
            end_xy=end_xy
        )
        self.redraw()

    def on_left_up(self, event):
        if not self._dragging:
            return
        self._dragging = False

        if self._drag_preview and self._shape_has_area(self._drag_preview):
            self.highlights.append(self._drag_preview)

        self._drag_preview = None
        self._drag_start = None
        self.redraw()

    def on_right_click(self, event):
        x, y = event.x, event.y

        idx_to_remove = None
        for i in range(len(self.highlights) - 1, -1, -1):
            if self._point_in_shape(x, y, self.highlights[i]):
                idx_to_remove = i
                break

        if idx_to_remove is not None:
            self.highlights.pop(idx_to_remove)
            self.redraw()

    def _make_shape_preview(self, shape_type, start_xy, end_xy):
        x0, y0 = start_xy
        x1, y1 = end_xy

        # RGBA for PIL drawing: (R,G,B,A)
        fill = (255, 255, 0, 80)
        outline = (255, 255, 200, 160)
        if shape_type == "cone":
            fill = (0, 200, 255, 70)
            outline = (180, 240, 255, 160)

        if shape_type == "square":
            left = min(x0, x1)
            right = max(x0, x1)
            top = min(y0, y1)
            bottom = max(y0, y1)
            return {
                "type": "square",
                "bbox": (left, top, right, bottom),
                "fill": fill,
                "outline": outline
            }

        if shape_type == "circle":
            fill = (255, 100, 100, 70)
            outline = (255, 240, 255, 160)
            cx = x0
            cy = y0
            r = math.hypot(x1 - x0, y1 - y0)
            return {
                "type": "circle",
                "center": (cx, cy),
                "r": r,
                "fill": fill,
                "outline": outline
            }

        ax, ay = x0, y0
        dx, dy = (x1 - x0, y1 - y0)
        dist = math.hypot(dx, dy)
        if dist < 1:
            dist = 1

        ang = math.atan2(dy, dx)

        aperture_deg = 53
        half = math.radians(aperture_deg / 2)

        length = dist  
        s = length

        a1 = ang - half
        a2 = ang + half

        p1 = (ax + math.cos(a1) * s, ay + math.sin(a1) * s)
        p2 = (ax + math.cos(a2) * s, ay + math.sin(a2) * s)

        return {
            "type": "cone",
            "apex": (ax, ay),
            "p1": p1,
            "p2": p2,
            "fill": fill,
            "outline": outline
        }

    def _shape_has_area(self, shape):
        if shape["type"] == "square":
            l, t, r, b = shape["bbox"]
            return (r - l) >= 3 and (b - t) >= 3
        if shape["type"] == "circle":
            return shape["r"] >= 3
        if shape["type"] == "cone":
            ax, ay = shape["apex"]
            p1x, p1y = shape["p1"]
            p2x, p2y = shape["p2"]
            area = abs((p1x-ax)*(p2y-ay) - (p1y-ay)*(p2x-ax)) * 0.5
            return area >= 10
        return False

    def _point_in_shape(self, x, y, shape):
        if shape["type"] == "square":
            l, t, r, b = shape["bbox"]
            return (l <= x <= r) and (t <= y <= b)

        if shape["type"] == "circle":
            cx, cy = shape["center"]
            return (x - cx) ** 2 + (y - cy) ** 2 <= (shape["r"] ** 2)

        if shape["type"] == "cone":
            # point-in-triangle for apex + p1 + p2
            ax, ay = shape["apex"]
            bx, by = shape["p1"]
            cx, cy = shape["p2"]
            return self._point_in_triangle(x, y, ax, ay, bx, by, cx, cy)

        return False

    def _point_in_triangle(self, px, py, x1, y1, x2, y2, x3, y3):
        # barycentric technique
        def sign(xa, ya, xb, yb, xc, yc):
            return (xa - xc) * (yb - yc) - (xb - xc) * (ya - yc)

        b1 = sign(px, py, x1, y1, x2, y2) < 0.0
        b2 = sign(px, py, x2, y2, x3, y3) < 0.0
        b3 = sign(px, py, x3, y3, x1, y1) < 0.0
        return (b1 == b2) and (b2 == b3)

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

        # Start with base composited image (plus black padding)
        if img.mode == "RGBA":
            bg = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
            bg.paste(img, (paste_x, paste_y), img)
        else:
            bg = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
            bg.paste(img, (paste_x, paste_y))
            bg = bg.convert("RGBA")

        # grid overlay
        if gs_val != 0:
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            size = 45
            ox = 0
            oy = 0

            if gs_val in (1, 2):
                v = 40 if gs_val == 1 else 120
                for x in range(ox, canvas_w, size):
                    draw.line((x, 0, x, canvas_h), fill=(255, 255, 255, v))
                for y in range(oy, canvas_h, size):
                    draw.line((0, y, canvas_w, y), fill=(255, 255, 255, v))
            else:
                v = 50 if gs_val == 3 else 100
                hex_h = size + 10
                s = max(3, hex_h // 2)
                horiz = int(1.5 * s)
                vert = int(s * (3 ** 0.5))
                if vert <= 0:
                    vert = s

                start_x = ox - s * 4
                start_y = oy - hex_h * 4

                def hex_points(cx, cy, s):
                    return [
                        (cx + s, cy),
                        (cx + s/2, cy + s * 0.8660254),
                        (cx - s/2, cy + s * 0.8660254),
                        (cx - s, cy),
                        (cx - s/2, cy - s * 0.8660254),
                        (cx + s/2, cy - s * 0.8660254),
                    ]

                cols = (canvas_w // horiz) + 6
                rows = (canvas_h // vert) + 6

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

            bg = Image.alpha_composite(bg, overlay)

        # Composite highlights (including preview)
        hl_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl_layer)

        def draw_shape(shape):
            if shape["type"] == "square":
                l, t, r, b = shape["bbox"]
                hd.rectangle([l, t, r, b], fill=shape["fill"], outline=shape["outline"])
            elif shape["type"] == "circle":
                cx, cy = shape["center"]
                r = shape["r"]
                hd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shape["fill"], outline=shape["outline"])
            elif shape["type"] == "cone":
                ax, ay = shape["apex"]
                p1 = shape["p1"]
                p2 = shape["p2"]
                hd.polygon([(ax, ay), p1, p2], fill=shape["fill"], outline=shape["outline"])

        for h in self.highlights:
            draw_shape(h)
        if self._drag_preview:
            draw_shape(self._drag_preview)

        bg = Image.alpha_composite(bg, hl_layer).convert("RGB")

        self.tk_img = ImageTk.PhotoImage(bg)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")


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
                btn = tk.Button(self.inner_frame, text=f"{item}",
                                command=lambda p=full_path: self.enter_dir(p),
                                width=10, height=2)
                btn.grid(row=row, column=col, padx=5, pady=5)

                col += 1
                if col > 3:
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
                if col > 3:
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

    def cycle_grid(self):
        val = (self.grid_state.get() + 1) % 5
        self.grid_state.set(val)
        if val == 0:
            self.grid_btn.config(text="Grid")
        elif val == 1:
            self.grid_btn.config(text="Sqr1")
        elif val == 2:
            self.grid_btn.config(text="Sqr2")
        elif val == 3:
            self.grid_btn.config(text="Hex1")
        else:
            self.grid_btn.config(text="Hex2")
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

            self.selected_image_path = dst
            self.load_image(dst)
            self.load_directory()

        self.watch_file(dst)

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


if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()

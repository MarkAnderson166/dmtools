import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
from screeninfo import get_monitors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

THUMB_SIZE = (120, 120)

class MapViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("DM Control")

        self.current_dir = BASE_DIR
        self.image_cache = {}
        self.current_image = None

        # Grid settings
        self.grid_enabled = tk.BooleanVar(value=False)
        self.grid_size = tk.IntVar(value=50)
        self.grid_offset_x = tk.IntVar(value=0)
        self.grid_offset_y = tk.IntVar(value=0)

        self.setup_ui()
        self.setup_viewer()
        self.load_directory()

    # ------------------------
    # SECOND SCREEN WINDOW
    # ------------------------
    def setup_viewer(self):
        monitors = get_monitors()

        if len(monitors) > 1:
            m = monitors[1]
        else:
            m = monitors[0]

        self.viewer = tk.Toplevel(self.root)
        self.viewer.overrideredirect(True)
        self.viewer.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
        self.viewer.configure(bg="black")

        self.canvas = tk.Canvas(self.viewer, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    # ------------------------
    # MAIN UI
    # ------------------------
    def setup_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x")

        ttk.Button(top, text="⬆ Up", command=self.go_up).pack(side="left")
        ttk.Button(top, text="🔄 Refresh", command=self.load_directory).pack(side="left")

        # Grid controls
        ttk.Checkbutton(top, text="Grid", variable=self.grid_enabled, command=self.redraw).pack(side="left")

        ttk.Label(top, text="Size").pack(side="left")
        ttk.Entry(top, textvariable=self.grid_size, width=5).pack(side="left")

        ttk.Label(top, text="Offset X").pack(side="left")
        ttk.Entry(top, textvariable=self.grid_offset_x, width=5).pack(side="left")

        ttk.Label(top, text="Offset Y").pack(side="left")
        ttk.Entry(top, textvariable=self.grid_offset_y, width=5).pack(side="left")

        ttk.Button(top, text="Apply Grid", command=self.redraw).pack(side="left")

        # Scrollable area
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill="both", expand=True)

        self.scroll_canvas = tk.Canvas(self.canvas_frame)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.scroll_canvas.yview)

        self.inner_frame = ttk.Frame(self.scroll_canvas)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        )

        self.scroll_canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    # ------------------------
    # DIRECTORY NAVIGATION
    # ------------------------
    def go_up(self):
        parent = os.path.dirname(self.current_dir)
        if os.path.commonpath([parent, BASE_DIR]) == BASE_DIR:
            self.current_dir = parent
            self.load_directory()

    def load_directory(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        items = sorted(os.listdir(self.current_dir))

        row = 0
        col = 0

        for item in items:
            full_path = os.path.join(self.current_dir, item)

            if os.path.isdir(full_path):
                btn = ttk.Button(self.inner_frame, text=f"[{item}]", command=lambda p=full_path: self.enter_dir(p))
                btn.grid(row=row, column=col, padx=5, pady=5)

            elif item.lower().endswith((".png", ".jpg", ".jpeg")):
                thumb = self.get_thumbnail(full_path)

                btn = tk.Button(self.inner_frame, image=thumb, command=lambda p=full_path: self.load_image(p))
                btn.image = thumb
                btn.grid(row=row, column=col, padx=5, pady=5)

            col += 1
            if col > 5:
                col = 0
                row += 1

    def enter_dir(self, path):
        self.current_dir = path
        self.load_directory()

    # ------------------------
    # IMAGE HANDLING
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
        self.redraw()

    # ------------------------
    # DRAWING
    # ------------------------
    def redraw(self):
        if not self.current_image:
            return

        img = self.current_image.copy()

        if self.grid_enabled.get():
            draw = ImageDraw.Draw(img)

            w, h = img.size
            size = self.grid_size.get()
            ox = self.grid_offset_x.get()
            oy = self.grid_offset_y.get()

            for x in range(ox, w, size):
                draw.line((x, 0, x, h), fill=(255, 255, 255, 120))

            for y in range(oy, h, size):
                draw.line((0, y, w, y), fill=(255, 255, 255, 120))

        self.tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")

        self.canvas.create_image(
            self.canvas.winfo_width() // 2,
            self.canvas.winfo_height() // 2,
            image=self.tk_img,
            anchor="center"
        )

    # ------------------------
    # START
    # ------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()

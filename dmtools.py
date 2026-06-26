# ------------------------------------------------------------
# --------- Mark Anderson ------------------------------------
# ------------------------------------------------------------

from random import randint
import os
import sys
import time
import json
import shutil
import platform
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw, ImageEnhance
from screeninfo import get_monitors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = "%sbattle-maps"%BASE_DIR.split('dmtools')[0]

THUMB_SIZE = (90, 160)

class MainApplication(tk.Tk):

  def __init__(self):
    super().__init__()
    self.title("DM Tools")
    self.geometry("800x670")
    #self.attributes('-topmost', True)
    self.configure(bg='#222')
    self.turn_index = 0
    self.highlight_tag = "highlight"

    self.current_dir = BASE_DIR
    self.image_cache = {}
    self.current_image = None

    self.rotation = 0
    self.mirrored = False
    self.zoom = 1.0
    self.brightness = 1.0

    self.grid_state = tk.IntVar(value=0)
    self.grid_enabled = tk.BooleanVar(value=False)
    self.grid_size = tk.IntVar(value=45)
    self.grid_offset_x = tk.IntVar(value=0)
    self.grid_offset_y = tk.IntVar(value=0)

    self.image_offset_x = tk.IntVar(value=0)
    self.image_offset_y = tk.IntVar(value=0)

    self.setup_ui()
    self.setup_viewer()
    self.load_directory()
    self.selected_image_path = None
    self.is_fullscreen = False
    self.watch_job = None
    self.watching_path = None
    self.load()

  # ------------------------------------
  # -------- map control funcs ---------
  #-------------------------------------

  def toggle_fullscreen(self):
    self.is_fullscreen = not self.is_fullscreen
    if self.is_fullscreen:
      self.viewer.attributes("-fullscreen", True)
    else:
      self.viewer.attributes("-fullscreen", False)

  def setup_viewer(self):
    self.viewer = tk.Toplevel(self)
    self.viewer.configure(bg="black")

    self.viewer.update_idletasks()

    # default fallback = full screen
    screen_w = self.viewer.winfo_screenwidth()
    screen_h = self.viewer.winfo_screenheight()

    x_offset = 0
    y_offset = 0
    '''
    try:
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
    '''

    self.view_offset_x = x_offset
    self.view_offset_y = y_offset
    self.view_w = screen_w
    self.view_h = screen_h

    self.viewer.geometry(f"{screen_w}x{screen_h}+{x_offset}+{y_offset}")
    self.viewer.overrideredirect(True)

    self.canvas = tk.Canvas(self.viewer, bg="black", highlightthickness=0)
    self.canvas.pack(fill="both", expand=True)


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
      self.grid_btn.config(text="GRID OFF", bg="red")
    elif val == 1:
      self.grid_btn.config(text="GRID LIGHT", bg="grey")
    elif val == 2:
      self.grid_btn.config(text="GRID DARK", bg="black")
    elif val == 3:
      self.grid_btn.config(text="GRID HEX-LIGHT", bg="grey")
    else:
      self.grid_btn.config(text="GRID HEX-DARK", bg="black")
    self.redraw()

  def change_zoom(self, factor):
    self.zoom = max(0.1, min(10.0, self.zoom * factor))
    self.redraw()

  def change_brightness(self, factor):
    self.brightness = max(0.1, min(5.0, self.brightness * factor))
    self.redraw()

  def change_image_offset(self, dx, dy):
    self.image_offset_x.set(self.image_offset_x.get() + dx)
    self.image_offset_y.set(self.image_offset_y.get() + dy)
    self.redraw()

  def change_grid_offset(self, dx, dy):
    self.grid_offset_x.set(self.grid_offset_x.get() + dx)
    self.grid_offset_y.set(self.grid_offset_y.get() + dy)
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

    # Calculate paste positions including image offsets (persisted)
    paste_x = (canvas_w - newW) // 2 + self.image_offset_x.get()
    paste_y = (canvas_h - newH) // 2 + self.image_offset_y.get()

    # Grid overlays: if hex variants selected produce hex pattern
    gs_val = self.grid_state.get()

    if gs_val != 0:
      # create full-size overlay
      overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
      draw = ImageDraw.Draw(overlay)
      size = max(5, self.grid_size.get())
      ox = self.grid_offset_x.get()
      oy = self.grid_offset_y.get()

      # linear grid variants (light/dark)
      if gs_val in (1, 2):
        if gs_val == 1:
          v = 40   # light grey alpha
        else:
          v = 120  # dark grey alpha

        for x in range(ox, canvas_w, size):
          draw.line((x, 0, x, canvas_h), fill=(255, 255, 255, v))
        for y in range(oy, canvas_h, size):
          draw.line((0, y, canvas_w, y), fill=(255, 255, 255, v))

      # hex grid variants
      else:
        if gs_val == 3:
          v = 40
        else:
          v = 120

        # draw hex grid: approximate by drawing hexagon lines tiled in a staggered grid
        hex_h = size
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
    # place at 0,0 since img already full canvas when grid on; otherwise anchored at paste_x,paste_y earlier
    self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")



  # ------------------------------------
  # ------------ UI funcs --------------
  #-------------------------------------

  def setup_ui(self):

    button_values = [1, 5, 10, 15, 20, 25]
    padding = 3
    width = 4
    fontsize = 22

    self.style = ttk.Style()
    self.style.theme_use("clam")
    self.style.configure('TButton', background='#522', foreground='#bbb', relief='flat',font=("Arial", fontsize-4), width=width)
    self.style.map('TButton', background=[('active', '#555')])

    self.style.configure("Custom.TEntry", fieldbackground="#000", foreground="#aaa",bordercolor="#312",lightcolor="#000",darkcolor="#000",borderwidth=4,relief="flat")
    self.style.map("Custom.TEntry",fieldbackground=[('focus','#353')])

    self.style.configure("Selected.TEntry", fieldbackground="#444", foreground="#fff" )
    self.style.configure("Turn.TEntry", fieldbackground="#262", foreground="#fff" )

    self.style.configure("Highlighted.TEntry", fieldbackground="#353", foreground="#fff", bordercolor="#312",relief="flat", padding=0)

      # init textboxes
    self.text_boxes = []
    for i in range(14):
      entry = ttk.Entry(self, width=12, font=("Arial", fontsize), style="Custom.TEntry")
      entry.grid(row=i, column=2, padx=padding, pady=padding)
      setattr(self, f'text_box{i+1}', entry)
      self.text_boxes.append(entry)
      entry.bind("<Button-1>", lambda e, ent=entry: self.set_current_textbox(ent))

      # init Buttons
    self.sort_button = ttk.Button(self, text="Sort", width=width, command=self.sort_textbox_entries,style="TButton",)
    self.sort_button.grid(row=0, column=0, columnspan=2, padx=padding, pady=padding, sticky="nsew")

    for i, value in enumerate(button_values):
      row = i // 2
      col = i % 2
      button = ttk.Button(self, text=str(value), width=width, command=lambda v=value: self.update_textbox(v), style="TButton")
      button.grid(row=row+2, column=col, padx=padding, pady=padding,sticky="nsew")

    self.up_button = ttk.Button(self, text="+", command=lambda v=-7: self.update_textbox(v),style="TButton")
    self.up_button.grid(row=5, column=1, rowspan=2, padx=padding, pady=padding,sticky="nsew")

    self.down_button = ttk.Button(self,text="-", command=lambda v=-8: self.update_textbox(v),style="TButton")
    self.down_button.grid(row=5, column=0, rowspan=2, padx=padding, pady=padding,sticky="nsew")

    self.roll_button=ttk.Button(self,text="Roll",command=lambda v=-9: self.update_textbox(v),style="TButton")
    self.roll_button.grid(row=7, column=0, padx=padding, pady=padding, columnspan=2, sticky="nsew")

    self.move_up_button = ttk.Button(self, text="^", command=self.move_entry_up, style="TButton")
    self.move_up_button.grid(row=9, column=0, columnspan=1, sticky="nsew", padx=padding, pady=padding)

    self.move_down_button = ttk.Button(self, text="v", command=self.move_entry_down, style="TButton")
    self.move_down_button.grid(row=9, column=1, columnspan=1, sticky="nsew", padx=padding, pady=padding)

    self.next_button = ttk.Button(self, text="Strip", width=width, command=self.strip_numbers, style="TButton",)
    self.next_button.grid(row=10, column=0, rowspan=1, columnspan=2, padx=padding, pady=padding, sticky="nsew")

    self.next_button = ttk.Button(self, text="Next", width=width, command=self.move_next, style="TButton",)
    self.next_button.grid(row=12, column=0, rowspan=2, columnspan=2, padx=padding, pady=padding, sticky="nsew")

    self.selected_value = None
    self.current_entry = None



      # mapcontrol Buttons
    '''
    ttk.Button(self, text="Up", command=self.go_up).pack(side="left", padx=5, pady=5)
    ttk.Button(self, text="Refresh", command=self.load_directory).pack(side="left", padx=5, pady=5)

    ttk.Button(self, text="Rotate", command=self.rotate_image).pack(side="left", padx=5)
    ttk.Button(self, text="Mirror", command=self.mirror_image).pack(side="left", padx=5)

    self.grid_btn = tk.Button(self, text="GRID OFF", bg="red", fg="white",
                              command=self.cycle_grid, height=2)
    self.grid_btn.pack(side="left", padx=10)

    # Grid controls
    grid_controls = ttk.Frame(self.root)
    grid_controls.pack(fill="x")

    ttk.Button(self, text="Fullscreen", command=self.toggle_fullscreen).pack(side="left", padx=5, pady=5)

    button = tk.Button(self, text="Edit Copy", command=self.copy_and_open_image).pack(side="left", padx=5, pady=5)

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

    # Image position offset controls
    of = ttk.Frame(grid_controls)
    of.pack(side="left", padx=10)
    ttk.Label(of, text="Image X Offset").pack()
    tk.Button(of, text="+", command=lambda: self.change_image_offset(10, 0), width=3, height=2).pack()
    tk.Button(of, text="-", command=lambda: self.change_image_offset(-10, 0), width=3, height=2).pack()

    ofy = ttk.Frame(grid_controls)
    ofy.pack(side="left", padx=10)
    ttk.Label(ofy, text="Image Y Offset").pack()
    tk.Button(ofy, text="+", command=lambda: self.change_image_offset(0, 10), width=3, height=2).pack()
    tk.Button(ofy, text="-", command=lambda: self.change_image_offset(0, -10), width=3, height=2).pack()

    # Grid size control (kept simple slider)
    gs = ttk.Frame(grid_controls)
    gs.pack(side="left", padx=10)
    ttk.Label(gs, text="Grid Size").pack()
    size_scale = ttk.Scale(gs, from_=5, to=200, orient="horizontal", variable=self.grid_size, command=lambda e: self.redraw())
    size_scale.pack()

    # Offset X/Y quick adjustments
    offx = ttk.Frame(grid_controls)
    offx.pack(side="left", padx=10)
    ttk.Label(offx, text="Grid Offset X").pack()
    tk.Button(offx, text="+", command=lambda: self.change_grid_offset(6, 0), width=3, height=2).pack()
    tk.Button(offx, text="-", command=lambda: self.change_grid_offset(-6, 0), width=3, height=2).pack()

    offy = ttk.Frame(grid_controls)
    offy.pack(side="left", padx=10)
    ttk.Label(offy, text="Grid Offset Y").pack()
    tk.Button(offy, text="+", command=lambda: self.change_grid_offset(0, 6), width=3, height=2).pack()
    tk.Button(offy, text="-", command=lambda: self.change_grid_offset(0, -6), width=3, height=2).pack()
    '''
    # Scrollable file view
    self.container = tk.Frame(self)
    #container.pack(fill="both", expand=True)
    self.container.grid(row=4, column=3, rowspan=5, columnspan=3, padx=padding, pady=padding, sticky="nsew")



    self.scroll_canvas = tk.Canvas(self.container)
    scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.scroll_canvas.yview)

    self.inner_frame = ttk.Frame(self.scroll_canvas)

    self.inner_frame.bind(
        "<Configure>",
        lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
    )

    self.scroll_canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
    self.scroll_canvas.configure(yscrollcommand=scrollbar.set)

    self.scroll_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")





    def toggle_grid(self):
      val = not self.grid_enabled.get()
      self.grid_enabled.set(val)
    '''
    self.grid_btn.config(
      text="GRID ON" if val else "GRID OFF",
      bg="green" if val else "red"
    )
    '''
    self.redraw()

    def rotate_image(self):
      self.rotation = (self.rotation + 90) % 360
      self.redraw()

    def mirror_image(self):
      self.mirrored = not self.mirrored
      self.redraw()

  # ------------------------------------
  # -------- init tracker funcs --------
  #-------------------------------------

  def set_current_textbox(self, textbox):
    for entry in self.text_boxes:
        entry.configure(style="Custom.TEntry")
    textbox.configure(style="Selected.TEntry")
    self.current_entry = textbox
    self.selected_value = None


  def update_textbox(self, value):
    if not self.current_entry:
      return
    current_value, name = self.get_current_value()
    if value == -9:
      value = randint(1, 20)
    elif value == -8:
      value = current_value -1
    elif value == -7:
      value = current_value +1

    new = f"{value:>2}: {name}"
    self.current_entry.delete(0, tk.END)
    self.current_entry.insert(0, new)
    self.save()


  def get_current_value(self):
    value = 0
    name = ""
    if self.current_entry:
      text = self.current_entry.get().strip()
      if ":" in text:
        parts = text.split(":", 1)
        try:
            value = int(parts[0].strip())
        except ValueError:
            value = 0
        name = parts[1].strip()
      else:
        parts = text.split()
        if parts:
          try:
            value = int(parts[0])
            name = " ".join(parts[1:]).strip()
          except ValueError:
            name = text
    return value, name


  def sort_textbox_entries(self):
    entries = []
    for entry in self.text_boxes:
      text = entry.get().strip()
      if text:
        try:
          number_part = int(text.split(":")[0]) if ":" in text else 0
          entries.append((number_part, text))
        except ValueError:
          continue

    entries.sort(key=lambda x: x[0], reverse=True)

    for i, (num, value) in enumerate(entries):
      self.text_boxes[i].delete(0, tk.END)
      if ":" in value:
        name = value.split(":", 1)[1].strip()
      else:
        parts = value.split()
        name = " ".join(parts).strip()
      formatted = f"{num:>2}: {name}"
      self.text_boxes[i].insert(0, formatted)

    for j in range(len(entries), len(self.text_boxes)):
      self.text_boxes[j].delete(0, tk.END)

    for entry in self.text_boxes:
      entry.configure(style="Custom.TEntry")

    for i, entry in enumerate(self.text_boxes):
      if entry.get().strip():
        entry.configure(style="Turn.TEntry")
        self.turn_index = i
        break
    else:
      self.turn_index = None

    self.current_entry = None
    self.selected_value = None
    self.save()


  def move_next(self):

    non_empty = [i for i, e in enumerate(self.text_boxes) if e.get().strip()]
    if not non_empty:
      return

    if self.turn_index is None or self.turn_index not in non_empty:
      self.turn_index = non_empty[0]
    else:
      idx = non_empty.index(self.turn_index)
      self.turn_index = non_empty[(idx + 1) % len(non_empty)]

    for entry in self.text_boxes:
      entry.configure(style="Custom.TEntry")

    self.text_boxes[self.turn_index].configure(style="Turn.TEntry")
    self.current_entry = None
    self.selected_value = None
    self.save()

  def update_highlighted_box(self):
    for i, entry in enumerate(self.text_boxes):
      if i == self.turn_index:
        entry.configure(style="Highlighted.TEntry")
      else:
        entry.configure(style="Custom.TEntry")

  def save(self):
    data = {
      "entries": [entry.get() for entry in self.text_boxes],
      "turn_index": self.turn_index
    }
    with open("names.txt", "w") as f:
      json.dump(data, f)

  def load(self):
    if not os.path.exists("names.txt"):
      return

    with open("names.txt", "r") as f:
      try:
        data = json.load(f)
      except json.JSONDecodeError:
        return

    entries = data.get("entries", [])
    for entry, text in zip(self.text_boxes, entries):
      entry.delete(0, tk.END)
      entry.insert(0, text)

    self.turn_index = data.get("turn_index", 0)
    self.update_highlighted_box()


  def strip_numbers(self):
    confirm = messagebox.askyesno("Confirm", "Strip all rolls?")
    if not confirm:
      return
    for entry in self.text_boxes:
      text = entry.get().strip()
      if ":" in text:
        parts = text.split(":", 1)
        name = parts[1].strip()
        entry.delete(0, tk.END)
        entry.insert(0, name)
    self.save()


  def move_entry_up(self):
      if not self.current_entry:
        return

      index = None
      for i, entry in enumerate(self.text_boxes):
        if entry == self.current_entry:
          index = i
          break

      if index is not None and index > 0:
        current_text = self.text_boxes[index].get()
        above_text = self.text_boxes[index - 1].get()

        # Swap text
        self.text_boxes[index].delete(0, tk.END)
        self.text_boxes[index].insert(0, above_text)

        self.text_boxes[index - 1].delete(0, tk.END)
        self.text_boxes[index - 1].insert(0, current_text)

        # Keep selection
        self.set_current_textbox(self.text_boxes[index - 1])
        self.save()


  def move_entry_down(self):
    if not self.current_entry:
      return

    index = None
    for i, entry in enumerate(self.text_boxes):
      if entry == self.current_entry:
        index = i
        break

    if index is not None and index < len(self.text_boxes) - 1:
      current_text = self.text_boxes[index].get()
      below_text = self.text_boxes[index + 1].get()

      # Swap text
      self.text_boxes[index].delete(0, tk.END)
      self.text_boxes[index].insert(0, below_text)

      self.text_boxes[index + 1].delete(0, tk.END)
      self.text_boxes[index + 1].insert(0, current_text)

      # Keep selection
      self.set_current_textbox(self.text_boxes[index + 1])
      self.save()



if __name__ == "__main__":
  app = MainApplication()
  app.mainloop()


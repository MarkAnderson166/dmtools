
button = tk.Button(root, text="Edit Copy",
                   command=lambda: copy_and_open_image(selected_image_path))



import os
import platform
import shutil
import subprocess
from pathlib import Path

def copy_and_open_image(src_path):
    src = Path(src_path)

    if not src.exists():
        raise FileNotFoundError(f"{src} not found")

    # Create copy filename
    dst = src.with_stem(src.stem + "_copy")

    # Copy file (cross-platform)
    shutil.copy2(src, dst)

    system = platform.system()

    try:
        if system == "Windows":
            # Try MS Paint first
            subprocess.Popen(["mspaint", str(dst)])

        elif system == "Linux":
            # Fedora / ChromeOS both land here
            # Try KolourPaint, then fallback options
            for editor in ["kolourpaint", "pinta", "gimp", "xdg-open"]:
                try:
                    subprocess.Popen([editor, str(dst)])
                    break
                except FileNotFoundError:
                    continue
            else:
                raise RuntimeError("No suitable image editor found")

        elif system == "Darwin":
            # macOS (just in case)
            subprocess.Popen(["open", str(dst)])

        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    except Exception as e:
        print(f"Failed to open editor: {e}")

    return dst

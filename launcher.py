"""Portable entry point, with unattended checks for testing the actual bundle."""
import json
from pathlib import Path
import sys
import traceback


def self_test(report: Path):
    import imagecodecs
    import imagecodecs._ultrahdr  # expose dependency errors instead of lazy stubs
    import numpy as np
    from PIL import Image
    from app import App
    from metadata import copy_exif, mpf_index

    app = App()
    app.withdraw()
    app.update()
    app.destroy()
    pixels = np.zeros((32, 64), np.uint32)
    pixels[:] = (3 << 30) | 800 | (800 << 10) | (800 << 20)
    encoded = imagecodecs.ultrahdr_encode(pixels, level=95, gamut="BT_2100", transfer="PQ")
    exif = Image.Exif()
    exif[271] = "Portable Self Test"
    exif[274] = 1
    encoded = copy_exif(encoded, exif.tobytes(), (64, 32))
    assert imagecodecs.ultrahdr_check(encoded)
    hdr = imagecodecs.ultrahdr_decode(encoded)
    assert float(hdr[..., :3].max()) > 1
    from io import BytesIO
    with Image.open(BytesIO(encoded)) as image:
        image.load()
        assert image.getexif()[271] == "Portable Self Test"
    _, _, entries = mpf_index(encoded)
    report.write_text(json.dumps({"ok": True, "frozen": bool(getattr(sys, "frozen", False)),
        "gui": True, "ultra_hdr": True, "exif": True, "mpf_images": len(entries),
        "codec": imagecodecs.ultrahdr_version()}, indent=2), encoding="utf-8")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        self_test(Path(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "--convert":
        del sys.argv[1]
        from converter import main as convert_main
        convert_main()
    else:
        from app import App
        App().mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        detail = traceback.format_exc()
        # A GUI bundle has no console. Write diagnostic text when a report was
        # requested; otherwise show a useful error without silently exiting.
        if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
            Path(sys.argv[2]).write_text(json.dumps({"ok": False, "error": detail}), encoding="utf-8")
        else:
            import tkinter.messagebox
            tkinter.messagebox.showerror("启动或运行失败", detail)
        raise SystemExit(1)

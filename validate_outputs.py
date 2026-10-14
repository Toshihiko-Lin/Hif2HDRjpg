"""Decode output images with both HDR and standard JPEG decoders."""
import argparse
import json
from pathlib import Path

import imagecodecs
import numpy as np
from PIL import Image
import pillow_heif
from metadata import normalized_exif, mpf_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--source", type=Path, help="对比原始 HIF 的 EXIF")
    args = parser.parse_args()
    results = []
    for path in sorted(args.folder.glob("*.jpg")):
        data = path.read_bytes()
        assert imagecodecs.ultrahdr_check(data), f"Missing gain map: {path}"
        with Image.open(path) as sdr:
            sdr.load()
            size = sdr.size
            output_exif = sdr.info.get("exif")
            exif = sdr.getexif()
            camera = exif.get(272)
            fields = exif.get_ifd(34665) if exif else {}
        hdr = imagecodecs.ultrahdr_decode(data, dtype=np.float16)
        assert hdr.shape == (size[1], size[0], 4)
        assert np.isfinite(hdr).all(), f"Non-finite HDR data: {path}"
        peak = float(hdr[..., :3].max())
        row = {"file": path.name, "dimensions": list(size), "bytes": len(data),
               "ultra_hdr": True, "sdr_decode": True, "hdr_decode": True,
               "linear_peak_relative_to_203_nits": peak,
               "highlights_above_sdr_white": peak > 1.0}
        _, _, images = mpf_index(data)
        row["mpf_images"] = len(images)
        if args.source:
            source = args.source / (path.stem.split("_HDR")[0] + ".HIF")
            original = pillow_heif.open_heif(source).info.get("exif")
            expected = normalized_exif(original, size) if original else None
            assert output_exif == expected, f"EXIF differs from source: {path}"
            row.update(exif_matches_source=True, exif_bytes=len(output_exif or b""),
                       camera=camera, lens=fields.get(42036),
                       capture_time=fields.get(36867), iso=fields.get(34855),
                       makernote_bytes=len(fields.get(37500, b"")))
        results.append(row)
        del hdr, data
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if not results:
        raise SystemExit("No JPEG files found")
    (args.folder / "validation.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

import tempfile
import unittest
from pathlib import Path

import imagecodecs
import numpy as np
from PIL import Image
import pillow_heif
import struct
from io import BytesIO

from converter import color_settings, convert_file, pack_rgb10, write_unique
from metadata import copy_exif, normalized_exif, mpf_index


class ConverterTests(unittest.TestCase):
    def test_channel_packing(self):
        rgb = np.array([[[1023, 0, 0], [0, 512, 0], [0, 0, 1023]]], dtype=np.uint16)
        result = pack_rgb10(rgb, 10)
        np.testing.assert_array_equal(result, [[(3 << 30) | 1023,
            (3 << 30) | (512 << 10), (3 << 30) | (1023 << 20)]])
        np.testing.assert_array_equal(result, pack_rgb10(rgb << 2, 12))
        np.testing.assert_array_equal(result, pack_rgb10(rgb << 6, 16))

    def test_sdr_and_missing_tags_rejected(self):
        with self.assertRaises(ValueError):
            color_settings(None)
        with self.assertRaises(ValueError):
            color_settings({"color_primaries": 1, "transfer_characteristics": 13}, True)
        self.assertEqual(color_settings(None, True), ("BT_2100", "PQ"))
        with self.assertRaises(ValueError):
            pack_rgb10(np.zeros((2, 2, 3), np.uint8), 8)

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            first = write_unique(Path(folder), "照片", b"first")
            second = write_unique(Path(folder), "照片", b"second")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")

    def test_real_hdr_container_roundtrip_and_sdr_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            rgb = np.zeros((64, 96, 3), np.uint16)
            rgb[:] = np.linspace(100, 900, 96, dtype=np.uint16)[None, :, None]
            heif = pillow_heif.from_bytes("RGB;10", (96, 64), rgb.tobytes())
            source = directory / "测试.HIF"
            heif.save(source, quality=100, save_nclx_profile=True,
                      color_primaries=9, transfer_characteristics=16,
                      matrix_coefficients=0, full_range_flag=1, chroma=444)
            target, info = convert_file(source, directory)
            self.assertEqual(info["transfer"], "PQ")
            self.assertTrue(imagecodecs.ultrahdr_check(target.read_bytes()))
            hdr = imagecodecs.ultrahdr_decode(target.read_bytes())
            self.assertEqual(hdr.shape, (64, 96, 4))
            self.assertGreater(float(hdr[..., :3].max()), 1.0)
            with Image.open(target) as sdr:
                sdr.load()
                self.assertEqual(sdr.size, (96, 64))
            sdr_source = directory / "SDR.HIF"
            pillow_heif.from_pillow(Image.new("RGB", (64, 64))).save(sdr_source)
            with self.assertRaises(ValueError):
                convert_file(sdr_source, directory)

    def test_exif_copy_preserves_makernote_gps_and_gainmap(self):
        exif = Image.Exif()
        exif[271] = "Canon"
        exif[272] = "Camera Test"
        exif[274] = 6
        exif[34665] = {36867: "2026:10:15 10:20:30", 34855: 640,
                       37500: b"Canon\x00\x00\x00" + bytes(range(256)),
                       40962: 32, 40963: 64, 42036: "Test lens"}
        exif[34853] = {1: "N", 2: (31, 12, 30), 3: "E", 4: (121, 30, 0)}
        raw = exif.tobytes()
        pixels = np.full((32, 64), (3 << 30) | 800 | (800 << 10) | (800 << 20), np.uint32)
        jpeg = imagecodecs.ultrahdr_encode(pixels, gamut="BT_2100", transfer="PQ")
        output = copy_exif(jpeg, raw, (64, 32))
        with Image.open(BytesIO(output)) as image:
            copied = image.getexif()
            self.assertEqual(copied[271], exif[271])
            self.assertEqual(copied[274], 1)
            self.assertEqual(copied.get_ifd(34665)[40962], 64)
            self.assertEqual(copied.get_ifd(34665)[40963], 32)
            for tag in (36867, 34855, 37500, 42036):
                self.assertEqual(copied.get_ifd(34665)[tag], exif[34665][tag])
            self.assertEqual(copied.get_ifd(34853), exif[34853])
        np.testing.assert_array_equal(imagecodecs.ultrahdr_decode(jpeg), imagecodecs.ultrahdr_decode(output))
        _, _, before = mpf_index(jpeg)
        _, _, after = mpf_index(output)
        self.assertEqual(after[0][1] - before[0][1], len(raw) + 4)
        self.assertTrue(imagecodecs.ultrahdr_check(output))

    def test_exif_big_endian_and_invalid_data(self):
        # One inline SHORT Orientation, big endian TIFF.
        raw = b"Exif\x00\x00MM\x00*\x00\x00\x00\x08" + struct.pack(">HHHI", 1, 274, 3, 1) + b"\x00\x06\x00\x00" + bytes(4)
        result = normalized_exif(raw, (64, 32))
        self.assertEqual(result[24:26], b"\x00\x01")
        with self.assertRaises(ValueError):
            normalized_exif(b"Exif\x00\x00" + bytes(70000), (64, 32))
        with self.assertRaises(ValueError):
            normalized_exif(b"Exif\x00\x00II*\x00\xff\xff\xff\xff", (64, 32))


if __name__ == "__main__":
    unittest.main()

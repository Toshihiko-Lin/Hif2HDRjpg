"""High-bit-depth HEIF -> Ultra HDR JPEG. No intermediate 8-bit conversion."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import imagecodecs
import numpy as np
import pillow_heif

from metadata import copy_exif

EXTENSIONS = {".hif", ".heif", ".heic"}


def color_settings(profile: dict | None, assume_canon: bool = False):
    profile = profile or {}
    primaries = int(profile.get("color_primaries", 2))
    transfer = int(profile.get("transfer_characteristics", 2))
    if assume_canon:
        # Only fill absent/unspecified tags; never reinterpret explicit SDR as HDR.
        primaries = 9 if primaries == 2 else primaries
        transfer = 16 if transfer == 2 else transfer
    gamuts = {1: "BT_709", 9: "BT_2100", 12: "DISPLAY_P3"}
    transfers = {16: "PQ", 18: "HLG"}
    if transfer not in transfers:
        raise ValueError(
            f"无法确认 HDR 传递函数（NCLX={transfer}）。仅接受 PQ/HLG；"
            "若确认是佳能 HDR PQ 且缺少标签，可勾选缺失标签按佳能 PQ 处理。"
        )
    if primaries not in gamuts:
        raise ValueError(f"不支持或缺失色域标签（NCLX={primaries}），无法可靠保留 HDR 颜色。")
    return gamuts[primaries], transfers[transfer]


def pack_rgb10(rgb: np.ndarray, bits: int) -> np.ndarray:
    """Pack libheif's unshifted RGB samples into libultrahdr RGBA1010102."""
    if bits not in (10, 12, 16) or rgb.dtype != np.uint16:
        raise ValueError("需要 10/12/16 位 RGB 输入，拒绝用 8 位图像生成伪 HDR。")
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("仅支持不含透明通道的 RGB 相机照片。")
    # Work one channel at a time to reduce peak memory on large camera files.
    packed = np.full(rgb.shape[:2], 3 << 30, dtype=np.uint32)
    for channel in range(3):
        values = rgb[..., channel].astype(np.uint32)
        values >>= bits - 10
        np.minimum(values, 1023, out=values)
        packed |= values << (10 * channel)
    return np.ascontiguousarray(packed)


def write_unique(directory: Path, stem: str, data: bytes) -> Path:
    """Exclusive creation also protects files created by another running instance."""
    directory.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        suffix = "" if index == 0 else f"_{index}"
        target = directory / f"{stem}_HDR{suffix}.jpg"
        try:
            handle = target.open("xb")
        except FileExistsError:
            index += 1
            continue
        try:
            with handle:
                handle.write(data)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target


def convert_file(source: Path, output_dir: Path, quality: int = 95,
                 scale: int = 1, assume_canon: bool = False,
                 report: Callable[[str], None] = lambda _: None) -> tuple[Path, dict]:
    source = Path(source)
    if source.suffix.lower() not in EXTENSIONS:
        raise ValueError("请选择 .HIF、.HEIF 或 .HEIC 文件。")
    if not 1 <= quality <= 100 or scale not in (1, 2, 4):
        raise ValueError("质量应为 1–100，增益图缩放应为 1、2 或 4。")
    if not imagecodecs.ULTRAHDR.available:
        raise RuntimeError("当前 imagecodecs 未包含 Ultra HDR 编码器，请重新运行安装脚本。")
    report("读取 HDR 标签")
    heif = pillow_heif.open_heif(source, convert_hdr_to_8bit=False,
                                 hdr_to_16bit=False)
    image = heif[heif.primary_index]
    gamut, transfer = color_settings(image.info.get("nclx_profile"), assume_canon)
    report("解码高位深像素")
    image.load()  # libheif applies container rotation/mirroring during decode.
    mode = image.mode
    if not mode.startswith("RGB;"):
        raise ValueError(f"需要高位深 RGB 照片，实际解码模式为 {mode}。")
    bits = int(mode.split(";")[1])
    pixels = np.asarray(image)[:, :image.size[0], :]
    packed = pack_rgb10(pixels, bits)
    details = {
        "source": str(source.resolve()), "width": image.size[0], "height": image.size[1],
        "source_bits": image.info.get("bit_depth", bits), "decoded_bits": bits,
        "gamut": gamut, "transfer": transfer, "quality": quality, "gainmap_scale": scale,
        "nclx": image.info.get("nclx_profile"),
    }
    exif = image.info.get("exif")
    del pixels, image, heif
    report("编码 Ultra HDR JPEG")
    encoded = imagecodecs.ultrahdr_encode(
        packed, level=quality, scale=scale, gamut=gamut, transfer=transfer,
    )
    del packed
    report("复制 EXIF 拍摄信息")
    encoded = copy_exif(encoded, exif, (details["width"], details["height"]))
    details["exif_copied"] = bool(exif)
    details["exif_bytes"] = len(exif) if exif else 0
    report("验证 HDR 增益图并保存")
    if not imagecodecs.ultrahdr_check(encoded):
        raise RuntimeError("输出没有有效的 Ultra HDR 增益图，已拒绝保存。")
    target = write_unique(Path(output_dir), source.stem, encoded)
    details.update(output=str(target.resolve()), output_bytes=len(encoded), ultra_hdr=True)
    return target, details


def main():
    parser = argparse.ArgumentParser(description="佳能 HIF 转 Ultra HDR JPG")
    parser.add_argument("inputs", type=Path, nargs="+", help="文件或文件夹")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-q", "--quality", type=int, default=95)
    parser.add_argument("--scale", type=int, choices=[1, 2, 4], default=1)
    parser.add_argument("--assume-canon-pq", action="store_true")
    parser.add_argument("--report", type=Path, help="将逐张结果写入 UTF-8 JSON 报告")
    args = parser.parse_args()
    files = []
    for path in args.inputs:
        files.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in EXTENSIONS)
                     if path.is_dir() else [path])
    files = list(dict.fromkeys(p.resolve() for p in files))
    if not files:
        parser.error("没有找到支持的照片")
    failed = False
    results = []
    for path in files:
        try:
            _, info = convert_file(path, args.output, args.quality, args.scale, args.assume_canon_pq)
            results.append(info)
            if sys.stdout is not None:
                print(json.dumps(info, ensure_ascii=False))
        except Exception as exc:
            failed = True
            results.append({"source": str(path), "error": str(exc)})
            if sys.stdout is not None:
                print(f"失败：{path.name}：{exc}")
    if args.report:
        args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

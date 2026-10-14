"""Assemble a folder and matching ZIP; never package personal test photos."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib import metadata as packages
import json
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
NAME = "CanonHifHdr-Portable"
SOURCES = {
    "pillow_heif-1.8.1.tar.gz": "https://codeload.github.com/bigcat88/pillow_heif/tar.gz/refs/tags/v1.8.1",
    "libheif-1.23.6.tar.gz": "https://codeload.github.com/strukturag/libheif/tar.gz/refs/tags/v1.23.6",
    "libde265-1.1.3.tar.gz": "https://codeload.github.com/strukturag/libde265/tar.gz/refs/tags/v1.1.3",
    "x265-e9b8812.tar.gz": "https://codeload.github.com/Multicorewareinc/x265/tar.gz/e9b8812",
    "libultrahdr-2.0.2.tar.gz": "https://codeload.github.com/google/libultrahdr/tar.gz/refs/tags/v2.0.2",
    "libjpeg-turbo-3.2.0.tar.gz": "https://codeload.github.com/libjpeg-turbo/libjpeg-turbo/tar.gz/refs/tags/3.2.0",
    "imagecodecs-2026.10.10.tar.gz": "https://codeload.github.com/cgohlke/imagecodecs/tar.gz/refs/tags/v2026.10.10",
}
SOURCE_FILES = ["app.py", "converter.py", "metadata.py", "launcher.py", "test_converter.py",
    "validate_outputs.py", "requirements.txt", "requirements-build.txt", "CanonHifHdr.spec",
    "build.bat", "install.bat", "start.bat", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "package_portable.py", "CHANGELOG.md"]


def compact_source_archive(original, target):
    """Keep source/build/license files; omit upstream binary test fixtures.

    These modified archives are for rebuilding the libraries, not for running
    their full upstream test suites (which need the original data archives).
    """
    removed = []
    code_suffixes = {".c", ".h", ".cc", ".hh", ".cpp", ".hpp", ".py", ".pyx",
                     ".pxd", ".pxi", ".asm", ".s", ".cmake", ".txt", ".md",
                     ".rst", ".sh", ".bat", ".ps1", ".yml", ".yaml", ".json"}
    media_suffixes = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".hif",
                      ".avif", ".webp", ".tif", ".tiff", ".bmp", ".pdf", ".ico"}
    with tarfile.open(original, "r:gz") as incoming, tarfile.open(target, "w:gz", compresslevel=9) as outgoing:
        for member in incoming:
            path = Path(member.name)
            relative = path.parts[1:]
            parts = set(p.lower() for p in relative[:-1])
            fixture = bool(parts & {"tests", "testimages", "fuzzing", "benchmarks"})
            is_code = path.suffix.lower() in code_suffixes or path.name in {
                "CMakeLists.txt", "Makefile", "meson.build", "configure", "LICENSE", "COPYING"}
            if member.isfile() and not is_code and (fixture or path.suffix.lower() in media_suffixes):
                removed.append(member.name)
                continue
            outgoing.addfile(member, incoming.extractfile(member) if member.isfile() else None)
    return removed


def download(item):
    name, url = item
    target = ROOT / "vendor_sources" / name
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(".part")
        request = urllib.request.Request(url, headers={"User-Agent": "CanonHifHdr-build/1.1"})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if temporary.read_bytes()[:2] != b"\x1f\x8b":
            raise ValueError(f"Invalid source archive: {name}")
        temporary.replace(target)
    return {"file": name, "source_url": url, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def collect_licenses(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for package in ("numpy", "Pillow", "pillow-heif", "imagecodecs", "pyinstaller"):
        dist = packages.distribution(package)
        for file in dist.files or []:
            if "license" in str(file).lower() or str(file).endswith("COPYING.txt"):
                original = Path(dist.locate_file(file))
                if original.is_file():
                    target = destination / package / Path(str(file))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, target)
    runtime = Path(sys.base_prefix)
    shutil.copy2(runtime / "LICENSE.txt", destination / "Python-LICENSE.txt")
    for file in (runtime / "tcl").rglob("license.terms"):
        target = destination / "TclTk" / file.relative_to(runtime / "tcl")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)


def main():
    binary = ROOT / "dist" / "CanonHifHdr"
    if not (binary / "CanonHifHdr.exe").exists():
        raise SystemExit("Run PyInstaller first")
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    folder = release / NAME
    # This is a fixed generated output within release, never a supplied path.
    if folder.exists():
        resolved = folder.resolve()
        if resolved.parent != release.resolve() or resolved.name != NAME:
            raise RuntimeError("Refusing to replace a folder outside the release directory")
        shutil.rmtree(resolved)
    shutil.copytree(binary, folder)
    source = folder / "source"
    source.mkdir()
    for name in SOURCE_FILES:
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(ROOT / "hooks", source / "hooks", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = list(pool.map(download, SOURCES.items()))
    (source / "vendor_sources").mkdir()
    for entry in manifest:
        target_source = source / "vendor_sources" / entry["file"]
        removed = compact_source_archive(ROOT / "vendor_sources" / entry["file"], target_source)
        entry["upstream_sha256"] = entry.pop("sha256")
        entry["sha256"] = hashlib.sha256(target_source.read_bytes()).hexdigest()
        entry["omitted_test_media"] = removed
    (source / "vendor_sources" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    collect_licenses(folder / "THIRD_PARTY_LICENSES")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", folder / "THIRD_PARTY_NOTICES.md")
    shutil.copy2(ROOT / "LICENSE", folder / "LICENSE")
    (folder / "使用说明.txt").write_text(
        "佳能 HIF → HDR JPG 1.1.0（Windows 64 位便携版）\n\n"
        "1. 将 ZIP 完整解压到任意文件夹。\n"
        "2. 双击 CanonHifHdr.exe，无需安装 Python，无需联网。\n"
        "3. 添加照片或文件夹，选择输出文件夹，点击开始转换。\n\n"
        "转换时默认保留 EXIF（机身、镜头、时间、曝光、ISO、GPS、MakerNote 等）。\n"
        "输出是带增益图的 Ultra HDR JPG；需支持 HDR 的屏幕和查看器显示高光。\n"
        "普通查看器可显示兼容的 SDR 版本，JPEG 压缩为有损。\n"
        "已应用到像素的旋转不重复应用，EXIF 方向统一为 1；尺寸字段同步更新。\n"
        "源文件不变，已有输出不覆盖。源文件无 EXIF 时日志会说明。\n\n"
        "_internal 是运行依赖目录，请与 EXE 一起保留，不要单独移动 EXE。\n"
        "source 包含可修改源码、构建脚本和依赖源码归档（已移除上游测试图片）。\n"
        "分发时请保留完整文件夹或直接发送同名 ZIP。\n"
        "详细说明见 source/README.md；依赖许可证见 THIRD_PARTY_LICENSES。\n\n"
        "支持 Windows 10/11 x64。已在 Windows 11 x64 上验证。\n"
        "此版本未做数字签名。\n",
        encoding="utf-8-sig")
    # The exact bytes shipped are inventoried, and the archive is created only
    # after all mandatory files have been successfully assembled.
    hashes = {str(p.relative_to(folder)).replace("\\", "/"):
              hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(folder.rglob("*")) if p.is_file()}
    (folder / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    target = release / (NAME + ".zip")
    temporary = release / (NAME + ".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(release))
    temporary.replace(target)
    print(json.dumps({"folder": str(folder), "zip": str(target), "zip_bytes": target.stat().st_size,
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()

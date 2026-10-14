"""Only JPEG/EXIF are used; omit unrelated AVIF/WebP/etc codec plugins."""
hiddenimports = ["PIL.JpegImagePlugin", "PIL.TiffImagePlugin"]

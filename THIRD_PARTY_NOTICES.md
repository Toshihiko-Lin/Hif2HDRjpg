# Bundled components

The application's original Python source uses the MIT license in LICENSE.
This does not replace the licenses of any dependencies or grant permission
to redistribute those dependencies under MIT. Keep the notices, licenses and
source archives together when sharing the portable ZIP.

The pillow-heif 1.8.1 Windows wheel identifies its binary wheel as GPLv2 due
to its bundled libraries. Its own Python/C wrapper is BSD-3-Clause. The
upstream LICENSES_bundled.txt is included unchanged. It lists libheif 1.23.6
(LGPLv3), libde265 1.1.3 (LGPLv3), x265 4.3 (GPLv2), and MinGW runtime
licenses. Upstream source archives and the wheel's build scripts are in
source/vendor_sources, along with the source URL and SHA-256 manifest.

Source archives omit upstream binary test fixtures and documentation media
to reduce package size; source code, build scripts and licenses are retained.
The original source URLs, original hashes, distributed archive hashes, and
lists of omitted fixtures are in source/vendor_sources/manifest.json. Full
upstream test suites require downloading their original fixture data.
The native codec DLLs remain
separate in _internal and can be replaced with ABI-compatible builds.
The app does not restrict modification or reverse engineering of those
libraries. Rebuild the application with source/build.bat. The original
dependency wheels, rather than modified codec builds, are used here.

Other bundled components include Python 3.12.10 (PSF license), Tcl/Tk 8.6
(Tcl/Tk license), NumPy 2.4.6 (BSD-3-Clause and bundled library notices),
Pillow 12.3.0 (HPND and bundled library notices), imagecodecs 2026.10.10
(BSD-3-Clause), and the PyInstaller 6.16.0 bootloader (GPL with its bootloader
exception). imagecodecs._ultrahdr contains libultrahdr 2.0.2 (Apache-2.0/MIT)
and its JPEG implementation. Only the Ultra HDR and shared imagecodecs
extension modules are packaged; the other imagecodecs codecs are omitted.
Upstream license texts are in THIRD_PARTY_LICENSES and the source archives.

Upstream projects:

- https://github.com/bigcat88/pillow_heif/tree/v1.8.1
- https://github.com/strukturag/libheif/tree/v1.23.6
- https://github.com/strukturag/libde265/tree/v1.1.3
- https://github.com/Multicorewareinc/x265/tree/e9b8812
- https://github.com/cgohlke/imagecodecs/tree/v2026.10.10
- https://github.com/google/libultrahdr/tree/v2.0.2
- https://github.com/libjpeg-turbo/libjpeg-turbo
- https://github.com/python/cpython/tree/v3.12.10
- https://github.com/numpy/numpy/tree/v2.4.6
- https://github.com/python-pillow/Pillow/tree/12.3.0
- https://github.com/pyinstaller/pyinstaller/tree/v6.16.0

Microsoft Visual C++ runtime files are also bundled as required by the
compiled extensions. See Microsoft's Visual Studio/Build Tools runtime
redistribution terms: https://visualstudio.microsoft.com/license-terms/ .

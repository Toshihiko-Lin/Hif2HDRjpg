# Hif2HDRjpg · 佳能 HIF → HDR JPG

简单的 Windows 桌面小工具，把佳能相机 HDR PQ 模式拍摄的 `.HIF` 转换为带增益图的 **Ultra HDR JPEG**，扩展名仍然是 `.jpg`。默认复制 EXIF 拍摄信息。

## 便携版与分发

[下载最新 Windows x64 便携版](https://github.com/Toshihiko-Lin/Hif2HDRjpg/releases/latest/download/CanonHifHdr-Portable.zip) · [查看 Release](https://github.com/Toshihiko-Lin/Hif2HDRjpg/releases)

下载一个完整 ZIP，解压后双击 `CanonHifHdr.exe` 即可运行，无需安装 Python 或额外下载。请保留同目录的 `_internal` 文件夹。当前版本压缩包约 38 MB。

成品单独位于 `release/CanonHifHdr-Portable`，对应压缩包为 `release/CanonHifHdr-Portable.zip`。发送这个 ZIP 即可，不需要发送整个开发工作目录。

完整解压，双击 `CanonHifHdr.exe`。无需安装 Python、无需联网、无需管理员权限。`_internal` 是必要运行依赖目录，必须随 EXE 一起保留。便携包还附带使用说明、源码、构建脚本、依赖源码归档和许可证；不包含个人照片、测试输出和虚拟环境。精简版移除了未使用的 Pillow 编码插件与依赖源码中的上游测试图片；代码、构建脚本、许可证与全部运行依赖仍在同一个 ZIP 中。

目标平台 Windows 10/11 x64，已在 Windows 11 x64 验证；未签名。源码运行方式见下文。

## 从源码启动

克隆或下载本仓库，然后双击 **`start.bat`**；没有虚拟环境时会自动调用安装脚本。

源码方式需要先安装 **64 位 Python 3.12 或更新版本**（包含 pip、Tcl/Tk，并将 Python 加入 PATH），也可以双击 `install.bat` 安装依赖。需要联网下载依赖，安装完成后离线转换即可。推荐使用已经验证的 Python 3.12。便携版不需要这些步骤。

## 操作

1. 点击“添加照片”或“添加文件夹”。文件夹只读取当前层，不递归。
2. 选择输出文件夹。默认在第一张照片旁创建 `HDR_JPG`。
3. 保持质量 95、增益图缩放 1，点击“开始转换”。
4. 点击“打开输出文件夹”查看结果。

输出命名为 `原文件名_HDR.jpg`；遇到同名文件自动增加 `_1`、`_2`。程序不修改原照片，不覆盖已有输出。单张失败后继续处理其他照片。“停止后续任务”会等待当前照片处理结束。

质量 1–100 控制 JPEG 压缩，100 仍然有损。增益图缩放 1 保留完整分辨率，2 或 4 会降低增益图分辨率、减小文件体积。大尺寸照片逐张处理，编码时可能占用数百 MB 内存。

## HDR 的含义与限制

普通 JPEG 的 8 位主图不能独立保存这些 PQ 高光。本程序使用 `pillow-heif / libheif` 直接解码高位深 RGB，再使用 `imagecodecs / Google libultrahdr` 编码 SDR 主图和 HDR 增益图。不会经过 Pillow 的 8 位 RGB 转换；佳能 10 位输入直接打包为 RGBA1010102，12/16 位输入会量化至 10 位。

输出保存 HDR 显示意图和高光，但不是无损复制。SDR 主图由编码库自动做色调映射，效果可能和佳能机内或 DPP 的 SDR 转换不同。

复制原始 EXIF 数据块，保留机身、镜头、拍摄时间、曝光、ISO、GPS（源文件有时）和佳能 MakerNote。只原位更新已有方向与尺寸标签，不搬移 MakerNote 数据；HEIF 容器的旋转/镜像已由解码器应用到像素，输出 EXIF 方向设为 1。JPEG 的 MPF 主图长度同步修正，增益图字节保持不变。源文件无 EXIF 时会明确显示。EXIF 超过 JPEG 单段上限 65533 字节或结构损坏时会报错，不静默丢失。独立的源 XMP 和 HEIF 容器专有字段不复制。

需要同时使用 HDR 屏幕、开启系统 HDR，以及支持 Ultra HDR 的查看软件，才能看到 HDR 效果。不支持的查看器会显示兼容的 SDR 主图。普通图片编辑软件重新保存可能移除增益图。程序验证了文件中的 HDR 数据，未对当前显示器的实际 HDR 呈现做验收。

默认只接受明确标记 PQ 或 HLG 的高位深图片；缺失或不支持的色彩标签会报错。如果确定照片为佳能 HDR PQ，但缺少 NCLX 标签，可以勾选“缺失标签按佳能 PQ 处理”。它只补充缺失值，不会把有明确 SDR 标签的照片当作 HDR。

格式说明：[Google libultrahdr](https://github.com/google/libultrahdr)。高位深解码说明：[pillow-heif 图像模式](https://pillow-heif.readthedocs.io/en/latest/image-modes.html)。Python 编解码接口：[imagecodecs](https://github.com/cgohlke/imagecodecs)。

## 命令行

```powershell
.\.venv\Scripts\python.exe converter.py "D:\照片" -o "D:\照片\HDR_JPG"
.\.venv\Scripts\python.exe converter.py "D:\照片\IMG_0001.HIF" -o "D:\输出" -q 95 --scale 1
CanonHifHdr.exe --convert "D:\照片" -o "D:\输出" --report "D:\转换报告.json"
```

文件和文件夹可以同时传入多个。输出中包含每张照片的识别参数；有任何失败时退出码为 1。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_converter
.\.venv\Scripts\python.exe validate_outputs.py validation_output
```

已使用 5 张 Canon EOS R7 的 6960 × 4640、10 位 PQ / BT.2020 实拍 HIF 验证：HDR 增益图、HDR 完整解码、普通 JPEG 完整解码、尺寸和高光值均正常，EXIF 与原片一致（含佳能 MakerNote）。便携 ZIP 也已解压到含中文和空格的新路径，在移除 Python 环境变量与 PATH 的条件下完成启动及全部 5 张转换。个人测试照片、测试输出和本地虚拟环境不随仓库或便携包分发。

用自己的照片复验：

```powershell
.\.venv\Scripts\python.exe converter.py "D:\照片" -o "D:\验证输出"
.\.venv\Scripts\python.exe validate_outputs.py "D:\验证输出" --source "D:\照片"
```

## 从源码构建

在 Windows x64 的 Python 3.12 环境双击 `build.bat`，会安装构建依赖、运行测试、执行 PyInstaller，并生成独立成品文件夹和 ZIP。打包阶段需要联网获取依赖源码归档，已有缓存可复用。

便携 EXE 支持 `--self-test 报告.json`，可验证打包后的 GUI、HDR 编解码和 EXIF 复制。便携版未要求系统 PATH 中有 Python。

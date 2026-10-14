"""Simple Tk GUI. Only the main thread touches widgets."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from converter import EXTENSIONS, convert_file


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("佳能 HIF → HDR JPG")
        self.geometry("920x670")
        self.minsize(760, 540)
        self.files: list[Path] = []
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.running = False
        self.output = tk.StringVar()
        self.quality = tk.StringVar(value="95")
        self.scale = tk.StringVar(value="1")
        self.assume = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="添加 HIF 照片，然后开始转换。")
        self.controls = []
        self.build()
        self.after(100, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def build(self):
        style = ttk.Style(self)
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("TButton", padding=(12, 6))
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="佳能 HIF → HDR JPG", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text="保留 HDR 高光与 EXIF 拍摄信息 · 普通查看器也能显示 SDR 版本").pack(anchor="w", pady=(6, 16))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x")
        for title, action in [("添加照片", self.add_files), ("添加文件夹", self.add_folder),
                              ("移除选中", self.remove), ("清空", self.clear)]:
            button = ttk.Button(toolbar, text=title, command=action)
            button.pack(side="left", padx=(0, 8))
            self.controls.append(button)
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True, pady=12)
        self.tree = ttk.Treeview(table, columns=("name", "status"), show="headings", height=10)
        self.tree.heading("name", text="照片（完整路径可在日志中查看）")
        self.tree.heading("status", text="状态")
        self.tree.column("name", width=470)
        self.tree.column("status", width=270)
        bar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        output = ttk.Frame(frame)
        output.pack(fill="x")
        ttk.Label(output, text="输出文件夹").pack(side="left")
        entry = ttk.Entry(output, textvariable=self.output)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        browse = ttk.Button(output, text="选择…", command=self.choose_output)
        browse.pack(side="left")
        self.controls.extend([entry, browse])
        settings = ttk.Frame(frame)
        settings.pack(fill="x", pady=12)
        ttk.Label(settings, text="JPEG 质量").pack(side="left")
        quality = ttk.Spinbox(settings, from_=1, to=100, textvariable=self.quality, width=5)
        quality.pack(side="left", padx=(8, 20))
        ttk.Label(settings, text="增益图缩放（1 最精细）").pack(side="left")
        scale = ttk.Combobox(settings, values=["1", "2", "4"], textvariable=self.scale,
                             state="readonly", width=4)
        scale.pack(side="left", padx=8)
        assume = ttk.Checkbutton(frame, text="仅当 HDR 标签缺失时，按佳能 PQ / BT.2020 处理（需确认源照片为 HDR PQ）",
                                 variable=self.assume)
        assume.pack(anchor="w")
        self.controls.extend([quality, scale, assume])
        self.scale_widget = scale
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(12, 6))
        self.start_button = ttk.Button(actions, text="开始转换", command=self.start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="停止后续任务", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="打开输出文件夹", command=self.open_output).pack(side="right")
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.pack(fill="x", pady=6)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        self.log = tk.Text(frame, height=5, state="disabled", wrap="word", font=("Microsoft YaHei UI", 9))
        self.log.pack(fill="x", pady=(8, 0))

    def add(self, paths):
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() in EXTENSIONS and path not in self.files:
                self.files.append(path)
                self.tree.insert("", "end", iid=str(path), values=(path.name, "等待转换"))
        if self.files and not self.output.get():
            self.output.set(str(self.files[0].parent / "HDR_JPG"))
        self.status.set(f"已添加 {len(self.files)} 张照片。")

    def add_files(self):
        self.add(filedialog.askopenfilenames(title="选择佳能 HDR 照片", filetypes=[
            ("HEIF 照片", "*.HIF *.hif *.HEIF *.heif *.HEIC *.heic"), ("所有文件", "*.*")]))

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择照片文件夹（不递归子文件夹）")
        if folder:
            try:
                self.add(sorted(p for p in Path(folder).iterdir() if p.is_file()))
            except OSError as exc:
                messagebox.showerror("无法读取文件夹", str(exc))

    def remove(self):
        for iid in self.tree.selection():
            self.files.remove(Path(iid))
            self.tree.delete(iid)

    def clear(self):
        self.files.clear()
        self.tree.delete(*self.tree.get_children())

    def choose_output(self):
        folder = filedialog.askdirectory(title="输出文件夹")
        if folder:
            self.output.set(folder)

    def open_output(self):
        if Path(self.output.get()).is_dir() and self.output.get():
            os.startfile(str(Path(self.output.get()).resolve()))
        else:
            messagebox.showinfo("输出文件夹", "转换后会自动创建输出文件夹。")

    def start(self):
        if not self.files or not self.output.get().strip():
            messagebox.showinfo("需要照片和输出位置", "请先添加照片并选择输出文件夹。")
            return
        try:
            quality = int(self.quality.get())
            scale = int(self.scale.get())
            if not 1 <= quality <= 100 or scale not in (1, 2, 4):
                raise ValueError()
        except ValueError:
            messagebox.showerror("参数无效", "质量请输入 1–100，增益图缩放请选择 1、2 或 4。")
            return
        files = list(self.files)
        output = Path(self.output.get().strip())
        assume = self.assume.get()
        self.running = True
        self.stop.clear()
        self.progress.configure(maximum=len(files), value=0)
        for widget in self.controls + [self.start_button]:
            widget.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        threading.Thread(target=self.work, args=(files, output, quality, scale, assume), daemon=True).start()

    def work(self, files, output, quality, scale, assume):
        success = failures = 0
        for index, path in enumerate(files):
            if self.stop.is_set():
                break
            self.events.put(("log", f"源文件：{path}"))
            try:
                target, info = convert_file(path, output, quality, scale, assume,
                    report=lambda text, p=path: self.events.put(("stage", str(p), text)))
                success += 1
                self.events.put(("stage", str(path), "完成 · HDR + EXIF" if info["exif_copied"] else "完成 · 源文件无 EXIF"))
                self.events.put(("log", f"保存：{target}\n{info['width']}×{info['height']} · {info['source_bits']} bit · {info['transfer']} · {info['gamut']}"))
            except Exception as exc:
                failures += 1
                self.events.put(("stage", str(path), "失败（见日志）"))
                self.events.put(("log", f"失败：{path.name}：{exc}"))
            self.events.put(("progress", index + 1))
        self.events.put(("done", success, failures, self.stop.is_set()))

    def cancel(self):
        self.stop.set()
        self.status.set("正在停止：当前照片处理完成后停止后续任务。")
        self.cancel_button.configure(state="disabled")

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "stage":
                    self.tree.set(event[1], "status", event[2])
                    if not self.stop.is_set():
                        self.status.set(f"{Path(event[1]).name}：{event[2]}")
                elif kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", event[1] + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "progress":
                    self.progress.configure(value=event[1])
                elif kind == "done":
                    self.running = False
                    for widget in self.controls + [self.start_button]:
                        widget.configure(state="normal")
                    self.scale_widget.configure(state="readonly")
                    self.cancel_button.configure(state="disabled")
                    self.status.set(f"{'已停止' if event[3] else '处理完成'}：成功 {event[1]} 张，失败 {event[2]} 张。")
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.running:
            self.cancel()
            messagebox.showinfo("正在处理照片", "已请求停止。请等待当前照片完成后关闭窗口。")
        else:
            self.destroy()


if __name__ == "__main__":
    App().mainloop()

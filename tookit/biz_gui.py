#!/usr/bin/env python3
"""
GUI frontend for binary container file conversion (.biz / .pak / .sum).

All format documentation is maintained in external reference files.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import os
import json
import threading
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from biz_tool import (
    detect_format, read_biz, write_biz, read_badge,
    read_pak_header, unpack_pak, MAGIC_BIZ,
)

LICENSE_TEXT = """MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

HELP_TEXT = """How to use:

1) Select files (.biz / .pak) via "Select Files"
2) Choose an output folder via "Output Folder"
3) Click "Extract" to decompress the containers
4) Select .sum files in the list, then click ".sum -> CSV"
   to export the tables as spreadsheets

File formats:
  .biz   - compressed archive (pizm + zlib)
  .pak   - resource pack (kapm + IDEA + custom LZ)
  .sum   - serialised database tables (exportable to CSV)"""


class BizGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Binary Data Converter")
        self.root.geometry("960x720")
        self.root.minsize(640, 480)

        # Internal state
        self.files = []            # [ {path, format, internal_name, size, raw_data}, ... ]
        self.output_dir = ""
        self.manifest = {}         # {original_name: {internal_name, format, ...}}

        self._setup_menubar()
        self._setup_ui()
        self._bind_events()

        self.status("Ready")

    # ── Menu bar ──

    def _setup_menubar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Usage", command=self._show_usage)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _show_usage(self):
        messagebox.showinfo("Usage", HELP_TEXT)

    def _show_about(self):
        messagebox.showinfo("About", LICENSE_TEXT)

    # ── UI Setup ──

    def _setup_ui(self):
        # ── Top button bar ──
        btn_frame = ttk.Frame(self.root, padding=(8, 6))
        btn_frame.pack(fill=tk.X)

        self.btn_select = ttk.Button(btn_frame, text="Select Files", command=self._select_files)
        self.btn_select.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_output = ttk.Button(btn_frame, text="Output Folder", command=self._select_output)
        self.btn_output.pack(side=tk.LEFT, padx=4)

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_decompress = ttk.Button(btn_frame, text="Extract", command=self._decompress)
        self.btn_decompress.pack(side=tk.LEFT, padx=4)

        self.btn_recompress = ttk.Button(btn_frame, text="Re-pack", command=self._recompress)
        self.btn_recompress.pack(side=tk.LEFT, padx=4)

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_sum_csv = ttk.Button(btn_frame, text=".sum → CSV", command=self._export_sum_csv)
        self.btn_sum_csv.pack(side=tk.LEFT, padx=4)

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_clear = ttk.Button(btn_frame, text="Clear List", command=self._clear)
        self.btn_clear.pack(side=tk.LEFT, padx=4)

        # ── Output directory indicator ──
        self.output_var = tk.StringVar(value="Output folder: (not set)")
        lbl_out = ttk.Label(self.root, textvariable=self.output_var, padding=(8, 2))
        lbl_out.pack(fill=tk.X)

        # ── File list (Treeview + Scrollbar) ──
        list_frame = ttk.Frame(self.root, padding=(8, 4))
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "size", "fmt", "info", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="extended", height=12)

        col_defs = [
            ("name",   "Filename",   220, tk.W),
            ("size",   "Size",        90, tk.E),
            ("fmt",    "Format",      80, tk.CENTER),
            ("info",   "Details",    320, tk.W),
            ("status", "Status",     150, tk.CENTER),
        ]
        for cid, text, width, anchor in col_defs:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Summary bar ──
        self.summary_var = tk.StringVar(value="0 files total")
        ttk.Label(self.root, textvariable=self.summary_var, padding=(8, 2)).pack(fill=tk.X)

        # ── Status bar ──
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               padding=(8, 3), relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _bind_events(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Right-click context menu
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Button-2>", self._on_tree_right_click)
        # Ctrl+C / Delete shortcuts
        self.tree.bind("<Control-c>", self._on_tree_copy)
        self.tree.bind("<Control-C>", self._on_tree_copy)
        self.tree.bind("<Delete>", self._on_tree_delete)
        self.tree.bind("<BackSpace>", self._on_tree_delete)

    def _on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            sel = self.tree.selection()
            if item not in sel:
                self.tree.selection_set(item)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Copy Selected Row(s)", command=self._copy_selected_rows)
        menu.add_command(label="Copy All", command=self._copy_all_rows)
        menu.add_separator()
        menu.add_command(label="Delete Selected (Delete)", command=self._remove_selected_rows)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_tree_copy(self, event=None):
        self._copy_selected_rows()

    def _copy_selected_rows(self):
        sel = self.tree.selection()
        if not sel:
            return
        lines = []
        for item_id in sel:
            vals = self.tree.item(item_id, "values")
            line = "\t".join(str(v) for v in vals)
            lines.append(line)
        text = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status(f"Copied {len(sel)} row(s)")

    def _copy_all_rows(self):
        children = self.tree.get_children()
        if not children:
            return
        lines = []
        for item_id in children:
            vals = self.tree.item(item_id, "values")
            line = "\t".join(str(v) for v in vals)
            lines.append(line)
        text = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status(f"Copied all {len(children)} rows")

    def _on_tree_delete(self, event=None):
        self._remove_selected_rows()

    def _remove_selected_rows(self):
        sel = self.tree.selection()
        if not sel:
            return
        n = len(sel)
        if not messagebox.askyesno("Confirm", f"Remove {n} selected file(s) from list?"):
            return
        removed_names = set()
        for item_id in sel:
            vals = self.tree.item(item_id, "values")
            if vals:
                removed_names.add(vals[0])
            self.tree.delete(item_id)
        self.files = [f for f in self.files if Path(f["path"]).name not in removed_names]
        self._update_summary()
        self.status(f"Removed {n} file(s)")

    # ── Event Handlers ──

    def status(self, msg):
        self.status_var.set(msg)
        self.root.update_idletasks()

    def _update_summary(self):
        n = len(self.files)
        if n == 0:
            self.summary_var.set("0 files total")
            return
        biz_n = sum(1 for f in self.files if f["format"] == "biz")
        pak_n = sum(1 for f in self.files if f["format"] == "pak")
        badg_n = sum(1 for f in self.files if f["format"] == "badge")
        other = n - biz_n - pak_n - badg_n
        parts = [f"{n} file(s)"]
        if biz_n:
            parts.append(f".biz x{biz_n}")
        if pak_n:
            parts.append(f".pak x{pak_n}")
        if badg_n:
            parts.append(f"Badge x{badg_n}")
        if other:
            parts.append(f"other x{other}")
        out = self.output_dir or "(not set)"
        self.summary_var.set(f"{'  |  '.join(parts)}  |  Output -> {Path(out).name if Path(out).exists() else out}")

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title="Select data files",
            filetypes=[("Supported formats", "*.biz *.pak *.in_ *.tga *.bmp *.dds *.cpse"),
                       (".biz container", "*.biz"),
                       (".pak resource pack", "*.pak"),
                       ("Images", "*.tga *.bmp *.dds"),
                       ("All files", "*.*")]
        )
        if not paths:
            return

        added = 0
        for path in paths:
            p = Path(path)
            if any(f["path"] == p for f in self.files):
                continue

            try:
                data = p.read_bytes()
            except Exception as e:
                self._tree_append(p, "ERR", f"Read error: {e}", "Error")
                self.files.append({"path": p, "format": "err", "internal_name": "",
                                    "size": p.stat().st_size})
                added += 1
                continue

            fmt = detect_format(data)
            info_text = ""

            if fmt == "biz":
                try:
                    iname, uncomp, _ = read_biz(data)
                    info_text = f"Internal: {iname}  ({uncomp:,} B)"
                except Exception as e:
                    info_text = f"Parse error: {e}"
                fmt_text = "BIZ"

            elif fmt == "pak":
                try:
                    hdr = read_pak_header(data)
                    orig = hdr["name_decoded"].decode("ascii", errors="replace")
                    info_text = f"Orig: {orig!r} (embedded .biz x {hdr['comp_size']:,} B)"
                except Exception as e:
                    info_text = f"Parse error: {e}"
                fmt_text = "PAK"

            elif fmt == "badge":
                sha1, bd = read_badge(data)
                info_text = f"SHA-1: {sha1.hex()[:16]}...  .biz: {len(bd)} B"
                fmt_text = "BADGE"

            else:
                fmt_text = "UNKNOWN"
                info_text = f"First 8 bytes: {data[:8].hex()}"

            self._tree_append(p, fmt_text, info_text, "Pending")
            self.files.append({
                "path": p,
                "format": fmt,
                "internal_name": info_text,
                "size": p.stat().st_size,
            })
            added += 1

        self._update_summary()
        self.status(f"Added {added} file(s)")

    def _select_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_dir = path
            self.output_var.set(f"Output folder: {path}")
            self._update_summary()
            self.status(f"Output folder set: {path}")

    def _decompress(self):
        if not self.output_dir:
            messagebox.showerror("Error", "Please select an output folder first")
            return
        if not self.files:
            messagebox.showerror("Error", "Please add files to the list first")
            return

        self._set_buttons_state(False)
        self.status("Extracting...")

        def worker():
            try:
                self._do_decompress()
            finally:
                self.root.after(0, lambda: self._set_buttons_state(True))

        threading.Thread(target=worker, daemon=True).start()

    def _make_out_name(self, src_path: Path, internal_name: str) -> str:
        """
        Derive output filename from source path & internal name.
        - If internal name has a real extension, use source stem + that extension.
        - .biz / .badge always produce .sum (the decompressed payload).
        - Otherwise fall back to original filename (e.g. .pak -> payload.bin).
        """
        src_stem = src_path.stem
        int_ext = Path(internal_name).suffix

        if int_ext and int_ext not in (".raw", ""):
            return src_stem + int_ext
        src_suffix = src_path.suffix.lower()
        if src_suffix in (".biz", ".badge"):
            return src_stem + ".sum"
        return src_path.name

    def _do_decompress(self):
        manifest = {}
        ok = fail = 0
        out_root = Path(self.output_dir)

        for idx, entry in enumerate(self.files):
            p = entry["path"]
            fmt = entry["format"]
            item_id = self._item_for_path(p)
            self._tree_update(item_id, "Extracting...")
            self.status(f"Extracting: {p.name}")

            try:
                data = p.read_bytes()
                raw_data = None
                out_name = ""

                if fmt == "biz":
                    iname, _, raw_data = read_biz(data)
                    out_name = self._make_out_name(p, iname)
                    entry["_internal_name"] = iname
                    entry["_raw_data"] = raw_data

                elif fmt == "pak":
                    orig_name, raw_data = unpack_pak(data)
                    out_name = Path(orig_name).name
                    entry["_raw_data"] = raw_data
                    entry["_internal_name"] = orig_name

                elif fmt == "badge":
                    _, bd_data = read_badge(data)
                    iname, _, raw_data = read_biz(bd_data)
                    out_name = self._make_out_name(p, iname)
                    entry["_internal_name"] = iname
                    entry["_raw_data"] = raw_data

                else:
                    self._tree_update(item_id, "Unsupported format")
                    fail += 1
                    continue

                if raw_data is None:
                    self._tree_update(item_id, "No data")
                    fail += 1
                    continue

                out_path = out_root / out_name
                counter = 1
                while out_path.exists():
                    stem = Path(out_name).stem
                    suffix = Path(out_name).suffix
                    out_path = out_root / f"{stem}_{counter}{suffix}"
                    counter += 1

                out_path.write_bytes(raw_data)
                manifest[out_path.name] = {
                    "internal_name": entry.get("_internal_name", ""),
                    "format": fmt,
                    "original_name": p.name,
                    "size": len(raw_data),
                }

                self._tree_update(item_id, f"[OK] -> {out_path.name} ({len(raw_data):,} B)")
                ok += 1

            except Exception as e:
                self._tree_update(item_id, f"[ERR] {e}")
                fail += 1

        if manifest:
            man_path = out_root / ".biz_manifest.json"
            man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            self.manifest = manifest

        self.root.after(0, lambda: self.status(f"Extract complete: {ok} OK, {fail} failed"))

    def _recompress(self):
        if not self.output_dir:
            messagebox.showerror("Error", "Please select an output folder first")
            return

        man_path = Path(self.output_dir) / ".biz_manifest.json"
        if man_path.exists():
            self.manifest = json.loads(man_path.read_text(encoding="utf-8"))
        elif self.files:
            for entry in self.files:
                if entry["format"] == "biz" and "_internal_name" in entry:
                    self.manifest[entry["path"].name] = {
                        "internal_name": entry["_internal_name"],
                        "format": "biz",
                        "original_name": entry["path"].name,
                        "size": entry.get("size", 0),
                    }
        else:
            messagebox.showerror("Error", "Nothing to re-pack. Extract files first.")
            return

        if not self.manifest:
            messagebox.showerror("Error", "No manifest information available")
            return

        self._set_buttons_state(False)
        self.status("Re-packing...")

        def worker():
            try:
                self._do_recompress()
            finally:
                self.root.after(0, lambda: self._set_buttons_state(True))

        threading.Thread(target=worker, daemon=True).start()

    def _do_recompress(self):
        ok = fail = 0
        out_root = Path(self.output_dir)
        compressed_dir = out_root / "_compressed"
        compressed_dir.mkdir(exist_ok=True)

        biz_map = {}
        for entry in self.files:
            if entry["format"] == "biz":
                iname = entry.get("_internal_name", "")
                if not iname:
                    try:
                        data = entry["path"].read_bytes()
                        iname, _, _ = read_biz(data)
                    except:
                        pass
                if iname:
                    biz_map[Path(entry["path"]).stem] = iname

        for raw_name, info in self.manifest.items():
            raw_path = out_root / raw_name
            if not raw_path.exists():
                status_text = f"Not found: {raw_name}"
                self._mark_item(info.get("original_name", raw_name), status_text)
                fail += 1
                continue

            iname = info.get("internal_name", "")
            fmt = info.get("format", "biz")

            try:
                raw_data = raw_path.read_bytes()

                if fmt == "biz":
                    if not iname:
                        for stem, candidate in biz_map.items():
                            if raw_name.startswith(stem):
                                iname = candidate
                                break
                    if not iname:
                        iname = raw_path.stem

                    out_data = write_biz(iname, raw_data)
                    out_path = compressed_dir / f"{raw_path.stem}.biz"
                    out_path.write_bytes(out_data)

                    self._mark_item(raw_name, f"[OK] -> .biz ({len(out_data):,} B)")
                    ok += 1

                elif fmt == "pak":
                    self._mark_item(raw_name, "[SKIP] .pak re-pack not yet supported")

                elif fmt == "badge":
                    self._mark_item(raw_name, "[SKIP] Badge re-pack not yet supported")

                else:
                    self._mark_item(raw_name, "[SKIP] Unsupported")

            except Exception as e:
                self._mark_item(raw_name, f"[ERR] {e}")
                fail += 1

        self.root.after(0, lambda: self.status(
            f"Re-pack complete: {ok} OK, {fail} failed  ->  {compressed_dir}"))

    def _export_sum_csv(self):
        """Export selected .sum files to CSV."""
        from cgdata_reader import load_sum, export_csv as sum_export_csv

        if not self.output_dir:
            messagebox.showerror("Error", "Please select an output folder first")
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Hint", "Select one or more files in the list first")
            return

        out_root = Path(self.output_dir)
        if not out_root.exists():
            messagebox.showerror("Error", f"Output folder does not exist: {out_root}")
            return

        target_sums = []
        skipped = []
        for item_id in sel:
            vals = self.tree.item(item_id, "values")
            if not vals:
                continue
            fname = vals[0]

            entry = None
            for e in self.files:
                if e["path"].name == fname:
                    entry = e
                    break

            if entry is None:
                skipped.append(fname)
                continue

            stem = entry["path"].stem
            candidate = out_root / f"{stem}.sum"
            if candidate.exists():
                target_sums.append(candidate)
            else:
                skipped.append(fname)

        if not target_sums:
            messagebox.showinfo("Hint", "No extracted .sum files found for the selected entries.\n\n"
                                        "Please click 'Extract' first to decompress .biz/.pak into .sum.")
            return

        self._set_buttons_state(False)
        self.status(f"Parsing {len(target_sums)} .sum file(s)...")

        def worker():
            total_ok = total_fail = 0
            for sf in target_sums:
                try:
                    csv_dir = sf.parent / f"{sf.stem}_csv"
                    gdata = load_sum(str(sf))
                    sum_export_csv(gdata, csv_dir)
                    total_ok += 1
                except Exception as e:
                    total_fail += 1
                    import traceback
                    traceback.print_exc()
            self.root.after(0, lambda: self.status(
                f".sum export complete: {total_ok} OK, {total_fail} failed"))
            self.root.after(0, lambda: self._set_buttons_state(True))

        threading.Thread(target=worker, daemon=True).start()

    def _mark_item(self, name_or_path, status_text):
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if vals and (vals[0] == Path(name_or_path).name or vals[3].startswith(name_or_path[:20])):
                self._tree_update(item_id, status_text)
                return

    def _clear(self):
        if self.files:
            if not messagebox.askyesno("Confirm", "Clear all files from the list?"):
                return
        self.files.clear()
        self.manifest.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._update_summary()
        self.status("Cleared")

    def _on_close(self):
        self.root.destroy()

    # ── Tree helpers ──

    def _tree_append(self, path, fmt_text, info_text, status_text):
        p = Path(path)
        self.tree.insert("", tk.END, values=(
            p.name,
            f"{p.stat().st_size:,}",
            fmt_text,
            info_text,
            status_text,
        ))

    def _tree_update(self, item_id, status_text):
        if not item_id:
            return
        vals = list(self.tree.item(item_id, "values"))
        if len(vals) >= 5:
            vals[4] = status_text
            self.tree.item(item_id, values=tuple(vals))
        self.root.update_idletasks()

    def _item_for_path(self, path):
        name = Path(path).name
        for item_id in self.tree.get_children():
            if self.tree.item(item_id, "values")[0] == name:
                return item_id
        return None

    def _set_buttons_state(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_select.config(state=state)
        self.btn_output.config(state=state)
        self.btn_decompress.config(state=state)
        self.btn_recompress.config(state=state)
        self.btn_sum_csv.config(state=state)
        self.btn_clear.config(state=state)


def main():
    root = tk.Tk()
    app = BizGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

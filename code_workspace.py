"""Local text editing. Documents never use the key API or execute their contents."""
import codecs
import os
from pathlib import Path
import stat
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

BG = "#10131E"
FG = "#F0F2FA"
MUTED = "#9AA3BA"
PURPLE = "#9B87F5"


class ExternalChangeError(OSError):
    pass


class Document:
    def __init__(self, path=None, text="", encoding="utf-8", bom=b"", newline="\n", original=None):
        self.path = path
        self.text = text
        self.encoding = encoding
        self.bom = bom
        self.newline = newline
        self.original = original

    @classmethod
    def open(cls, path):
        path = Path(path).expanduser().resolve()
        raw = path.read_bytes()
        encoding, bom = "utf-8", b""
        for marker, codec in ((codecs.BOM_UTF8, "utf-8"),
                              (codecs.BOM_UTF16_LE, "utf-16-le"),
                              (codecs.BOM_UTF16_BE, "utf-16-be")):
            if raw.startswith(marker):
                encoding, bom = codec, marker
                break
        text = raw[len(bom):].decode(encoding)
        if "\x00" in text:
            raise ValueError("This appears to be a binary file. Open a text or script file instead.")
        newline = "\r\n" if "\r\n" in text else ("\r" if "\r" in text else "\n")
        return cls(path, text.replace("\r\n", "\n").replace("\r", "\n"),
                   encoding, bom, newline, raw)

    def save(self, text, path=None, overwrite=False):
        target = Path(path).expanduser().resolve() if path else self.path
        if target is None:
            raise ValueError("Choose a filename first.")
        if target == self.path and not overwrite:
            try:
                current = target.read_bytes()
            except FileNotFoundError:
                current = None
            if current != self.original:
                raise ExternalChangeError("The file was changed or removed outside this editor.")
        # An untouched file retains even mixed line endings exactly.
        raw = (self.original if text == self.text and self.original is not None else
               self.bom + text.replace("\n", self.newline).encode(self.encoding))
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
        fd, temp = tempfile.mkstemp(prefix=".solos-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(temp, mode)
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        self.path, self.text, self.original = target, text, raw


class EditorTab:
    def __init__(self, workspace, document, title):
        self.workspace, self.document, self.title = workspace, document, title
        self.frame = tk.Frame(workspace.notebook, bg=BG)
        self.gutter = tk.Canvas(self.frame, width=58, bg=BG, highlightthickness=0)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text = tk.Text(self.frame, bg=BG, fg=FG, insertbackground=FG,
                            selectbackground="#483B73", font=("Consolas", 12),
                            wrap="none", undo=True, maxundo=200, borderwidth=0,
                            highlightthickness=0, padx=8, pady=10, tabs=(32,))
        self.text.grid(row=0, column=1, sticky="nsew")
        # Handle editor shortcuts before Tk Text's built-in class bindings.
        for sequence, command in workspace.commands:
            self.text.bind(sequence, lambda e, fn=command: workspace.shortcut(fn))
        vertical = ttk.Scrollbar(self.frame, command=self.text.yview)
        vertical.grid(row=0, column=2, sticky="ns")
        horizontal = ttk.Scrollbar(self.frame, orient="horizontal", command=self.text.xview)
        horizontal.grid(row=1, column=1, sticky="ew")
        self.text.configure(xscrollcommand=horizontal.set,
                            yscrollcommand=lambda a, b: (vertical.set(a, b), self.draw_lines()))
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)
        self.text.insert("1.0", document.text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.dirty = False
        self.text.bind("<<Modified>>", self.changed)
        self.text.bind("<KeyRelease>", lambda e: workspace.update_status())
        self.text.bind("<ButtonRelease-1>", lambda e: workspace.update_status())
        self.text.bind("<Configure>", lambda e: self.draw_lines())
        workspace.notebook.add(self.frame, text=title)
        workspace.notebook.select(self.frame)
        self.text.focus_set()

    def content(self):
        return self.text.get("1.0", "end-1c")

    def changed(self, event=None):
        if self.text.edit_modified():
            self.dirty = True
            self.text.edit_modified(False)
            self.workspace.notebook.tab(self.frame, text=self.title + " *")
            self.draw_lines()
            self.workspace.update_status()

    def draw_lines(self):
        self.gutter.delete("all")
        index = self.text.index("@0,0")
        while True:
            info = self.text.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(48, info[1], anchor="ne", text=index.split(".")[0],
                                    fill=MUTED, font=("Consolas", 11))
            index = self.text.index(index + "+1line")

    def has_changes(self):
        return self.content() != self.document.text


class CodeWorkspace(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0B0D14", corner_radius=0)
        self.tabs = {}
        self.counter = 0
        self.folder = None
        self.entries = []
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", padx=24, pady=(16, 8))
        ctk.CTkLabel(heading, text="Code workspace", font=("Segoe UI", 26, "bold"),
                     text_color=FG).pack(side="left")
        ctk.CTkLabel(heading, text="Local files · Saved on your computer", text_color=MUTED).pack(side="right")
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=8)
        for label, command in (("New", self.new), ("Open files", self.open_files),
                               ("Open folder", self.open_folder), ("Save", self.save),
                               ("Save as", lambda: self.save(save_as=True)),
                               ("Save all", self.save_all), ("Close tab", self.close_tab)):
            ctk.CTkButton(toolbar, text=label, command=command, width=100, height=32,
                          fg_color="#241B45", hover_color="#483B73").pack(side="left", padx=(0, 8))
        search = ctk.CTkFrame(self, fg_color="transparent")
        search.pack(fill="x", padx=24, pady=(0, 8))
        self.query = ctk.CTkEntry(search, placeholder_text="Find in current file (Ctrl+F)", width=280)
        self.query.pack(side="left")
        self.query.bind("<Return>", lambda e: self.find_next())
        ctk.CTkButton(search, text="Find next", command=self.find_next, width=100,
                      fg_color="#241B45").pack(side="left", padx=8)
        self.find_result = ctk.CTkLabel(search, text="", text_color=MUTED)
        self.find_result.pack(side="left")
        body = tk.PanedWindow(self, orient="horizontal", bg="#0B0D14", sashwidth=8, bd=0)
        body.pack(fill="both", expand=True, padx=24)
        sidebar = tk.Frame(body, bg=BG)
        self.folder_label = tk.Label(sidebar, text="Open a folder to browse files", bg=BG, fg=MUTED,
                                     anchor="w", wraplength=210, padx=8, pady=8)
        self.folder_label.pack(fill="x")
        actions = tk.Frame(sidebar, bg=BG)
        actions.pack(fill="x")
        for label, command in (("↑ Parent", self.parent_folder), ("Refresh", self.refresh_folder)):
            tk.Button(actions, text=label, command=command, bg="#241B45", fg=FG,
                      relief="flat").pack(side="left", padx=5, pady=5)
        self.files = tk.Listbox(sidebar, bg=BG, fg=FG, selectbackground="#483B73",
                               borderwidth=0, highlightthickness=0, exportselection=False)
        scrollbar = ttk.Scrollbar(sidebar, command=self.files.yview)
        scrollbar.pack(side="right", fill="y")
        self.files.configure(yscrollcommand=scrollbar.set)
        self.files.pack(fill="both", expand=True)
        self.files.bind("<Double-Button-1>", self.open_selected)
        self.files.bind("<Return>", self.open_selected)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Code.TNotebook", background=BG, borderwidth=0)
        style.configure("Code.TNotebook.Tab", background="#171B28", foreground=MUTED, padding=(14, 9))
        style.map("Code.TNotebook.Tab", background=[("selected", "#241B45")], foreground=[("selected", FG)])
        self.notebook = ttk.Notebook(body, style="Code.TNotebook")
        body.add(sidebar, width=230, minsize=160)
        body.add(self.notebook, minsize=400, stretch="always")
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_status())
        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=MUTED)
        self.status.pack(fill="x", padx=24, pady=8)
        self.commands = (("<Control-n>", self.new), ("<Control-o>", self.open_files),
                                  ("<Control-s>", self.save),
                                  ("<Control-Shift-S>", lambda: self.save(save_as=True)),
                                  ("<Control-w>", self.close_tab),
                                  ("<Control-f>", self.query.focus_set))
        for sequence, command in self.commands:
            self.winfo_toplevel().bind(sequence, lambda e, fn=command: self.shortcut(fn), add="+")
        self.new()

    def shortcut(self, command):
        if self.winfo_ismapped():
            command()
            return "break"

    def active(self):
        return self.tabs.get(self.notebook.select())

    def new(self):
        self.counter += 1
        tab = EditorTab(self, Document(), "Untitled %d" % self.counter)
        self.tabs[str(tab.frame)] = tab
        self.update_status()
        return tab

    def open_files(self):
        paths = filedialog.askopenfilenames(parent=self, title="Open local scripts or text files",
                    filetypes=[("Text and scripts", "*.txt *.lua *.luau *.py *.json *.js *.md"), ("All files", "*")])
        for path in paths:
            self.open_path(path)

    def open_path(self, path):
        path = Path(path).expanduser().resolve()
        for tab in self.tabs.values():
            if tab.document.path == path:
                self.notebook.select(tab.frame)
                tab.text.focus_set()
                return tab
        try:
            document = Document.open(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot open file", str(error), parent=self)
            return None
        tab = EditorTab(self, document, path.name)
        self.tabs[str(tab.frame)] = tab
        self.update_status()
        return tab

    def save(self, tab=None, save_as=False):
        tab = tab or self.active()
        if tab is None:
            return True
        path = tab.document.path
        if save_as or path is None:
            chosen = filedialog.asksaveasfilename(parent=self, title="Save local file",
                         initialdir=str(path.parent) if path else (str(self.folder) if self.folder else None),
                         initialfile=path.name if path else tab.title + ".txt",
                         defaultextension=".txt", filetypes=[("All files", "*")])
            if not chosen:
                return False
            path = Path(chosen).expanduser().resolve()
        if any(other is not tab and other.document.path == path for other in self.tabs.values()):
            messagebox.showerror("File already open", "That file is open in another tab. Save or close that tab first.", parent=self)
            return False
        try:
            try:
                tab.document.save(tab.content(), path)
            except ExternalChangeError:
                if not messagebox.askyesno("File changed on disk",
                    "This file was changed or removed outside the editor. Replace it with this tab's contents?",
                    parent=self, default="no"):
                    return False
                tab.document.save(tab.content(), path, overwrite=True)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot save file", str(error), parent=self)
            return False
        tab.title = tab.document.path.name
        tab.dirty = False
        tab.text.edit_modified(False)
        self.notebook.tab(tab.frame, text=tab.title)
        self.update_status()
        self.refresh_folder()
        return True

    def save_all(self):
        for tab in list(self.tabs.values()):
            if (tab.has_changes() or tab.document.path is None) and not self.save(tab):
                return False
        return True

    def confirm_close(self, tab):
        if not tab.has_changes():
            return True
        self.notebook.select(tab.frame)
        answer = messagebox.askyesnocancel("Unsaved changes", "Save changes to %s?" % tab.title, parent=self)
        return answer is False or (answer is True and self.save(tab))

    def can_close(self):
        return all(self.confirm_close(tab) for tab in list(self.tabs.values()))

    def close_tab(self):
        tab = self.active()
        if tab and self.confirm_close(tab):
            self.tabs.pop(str(tab.frame))
            self.notebook.forget(tab.frame)
            tab.frame.destroy()
            self.update_status()

    def open_folder(self):
        chosen = filedialog.askdirectory(parent=self, title="Browse a local code folder")
        if chosen:
            self.folder = Path(chosen)
            self.refresh_folder()

    def parent_folder(self):
        if self.folder:
            self.folder = self.folder.parent
            self.refresh_folder()

    def refresh_folder(self):
        if self.folder is None:
            return
        try:
            entries = sorted(self.folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as error:
            self.folder_label.configure(text=str(error))
            return
        self.entries = entries
        self.folder_label.configure(text=str(self.folder))
        self.files.delete(0, "end")
        for path in entries:
            self.files.insert("end", ("▸ " if path.is_dir() else "  ") + path.name)

    def open_selected(self, event=None):
        selection = self.files.curselection()
        if selection:
            path = self.entries[selection[0]]
            if path.is_dir():
                self.folder = path
                self.refresh_folder()
            else:
                self.open_path(path)

    def find_next(self):
        tab, query = self.active(), self.query.get()
        if not tab or not query:
            return
        text = tab.text
        index = text.search(query, "insert", stopindex="end", nocase=True, exact=True)
        if not index:
            index = text.search(query, "1.0", stopindex="insert", nocase=True, exact=True)
        text.tag_remove("sel", "1.0", "end")
        self.find_result.configure(text="" if index else "No match")
        if index:
            end = "%s+%dc" % (index, len(query))
            text.tag_add("sel", index, end)
            text.mark_set("insert", end)
            text.see(index)
            text.focus_set()
            self.update_status()

    def update_status(self):
        tab = self.active()
        if not tab:
            self.status.configure(text="New or Open files to start editing · Ctrl+N / Ctrl+O")
            return
        line, column = tab.text.index("insert").split(".")
        doc = tab.document
        newline = {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}[doc.newline]
        self.status.configure(text="%s   |   Ln %s, Col %d   |   %s · %s   |   Ctrl+S to save" %
                              (doc.path or "Unsaved local file", line, int(column) + 1, doc.encoding.upper(), newline))

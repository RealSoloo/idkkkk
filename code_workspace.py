"""Local text editing. Documents never use the key API or execute their contents."""
from bisect import bisect_right
import ast
import sys
import importlib.metadata
import json
import queue
import re
import threading
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


EDITOR_REVISION = "editor-3"

LANGUAGES = ["Luau", "Python", "JSON", "JavaScript", "Plain text"]
COLORS = {"keyword": "#BDA7FF", "string": "#91D9B1", "comment": "#697892",
          "number": "#F4BD6A", "function": "#81CDE8", "operator": "#D7B8EE"}


def language_for(path):
    suffix = Path(path).suffix.lower() if path else ""
    return {".py": "Python", ".json": "JSON", ".js": "JavaScript",
            ".md": "Plain text"}.get(suffix, "Luau")


def analyze_code(source, language):
    """Parse only; never import, evaluate, or run the user's code."""
    highlights, problems = [], []
    notice = "Syntax checked · runtime errors are not checked"
    try:
        from pygments.lexers import get_lexer_by_name
        from pygments.token import Keyword, String, Comment, Number, Name, Operator
        lexer = get_lexer_by_name({"Luau": "luau", "Python": "python", "JSON": "json",
                                  "JavaScript": "javascript", "Plain text": "text"}[language])
        for offset, token, value in lexer.get_tokens_unprocessed(source):
            for kind, family in (("keyword", Keyword), ("string", String), ("comment", Comment),
                                 ("number", Number), ("function", Name.Function), ("operator", Operator)):
                if token in family:
                    highlights.append((kind, offset, offset + len(value)))
                    break
    except ImportError as error:
        notice = "Highlighting unavailable: " + str(error)
    except Exception as error:
        notice = "Highlighting unavailable: " + str(error)
    try:
        if language == "Python":
            ast.parse(source)
        elif language == "JSON":
            json.loads(source)
        elif language == "Luau":
            from tree_sitter import Language, Parser
            import tree_sitter_luau
            raw = source.encode("utf-8")
            tree = Parser(Language(tree_sitter_luau.language())).parse(raw)
            lines = raw.split(b"\n")
            stack = [tree.root_node]
            while stack and len(problems) < 100:
                node = stack.pop()
                if node.is_missing or node.type == "ERROR":
                    row, byte_col = node.start_point
                    line = lines[row]
                    col = len(line[:byte_col].decode("utf-8", errors="replace")) + 1
                    detail = "Expected " + node.type if node.is_missing else "Unexpected or incomplete syntax"
                    problems.append((row + 1, col, detail))
                    if node.type == "ERROR":
                        continue
                stack.extend(reversed(node.children))
        else:
            notice = "Highlighting only · syntax checking unavailable for " + language
    except SyntaxError as error:
        problems.append((error.lineno or 1, error.offset or 1, error.msg))
    except json.JSONDecodeError as error:
        problems.append((error.lineno, error.colno, error.msg))
    except ImportError as error:
        notice = "Luau checks unavailable: " + str(error)
    except Exception as error:
        notice = "Syntax checker unavailable: " + str(error)
    return highlights, problems, notice


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
        self.language = language_for(document.path)
        self.revision = 0
        self.analysis_job = None
        self.problems = []
        self.notice = "Checking syntax…"
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
        vertical = ctk.CTkScrollbar(self.frame, command=self.text.yview, fg_color=BG, button_color="#333A50", button_hover_color=PURPLE)
        vertical.grid(row=0, column=2, sticky="ns")
        horizontal = ctk.CTkScrollbar(self.frame, orientation="horizontal", command=self.text.xview, fg_color=BG, button_color="#333A50", button_hover_color=PURPLE)
        horizontal.grid(row=1, column=1, sticky="ew")
        self.text.configure(xscrollcommand=horizontal.set,
                            yscrollcommand=lambda a, b: (vertical.set(a, b), self.draw_lines()))
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)
        for kind, color in COLORS.items():
            self.text.tag_configure(kind, foreground=color)
        self.text.tag_configure("current_line", background="#171D2D")
        self.text.tag_configure("error", underline=True, foreground="#FB7185")
        self.text.bind("<Return>", self.indent_return)
        self.text.bind("<Tab>", self.indent_tab)
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
        self.schedule_analysis()

    def content(self):
        return self.text.get("1.0", "end-1c")

    def changed(self, event=None):
        if self.text.edit_modified():
            self.dirty = True
            self.text.edit_modified(False)
            self.workspace.notebook.tab(self.frame, text=self.title + " *")
            self.draw_lines()
            self.schedule_analysis()
            self.workspace.update_status()

    def indent_return(self, event=None):
        prefix = self.text.get("insert linestart", "insert")
        indent = re.match(r"[ \t]*", prefix).group()
        if re.search(r"(?:\bthen|\bdo|\belse|\brepeat|\bfunction.*\)|[{:])\s*$", prefix):
            indent += "    "
        if self.text.tag_ranges("sel"):
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", "\n" + indent)
        self.text.see("insert")
        return "break"

    def indent_tab(self, event=None):
        self.text.insert("insert", "    ")
        return "break"

    def schedule_analysis(self):
        self.revision += 1
        self.problems = []
        self.notice = "Checking syntax…"
        self.text.tag_remove("error", "1.0", "end")
        if self.analysis_job:
            self.text.after_cancel(self.analysis_job)
        self.analysis_job = self.text.after(400, self.start_analysis)

    def start_analysis(self):
        self.analysis_job = None
        source, language, revision = self.content(), self.language, self.revision
        # Workers only handle strings. Tk calls stay on the UI thread.
        results = self.workspace.analysis_results
        def work():
            try:
                result = analyze_code(source, language)
            except Exception as error:
                result = ([], [], "Checker unavailable: " + str(error))
            results.put((self, revision, result))
        threading.Thread(target=work, daemon=True).start()

    def apply_analysis(self, result):
        highlights, self.problems, self.notice = result
        source = self.content()
        starts = [0] + [match.end() for match in re.finditer("\n", source)]
        def text_index(offset):
            row = bisect_right(starts, offset)
            return "%d.%d" % (row, offset - starts[row - 1])
        for kind in COLORS:
            self.text.tag_remove(kind, "1.0", "end")
            ranges = []
            for name, start, end in highlights:
                if name == kind:
                    ranges.extend((text_index(start), text_index(end)))
            for offset in range(0, len(ranges), 1000):
                self.text.tag_add(kind, *ranges[offset:offset + 1000])
        self.text.tag_remove("error", "1.0", "end")
        for line, column, _ in self.problems:
            index = "%d.%d" % (line, max(0, column - 1))
            self.text.tag_add("error", index, index + " lineend+1c")
        self.text.tag_raise("error")
        self.text.tag_raise("sel")
        self.draw_lines()
        if self.workspace.active() is self:
            self.workspace.update_status()

    def draw_lines(self):
        self.gutter.delete("all")
        index = self.text.index("@0,0")
        while True:
            info = self.text.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(48, info[1], anchor="ne", text=index.split(".")[0],
                                    fill="#FB7185" if any(p[0] == int(index.split(".")[0]) for p in self.problems) else MUTED, font=("Consolas", 11))
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
        self.analysis_results = queue.Queue()
        self.closing = False
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", padx=24, pady=(16, 8))
        ctk.CTkLabel(heading, text="Code workspace", font=("Segoe UI", 24, "bold"),
                     text_color=FG).pack(side="left")
        ctk.CTkLabel(heading, text="LOCAL WORKSPACE  /  Saved on your computer", text_color=MUTED).pack(side="right")
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=8)
        for label, command in (("New", self.new), ("Open files", self.open_files),
                               ("Open folder", self.open_folder), ("Save", self.save),
                               ("Save as", lambda: self.save(save_as=True)),
                               ("Save all", self.save_all), ("Close tab", self.close_tab)):
            ctk.CTkButton(toolbar, text=label, command=command, width=100, height=32,
                          fg_color=PURPLE if label == "Save" else "#171B28", text_color=BG if label == "Save" else FG,
                          border_width=1, border_color="#2B3247", hover_color="#483B73").pack(side="left", padx=(0, 8))
        search = ctk.CTkFrame(self, fg_color="transparent")
        search.pack(fill="x", padx=24, pady=(0, 8))
        self.query = ctk.CTkEntry(search, placeholder_text="Find in file  ·  Ctrl+F", width=280,
                                  fg_color=BG, border_color="#2B3247", text_color=FG)
        self.query.pack(side="left")
        self.query.bind("<Return>", lambda e: self.find_next())
        ctk.CTkButton(search, text="Find next", command=self.find_next, width=100,
                      fg_color="#241B45").pack(side="left", padx=8)
        self.find_result = ctk.CTkLabel(search, text="", text_color=MUTED)
        self.find_result.pack(side="left")
        self.language_menu = ctk.CTkOptionMenu(search, values=LANGUAGES, command=self.change_language,
                                              fg_color="#171B28", button_color="#2B3247",
                                              button_hover_color="#483B73", width=130)
        self.language_menu.pack(side="right")
        ctk.CTkLabel(search, text="Language", text_color=MUTED).pack(side="right", padx=12)
        body = tk.PanedWindow(self, orient="horizontal", bg="#0B0D14", sashwidth=8, bd=0)
        body.pack(fill="both", expand=True, padx=24)
        sidebar = ctk.CTkFrame(body, fg_color=BG, corner_radius=12, border_width=1, border_color="#2B3247")
        ctk.CTkLabel(sidebar, text="EXPLORER", text_color=PURPLE, anchor="w", font=("Segoe UI", 11, "bold")).pack(fill="x", padx=14, pady=(12, 0))
        self.folder_label = tk.Label(sidebar, text="Open a folder to browse files", bg=BG, fg=MUTED,
                                     anchor="w", wraplength=210, padx=8, pady=8)
        self.folder_label.pack(fill="x")
        actions = tk.Frame(sidebar, bg=BG)
        actions.pack(fill="x")
        for label, command in (("↑ Parent", self.parent_folder), ("Refresh", self.refresh_folder)):
            ctk.CTkButton(actions, text=label, command=command, fg_color="#171B28", hover_color="#483B73", width=90, height=28).pack(side="left", padx=5, pady=5)
        self.files = tk.Listbox(sidebar, bg=BG, fg=FG, selectbackground="#483B73",
                               font=("Segoe UI", 12), activestyle="none", selectborderwidth=0,
                               borderwidth=0, highlightthickness=0, exportselection=False)
        scrollbar = ctk.CTkScrollbar(sidebar, command=self.files.yview, fg_color=BG, button_color="#333A50")
        scrollbar.pack(side="right", fill="y")
        self.files.configure(yscrollcommand=scrollbar.set)
        self.files.pack(fill="both", expand=True)
        self.files.bind("<Double-Button-1>", self.open_selected)
        self.files.bind("<Return>", self.open_selected)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Code.TNotebook", background=BG, borderwidth=0, lightcolor=BG, darkcolor=BG, bordercolor=BG)
        style.configure("Code.TNotebook.Tab", background="#171B28", foreground=MUTED, padding=(18, 11), font=("Segoe UI", 11), borderwidth=0, lightcolor=BG, darkcolor=BG, bordercolor=BG)
        style.map("Code.TNotebook.Tab", background=[("selected", "#241B45")], foreground=[("selected", FG)])
        style.layout("Code.TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
        editor_area = tk.Frame(body, bg=BG)
        self.notebook = ttk.Notebook(editor_area, style="Code.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        problems_panel = ctk.CTkFrame(editor_area, fg_color="#131722", corner_radius=0, height=120)
        problems_panel.pack(fill="x", pady=(1, 0))
        problem_bar = ctk.CTkFrame(problems_panel, fg_color="transparent")
        problem_bar.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkButton(problem_bar, text="Check setup", width=96, height=26,
                      fg_color="#241B45", command=self.check_setup).pack(side="right")
        ctk.CTkButton(problem_bar, text="Check code", width=96, height=26,
                      fg_color="#171B28", command=self.check_now).pack(side="right", padx=6)
        self.problem_heading = ctk.CTkLabel(problem_bar, text="PROBLEMS", text_color=MUTED, anchor="w", font=("Segoe UI", 11, "bold"))
        self.problem_heading.pack(side="left", fill="x", expand=True)
        self.problem_list = tk.Listbox(problems_panel, height=3, bg="#131722", fg="#FB7185", font=("Segoe UI", 11),
                                      selectbackground="#302748", activestyle="none", bd=0, highlightthickness=0)
        self.problem_list.pack(fill="x", padx=14, pady=(0, 10))
        self.problem_list.bind("<<ListboxSelect>>", self.jump_problem)
        self.problem_detail = ctk.CTkLabel(problems_panel, text="", text_color=MUTED, anchor="w",
                                          justify="left", wraplength=680)
        self.problem_detail.pack(fill="x", padx=14, pady=(0, 6))
        body.add(sidebar, width=230, minsize=160)
        body.add(editor_area, minsize=400, stretch="always")
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
        self.after(100, self.poll_analysis)

    def destroy(self):
        self.closing = True
        super().destroy()

    def poll_analysis(self):
        try:
            while True:
                tab, revision, result = self.analysis_results.get_nowait()
                if str(tab.frame) in self.tabs and tab.revision == revision:
                    try:
                        tab.apply_analysis(result)
                    except Exception as error:
                        tab.notice = "Editor display unavailable: " + str(error)
                        if self.active() is tab:
                            self.update_status()
        except queue.Empty:
            pass
        self.after(100, self.poll_analysis)

    def check_now(self):
        tab = self.active()
        if tab:
            tab.schedule_analysis()
            tab.text.after_cancel(tab.analysis_job)
            tab.start_analysis()
            self.update_status()

    def check_setup(self):
        colors, _, valid_notice = analyze_code('local value: number = 2', "Luau")
        _, errors, invalid_notice = analyze_code('local value = )', "Luau")
        versions = []
        for package in ("Pygments", "tree-sitter", "tree-sitter-luau"):
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = "NOT INSTALLED"
            versions.append(package + ": " + version)
        tab = self.active()
        report = "\n".join([
            "Solos Code Workspace " + EDITOR_REVISION,
            "Python: " + sys.version.split()[0], "Interpreter: " + sys.executable,
            "Editor file: " + str(Path(__file__).resolve()), *versions,
            "Luau color test: " + ("PASS" if colors else "FAIL"),
            "Luau error test: " + ("PASS" if errors else "FAIL"),
            "Color test status: " + valid_notice, "Error test status: " + invalid_notice,
            "Selected language: " + (tab.language if tab else "none"),
            "Current status: " + (tab.notice if tab else "no file open"),
        ])
        self.clipboard_clear()
        self.clipboard_append(report)
        messagebox.showinfo("Editor setup · report copied", report +
                            "\n\nReport copied to clipboard. No document contents are included.", parent=self)
        return report

    def change_language(self, language):
        tab = self.active()
        if tab:
            tab.language = language
            tab.schedule_analysis()
            self.update_status()

    def jump_problem(self, event=None):
        tab = self.active()
        selected = self.problem_list.curselection()
        if tab and selected and selected[0] < len(tab.problems):
            line, column, _ = tab.problems[selected[0]]
            index = "%d.%d" % (line, max(0, column - 1))
            tab.text.mark_set("insert", index)
            tab.text.see(index)
            tab.text.focus_set()

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
        previous_path = tab.document.path
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
        if path != previous_path and path.suffix.lower() in (".py", ".json", ".js", ".lua", ".luau", ".md"):
            tab.language = language_for(path)
            tab.schedule_analysis()
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
            if tab.analysis_job:
                tab.text.after_cancel(tab.analysis_job)
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
        if self.closing:
            return
        tab = self.active()
        if not tab:
            self.problem_list.delete(0, "end")
            self.problem_heading.configure(text="PROBLEMS · Open a file to check syntax", text_color=MUTED)
            self.problem_detail.configure(text="")
            self.status.configure(text="New or Open files to start editing · Ctrl+N / Ctrl+O")
            return
        self.language_menu.set(tab.language)
        unavailable = "unavailable" in tab.notice.lower()
        if unavailable:
            headline, color = "CHECKER / HIGHLIGHTING UNAVAILABLE", "#FB7185"
            detail = tab.notice + "\nRun python -m pip install -r requirements.txt, then restart the app. Use Check setup to copy details."
        elif tab.notice == "Checking syntax…":
            headline, color, detail = "CHECKING…", MUTED, ""
        elif tab.notice.startswith("Highlighting only"):
            headline, color, detail = "SYNTAX CHECKING OFF", "#F4BD6A", tab.notice
        else:
            headline = "%d SYNTAX ISSUE%s" % (len(tab.problems), "" if len(tab.problems) == 1 else "S")
            color = "#FB7185" if tab.problems else "#43D9AC"
            detail = "Syntax only · misspelled names, invalid game APIs and logic bugs are not checked."
        self.problem_heading.configure(text=headline, text_color=color)
        self.problem_detail.configure(text=detail)
        self.problem_list.delete(0, "end")
        for row, col, detail in tab.problems:
            self.problem_list.insert("end", "  Line %d:%d   %s" % (row, col, detail))
        tab.text.tag_remove("current_line", "1.0", "end")
        tab.text.tag_add("current_line", "insert linestart", "insert lineend+1c")
        tab.text.tag_lower("current_line")
        line, column = tab.text.index("insert").split(".")
        doc = tab.document
        newline = {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}[doc.newline]
        self.status.configure(text="%s   |   Ln %s, Col %d   |   %s · %s   |   Ctrl+S to save" %
                              (doc.path or "Unsaved local file", line, int(column) + 1, doc.encoding.upper(), newline))

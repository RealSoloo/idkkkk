"""Local text editing. Documents never use the key API or execute their contents."""
from bisect import bisect_right
import ast
import base64
import time
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
from lua_preview import LuaPreview, PreviewPlan, build_preview, EXAMPLE_SOURCE

BG = "#10131E"
FG = "#F0F2FA"
MUTED = "#9AA3BA"
PURPLE = "#9B87F5"


EDITOR_REVISION = "editor-5"
SESSION_PATH = Path.home() / ".solos_code_workspace.json"

LANGUAGES = ["Luau", "Python", "JSON", "JavaScript", "Plain text"]
COLORS = {
    "keyword": "#CE8CFF", "string": "#B6F36A", "comment": "#8B9CB6",
    "number": "#FFAE57", "function": "#FFD866", "operator": "#FF79C6",
    "variable": "#8CDCFE", "property": "#FFC9A3", "builtin": "#5EF0D5",
    "punctuation": "#E9D86C",
}


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
        from pygments.token import Keyword, String, Comment, Number, Name, Operator, Punctuation
        lexer = get_lexer_by_name({"Luau": "luau", "Python": "python", "JSON": "json",
                                  "JavaScript": "javascript", "Plain text": "text"}[language])
        previous = ""
        call_suffix = re.compile(r"\s*[(]")
        for offset, token, value in lexer.get_tokens_unprocessed(source):
            if token in Name:
                if token in Name.Function or call_suffix.match(source, offset + len(value)):
                    kind = "function"
                elif previous in (".", ":"):
                    kind = "property"
                elif token in Name.Builtin or token in Name.Class:
                    kind = "builtin"
                else:
                    kind = "variable"
                highlights.append((kind, offset, offset + len(value)))
            for kind, family in (("keyword", Keyword), ("string", String), ("comment", Comment),
                                 ("number", Number), ("operator", Operator), ("punctuation", Punctuation)):
                if token in family:
                    highlights.append((kind, offset, offset + len(value)))
                    break
            if value.strip() and token not in Comment:
                previous = value
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
        self.preview_result = None
        self.analysis_job = None
        self.problems = []
        self.notice = "Checking syntax…"
        self.frame = tk.Frame(workspace.notebook, bg=BG)
        self.gutter = tk.Canvas(self.frame, width=58, bg=BG, highlightthickness=0)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text = tk.Text(self.frame, bg=BG, fg=FG, insertbackground=FG,
                            selectbackground="#483B73", font=("Consolas", workspace.font_size),
                            wrap="none", height=1, width=1, undo=True, maxundo=200, borderwidth=0,
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
            self.workspace.schedule_session()
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
        preview_results = self.workspace.preview_results
        make_preview = self.workspace.preview_enabled and language == "Luau"
        def work():
            try:
                result = analyze_code(source, language)
            except Exception as error:
                result = ([], [], "Checker unavailable: " + str(error))
            results.put((self, revision, result))
            if make_preview:
                preview_results.put((self, revision, build_preview(source)))
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
                                    fill="#FB7185" if any(p[0] == int(index.split(".")[0]) for p in self.problems) else MUTED, font=("Consolas", self.workspace.font_size - 1))
            index = self.text.index(index + "+1line")

    def has_changes(self):
        return self.content() != self.document.text


class CodeWorkspace(ctk.CTkFrame):
    def __init__(self, parent, session_path=None):
        super().__init__(parent, fg_color="#0B0D14", corner_radius=0)
        self.tabs = {}
        self.counter = 0
        self.folder = None
        self.entries = []
        self.analysis_results = queue.Queue()
        self.preview_results = queue.Queue()
        self.closing = False
        self.restoring = True
        self.session_job = None
        self.session_load_error = None
        self.unrestored_tabs = []
        self.session_path = Path(session_path) if session_path is not None else SESSION_PATH
        self.session = self.load_session()
        self.workspace_name = self.session.get("active", "")
        if self.workspace_name not in self.session["workspaces"]:
            self.workspace_name = next(iter(self.session["workspaces"]))
        self.preview_enabled = bool(self.session.get("preview_enabled", False))
        self.font_size = self.session.get("font_size", 14)
        if self.font_size not in (12, 14, 16, 18, 20):
            self.font_size = 14
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", padx=24, pady=(16, 8))
        title_block = ctk.CTkFrame(heading, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="YOUR CODE, ORGANIZED", font=("Segoe UI", 11, "bold"),
                     text_color=PURPLE, anchor="w").pack(anchor="w")
        self.workspace_title = ctk.CTkLabel(title_block, text=self.workspace_name, font=("Segoe UI", 28, "bold"), text_color=FG)
        self.workspace_title.pack(anchor="w")
        self.session_label = ctk.CTkLabel(heading, text="●  Local workspace", text_color="#43D9AC", font=("Segoe UI", 13))
        self.session_label.pack(side="right", padx=8)
        body = tk.PanedWindow(self, orient="horizontal", bg="#0B0D14", sashwidth=12, bd=0)
        body.pack(fill="both", expand=True, padx=24, pady=(12, 0))
        sidebar = ctk.CTkFrame(body, fg_color="#131722", corner_radius=14, border_width=1, border_color="#2B3247")
        ctk.CTkLabel(sidebar, text="WORKSPACES", text_color=MUTED, anchor="w", font=("Segoe UI", 11, "bold")).pack(fill="x", padx=18, pady=(16, 8))
        workspace_holder = ctk.CTkFrame(sidebar, fg_color="transparent", height=150)
        workspace_holder.pack(fill="x", padx=10)
        workspace_holder.pack_propagate(False)
        self.workspace_buttons = ctk.CTkScrollableFrame(workspace_holder, fg_color="transparent", height=110, scrollbar_button_color="#333A50")
        self.workspace_buttons.pack(fill="both", expand=True)
        group_actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        group_actions.pack(fill="x", padx=14, pady=(8, 16))
        ctk.CTkButton(group_actions, text="+ Workspace", width=120, height=30, fg_color="#302448", hover_color="#483B73", command=self.create_workspace).pack(side="left")
        ctk.CTkButton(group_actions, text="Rename", width=78, height=30, fg_color="transparent", hover_color="#242038", command=self.rename_workspace).pack(side="right")
        ctk.CTkFrame(sidebar, height=1, fg_color="#2B3247").pack(fill="x", padx=14)
        library_bar = ctk.CTkFrame(sidebar, fg_color="transparent")
        library_bar.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(library_bar, text="FILES", text_color=MUTED, font=("Segoe UI", 11, "bold")).pack(side="left")
        ctk.CTkButton(library_bar, text="+ Add", width=64, height=28, fg_color="#241B45", command=self.open_files).pack(side="right")
        library_frame = tk.Frame(sidebar, bg="#131722")
        library_frame.pack(fill="both", expand=True, padx=12)
        self.library = tk.Listbox(library_frame, bg="#131722", fg=FG, selectbackground="#302448", height=7,
                                 font=("Segoe UI", 12), activestyle="none", bd=0, highlightthickness=0, exportselection=False)
        library_scroll = ctk.CTkScrollbar(library_frame, command=self.library.yview, height=60, fg_color="#131722", button_color="#333A50")
        library_scroll.pack(side="right", fill="y")
        self.library.configure(yscrollcommand=library_scroll.set)
        self.library.pack(fill="both", expand=True)
        self.library.bind("<Double-Button-1>", self.open_library)
        self.library.bind("<Return>", self.open_library)
        ctk.CTkButton(sidebar, text="Remove selected from workspace", fg_color="transparent", hover_color="#242038", text_color=MUTED, height=26,
                      command=self.remove_library_file).pack(fill="x", padx=12, pady=(2, 10))
        self.folder_label = ctk.CTkLabel(sidebar, text="Browse a folder", text_color=MUTED, anchor="w", wraplength=220)
        self.folder_label.pack(fill="x", padx=16)
        actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=6)
        for label, command in (("Folder", self.open_folder), ("Up", self.parent_folder), ("Refresh", self.refresh_folder)):
            ctk.CTkButton(actions, text=label, command=command, fg_color="#1E2333", hover_color="#483B73", width=68, height=28).pack(side="left", padx=2)
        self.files = tk.Listbox(sidebar, bg="#131722", fg=MUTED, selectbackground="#302448", height=4,
                               font=("Segoe UI", 11), activestyle="none", bd=0, highlightthickness=0, exportselection=False)
        self.files.pack(fill="x", padx=16, pady=(0, 14))
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
        toolbar = ctk.CTkFrame(editor_area, fg_color="#171B28", corner_radius=0)
        toolbar.pack(fill="x")
        for label, command in (("+ New file", self.new), ("Open", self.open_files),
                               ("Save", self.save), ("Save as", lambda: self.save(save_as=True)),
                               ("Save all", self.save_all), ("Close tab", self.close_tab)):
            ctk.CTkButton(toolbar, text=label, command=command, width=82, height=34,
                          fg_color=PURPLE if label == "Save" else "transparent", text_color=BG if label == "Save" else FG,
                          hover_color="#483B73", font=("Segoe UI", 13)).pack(side="left", padx=3, pady=10)
        self.preview_button = ctk.CTkButton(toolbar, text="Preview", width=88, height=34,
                                           fg_color="#302448", command=self.toggle_preview)
        self.preview_button.pack(side="left", padx=3)
        self.font_menu = ctk.CTkOptionMenu(toolbar, values=["12", "14", "16", "18", "20"], width=66,
                                         fg_color="#242A3D", button_color="#242A3D", command=self.change_font_size)
        self.font_menu.set(str(self.font_size))
        self.font_menu.pack(side="right", padx=12)
        ctk.CTkLabel(toolbar, text="Text size", text_color=MUTED).pack(side="right")
        search = ctk.CTkFrame(editor_area, fg_color=BG, corner_radius=0)
        search.pack(fill="x", pady=(1, 8))
        self.query = ctk.CTkEntry(search, placeholder_text="Find in file · Ctrl+F", width=260, height=32, fg_color="#131722", border_color="#2B3247")
        self.query.pack(side="left", padx=(12, 6), pady=8)
        self.query.bind("<Return>", lambda e: self.find_next())
        ctk.CTkButton(search, text="Next", width=64, height=30, fg_color="#241B45", command=self.find_next).pack(side="left")
        self.find_result = ctk.CTkLabel(search, text="", text_color=MUTED)
        self.find_result.pack(side="left", padx=8)
        self.language_menu = ctk.CTkOptionMenu(search, values=LANGUAGES, command=self.change_language, width=130,
                                              fg_color="#171B28", button_color="#242A3D")
        self.language_menu.pack(side="right", padx=12)
        self.editor_split = tk.PanedWindow(editor_area, orient="horizontal", bg="#2B3247", sashwidth=6, bd=0)
        self.editor_split.pack(fill="both", expand=True)
        self.editor_content = tk.Frame(self.editor_split, bg=BG)
        self.editor_split.add(self.editor_content, minsize=250, width=600, stretch="always")
        self.preview = LuaPreview(self.editor_split, self.select_preview_line, self.new_preview_example)
        if self.preview_enabled:
            self.editor_split.add(self.preview, minsize=320, width=420, stretch="always")
            self.after_idle(self.balance_preview)
        self.empty_state = ctk.CTkFrame(self.editor_content, fg_color=BG, corner_radius=0)
        center = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(center, text="{  }", text_color=PURPLE, font=("Consolas", 42, "bold")).pack(pady=(0, 16))
        ctk.CTkLabel(center, text="A home for your scripts", text_color=FG, font=("Segoe UI", 24, "bold")).pack()
        ctk.CTkLabel(center, text="Add files to this workspace or start a new draft.\nYour tabs and drafts will be here when you return.",
                     text_color=MUTED, font=("Segoe UI", 14), justify="center").pack(pady=(8, 24))
        ctk.CTkButton(center, text="+ Add files", width=190, height=42, fg_color=PURPLE, text_color=BG,
                      hover_color="#B49EFF", command=self.open_files).pack()
        ctk.CTkButton(center, text="Start a blank draft", width=190, height=34, fg_color="transparent",
                      hover_color="#242038", command=self.new).pack(pady=8)
        self.notebook = ttk.Notebook(self.editor_content, style="Code.TNotebook")
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
        body.add(sidebar, width=270, minsize=250)
        body.add(editor_area, minsize=400, stretch="always")
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.tab_changed())
        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=MUTED)
        self.status.pack(side="bottom", fill="x", padx=24, pady=8, before=body)
        self.commands = (("<Control-n>", self.new), ("<Control-o>", self.open_files),
                                  ("<Control-s>", self.save),
                                  ("<Control-Shift-S>", lambda: self.save(save_as=True)),
                                  ("<Control-w>", self.close_tab),
                                  ("<Control-f>", self.query.focus_set))
        for sequence, command in self.commands:
            self.winfo_toplevel().bind(sequence, lambda e, fn=command: self.shortcut(fn), add="+")
        self.restore_workspace()
        self.poll_job = self.after(100, self.poll_analysis)

    def load_session(self):
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("workspaces"), dict) or not data["workspaces"]:
                raise ValueError("Invalid workspace file")
            for name, group in data["workspaces"].items():
                if not isinstance(name, str) or not isinstance(group, dict):
                    raise ValueError("Invalid workspace entry")
                if not isinstance(group.get("tabs", []), list) or not isinstance(group.get("files", []), list):
                    raise ValueError("Invalid workspace files")
                if any(not isinstance(item, dict) for item in group.get("tabs", [])):
                    raise ValueError("Invalid tab record")
                if any(not isinstance(item, str) for item in group.get("files", [])):
                    raise ValueError("Invalid file path")
            return data
        except FileNotFoundError:
            return {"active": "My scripts", "workspaces": {"My scripts": {"tabs": [], "files": []}}}
        except (OSError, ValueError) as error:
            self.session_load_error = str(error)
            return {"active": "Recovered workspace", "workspaces": {"Recovered workspace": {"tabs": [], "files": []}}}

    def capture_workspace(self):
        group = self.session["workspaces"][self.workspace_name]
        records = []
        for tab in self.tabs.values():
            doc = tab.document
            entry = {"path": str(doc.path) if doc.path else None, "title": tab.title,
                     "language": tab.language, "cursor": tab.text.index("insert"),
                     "scroll": tab.text.yview()[0]}
            if doc.path is None or tab.has_changes():
                entry["draft"] = tab.content()
                entry["baseline"] = doc.text
                entry["encoding"] = doc.encoding
                entry["bom"] = doc.bom.hex()
                entry["newline"] = doc.newline
                entry["original"] = base64.b64encode(doc.original).decode("ascii") if doc.original is not None else None
            records.append(entry)
        records.extend(record for record in self.unrestored_tabs
                       if record.get("path") not in [str(t.document.path) for t in self.tabs.values()])
        group.update(tabs=records, folder=str(self.folder) if self.folder else None,
                     selected=list(self.tabs).index(self.notebook.select()) if self.active() else 0)
        self.session["active"] = self.workspace_name
        self.session["font_size"] = self.font_size
        self.session["preview_enabled"] = self.preview_enabled

    def persist_session(self, notify=False):
        if self.restoring or self.closing:
            return True
        if self.session_job:
            self.after_cancel(self.session_job)
            self.session_job = None
        self.capture_workspace()
        try:
            if self.session_load_error:
                # Preserve an unreadable session before creating a new one.
                backup = self.session_path.with_name(self.session_path.name + ".unreadable-" + str(time.time_ns()))
                if self.session_path.exists():
                    self.session_path.rename(backup)
                self.session_load_error = None
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            Document().save(json.dumps(self.session, ensure_ascii=True), self.session_path, overwrite=True)
            self.session_label.configure(text="●  Workspace saved locally", text_color="#43D9AC")
            return True
        except (OSError, ValueError) as error:
            self.session_label.configure(text="Workspace could not be saved", text_color="#FB7185")
            if notify:
                messagebox.showerror("Workspace not saved", "Your tabs are still open. Save your files before exiting.\n\n" + str(error), parent=self)
            return False

    def schedule_session(self):
        if self.restoring or self.closing:
            return
        self.session_label.configure(text="Saving workspace…", text_color=MUTED)
        if self.session_job:
            self.after_cancel(self.session_job)
        self.session_job = self.after(800, self.persist_session)

    def restore_workspace(self):
        self.restoring = True
        group = self.session["workspaces"][self.workspace_name]
        self.folder = Path(group["folder"]) if group.get("folder") else None
        missing = []
        self.unrestored_tabs = []
        for record in group.get("tabs", []):
            try:
                path = Path(record["path"]) if record.get("path") else None
                if "draft" in record:
                    original = base64.b64decode(record["original"]) if record.get("original") is not None else None
                    doc = Document(path, record.get("baseline", ""), record.get("encoding", "utf-8"),
                                   bytes.fromhex(record.get("bom", "")), record.get("newline", "\n"), original)
                elif path:
                    doc = Document.open(path)
                else:
                    doc = Document()
                title = record.get("title") or (path.name if path else "Untitled")
                tab = EditorTab(self, doc, title)
                self.tabs[str(tab.frame)] = tab
                if "draft" in record:
                    tab.text.delete("1.0", "end")
                    tab.text.insert("1.0", record["draft"])
                    tab.text.edit_reset()
                    tab.dirty = tab.has_changes()
                    self.notebook.tab(tab.frame, text=title + (" *" if tab.dirty else ""))
                tab.text.edit_modified(False)
                tab.language = record.get("language") if record.get("language") in LANGUAGES else language_for(path)
                tab.text.mark_set("insert", record.get("cursor", "1.0"))
                tab.text.yview_moveto(float(record.get("scroll", 0)))
                tab.schedule_analysis()
            except (OSError, ValueError, KeyError, TypeError, tk.TclError) as error:
                self.unrestored_tabs.append(record)
                missing.append(str(record.get("path", "Draft")) + ": " + str(error))
        if self.tabs:
            selected = min(max(0, int(group.get("selected", 0))), len(self.tabs) - 1)
            self.notebook.select(list(self.tabs)[selected])
        self.counter = max([int(t.title.split()[-1]) for t in self.tabs.values()
                            if re.fullmatch(r"Untitled \d+", t.title)] + [0])
        self.restoring = False
        self.refresh_library()
        self.refresh_folder()
        self.render_workspaces()
        self.update_status()
        if missing:
            self.session_label.configure(text="Some files are missing · select them in Files to retry", text_color="#F4BD6A")

    def switch_workspace(self, name):
        if name == self.workspace_name:
            return
        if not self.persist_session(notify=True):
            return
        self.restoring = True
        for tab in list(self.tabs.values()):
            if tab.analysis_job:
                tab.text.after_cancel(tab.analysis_job)
            self.notebook.forget(tab.frame)
            tab.frame.destroy()
        self.tabs.clear()
        self.workspace_name = name
        self.restore_workspace()
        self.persist_session()

    def create_workspace(self):
        name = ctk.CTkInputDialog(text="Name your workspace (for example LT2 or Phantom Forces)", title="New workspace").get_input()
        if name and name.strip():
            name = name.strip()
            if name in self.session["workspaces"]:
                self.switch_workspace(name)
                return
            self.session["workspaces"][name] = {"tabs": [], "files": []}
            self.switch_workspace(name)

    def rename_workspace(self):
        name = ctk.CTkInputDialog(text="New name for " + self.workspace_name, title="Rename workspace").get_input()
        if not name or not name.strip() or name.strip() == self.workspace_name:
            return
        name = name.strip()
        if name in self.session["workspaces"]:
            messagebox.showerror("Name already used", "Choose a different workspace name.", parent=self)
            return
        self.capture_workspace()
        self.session["workspaces"][name] = self.session["workspaces"].pop(self.workspace_name)
        self.workspace_name = name
        self.render_workspaces()
        self.persist_session(notify=True)

    def render_workspaces(self):
        for child in self.workspace_buttons.winfo_children():
            child.destroy()
        for name in self.session["workspaces"]:
            selected = name == self.workspace_name
            ctk.CTkButton(self.workspace_buttons, text=name, anchor="w", height=38,
                          fg_color="#302448" if selected else "transparent", text_color="#D5BCFF" if selected else MUTED,
                          hover_color="#242038", font=("Segoe UI", 14, "bold" if selected else "normal"),
                          command=lambda n=name: self.switch_workspace(n)).pack(fill="x", pady=3)
        self.workspace_title.configure(text=self.workspace_name)

    def pin_file(self, path):
        paths = self.session["workspaces"][self.workspace_name].setdefault("files", [])
        if str(path) not in paths:
            paths.append(str(path))
        self.refresh_library()
        self.schedule_session()

    def refresh_library(self):
        self.library_paths = self.session["workspaces"][self.workspace_name].get("files", [])
        self.library.delete(0, "end")
        for path in self.library_paths:
            self.library.insert("end", "  " + Path(path).name + ("  (missing)" if not Path(path).exists() else ""))

    def open_library(self, event=None):
        selected = self.library.curselection()
        if selected:
            self.open_path(self.library_paths[selected[0]])

    def remove_library_file(self):
        selected = self.library.curselection()
        if selected:
            del self.library_paths[selected[0]]
            self.refresh_library()
            self.schedule_session()

    def change_font_size(self, value):
        self.font_size = int(value)
        for tab in self.tabs.values():
            tab.text.configure(font=("Consolas", self.font_size))
            tab.draw_lines()
        self.schedule_session()

    def tab_changed(self):
        self.update_status()
        self.schedule_session()


    def destroy(self):
        if getattr(self, "poll_job", None):
            self.after_cancel(self.poll_job)
            self.poll_job = None
        for tab in self.tabs.values():
            if tab.analysis_job:
                tab.text.after_cancel(tab.analysis_job)
                tab.analysis_job = None
        if self.session_job:
            self.after_cancel(self.session_job)
            self.session_job = None
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
        try:
            while True:
                tab, revision, plan = self.preview_results.get_nowait()
                if str(tab.frame) in self.tabs and tab.revision == revision:
                    tab.preview_result = (revision, plan)
                    if self.active() is tab:
                        self.refresh_preview()
        except queue.Empty:
            pass
        self.poll_job = self.after(100, self.poll_analysis)

    def balance_preview(self):
        if self.preview_enabled and self.editor_split.winfo_exists():
            self.editor_split.sash_place(0, int(self.editor_split.winfo_width() * 0.55), 0)

    def toggle_preview(self):
        self.preview_enabled = not self.preview_enabled
        if self.preview_enabled:
            self.editor_split.add(self.preview, minsize=320, width=420, stretch="always")
            self.after_idle(self.balance_preview)
            if self.active():
                self.active().schedule_analysis()
        else:
            self.editor_split.forget(self.preview)
        self.preview_button.configure(text="Hide preview" if self.preview_enabled else "Preview")
        self.refresh_preview()
        self.schedule_session()

    def refresh_preview(self):
        if not self.preview_enabled:
            return
        tab = self.active()
        if not tab or tab.language != "Luau":
            self.preview.show(PreviewPlan(error="Open a Luau script or choose Example."), (id(tab), "unsupported"))
        elif tab.preview_result and tab.preview_result[0] == tab.revision:
            try:
                self.preview.show(tab.preview_result[1], (id(tab), tab.revision))
            except Exception as error:
                self.preview.show(PreviewPlan(error="Preview could not draw this layout: " + str(error)), (id(tab), tab.revision, "error"))
        else:
            self.preview.show(PreviewPlan(error="Updating preview…"), (id(tab), tab.revision, "pending"))

    def select_preview_line(self, line):
        tab = self.active()
        if tab:
            index = "%d.0" % line
            tab.text.mark_set("insert", index)
            tab.text.see(index)
            tab.text.focus_set()
            self.update_status()

    def new_preview_example(self):
        tab = self.new()
        tab.text.insert("1.0", EXAMPLE_SOURCE)
        if not self.preview_enabled:
            self.toggle_preview()

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
            self.schedule_session()
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
        self.schedule_session()
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
                self.pin_file(path)
                return tab
        try:
            document = Document.open(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot open file", str(error), parent=self)
            return None
        tab = EditorTab(self, document, path.name)
        self.tabs[str(tab.frame)] = tab
        self.pin_file(path)
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
        self.pin_file(path)
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
        return self.persist_session(notify=True)

    def close_tab(self):
        tab = self.active()
        if tab and self.confirm_close(tab):
            self.tabs.pop(str(tab.frame))
            self.notebook.forget(tab.frame)
            if tab.analysis_job:
                tab.text.after_cancel(tab.analysis_job)
            tab.frame.destroy()
            self.update_status()
            self.persist_session()

    def open_folder(self):
        chosen = filedialog.askdirectory(parent=self, title="Browse a local code folder")
        if chosen:
            self.folder = Path(chosen)
            self.refresh_folder()
            self.schedule_session()

    def parent_folder(self):
        if self.folder:
            self.folder = self.folder.parent
            self.refresh_folder()

    def refresh_folder(self):
        if self.folder is None:
            self.files.delete(0, "end")
            self.folder_label.configure(text="Browse a folder")
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
        self.refresh_preview()
        if not tab:
            self.notebook.pack_forget()
            self.empty_state.pack(fill="both", expand=True)
            self.problem_list.delete(0, "end")
            self.problem_heading.configure(text="PROBLEMS · Open a file to check syntax", text_color=MUTED)
            self.problem_detail.configure(text="")
            self.status.configure(text="New or Open files to start editing · Ctrl+N / Ctrl+O")
            return
        self.empty_state.pack_forget()
        self.notebook.pack(fill="both", expand=True)
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

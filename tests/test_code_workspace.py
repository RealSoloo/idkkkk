"""Run with a Tk display: python -m unittest discover -s tests -p test_code_workspace.py."""
import codecs
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from code_workspace import Document, ExternalChangeError, CodeWorkspace, analyze_code


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "script.txt"

    def test_encodings_and_line_endings(self):
        for encoding, bom, newline in (("utf-8", b"", "\n"), ("utf-8", codecs.BOM_UTF8, "\r\n"),
                                       ("utf-16-le", codecs.BOM_UTF16_LE, "\r\n"),
                                       ("utf-16-be", codecs.BOM_UTF16_BE, "\r")):
            with self.subTest(encoding=encoding, newline=newline):
                self.path.write_bytes(bom + ("hello" + newline + "λ").encode(encoding))
                doc = Document.open(self.path)
                self.assertEqual(doc.text, "hello\nλ")
                doc.save(doc.text + "\nworld")
                self.assertEqual(self.path.read_bytes(), bom + newline.join(("hello", "λ", "world")).encode(encoding))

    def test_external_changes_are_not_lost(self):
        self.path.write_text("original")
        doc = Document.open(self.path)
        self.path.write_text("external edit")
        with self.assertRaises(ExternalChangeError):
            doc.save("my edit")
        self.assertEqual(self.path.read_text(), "external edit")
        doc.save("my edit", overwrite=True)
        self.assertEqual(self.path.read_text(), "my edit")
        self.path.unlink()
        with self.assertRaises(ExternalChangeError):
            doc.save("new edit")

    def test_failed_replace_keeps_original_and_cleans_temp(self):
        self.path.write_text("original")
        doc = Document.open(self.path)
        with patch("code_workspace.os.replace", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                doc.save("new")
        self.assertEqual(self.path.read_text(), "original")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.assertEqual(doc.text, "original")

    def test_mixed_newlines_unchanged_and_save_as(self):
        self.path.write_bytes(b"a\r\nb\nc\r")
        doc = Document.open(self.path)
        dest = self.path.with_suffix(".lua")
        doc.save(doc.text, dest)
        self.assertEqual(dest.read_bytes(), self.path.read_bytes())

    def test_binary_rejected(self):
        self.path.write_bytes(b"hello\x00world")
        with self.assertRaises(ValueError):
            Document.open(self.path)


class AnalysisTests(unittest.TestCase):
    def test_luau_types_comments_and_errors(self):
        valid = '-- missing end here is only a comment\nlocal n: number = 2\nn += 1\nfor i=1,3 do if i == 2 then continue end end'
        colors, errors, notice = analyze_code(valid, "Luau")
        self.assertFalse(errors)
        self.assertIn("Syntax checked", notice)
        self.assertTrue(any(kind == "comment" for kind, _, _ in colors))
        self.assertTrue(analyze_code('local x = )', "Luau")[1])
        self.assertTrue(analyze_code('if true then\n print("hello")', "Luau")[1])

    def test_other_languages_and_no_execution(self):
        self.assertTrue(analyze_code('if True\n pass', "Python")[1])
        self.assertTrue(analyze_code('{"x":}', "JSON")[1])
        self.assertFalse(analyze_code('raise RuntimeError("must not run")', "Python")[1])
        self.assertIn("Highlighting only", analyze_code('let x = ;', "JavaScript")[2])


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "GUI requires a display")
class GuiTests(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.geometry("1440x900")
        self.directory = tempfile.TemporaryDirectory()
        self.workspace = CodeWorkspace(self.root, session_path=Path(self.directory.name) / "workspace.json")
        self.workspace.new()
        self.workspace.pack(fill="both", expand=True)
        self.root.update()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.close_root)
        self.path = Path(self.directory.name) / "script.lua"
        self.path.write_text("local hello = 1\n")

    def close_root(self):
        for job in self.root.tk.call("after", "info"):
            self.root.tk.call("after", "cancel", job)
        self.root.destroy()

    def test_app_navigation_shortcuts_and_cancel_exit(self):
        import run
        run.load("api", "Api")
        appmod = run.load("solos_app", "App")
        self.workspace.pack_forget()
        with patch.object(appmod, "CONFIG_PATH", str(self.path.parent / "config.json")):
            app = appmod.App(self.root)
        with patch("code_workspace.SESSION_PATH", self.path.parent / "app-workspace.json"):
            app.show_page("Code Workspace")
        self.root.update()
        tab = app.editor.open_path(self.path)
        self.root.update()
        tab.text.focus_force()
        before = tab.content()
        with patch("code_workspace.filedialog.askopenfilenames", return_value=()):
            tab.text.event_generate("<Control-o>")
            self.root.update()
        self.assertEqual(tab.content(), before)
        app.show_page("Key Manager")
        app.toggle_conn_strip()
        app.toggle_conn_strip()
        self.root.update()
        self.assertTrue(app.conn_strip.winfo_ismapped())
        app.show_page("Code Workspace")
        tab.text.insert("end", "unsaved")
        with patch.object(app.editor, "can_close", return_value=False):
            app.close()
        self.assertTrue(self.root.winfo_exists())
        self.assertTrue(tab.has_changes())

    def test_open_edit_save_find_and_close(self):
        ws = self.workspace
        tab = ws.open_path(self.path)
        self.assertIs(ws.open_path(self.path), tab)
        tab.text.insert("end", "print(hello)\n")
        self.root.update()
        self.assertTrue(tab.has_changes())
        self.assertIn("*", ws.notebook.tab(tab.frame, "text"))
        ws.query.insert(0, "hello")
        tab.text.mark_set("insert", "1.0")
        ws.find_next()
        self.assertEqual(tab.text.get("sel.first", "sel.last"), "hello")
        self.assertTrue(ws.save())
        self.assertEqual(self.path.read_text(), "local hello = 1\nprint(hello)\n")
        self.assertFalse(tab.has_changes())
        tab.text.insert("end", "unsaved")
        with patch("code_workspace.messagebox.askyesnocancel", return_value=None):
            ws.close_tab()
            self.assertIn(str(tab.frame), ws.tabs)
            self.assertTrue(ws.can_close())
        with patch("code_workspace.messagebox.askyesnocancel", return_value=False):
            ws.close_tab()
            self.assertNotIn(str(tab.frame), ws.tabs)

    def test_save_as_cancel_error_and_folder(self):
        ws = self.workspace
        tab = ws.active()
        tab.text.insert("end", "new text")
        with patch("code_workspace.filedialog.asksaveasfilename", return_value=""):
            self.assertFalse(ws.save())
        dest = self.path.parent / "new.txt"
        with patch("code_workspace.filedialog.asksaveasfilename", return_value=str(dest)):
            self.assertTrue(ws.save())
        self.assertEqual(dest.read_text(), "new text")
        dest.write_text("external")
        with patch("code_workspace.messagebox.askyesno", return_value=False):
            self.assertFalse(ws.save())
        self.assertEqual(dest.read_text(), "external")
        ws.folder = self.path.parent
        ws.refresh_folder()
        self.assertEqual(set(ws.entries), {self.path, dest})
        with patch("code_workspace.Document.save", side_effect=OSError("test failure")), \
             patch("code_workspace.messagebox.showerror") as error:
            self.assertFalse(ws.save())
            error.assert_called_once()

    def test_live_diagnostics_and_navigation(self):
        ws = self.workspace
        tab = ws.active()
        tab.text.insert("1.0", "local x = )")
        deadline = time.monotonic() + 5
        while not tab.problems and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertTrue(tab.problems)
        self.assertTrue(tab.text.tag_ranges("error"))
        self.assertTrue(tab.text.tag_ranges("keyword"))
        ws.problem_list.selection_set(0)
        ws.jump_problem()
        self.assertEqual(tab.text.index("insert").split(".")[0], "1")
        tab.text.delete("1.0", "end")
        tab.text.insert("1.0", "local x: number = 3")
        self.root.update()
        deadline = time.monotonic() + 5
        while tab.notice == "Checking syntax…" and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertEqual(tab.problems, [])
        self.assertFalse(tab.text.tag_ranges("error"))
        self.assertIn("Syntax checked", tab.notice)

    def test_missing_parser_is_visible(self):
        import sys
        tab = self.workspace.active()
        with patch.dict(sys.modules, {"tree_sitter_luau": None}):
            result = analyze_code("local x = )", "Luau")
        tab.apply_analysis(result)
        self.assertIn("UNAVAILABLE", self.workspace.problem_heading.cget("text"))
        self.assertNotIn("0 SYNTAX", self.workspace.problem_heading.cget("text"))
        self.assertIn("pip install", self.workspace.problem_detail.cget("text"))

    def test_setup_report_and_txt_language(self):
        path = self.path.with_suffix(".txt")
        path.write_text("local x = )")
        tab = self.workspace.open_path(path)
        self.assertEqual(tab.language, "Luau")
        tab.apply_analysis(analyze_code(tab.content(), tab.language))
        self.assertTrue(tab.problems)
        self.assertTrue(tab.text.tag_ranges("keyword"))
        with patch("code_workspace.messagebox.showinfo"):
            report = self.workspace.check_setup()
        self.assertIn("editor-4", report)
        self.assertIn("Luau color test: PASS", report)
        self.assertIn("Luau error test: PASS", report)
        self.assertNotIn("local x = )", report)

    def test_display_failure_does_not_stop_later_checks(self):
        ws = self.workspace
        tab = ws.active()
        result = analyze_code("local x = )", "Luau")
        ws.analysis_results.put((tab, tab.revision, result))
        with patch.object(tab, "apply_analysis", side_effect=RuntimeError("display test")):
            ws.poll_analysis()
        self.assertIn("display test", tab.notice)
        ws.analysis_results.put((tab, tab.revision, result))
        ws.poll_analysis()
        self.assertTrue(tab.problems)
        self.assertNotIn("unavailable", tab.notice)

    def test_workspace_restart_restores_drafts_and_external_conflicts(self):
        ws = self.workspace
        tab = ws.open_path(self.path)
        tab.text.insert("end", "-- draft")
        tab.language = "Plain text"
        tab.text.mark_set("insert", "2.3")
        draft = ws.new()
        draft.text.insert("end", "unsaved new script")
        ws.font_size = 18
        self.assertTrue(ws.can_close())
        session_path = ws.session_path
        self.path.write_text("external change")
        ws.destroy()
        restored = CodeWorkspace(self.root, session_path=session_path)
        restored.pack(fill="both", expand=True)
        self.workspace = restored
        tabs = list(restored.tabs.values())
        file_tab = next(t for t in tabs if t.document.path == self.path)
        self.assertTrue(file_tab.content().endswith("-- draft"))
        self.assertEqual(file_tab.language, "Plain text")
        self.assertEqual(file_tab.text.index("insert"), "2.3")
        self.assertEqual(restored.active().content(), "unsaved new script")
        self.assertEqual(restored.font_size, 18)
        self.assertIn(str(self.path), restored.library_paths)
        with patch("code_workspace.messagebox.askyesno", return_value=False):
            self.assertFalse(restored.save(file_tab))
        self.assertEqual(self.path.read_text(), "external change")

    def test_workspace_switch_keeps_separate_files_and_drafts(self):
        ws = self.workspace
        first_name = ws.workspace_name
        tab = ws.open_path(self.path)
        tab.text.insert("end", "-- first workspace")
        ws.session["workspaces"]["LT2"] = {"tabs": [], "files": []}
        ws.switch_workspace("LT2")
        self.assertFalse(ws.tabs)
        self.assertFalse(ws.library_paths)
        ws.new().text.insert("end", "-- LT2 draft")
        ws.switch_workspace(first_name)
        self.assertTrue(any(t.content().endswith("-- first workspace") for t in ws.tabs.values()))
        self.assertIn(str(self.path), ws.library_paths)
        ws.switch_workspace("LT2")
        self.assertEqual(ws.active().content(), "-- LT2 draft")
        self.assertTrue(ws.can_close())

    def test_closed_tab_stays_in_library_and_discarded_draft_is_removed(self):
        ws = self.workspace
        tab = ws.open_path(self.path)
        tab.text.insert("end", "discard me")
        with patch("code_workspace.messagebox.askyesnocancel", return_value=False):
            ws.close_tab()
        self.assertIn(str(self.path), ws.library_paths)
        contents = ws.session_path.read_text()
        self.assertNotIn("discard me", contents)
        reopened = ws.open_path(self.path)
        self.assertNotIn("discard me", reopened.content())

    def test_session_write_failure_blocks_exit(self):
        ws = self.workspace
        ws.active().text.insert("end", "keep this draft")
        with patch("code_workspace.os.replace", side_effect=OSError("disk full")), \
             patch("code_workspace.messagebox.showerror"):
            self.assertFalse(ws.can_close())
        self.assertEqual(ws.active().content(), "keep this draft")
        self.assertIn("could not be saved", ws.session_label.cget("text"))

    def test_corrupt_session_is_preserved(self):
        path = self.path.parent / "broken.json"
        path.write_text("not valid json")
        ws = CodeWorkspace(self.root, session_path=path)
        ws.new().text.insert("end", "recovered")
        self.assertTrue(ws.persist_session())
        backups = list(path.parent.glob("broken.json.unreadable-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "not valid json")
        ws.destroy()

    def test_icon_picker_copies_and_applies_png(self):
        import run
        import tkinter as tk
        run.load("api", "Api")
        module = run.load("solos_app", "App")
        icon_path = self.path.parent / "logo.png"
        image = tk.PhotoImage(master=self.root, width=32, height=32)
        image.put("#9B87F5", to=(0, 0, 32, 32))
        image.write(str(icon_path), format="png")
        with patch.object(module, "CONFIG_PATH", str(self.path.parent / "app-config.json")):
            app = module.App(self.root)
            with patch.object(module.filedialog, "askopenfilename", return_value=str(icon_path)):
                app.choose_app_icon()
            saved_icon = Path(app.cfg["icon_path"])
            self.assertEqual(saved_icon.read_bytes(), icon_path.read_bytes())
            self.assertTrue(hasattr(app, "_icon_image"))
            self.assertEqual(app.load_config()["icon_path"], str(saved_icon))

    def test_large_script(self):
        text = "local example = 'a line of Lua'\n" * 17000
        self.path.write_text(text)
        tab = self.workspace.open_path(self.path)
        self.root.update()
        tab.apply_analysis(analyze_code(text, "Luau"))
        self.assertTrue(tab.text.tag_ranges("keyword"))
        tab.text.insert("end", "-- end\n")
        self.assertTrue(self.workspace.save())
        self.assertEqual(self.path.read_text(), text + "-- end\n")


if __name__ == "__main__":
    unittest.main()

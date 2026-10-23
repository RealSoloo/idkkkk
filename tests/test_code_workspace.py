"""Run with a Tk display: python -m unittest discover -s tests -p test_code_workspace.py."""
import codecs
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_workspace import Document, ExternalChangeError, CodeWorkspace


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


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "GUI requires a display")
class GuiTests(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.geometry("1440x900")
        self.workspace = CodeWorkspace(self.root)
        self.workspace.pack(fill="both", expand=True)
        self.root.update()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.close_root)
        self.path = Path(self.directory.name) / "script.lua"
        self.path.write_text("local hello = 1\n")

    def close_root(self):
        for job in self.root.tk.call("after", "info"):
            self.root.after_cancel(job)
        self.root.destroy()

    def test_app_navigation_shortcuts_and_cancel_exit(self):
        import run
        run.load("api", "Api")
        appmod = run.load("solos_app", "App")
        self.workspace.pack_forget()
        with patch.object(appmod, "CONFIG_PATH", str(self.path.parent / "config.json")):
            app = appmod.App(self.root)
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
        with patch("code_workspace.messagebox.askyesnocancel", return_value=None):
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
            self.assertFalse(ws.can_close())
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

    def test_large_script(self):
        text = "local example = 'a line of Lua'\n" * 17000
        self.path.write_text(text)
        tab = self.workspace.open_path(self.path)
        self.root.update()
        tab.text.insert("end", "-- end\n")
        self.assertTrue(self.workspace.save())
        self.assertEqual(self.path.read_text(), text + "-- end\n")


if __name__ == "__main__":
    unittest.main()

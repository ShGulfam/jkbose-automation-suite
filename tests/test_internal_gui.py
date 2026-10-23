import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

class InternalGuiTests(unittest.TestCase):
    def test_default_internal_actions_fit_the_smallest_supported_window(self):
        import tkinter as tk
        import gui_main
        try: root=tk.Tk()
        except tk.TclError: self.skipTest('No desktop display available.')
        try:
            app=gui_main.App(root); app._show_section('internal')
            root.geometry('960x640'); root.update()
            canvas=app.content_canvas
            right=canvas.winfo_rootx()+canvas.winfo_width()
            bottom=canvas.winfo_rooty()+canvas.winfo_height()
            for button in app.run_buttons:
                if button.winfo_ismapped():
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),right)
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),bottom)
        finally: root.destroy()

    def test_compact_controls_and_activity_tab_preserve_work_and_submission_guards(self):
        import tkinter as tk
        import gui_main
        try: root=tk.Tk()
        except tk.TclError: self.skipTest('No desktop display available.')
        root.withdraw()
        try:
            app=gui_main.App(root); app._show_section('internal'); root.update_idletasks()
            self.assertEqual(len(app.workspace_tabs.tabs()),2)
            self.assertEqual(app.workspace_tabs.select(),str(app.workspace_tab))
            self.assertFalse(app.ia_advanced_open.get())
            self.assertEqual(app.ia_advanced_panel.winfo_manager(),'')
            app.ia['session'].set('2025-26')
            app._log('Synthetic read-only event\n')
            self.assertTrue(app.log_unread)
            app.workspace_tabs.select(app.activity_tab); root.update()
            self.assertFalse(app.log_unread)
            self.assertIn('Synthetic read-only event',app.log_widget.get('1.0','end'))
            self.assertEqual(app.ia['session'].get(),'2025-26')
            app._show_section('internal')
            app.ia_session_confirm.set(True)
            app._toggle_internal_advanced()
            self.assertEqual(app.ia_advanced_panel.winfo_manager(),'pack')
            self.assertTrue(app.ia_session_confirm.get())
            app.ia['maximum'].set('20')
            self.assertFalse(app.ia_session_confirm.get())
            app.ia_subject_mode.set('Selected subjects')
            self.assertEqual(app.ia_selection_panel.winfo_manager(),'pack')
            self.assertEqual(app.ia_single_subject.winfo_manager(),'')
            app.ia_subject_mode.set('All workbook subjects')
            self.assertEqual(app.ia_selection_panel.winfo_manager(),'')
            app._set_running(True,'Synthetic')
            self.assertTrue(all(str(button['state'])=='disabled' for button in app.run_buttons))
            self.assertEqual(str(app.stop_btn['state']),'normal')
            self.assertFalse(app.ia_session_confirm.get())
            with tempfile.TemporaryDirectory() as folder:
                output=Path(folder)/'activity.txt'
                with patch.object(gui_main.filedialog,'asksaveasfilename',return_value=str(output)):
                    app._save_activity_log()
                self.assertIn('Synthetic read-only event',output.read_text())
        finally: root.destroy()

    def test_gui_section_and_explicit_session_confirmation(self):
        import tkinter as tk
        import gui_main
        try: root = tk.Tk()
        except tk.TclError: self.skipTest('No desktop display available for hidden GUI smoke test.')
        root.withdraw()
        try:
            app = gui_main.App(root)
            self.assertIn('internal', app.sections)
            self.assertIn('internal', app.nav_buttons)
            self.assertEqual(app.ia['component_max'].get(), '')
            self.assertEqual(app.ia['maximum'].get(), 'Auto')
            self.assertEqual(app.ia['report_session'].get(),'Auto')
            self.assertTrue(app.ia_combine_biology.get())
            self.assertEqual(app.ia_subject_mode.get(),'Single subject')
            self.assertIn('Mathematics',app.ia_subject_choices)
            self.assertEqual(Path(app.ia['history'].get()), Path(gui_main.__file__).parent / 'history' / 'internal_assessment')
            app.ia_session_confirm.set(True)
            app.ia['session'].set('2025-26')
            self.assertFalse(app.ia_session_confirm.get())
            app.ia_session_confirm.set(True)
            app.ia['report_session'].set('2026-2027')
            self.assertFalse(app.ia_session_confirm.get())
            app.ia_session_confirm.set(True)
            app.ia_subject_mode.set('Selected subjects')
            self.assertFalse(app.ia_session_confirm.get())
            app.ia_session_confirm.set(True)
            app.ia_subject_choices['Physics'].set(True)
            self.assertFalse(app.ia_session_confirm.get())
            app.ia_session_confirm.set(True)
            app.ia_combine_biology.set(False)
            self.assertFalse(app.ia_session_confirm.get())
        finally: root.destroy()

    def test_cli_defaults_never_enable_saving(self):
        import main
        args = main.build_parser().parse_args(['internal', '--excel-file', 'synthetic.xlsx', '--class', '12', '--session', '2025-26', '--subject', 'Physics'])
        self.assertFalse(args.execute); self.assertFalse(args.confirm_session)
        self.assertEqual(args.maximum, 'Auto'); self.assertTrue(args.combine_biology)
        self.assertEqual(args.report_session,'Auto')
        selected=main.build_parser().parse_args(['internal','--excel-file','synthetic.xlsx','--class','11','--session','2025-26','--subjects','PH','MA'])
        self.assertEqual(selected.subjects,['PH','MA']); self.assertFalse(selected.execute)
        all_subjects=main.build_parser().parse_args(['internal','--excel-file','synthetic.xlsx','--class','11','--session','2025-26','--all-subjects'])
        self.assertTrue(all_subjects.all_subjects); self.assertFalse(all_subjects.execute)

if __name__ == '__main__': unittest.main()

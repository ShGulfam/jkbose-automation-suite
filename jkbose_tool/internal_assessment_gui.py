"""Internal Assessment GUI controls; automation stays in the feature modules."""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from .features.internal_assessment import SUBJECTS, load_plan, submission_issues, Audit, RunLock, DEFAULT_HISTORY_ROOT, prepare_history_root
from .features.internal_assessment_batch import load_jobs, workbook_subjects
from .internal_assessment_approval_gui import PrincipalApprovalGUI

class InternalAssessmentGUI(PrincipalApprovalGUI):
    def _build_internal_section(self, parent):
        self._section_header(parent, 'Internal Assessment',
            'Choose your workbook and cohort. Submit shows a preview, checks reports and processes valid awards.')
        card = self._card(parent)
        defaults = {'file': '', 'sheet': 'Auto', 'class': '11', 'session': '',
                    'subject': 'Biology', 'maximum': 'Auto', 'component_max': '', 'report_session':'Auto',
                    'account': 'sch010061',
                    'history': str(DEFAULT_HISTORY_ROOT)}
        self.ia = {key: tk.StringVar(value=value) for key, value in defaults.items()}
        self.ia_combine_biology = tk.BooleanVar(value=True)
        self.ia_subject_mode=tk.StringVar(value='Single subject')
        self.ia_subject_choices={subject:tk.BooleanVar(value=False) for subject in dict.fromkeys(SUBJECTS.values())}
        self._field_row(card, 'Awards workbook', self.ia['file'], browse_kind='open', filetypes=[('Excel awards', '*.xlsx')])
        cohort=ttk.Frame(card,style='Card.TFrame'); cohort.pack(fill='x',pady=8)
        for column,(label,key,values) in enumerate([
                ('Class','class',['10','11','12']), ('Academic session','session',None), ('School account','account',None)]):
            cell=ttk.Frame(cohort,style='Card.TFrame'); cell.grid(row=0,column=column,sticky='ew',padx=(0,16))
            cohort.columnconfigure(column,weight=1)
            ttk.Label(cell,text=label,style='Muted.Card.TLabel').pack(anchor='w',pady=(0,3))
            widget=(ttk.Combobox(cell,textvariable=self.ia[key],values=values,state='readonly',width=10)
                    if values else ttk.Entry(cell,textvariable=self.ia[key],width=18))
            widget.pack(fill='x')
        subjects=ttk.Frame(card,style='Card.TFrame'); subjects.pack(fill='x',pady=(4,8))
        ttk.Label(subjects,text='Subjects to run',style='Card.TLabel').pack(side='left',padx=(0,12))
        ttk.Combobox(subjects,textvariable=self.ia_subject_mode,values=['Single subject','Selected subjects','All workbook subjects'],state='readonly',width=23).pack(side='left')
        self.ia_single_subject=ttk.Frame(subjects,style='Card.TFrame')
        ttk.Combobox(self.ia_single_subject,textvariable=self.ia['subject'],values=sorted(set(SUBJECTS.values())),state='readonly',width=24).pack()
        self.ia_selection_holder=ttk.Frame(card,style='Card.TFrame'); self.ia_selection_holder.pack(fill='x')
        selection=ttk.LabelFrame(self.ia_selection_holder,text='Choose workbook subjects',style='Card.TLabelframe',padding=8)
        self.ia_selection_panel=selection
        for index,(subject,variable) in enumerate(self.ia_subject_choices.items()):
            ttk.Checkbutton(selection,text=subject,variable=variable).grid(row=index//3,column=index%3,sticky='w',padx=8,pady=2)
        ttk.Button(selection,text='Read workbook subjects',command=self._select_internal_workbook_subjects).grid(row=(len(self.ia_subject_choices)+2)//3,column=0,columnspan=3,sticky='w',pady=5)
        ttk.Checkbutton(card,text='Combine Botany + Zoology as Biology',variable=self.ia_combine_biology).pack(anchor='w',pady=(4,8))
        ttk.Label(card,text='Submit previews the selected workbook, then validates and processes eligible batches. Match read only is optional. Explicit absences submit as Absent. Absent students require manual Principal approval in all subjects. Other unsafe rows still block their displayed batch.',style='Muted.Card.TLabel',wraplength=690).pack(anchor='w',pady=(0,8))
        self.ia_advanced_open=tk.BooleanVar(value=False)
        self.ia_advanced_button=ttk.Button(card,text='Advanced settings ▸',command=self._toggle_internal_advanced)
        self.ia_advanced_button.pack(anchor='w',pady=(0,6))
        advanced_holder=ttk.Frame(card,style='Card.TFrame'); advanced_holder.pack(fill='x')
        self.ia_advanced_panel=ttk.LabelFrame(advanced_holder,text='Matching, limits and history',style='Card.TLabelframe',padding=8)
        self._field_row(self.ia_advanced_panel,'Worksheet',self.ia['sheet'])
        self._field_row(self.ia_advanced_panel,'Board report session',self.ia['report_session'],help_text='Auto: workbook 2025-26 → Students report 2026-2027. Other cycles need a verified report year.')
        self._field_row(self.ia_advanced_panel,'Excel maximum',self.ia['maximum'],help_text='JKBOSE supplies the official maximum. A difference requires manual review.')
        self._field_row(self.ia_advanced_panel,'Private history',self.ia['history'],browse_kind='dir')
        reconcile=ttk.Button(self.ia_advanced_panel,text='Reconcile an uncertain batch…',command=self._reconcile_internal)
        reconcile.pack(anchor='w',pady=6); self.run_buttons.append(reconcile)
        self.ia_session_confirm = tk.BooleanVar(value=False)
        for key in ['file', 'sheet', 'class', 'session', 'report_session', 'subject', 'maximum', 'account', 'history']:
            self.ia[key].trace_add('write', lambda *_: self.ia_session_confirm.set(False))
        self.ia_combine_biology.trace_add('write', lambda *_: self.ia_session_confirm.set(False))
        self.ia_subject_mode.trace_add('write',lambda *_:self.ia_session_confirm.set(False))
        for variable in self.ia_subject_choices.values(): variable.trace_add('write',lambda *_:self.ia_session_confirm.set(False))
        self.ia_subject_mode.trace_add('write',lambda *_:self._update_internal_subject_controls())
        self._update_internal_subject_controls()
        ttk.Checkbutton(card,text='I confirm the academic session and school account match JKBOSE,\nand no other operator is submitting these subjects.',variable=self.ia_session_confirm).pack(anchor='w',pady=(6,10))
        actions=ttk.Frame(card,style='Card.TFrame'); actions.pack(fill='x',pady=4)
        for text,command,style in [
                ('1. Preview Excel',lambda:self._internal_preview(False),'TButton'),
                ('2. Match read only',lambda:self._start_internal(False),'Accent.TButton'),
                ('3. Preview & Submit',lambda:self._start_internal(True),'TButton'),
                ('Principal approval…',self._open_principal_approval,'TButton')]:
            button=ttk.Button(actions,text=text,command=command,style=style)
            button.pack(side='left',padx=(0,8)); self.run_buttons.append(button)
        ttk.Button(card,text='Open History — latest reports',command=self._open_internal_history).pack(anchor='w',pady=(10,0))

    def _update_internal_subject_controls(self):
        self.ia_single_subject.pack_forget(); self.ia_selection_panel.pack_forget()
        if self.ia_subject_mode.get()=='Single subject':
            self.ia_single_subject.pack(side='left',padx=(12,0))
        elif self.ia_subject_mode.get()=='Selected subjects':
            self.ia_selection_panel.pack(fill='x',pady=(0,8))

    def _toggle_internal_advanced(self):
        opened=not self.ia_advanced_open.get(); self.ia_advanced_open.set(opened)
        self.ia_advanced_panel.pack_forget()
        if opened: self.ia_advanced_panel.pack(fill='x',pady=(0,8))
        self.ia_advanced_button.configure(text='Advanced settings ▾' if opened else 'Advanced settings ▸')

    def _internal_plan(self):
        return load_plan(self.ia['file'].get(), self.ia['sheet'].get(), self.ia['class'].get(),
                         self.ia['session'].get(), self.ia['subject'].get(), self.ia['maximum'].get(),
                         biology_component_max=self.ia['component_max'].get(),
                         combine_biology=self.ia_combine_biology.get())

    def _select_internal_workbook_subjects(self):
        try:
            available=workbook_subjects(self.ia['file'].get(),self.ia['sheet'].get(),self.ia['class'].get(),
                                        self.ia['session'].get(),self.ia_combine_biology.get())
            for subject,variable in self.ia_subject_choices.items(): variable.set(subject in available)
            self.ia_subject_mode.set('Selected subjects')
        except Exception as error: messagebox.showerror('Internal Assessment',str(error))

    def _internal_jobs(self):
        mode=self.ia_subject_mode.get()
        subjects=[self.ia['subject'].get()] if mode=='Single subject' else [subject for subject,variable in self.ia_subject_choices.items() if variable.get()]
        return load_jobs(self.ia['file'].get(),self.ia['sheet'].get(),self.ia['class'].get(),self.ia['session'].get(),
                         subjects,mode=='All workbook subjects',self.ia['maximum'].get(),self.ia['component_max'].get(),self.ia_combine_biology.get())

    def _internal_preview(self, require_confirm=False):
        try:
            jobs = self._internal_jobs()
            history_root = prepare_history_root(self.ia['history'].get())
            with RunLock(history_root):
                for job in jobs:
                    plan=job['plan']
                    if plan is None: continue
                    audit = Audit(history_root, plan)
                    audit.append('offline_preview', source=plan.manifest(), awards=plan.rows())
                    audit.report(plan)
        except Exception as error:
            messagebox.showerror('Internal Assessment', str(error)); return None
        try:
            from .features.internal_assessment_tracking import refresh_tracking_copy
            with RunLock(history_root):
                output=refresh_tracking_copy(self.ia['file'].get(),history_root,self.ia['class'].get(),self.ia['session'].get(),self.ia['account'].get())
            self._log('[TRACKING EXCEL] '+output+'\n')
        except Exception as tracking_error:self._log('[TRACKING NOT REFRESHED] '+str(tracking_error)+'\n')
        top = tk.Toplevel(self.root); top.title('Internal Assessment source preview')
        top.geometry('1180x620'); top.transient(self.root)
        result = {'accepted': not require_confirm}
        plans=[job['plan'] for job in jobs if job['plan']]
        blocked = sum(bool(submission_issues(award)) for plan in plans for award in plan.awards)
        ttk.Label(top, text=f'School {self.ia["account"].get()} | Class {self.ia["class"].get()} | {self.ia["session"].get()} | {len(jobs)} subjects | '
                  f'{sum(len(plan.awards) for plan in plans)} awards | {blocked} manual exceptions | '
                  f'{sum(job["plan"] is None for job in jobs)} subjects blocked at source',
                  padding=12).pack(anchor='w')
        ttk.Label(top, text='Offline limits come from Excel. The live JKBOSE maximum is authoritative. Explicit absences submit as Absent; these students require manual Principal approval. Failed, over-maximum or unsafe awards still block the displayed batch.',
                  padding=8).pack(anchor='w')
        search = tk.StringVar(); entry = ttk.Entry(top, textvariable=search); entry.pack(fill='x', padx=12, pady=4)
        frame = ttk.Frame(top); frame.pack(fill='both', expand=True, padx=12)
        columns = ('serial','group_serial','class','subject','reg', 'name', 'exam', 'parts', 'marks', 'status')
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for key, label, width in [('serial','S.No.',55),('group_serial','Class/Subject S.No.',125),('class','Class',55),('subject','Subject',150),('reg', 'Registration number', 175), ('name', 'Student name', 190),
                                  ('exam', 'Exam roll', 110), ('parts', 'Source components', 180),
                                  ('marks', 'Marks', 70), ('status', 'Validation / manual action', 390)]:
            tree.heading(key, text=label); tree.column(key, width=width, stretch=False)
        vertical = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky='nsew'); vertical.grid(row=0, column=1, sticky='ns'); horizontal.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        def render(*_):
            tree.delete(*tree.get_children())
            needle = search.get().lower()
            serial = 0
            group_serials = {}
            for job in jobs:
                plan=job['plan']
                if plan is None:
                    if needle in (job['subject']+' '+job['error']).lower(): tree.insert('','end',values=('','','',job['subject'],'','','','','',job['error']))
                    continue
                for award in plan.awards:
                    serial += 1
                    group = (plan.student_class, plan.subject)
                    group_serials[group] = group_serials.get(group, 0) + 1
                    text = ' '.join([plan.student_class,plan.subject,award.regno, award.name, award.exam_roll, *award.issues]).lower()
                    if needle not in text: continue
                    tree.insert('', 'end', values=(serial,group_serials[group],plan.student_class,plan.subject,award.regno, award.name, award.exam_roll,
                        ', '.join(f'{key}: {value or "missing"}' for key, value in award.components.items()),
                        f'{award.marks or ("AB" if award.attendance=="A" else "missing")}/{plan.maximum}', '; '.join(award.issues) or 'Eligible for live matching; official maximum checked on JKBOSE'))
        search.trace_add('write', render); render()
        footer = ttk.Frame(top, padding=12); footer.pack(fill='x')
        ttk.Label(footer, text=f'Private subject reports: {self.ia["history"].get()}').pack(side='left')
        ttk.Button(footer, text='Close', command=top.destroy).pack(side='right')
        if require_confirm:
            def accept(): result['accepted'] = True; top.destroy()
            ttk.Button(footer, text='Confirm preview & Submit', command=accept).pack(side='right', padx=8)
        top.grab_set(); self.root.wait_window(top)
        return jobs if result['accepted'] else None

    def _start_internal(self, execute):
        import main as cli
        if not execute and not self.ia_session_confirm.get():
            messagebox.showwarning('Internal Assessment', 'Confirm the active session and exclusive operation first.'); return
        try: jobs=self._internal_preview(require_confirm=True) if execute else self._internal_jobs()
        except Exception as error:messagebox.showerror('Internal Assessment',str(error));return
        if jobs is None:return
        self._start_task('Internal Assessment', cli.cmd_internal,
            dict(excel_file=self.ia['file'].get(),jobs=jobs,student_class=self.ia['class'].get(),session=self.ia['session'].get(),history_dir=self.ia['history'].get(),
                 school_account=self.ia['account'].get().strip(), report_session=self.ia['report_session'].get().strip(), execute=execute, confirm_session=True,
                 automatic_submit=execute,on_driver_ready=self._set_driver_ready), needs_stop=True)

    def _open_internal_history(self):
        path = Path(self.ia['history'].get())
        if not path.is_dir(): messagebox.showinfo('Internal Assessment', 'Create a preview first to initialize history.'); return
        index = path / 'OPEN HISTORY.html'
        if os.name == 'nt': os.startfile(str(index if index.is_file() else path))
        else: messagebox.showinfo('Private history', str(path))

    def _reconcile_internal(self):
        try:
            history_root = prepare_history_root(self.ia['history'].get())
            from .features.internal_assessment_reconciliation import build_reconciliation_references, resolve_manifest
            with RunLock(history_root):
                chooser_folder, references = build_reconciliation_references(history_root)
            path = filedialog.askopenfilename(title='Choose class and subject needing reconciliation',
                initialdir=str(chooser_folder),filetypes=[('Reconciliation reference or manifest','*.json')])
            if not path: return
            folder = resolve_manifest(path,history_root).parent
            with RunLock(history_root):
                audit, plan = Audit.existing(folder)
                batches = sorted(audit.unresolved())
            if not batches: raise ValueError('This run has no unresolved submission.')
        except Exception as error: messagebox.showerror('Manual reconciliation', str(error)); return
        top = tk.Toplevel(self.root); top.title('Manually reconcile an uncertain batch'); top.transient(self.root)
        frame = ttk.Frame(top, padding=18); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'Class {plan.student_class} | {plan.session} | {plan.subject}\n'
                  'First inspect these students on JKBOSE yourself. This action records your finding; it does not change JKBOSE awards.',
                  wraplength=650).pack(anchor='w', pady=8)
        batch, decision, actor = tk.StringVar(value=batches[0]), tk.StringVar(), tk.StringVar()
        ttk.Combobox(frame, textvariable=batch, values=batches, state='readonly', width=40).pack(anchor='w', pady=4)
        details = tk.StringVar()
        def selected(*_):
            attempt = next(event for event in audit.events if event['kind'] == 'submit_attempt' and event['batch_id'] == batch.get())
            details.set('Registration numbers: ' + ', '.join(attempt['registrations']))
        batch.trace_add('write', selected); selected()
        ttk.Label(frame, textvariable=details, wraplength=650).pack(anchor='w', pady=8)
        choices = {'Saved on JKBOSE — never retry these awards': 'saved_manually_verified',
                   'NOT saved on JKBOSE — permit a freshly validated retry': 'not_saved_manually_verified'}
        ttk.Combobox(frame, textvariable=decision, values=list(choices), state='readonly', width=72).pack(anchor='w', pady=4)
        ttk.Label(frame, text='Administrator who checked JKBOSE').pack(anchor='w'); ttk.Entry(frame, textvariable=actor, width=45).pack(anchor='w', pady=4)
        ttk.Label(frame, text='What you checked and what JKBOSE showed (required)').pack(anchor='w')
        note = tk.Text(frame, height=4, width=80); note.pack(fill='x', pady=4)
        confirmed = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text='I manually checked the entire batch on JKBOSE and confirm the selected outcome.', variable=confirmed).pack(anchor='w', pady=8)
        def record():
            try:
                if not confirmed.get() or decision.get() not in choices: raise ValueError('Check JKBOSE and explicitly confirm the outcome first.')
                if not messagebox.askyesno('Record manual finding?', 'Record this administrator attestation permanently in audit history?', parent=top): return
                with RunLock(history_root):
                    current, current_plan = Audit.existing(folder)
                    current.reconcile(batch.get(), choices[decision.get()], actor.get(), note.get('1.0', 'end').strip())
                    current.report(current_plan)
                top.destroy(); messagebox.showinfo('Manual reconciliation', 'Manual finding recorded. Reopen the source preview and perform a read-only JKBOSE check before resuming.')
            except Exception as error: messagebox.showerror('Manual reconciliation', str(error), parent=top)
        ttk.Button(frame, text='Record manual verification', command=record).pack(anchor='w', pady=8)
        top.grab_set(); self.root.wait_window(top)

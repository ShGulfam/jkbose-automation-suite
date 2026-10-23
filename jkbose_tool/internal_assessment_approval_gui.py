"""Principal controls share the Internal Assessment source/subject selection."""
from pathlib import Path
import threading,json,os
import tkinter as tk
from tkinter import ttk,messagebox,filedialog

class PrincipalApprovalGUI:
    def _open_principal_approval(self):
        from .features.internal_assessment_approval import accounts
        top=tk.Toplevel(self.root);top.title('Principal Internal Assessment');top.transient(self.root);top.grab_set()
        frame=ttk.Frame(top,padding=16);frame.pack(fill='both',expand=True)
        school=self.ia['account'].get().strip().lower();principal=tk.StringVar(value='prin'+school[3:] if school.startswith('sch') else '')
        ttk.Label(frame,text='Uses the selected workbook, class, session and subjects above.\nSeparate Principal login; this does not submit marks.',wraplength=550).pack(anchor='w',pady=6)
        ttk.Label(frame,text='Expected Principal account').pack(anchor='w');ttk.Entry(frame,textvariable=principal,width=30).pack(anchor='w',pady=5)
        confirmed=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,text='I confirm the examination session and that no other operator\nis approving these requests.',variable=confirmed).pack(anchor='w',pady=8)
        def start(execute):
            import main as cli
            try:
                accounts(school,principal.get().strip())
                if execute and not confirmed.get():raise ValueError('Confirm the examination session and exclusive Principal operation first.')
                jobs=self._internal_jobs()
                kwargs=dict(excel_file=self.ia['file'].get(),jobs=jobs,school_account=school,principal_account=principal.get().strip(),
                            history_dir=self.ia['history'].get(),report_session=self.ia['report_session'].get().strip(),execute=execute,
                            confirm_session=True,confirm_callback=self._confirm_principal_approval,on_driver_ready=self._set_driver_ready)
            except Exception as error:messagebox.showerror('Principal approval',str(error),parent=top);return
            top.destroy();self._start_task('Principal Internal Assessment',cli.cmd_internal_approve,kwargs,needs_stop=True)
        actions=ttk.Frame(frame);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Check requests (read only)',command=lambda:start(False)).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='Preview & Approve',command=lambda:start(True)).pack(side='left')
        ttk.Button(frame,text='Reconcile uncertain approval…',command=lambda:(top.destroy(),self._reconcile_principal())).pack(anchor='w',pady=5)
        ttk.Button(frame,text='Open Principal history',command=lambda:self._open_principal_history()).pack(anchor='w',pady=5)

    def _confirm_principal_approval(self,data):
        event=threading.Event();answer={'accepted':False};window={}
        def show():
            if self.stop_event.is_set():event.set();return
            top=tk.Toplevel(self.root);window['top']=top;top.title('Principal approval preview');top.geometry('1050x580');top.transient(self.root);top.grab_set()
            scope=data['scope'];eligible=sum(row['eligible'] for row in data['rows'])
            ttk.Label(top,text=f'Principal {scope["principal"]} | Class {scope["class"]} | School session {scope["session"]} | Board report {data["report_session"]}\n{eligible} exact awards ready; held awards remain untouched.',padding=12).pack(anchor='w')
            frame=ttk.Frame(top);frame.pack(fill='both',expand=True,padx=12)
            tree=ttk.Treeview(frame,columns=('subject','reg','exam','name','marks','outcome'),show='headings')
            for key,label,width in [('subject','Subject',130),('reg','Registration',170),('exam','Exam roll',110),('name','Student',190),('marks','Given / Max',90),('outcome','Validation / action',340)]:
                tree.heading(key,text=label);tree.column(key,width=width,stretch=False)
            y=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
            tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);tree.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew');frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
            for entry in data['rows']:
                r=entry['request'];tree.insert('','end',values=(r['subject'],r['regno'],r['exam_roll'],r['name'],r['marks']+' / '+r['maximum'],'Approve' if entry['eligible'] else '; '.join(entry['reasons'])))
            def finish(accepted=False):answer['accepted']=accepted;top.destroy();event.set()
            footer=ttk.Frame(top,padding=12);footer.pack(fill='x')
            ttk.Button(footer,text='Cancel',command=finish).pack(side='right')
            if eligible:ttk.Button(footer,text=f'Approve {eligible} matched awards',command=lambda:finish(True)).pack(side='right',padx=8)
            top.protocol('WM_DELETE_WINDOW',finish)
        self.root.after(0,show)
        while not event.wait(.2):
            if self.stop_event.is_set():
                def close():
                    top=window.get('top')
                    if top and top.winfo_exists():top.destroy()
                self.root.after(0,close);return False
        return answer['accepted'] and not self.stop_event.is_set()

    def _open_principal_history(self):
        from .features.internal_assessment_history import storage_root
        folder=storage_root(self.ia['history'].get())/'Principal_Approvals'
        if not folder.is_dir():messagebox.showinfo('Principal history','Run Check requests first.');return
        if os.name=='nt':os.startfile(str(folder/'OPEN HISTORY.html' if (folder/'OPEN HISTORY.html').is_file() else folder))

    def _reconcile_principal(self):
        from .features.internal_assessment import RunLock,prepare_history_root
        from .features.internal_assessment_history import storage_root
        from .features.internal_assessment_approval import ApprovalJournal
        try:
            root=prepare_history_root(self.ia['history'].get());folder=storage_root(root)/'Principal_Approvals'
            path=filedialog.askopenfilename(title='Select Principal approval journal',initialdir=str(folder),filetypes=[('Principal journal','events.jsonl')])
            if not path:return
            path=Path(path).resolve()
            if not path.is_relative_to(folder.resolve()) or path.name!='events.jsonl':raise ValueError('Select a journal inside Principal_Approvals.')
            first=json.loads(path.read_text(encoding='utf-8').splitlines()[0]);scope=first['scope'];journal=ApprovalJournal(root,scope)
            if journal.path.resolve()!=path:raise ValueError('Principal journal scope differs from its folder.')
            unresolved=journal.unresolved()
            if not unresolved:raise ValueError('No uncertain Principal actions in this journal.')
        except Exception as error:messagebox.showerror('Principal reconciliation',str(error));return
        top=tk.Toplevel(self.root);top.title('Reconcile uncertain Principal approval');top.transient(self.root);top.grab_set();frm=ttk.Frame(top,padding=16);frm.pack(fill='both',expand=True)
        labels={f'{rid} - {e["request"]["subject"]} - {e["request"]["name"]}':rid for rid,e in unresolved.items()}
        selected=tk.StringVar(value=next(iter(labels)));outcome=tk.StringVar();actor=tk.StringVar();confirmed=tk.BooleanVar(value=False)
        ttk.Label(frm,text=f'Principal {scope["principal"]} | Class {scope["class"]} | {scope["session"]}').pack(anchor='w')
        ttk.Label(frm,text='Inspect the official status yourself first. This records your finding; it does not change JKBOSE.',wraplength=650).pack(anchor='w',pady=8)
        ttk.Combobox(frm,textvariable=selected,values=list(labels),state='readonly',width=80).pack(fill='x')
        choices={'Approved on JKBOSE — never repeat':'approved','Not approved — permit a freshly validated action':'not_approved'}
        ttk.Combobox(frm,textvariable=outcome,values=list(choices),state='readonly',width=80).pack(fill='x',pady=8)
        ttk.Label(frm,text='Administrator who verified').pack(anchor='w');ttk.Entry(frm,textvariable=actor,width=45).pack(anchor='w')
        ttk.Label(frm,text='Specific official verification note (20+ characters)').pack(anchor='w');note=tk.Text(frm,height=4,width=80);note.pack(fill='x')
        ttk.Checkbutton(frm,text='I checked this exact request on JKBOSE and confirm the outcome.',variable=confirmed).pack(anchor='w',pady=8)
        def record():
            try:
                if not confirmed.get() or outcome.get() not in choices:raise ValueError('Confirm the exact official outcome first.')
                with RunLock(root):ApprovalJournal(root,scope).reconcile(labels[selected.get()],choices[outcome.get()],actor.get(),note.get('1.0','end').strip())
                top.destroy();messagebox.showinfo('Principal reconciliation','Finding recorded. Run a fresh Principal preview before continuing.')
            except Exception as error:messagebox.showerror('Principal reconciliation',str(error),parent=top)
        ttk.Button(frm,text='Record official finding',command=record).pack(anchor='w')

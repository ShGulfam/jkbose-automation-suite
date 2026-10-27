"""Read-only file verification controls, summaries and private history."""
from pathlib import Path
import os
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,scrolledtext

class AwardVerificationGUI:
    def _open_award_verification(self):
        from .features.internal_assessment_verification import verify_files,save_history,load_history,list_history,save_report_copy,history_root,local_time
        top=tk.Toplevel(self.root);top.title('Internal Assessment - Verify files');top.geometry('1050x710');top.minsize(800,560);top.transient(self.root)
        notebook=ttk.Notebook(top)
        inputs=ttk.Frame(notebook,padding=12);results=ttk.Frame(notebook,padding=12);history=ttk.Frame(notebook,padding=12)
        for frame,title in [(inputs,'Choose files'),(results,'Analysis'),(history,'Verification history')]:notebook.add(frame,text=title)
        cls=tk.StringVar(value=self.ia['class'].get()or'11');session=tk.StringVar(value=self.ia['session'].get());status=tk.StringVar(value='Offline comparison only. No marks or portal records are changed.')
        cohort=ttk.Frame(inputs);cohort.pack(fill='x',pady=(0,10));ttk.Label(cohort,text='Class').pack(side='left');ttk.Combobox(cohort,textvariable=cls,values=[str(i)for i in range(1,13)],width=7).pack(side='left',padx=8);ttk.Label(cohort,text='School session (YYYY-YY)').pack(side='left',padx=(12,6));ttk.Entry(cohort,textvariable=session,width=15).pack(side='left')
        limits=tk.StringVar();rules=ttk.Frame(inputs);rules.pack(fill='x',pady=(0,10));ttk.Label(rules,text='Subject maxima').pack(side='left');ttk.Entry(rules,textvariable=limits).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Label(inputs,text='11th/12th limits are built in. For other classes enter each subject name/code and maximum, for example English=20; Science=10. Custom subjects use the exact name printed in the files.',wraplength=920).pack(anchor='w',pady=(0,10))
        ttk.Label(inputs,text='Choose any combination: admit cards + school awards, admit cards + JKBOSE awards, or school + JKBOSE awards. Each award file is checked as its own snapshot; award files should each cover all students/subjects expected in that source.',wraplength=920).pack(anchor='w',pady=(0,10))
        def responsive(event):
            for child in inputs.winfo_children():
                if isinstance(child,ttk.Label):child.configure(wraplength=max(250,event.width-28))
        inputs.bind('<Configure>',responsive)
        selections={};boxes={};filearea=ttk.Frame(inputs);filearea.pack(fill='both',expand=True)
        for col,(role,title)in enumerate([('admit','Admit-card PDFs'),('school','School awards (PDF / Excel)'),('jkbose','JKBOSE awards (PDF / Excel)')]):
            panel=ttk.LabelFrame(filearea,text=title,padding=8);panel.grid(row=0,column=col,sticky='nsew',padx=(0,8));filearea.columnconfigure(col,weight=1)
            selections[role]=[];box=tk.Listbox(panel,height=12,width=1,selectmode='extended');boxes[role]=box;box.pack(fill='both',expand=True)
            def add(role=role,box=box):
                paths=filedialog.askopenfilenames(parent=top,title='Choose '+role+' evidence',filetypes=[('PDF admit cards','*.pdf')]if role=='admit'else[('PDF or Excel awards','*.pdf *.xlsx *.xls *.html')])
                for path in paths:
                    if path not in selections[role]:selections[role].append(path);box.insert('end',Path(path).name)
            def remove(role=role,box=box):
                for index in reversed(box.curselection()):box.delete(index);selections[role].pop(index)
            buttons=ttk.Frame(panel);buttons.pack(fill='x',pady=(8,0));ttk.Button(buttons,text='Add files…',command=add).pack(side='left');ttk.Button(buttons,text='Remove',command=remove).pack(side='right')
        filearea.rowconfigure(0,weight=1)
        ttk.Label(inputs,text='Supports combined Botany/Zoology, individual JKBOSE requests and grouped student/subject marks. Healthcare and IT/ITES are excluded from required Internal Assessment subjects. Scans need readable/OCR text; unsupported layouts are flagged.',wraplength=920).pack(anchor='w',pady=10)
        ttk.Label(top,textvariable=status,wraplength=980).pack(side='bottom',fill='x',padx=16,pady=(0,5))
        overview=scrolledtext.ScrolledText(results,height=11,wrap='word',font=('Segoe UI',10),state='disabled');overview.pack(fill='x',pady=(0,10))
        treeframe=ttk.Frame(results);treeframe.pack(fill='both',expand=True);columns=('kind','source','name','roll','reg','subject','detail');tree=ttk.Treeview(treeframe,columns=columns,show='headings')
        for key,label,width in [('kind','Finding',180),('source','Source',220),('name','Student',160),('roll','Exam roll',110),('reg','Registration',170),('subject','Subject',110),('detail','Details',420)]:tree.heading(key,text=label);tree.column(key,width=width,stretch=False)
        ys=ttk.Scrollbar(treeframe,orient='vertical',command=tree.yview);xs=ttk.Scrollbar(treeframe,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew');treeframe.rowconfigure(0,weight=1);treeframe.columnconfigure(0,weight=1)
        selected={'folder':None};history_rows={}
        histories=ttk.Treeview(history,columns=('date','class','session','outcome'),show='headings')
        for key,label,width in [('date','Recorded (IST)',190),('class','Class',70),('session','School session',120),('outcome','Result',460)]:histories.heading(key,text=label);histories.column(key,width=width)
        histories.pack(fill='both',expand=True)
        def refresh_history():
            histories.delete(*histories.get_children());history_rows.clear()
            try:
                for i,row in enumerate(list_history(self.ia['history'].get())):history_rows[str(i)]=row;histories.insert('','end',iid=str(i),values=(local_time(row['created_at']),row['student_class'],row['session'],row['outcome']))
            except Exception as exc:status.set('History could not be read: '+str(exc))
        def display(folder):
            try:
                report=load_history(folder,self.ia['history'].get());selected['folder']=folder
                lines=[report['outcome'],f'Class {report["student_class"]} | School session {report["session"]}',f'Admit-card students: {report["admit_students"]} | Expected subject awards: {report["expected_awards"] if report["expected_awards"]is not None else "not verified"}',f'Issues: {report["error_count"]} | Warnings: {report["warning_count"]}',report['scope_note'],'']
                for source in report['sources']:lines.append(f'{source["source"]}: {source["students"]} students, {source["awards"]} awards; missing {source["missing"] if source["missing"]is not None else "n/a"}, extra {source["extra"] if source["extra"]is not None else "n/a"}.')
                lines.extend(['','Subject totals (each source in the order above):'])
                for code,label in report.get('subject_labels',{}).items():
                    counts=[str(s['subjects'].get(code,0))for s in report['sources']]
                    expected=report.get('expected_subjects',{}).get(code,0)
                    if expected or any(int(c)for c in counts):lines.append(f'{label}: expected {expected if report["completeness_checked"]else "unverified"}; files '+', '.join(counts))
                lines.append('Every selected award file is a separate snapshot. No live submission/approval status is inferred.')
                overview.configure(state='normal');overview.delete('1.0','end');overview.insert('1.0','\n'.join(lines));overview.configure(state='disabled');tree.delete(*tree.get_children())
                for row in report['issues']:tree.insert('','end',values=tuple(row[key]for key in columns))
                notebook.select(results);status.set('Analysis retained in private verification history. Save PDF as… creates a copy anywhere you choose.');refresh_history()
            except Exception as exc:messagebox.showerror('Verification history',str(exc),parent=top)
        def open_selected():
            chosen=histories.selection()
            if chosen:display(history_rows[chosen[0]]['folder'])
        ttk.Button(history,text='Open selected analysis',command=open_selected).pack(anchor='w',pady=8);histories.bind('<Double-1>',lambda event:open_selected())
        footer=ttk.Frame(top,padding=12);footer.pack(side='bottom',fill='x')
        def save():
            if not selected['folder']:messagebox.showinfo('Save verification','Run a verification or open an earlier analysis first.',parent=top);return
            try:
                report=load_history(selected['folder'],self.ia['history'].get());path=filedialog.asksaveasfilename(parent=top,title='Save verification PDF',defaultextension='.pdf',initialfile=f'Class_{report["student_class"]}_Internal_Assessment_Verification_{report["session"]}.pdf',filetypes=[('PDF report','*.pdf')])
                if path:save_report_copy(selected['folder'],path,self.ia['history'].get());status.set('PDF copy saved: '+path)
            except Exception as exc:messagebox.showerror('Save verification',str(exc),parent=top)
        def start():
            if self.worker and self.worker.is_alive():messagebox.showinfo('Verification','Wait for the current task to finish.',parent=top);return
            files={role:list(paths)for role,paths in selections.items()};chosen_class=cls.get();chosen_session=session.get().strip();chosen_limits=limits.get();root=self.ia['history'].get();status.set('Reading selected files and comparing paired identifiers…')
            def work(stop_event=None):
                report=verify_files(files['admit'],files['school'],files['jkbose'],chosen_class,chosen_session,stop_event,subject_maxima=chosen_limits)
                if stop_event and stop_event.is_set():raise ValueError('Verification stopped before history was saved.')
                folder=save_history(report,root);print(f'[VERIFICATION] {report["outcome"]}; {report["error_count"]} issues; {report["warning_count"]} warnings.');print('[VERIFICATION HISTORY] '+folder)
                def show():
                    if top.winfo_exists():display(folder)
                self.root.after(0,show)
            def task(stop_event=None):
                try:work(stop_event)
                except Exception as exc:
                    text='Verification could not complete: '+str(exc)
                    self.root.after(0,lambda:status.set(text)if top.winfo_exists()else None)
                    raise
            self._start_task('Offline Internal Assessment Verification',task,{},needs_stop=True)
        ttk.Button(footer,text='Verify selected files',command=start).pack(side='left');ttk.Button(footer,text='Save PDF as…',command=save).pack(side='left',padx=8);ttk.Button(footer,text='Refresh history',command=refresh_history).pack(side='left');ttk.Button(footer,text='Close',command=top.destroy).pack(side='right')
        notebook.pack(fill='both',expand=True,padx=12,pady=12)
        refresh_history()
        if history_rows:status.set('Latest verification is retained in the Verification history tab. Open it without rerunning files.')

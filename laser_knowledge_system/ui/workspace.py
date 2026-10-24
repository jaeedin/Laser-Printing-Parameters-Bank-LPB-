from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QBoxLayout, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import RepositoryError, SQLiteRepository
from laser_knowledge_system.domain.experiments import Experiment, ExperimentRun, ResultRecord
from laser_knowledge_system.domain.machines import MachineProfile
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord
from laser_knowledge_system.domain.notebook import NotebookEntry
from laser_knowledge_system.domain.presets import Preset
from laser_knowledge_system.domain.processes import ParameterValueType, ProcessDefinition, ProcessType, standard_engraving_defaults, standard_engraving_parameters
from laser_knowledge_system.portable import export_experiment, import_experiment
from laser_knowledge_system.portable_materials import MaterialPackage, clear_experiment_draft, clear_open_record, delete_package, find_profile, import_profiles, load_experiment_drafts, load_open_record, save_experiment_draft, save_open_record, scan_packages, sync_vault, update_package, vault_path, write_package

STYLE = """QMainWindow,QWidget{background:#F6F7F6;color:#17211D;font-family:'Segoe UI';}QFrame#sidebar,QFrame#sidebar QWidget{background:#16231E;}QFrame#card{background:#FFFFFF;border:1px solid #D3DBD6;border-radius:10px;}QFrame#sidebar QLabel,QLabel#brand,QFrame#sidebar QLabel#muted{color:#E7F0EA;}QLabel#brand{font-size:20px;font-weight:700;}QLabel#muted{color:#66756D;font-size:12px;}QLabel#title{font-size:28px;font-weight:700;color:#17211D;}QLabel#subtitle{color:#4E5F55;font-size:14px;}QLabel#section{font-size:16px;font-weight:700;}QLabel#metric{color:#17211D;font-size:26px;font-weight:700;}QPushButton{border:1px solid #718078;border-radius:7px;min-height:38px;padding:0 14px;font-weight:600;background:#FFFFFF;color:#17211D;}QPushButton:hover{background:#EDF4EF;}QPushButton:focus,QLineEdit:focus,QComboBox:focus,QTextEdit:focus,QDoubleSpinBox:focus,QSpinBox:focus{border:2px solid #28734A;}QPushButton:disabled{background:#E6EAE7;color:#7A847E;border-color:#CCD3CE;}QPushButton#primary{background:#1E6A42;color:white;border-color:#1E6A42;}QPushButton#primary:hover{background:#175636;}QPushButton#secondary{background:#FFFFFF;color:#17211D;border-color:#718078;}QFrame#sidebar QPushButton#nav{background:transparent;color:#E7F0EA;border:0;text-align:left;min-height:42px;}QFrame#sidebar QPushButton#nav:hover,QFrame#sidebar QPushButton#nav:checked{background:#294238;color:#FFFFFF;}QLineEdit,QComboBox,QTextEdit,QDoubleSpinBox,QSpinBox{background:white;border:1px solid #8A9890;border-radius:7px;padding:8px;}QTableWidget{background:white;alternate-background-color:#F1F5F2;border:1px solid #D3DBD6;border-radius:8px;}QTableWidget::item:selected{background:#D7EBDD;color:#17211D;}QHeaderView::section{background:#E8EFEA;border:0;padding:9px;font-weight:700;}QScrollArea{border:0;}"""

def card():
    frame=QFrame(); frame.setObjectName("card"); layout=QVBoxLayout(frame); layout.setContentsMargins(20,18,20,18); layout.setSpacing(8); return frame,layout

class DashboardPage(QWidget):
    def __init__(self,repo,start,open_existing):
        super().__init__(); self.repo,self.open_existing=repo,open_existing; layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18)
        for text,name in (("LOCAL-FIRST LASER KNOWLEDGE","muted"),("Overview","title"),("Your materials, trials, and proven settings in one local workspace.","subtitle")):
            label=QLabel(text); label.setObjectName(name); layout.addWidget(label)
        button=QPushButton("Start a new experiment"); button.setObjectName("primary"); button.clicked.connect(start); layout.addWidget(button,alignment=Qt.AlignmentFlag.AlignLeft)
        metrics=QHBoxLayout(); self.metrics_layout=metrics; self.metric_boxes=[]; self.metrics=[]
        for text in ("Materials in library","Recorded experiments","Established presets"):
            box,inner=card(); value=QLabel("0"); value.setObjectName("metric"); self.metrics.append(value); self.metric_boxes.append(box); inner.addWidget(value); inner.addWidget(QLabel(text)); metrics.addWidget(box)
        layout.addLayout(metrics); box,inner=card(); section=QLabel("Recent experiments"); section.setObjectName("section"); inner.addWidget(section); helper=QLabel("Double-click an experiment to continue scoring its trials. Use the Experiments page for the full register."); helper.setObjectName("subtitle"); inner.addWidget(helper); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Experiment","Objective","Material / process","Trials","Best score","Status"]); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); self.table.cellDoubleClicked.connect(lambda r,_:self.open_existing(self.table.item(r,0).data(Qt.ItemDataRole.UserRole))); inner.addWidget(self.table); layout.addWidget(box,stretch=1); self.refresh()
    def refresh(self):
        experiments=self.repo.list_experiments(); self.metrics[0].setText(str(len(self.repo.list_materials()))); self.metrics[1].setText(str(len(experiments))); self.metrics[2].setText(str(len(self.repo.list_presets()))); self.table.setRowCount(0)
        for n,experiment in enumerate(experiments[:8],1):
            row=self.table.rowCount(); self.table.insertRow(row)
            material=self.repo.get_material(experiment.material_id); process=self.repo.get_process(experiment.process_id); scores=[self._score(run.results) for run in experiment.runs if run.results]; best=max(scores) if scores else None
            for col,value in enumerate((f"Experiment {n}",experiment.objective,f"{material.name if material else 'Unknown'} / {process.name if process else 'Unknown'}",str(len(experiment.runs)),f"{best:.1f}/10" if best is not None else "Not scored",experiment.status.value.title())):
                item=QTableWidgetItem(value); self.table.setItem(row,col,item)
                if col==0:item.setData(Qt.ItemDataRole.UserRole,experiment.id)
    @staticmethod
    def _score(result):
        return (result.quality + result.contrast + result.detail + (10 - result.burn)) / 4
    def resizeEvent(self,event):
        super().resizeEvent(event)
        direction = QBoxLayout.Direction.TopToBottom if self.width() < 780 else QBoxLayout.Direction.LeftToRight
        if self.metrics_layout.direction() != direction:
            self.metrics_layout.setDirection(direction)

class ExperimentWorkspaceWidget(QWidget):
    def __init__(self,repo=None,go_home=None):
        super().__init__(); self.repo,self.experiment_id,self.parameter_inputs=repo,None,{}; layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18)
        header=QHBoxLayout(); self.title_label=QLabel("Create experiment"); self.title_label.setObjectName("title"); header.addWidget(self.title_label); header.addStretch(); export=QPushButton("Export block"); export.setObjectName("secondary"); export.clicked.connect(self._export); header.addWidget(export); delete_experiment=QPushButton("Delete experiment"); delete_experiment.setObjectName("secondary"); delete_experiment.clicked.connect(self._delete_experiment); header.addWidget(delete_experiment)
        if go_home: back=QPushButton("Back to overview"); back.setObjectName("secondary"); back.clicked.connect(go_home); header.addWidget(back)
        layout.addLayout(header); setup,inner=card(); section=QLabel("Experiment context"); section.setObjectName("section"); inner.addWidget(section); self.material_combo=QComboBox(); self.machine_combo=QComboBox(); self.process_combo=QComboBox(); self.objective_input=QLineEdit(); self.objective_input.setPlaceholderText("For example: produce a dark, high-contrast mark"); form=QFormLayout(); form.addRow("Material",self.material_combo); form.addRow("Machine",self.machine_combo); form.addRow("Process",self.process_combo); form.addRow("Objective",self.objective_input); inner.addLayout(form)
        adds=QHBoxLayout()
        for text,handler in (("Add material",self._add_material),("Add machine",self._add_machine),("Add process",self._add_process)):
            button=QPushButton(text); button.setObjectName("secondary"); button.clicked.connect(handler); adds.addWidget(button)
        inner.addLayout(adds); self.start_button=QPushButton("Start experiment"); self.start_button.setObjectName("primary"); self.start_button.clicked.connect(self._start); inner.addWidget(self.start_button,alignment=Qt.AlignmentFlag.AlignLeft); self.feedback=QLabel("Choose the context, then record trials."); self.feedback.setObjectName("subtitle"); inner.addWidget(self.feedback); layout.addWidget(setup)
        work_row=QGridLayout(); work_row.setHorizontalSpacing(18); parameters,pinner=card(); label=QLabel("1. Set trial values"); label.setObjectName("section"); pinner.addWidget(label); parameter_help=QLabel("Change the laser values for this trial."); parameter_help.setObjectName("subtitle"); pinner.addWidget(parameter_help); self.parameter_form=QFormLayout(); pinner.addLayout(self.parameter_form); work_row.addWidget(parameters,0,0)
        scoring,sinner=card(); label=QLabel("2. Score the result"); label.setObjectName("section"); sinner.addWidget(label); score_help=QLabel("Score each area from 0 (poor) to 10 (excellent). Burn is reversed in the total: lower is better."); score_help.setWordWrap(True); score_help.setObjectName("subtitle"); sinner.addWidget(score_help); score_grid=QGridLayout(); self.quality_input=self._score_box(5); self.contrast_input=self._score_box(5); self.detail_input=self._score_box(5); self.burn_input=self._score_box(0); score_grid.addWidget(QLabel("Overall quality"),0,0); score_grid.addWidget(self.quality_input,0,1); score_grid.addWidget(QLabel("Contrast"),1,0); score_grid.addWidget(self.contrast_input,1,1); score_grid.addWidget(QLabel("Detail"),2,0); score_grid.addWidget(self.detail_input,2,1); score_grid.addWidget(QLabel("Burn / damage"),3,0); score_grid.addWidget(self.burn_input,3,1); sinner.addLayout(score_grid); self.total_score=QLabel("Trial score: 7.5 / 10"); self.total_score.setObjectName("section"); sinner.addWidget(self.total_score); self.observation_input=QLineEdit(); self.observation_input.setPlaceholderText("Short observation, e.g. sharp edges; no heat mark"); sinner.addWidget(self.observation_input); self.record_run_button=QPushButton("Record scored trial"); self.record_run_button.setObjectName("primary"); self.record_run_button.setEnabled(False); self.record_run_button.clicked.connect(self._record_run); sinner.addWidget(self.record_run_button,alignment=Qt.AlignmentFlag.AlignLeft); work_row.addWidget(scoring,0,1); work_row.setColumnStretch(0,1); work_row.setColumnStretch(1,1); layout.addLayout(work_row)
        runs,rinner=card(); label=QLabel("3. Compare trials and choose the winner"); label.setObjectName("section"); rinner.addWidget(label); comparison_help=QLabel("The total score combines quality, contrast, detail, and the inverse of burn. Select the strongest trial, then save its values as your standard preset."); comparison_help.setObjectName("subtitle"); comparison_help.setWordWrap(True); rinner.addWidget(comparison_help); self.runs_table=QTableWidget(0,9); self.runs_table.setHorizontalHeaderLabels(["Run","Power","Speed","Passes","Total","Quality","Contrast","Detail","Burn"]); self.runs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.runs_table.verticalHeader().setVisible(False); self.runs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); rinner.addWidget(self.runs_table); actions=QHBoxLayout(); best=QPushButton("Save selected trial as best parameter preset"); best.setObjectName("secondary"); best.clicked.connect(self._save_best); actions.addWidget(best); snapshot=QPushButton("Add snapshot to selected trial"); snapshot.setObjectName("secondary"); snapshot.clicked.connect(self._add_snapshot); actions.addWidget(snapshot); remove=QPushButton("Delete selected trial"); remove.setObjectName("secondary"); remove.clicked.connect(self._delete_run); actions.addWidget(remove); actions.addStretch(); rinner.addLayout(actions); layout.addWidget(runs,stretch=1)
        notes,ninner=card(); label=QLabel("Experiment notebook"); label.setObjectName("section"); ninner.addWidget(label); self.notebook=QTextEdit(); self.notebook.setPlaceholderText("Record observations, defects, and changes between runs."); self.notebook.setMinimumHeight(80); ninner.addWidget(self.notebook); note=QPushButton("Save note"); note.setObjectName("secondary"); note.clicked.connect(self._save_note); ninner.addWidget(note,alignment=Qt.AlignmentFlag.AlignLeft); layout.addWidget(notes); self._load_library(); self.process_combo.currentIndexChanged.connect(self._build_parameters)
    def _load_library(self):
        for combo,placeholder in ((self.material_combo,"Choose material"),(self.machine_combo,"Choose machine"),(self.process_combo,"Choose process")): combo.clear(); combo.addItem(placeholder,None)
        if self.repo:
            for item in self.repo.list_materials():self.material_combo.addItem(item.name,item.id)
            for item in self.repo.list_machines():self.machine_combo.addItem(item.name,item.id)
            for item in self.repo.list_processes():self.process_combo.addItem(item.name,item.id)
    def _ask(self,title,prompt):
        value,ok=QInputDialog.getText(self,title,prompt); return value.strip() if ok and value.strip() else None
    def _add_material(self):
        name=self._ask("Add material","Material name:")
        if name and self.repo:self.repo.add_material(MaterialRecord(f"mat-{uuid4()}",MaterialFamily.OTHER,name)); self._load_library(); self.material_combo.setCurrentIndex(self.material_combo.count()-1)
    def _add_machine(self):
        name=self._ask("Add machine","Machine name:")
        if name and self.repo:self.repo.add_machine(MachineProfile(f"machine-{uuid4()}",name,"unspecified",0,"unspecified","unspecified")); self._load_library(); self.machine_combo.setCurrentIndex(self.machine_combo.count()-1)
    def _add_process(self):
        name=self._ask("Add process","Process name:")
        if name and self.repo:
            defaults=standard_engraving_defaults()
            self.repo.add_process(ProcessDefinition(f"process-{uuid4()}",name,ProcessType.ENGRAVING,default_parameters=defaults,parameter_schema=standard_engraving_parameters())); self._load_library(); self.process_combo.setCurrentIndex(self.process_combo.count()-1)
    def _build_parameters(self):
        while self.parameter_form.rowCount()>0:self.parameter_form.removeRow(0)
        self.parameter_inputs={}; process=self.repo.get_process(self.process_combo.currentData()) if self.repo and self.process_combo.currentData() else None
        if not process:return
        standard=standard_engraving_parameters(); known={item.key for item in process.parameter_schema}; missing=[item for item in standard if item.key not in known]
        if missing:
            process.parameter_schema.extend(missing); process.default_parameters={**standard_engraving_defaults(),**process.default_parameters}; self.repo.update_process(process)
        for definition in process.parameter_schema:
            value=process.default_parameters.get(definition.key)
            if definition.value_type is ParameterValueType.BOOLEAN:
                widget=QCheckBox(); widget.setChecked(bool(value))
            elif definition.value_type is ParameterValueType.CHOICE:
                widget=QComboBox(); widget.addItems(definition.choices); widget.setCurrentText(str(value or definition.choices[0]))
            elif definition.value_type is ParameterValueType.INTEGER: widget=QSpinBox(); widget.setRange(int(definition.minimum or -999999),int(definition.maximum or 999999)); widget.setValue(int(value or 0))
            else: widget=QDoubleSpinBox(); widget.setDecimals(3); widget.setRange(definition.minimum if definition.minimum is not None else -999999,definition.maximum if definition.maximum is not None else 999999); widget.setValue(float(value or 0))
            self.parameter_inputs[definition.key]=widget; self.parameter_form.addRow(definition.label+(f" ({definition.unit})" if definition.unit else ""),widget)
    def _score_box(self,value):
        box=QDoubleSpinBox(); box.setRange(0,10); box.setSingleStep(.5); box.setValue(value); box.valueChanged.connect(self._update_total_score); return box
    def _update_total_score(self):
        if hasattr(self,"total_score"):
            score=(self.quality_input.value()+self.contrast_input.value()+self.detail_input.value()+(10-self.burn_input.value()))/4
            self.total_score.setText(f"Trial score: {score:.1f} / 10")
    def _start(self):
        missing=[name for name,value in (("material",self.material_combo.currentData()),("machine",self.machine_combo.currentData()),("process",self.process_combo.currentData()),("objective",self.objective_input.text().strip())) if not value]
        if missing:self.feedback.setText("Choose: "+", ".join(missing)+"."); return
        try:
            experiment=Experiment(f"exp-{uuid4()}",self.material_combo.currentData(),self.machine_combo.currentData(),self.process_combo.currentData(),self.objective_input.text().strip()); self.repo.add_experiment(experiment); self.experiment_id=experiment.id; self.start_button.setEnabled(False); self.record_run_button.setEnabled(True); self.feedback.setText("Experiment saved locally. Record its trial runs below.")
        except RepositoryError as error:self.feedback.setText(str(error))
    def _parameter_values(self):return {key:(widget.currentText() if isinstance(widget,QComboBox) else widget.isChecked() if isinstance(widget,QCheckBox) else widget.value()) for key,widget in self.parameter_inputs.items()}
    def _record_run(self):
        try:
            process=self.repo.get_process(self.process_combo.currentData()); parameters=self._parameter_values(); process.validate_parameters(parameters); number=len(self.repo.list_runs(self.experiment_id))+1; result=ResultRecord(quality=self.quality_input.value(),contrast=self.contrast_input.value(),detail=self.detail_input.value(),burn=self.burn_input.value(),observations=self.observation_input.text().strip()); self.repo.add_run(ExperimentRun(f"run-{uuid4()}",self.experiment_id,number,parameters,result)); self.observation_input.clear(); self._load_runs(); self.feedback.setText(f"Trial {number} recorded with a {self._result_score(result):.1f}/10 score.")
        except (RepositoryError,ValueError) as error:self.feedback.setText(str(error))
    def _load_runs(self):
        self.runs_table.setRowCount(0)
        for run in self.repo.list_runs(self.experiment_id):
            row=self.runs_table.rowCount(); self.runs_table.insertRow(row); p,r=run.parameters,run.results
            score=f"{self._result_score(r):.1f}" if r else "—"
            for col,value in enumerate((str(run.run_number),str(p.get("power_percent",p.get("power_w","—"))),str(p.get("speed_mm_s","—")),str(p.get("passes","—")),score,str(r.quality if r else "—"),str(r.contrast if r else "—"),str(r.detail if r else "—"),str(r.burn if r else "—"))):
                item=QTableWidgetItem(value); self.runs_table.setItem(row,col,item)
                if col==0:item.setData(Qt.ItemDataRole.UserRole,run.id)
    @staticmethod
    def _result_score(result):
        return (result.quality + result.contrast + result.detail + (10 - result.burn)) / 4
    def _save_best(self):
        if not self.experiment_id or self.runs_table.currentRow()<0:self.feedback.setText("Select a trial first."); return
        experiment=self.repo.get_experiment(self.experiment_id); run_id=self.runs_table.item(self.runs_table.currentRow(),0).data(Qt.ItemDataRole.UserRole); run=next(run for run in experiment.runs if run.id==run_id); experiment.selected_best_run_id=run_id; self.repo.update_experiment_selection(experiment); name=self._ask("Save best parameters","Preset name:")
        if name:self.repo.create_preset(Preset.from_experiment_run(id=f"preset-{uuid4()}",name=name,experiment_id=experiment.id,run_id=run.id,run_parameters=run.parameters,source_quality=run.results.quality if run.results else None)); self.feedback.setText("Best parameter values saved as an established preset.")
    def _save_note(self):
        if self.experiment_id and self.notebook.toPlainText().strip():self.repo.add_notebook_entry(NotebookEntry(id=f"note-{uuid4()}",experiment_id=self.experiment_id,text=self.notebook.toPlainText().strip())); self.notebook.clear(); self.feedback.setText("Notebook entry saved.")
    def load_experiment(self,experiment_id):
        experiment=self.repo.get_experiment(experiment_id)
        if not experiment:return
        self._load_library(); self.experiment_id=experiment.id; self.title_label.setText("Experiment"); self.material_combo.setCurrentIndex(self.material_combo.findData(experiment.material_id)); self.machine_combo.setCurrentIndex(self.machine_combo.findData(experiment.machine_id)); self.process_combo.setCurrentIndex(self.process_combo.findData(experiment.process_id)); self.objective_input.setText(experiment.objective); self.start_button.setEnabled(False); self.record_run_button.setEnabled(True); self._load_runs(); self.feedback.setText("Loaded saved experiment.")
    def _selected_run_id(self):
        row=self.runs_table.currentRow()
        return self.runs_table.item(row,0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None
    def _delete_run(self):
        run_id=self._selected_run_id()
        if not run_id:self.feedback.setText("Select a trial to delete."); return
        if QMessageBox.question(self,"Delete trial","Delete this trial and its scores? This cannot be undone.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.repo.delete_run(run_id); self._load_runs(); self.feedback.setText("Trial deleted. You can record the improved variable set now.")
    def _delete_experiment(self):
        if not self.experiment_id:self.feedback.setText("Open an experiment before deleting it."); return
        if QMessageBox.question(self,"Delete experiment","Delete this experiment, its trials, notes, and presets? This cannot be undone.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.repo.delete_experiment(self.experiment_id); self.experiment_id=None; self.feedback.setText("Experiment deleted."); self.start_button.setEnabled(True); self.record_run_button.setEnabled(False); self.runs_table.setRowCount(0)
    def _add_snapshot(self):
        run_id=self._selected_run_id()
        if not run_id:self.feedback.setText("Select a trial before adding a snapshot."); return
        source,_=QFileDialog.getOpenFileName(self,"Choose trial snapshot","","Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not source:return
        image=QImage(source)
        if image.isNull():self.feedback.setText("That image could not be opened."); return
        folder=Path.cwd()/"laser_snapshots"/self.experiment_id; folder.mkdir(parents=True,exist_ok=True); target=folder/f"{run_id}-{len(list(folder.glob(run_id+'-*.webp')))+1}.webp"
        if not image.save(str(target),"WEBP",90):self.feedback.setText("Could not convert the snapshot to WebP."); return
        experiment=self.repo.get_experiment(self.experiment_id); run=next(item for item in experiment.runs if item.id==run_id); run.results.photo_evidence.append(str(target)); self.repo.update_run(run); self.feedback.setText(f"Snapshot saved as WebP: {target.name}")
    def _export(self):
        if not self.experiment_id:self.feedback.setText("Start or open an experiment before exporting it."); return
        folder=QFileDialog.getExistingDirectory(self,"Choose folder for the shareable experiment block")
        if folder:
            output=Path(folder)/f"{self.objective_input.text().strip() or 'experiment'}.laserblock"
            try: export_experiment(self.repo,self.experiment_id,output); self.feedback.setText(f"Shareable experiment block saved: {output.name}")
            except (OSError,ValueError) as error:self.feedback.setText(str(error))

class ExperimentLibraryPage(QWidget):
    """A dedicated register so experiments are not hidden inside the overview."""
    def __init__(self, repo, open_existing, start):
        super().__init__(); self.repo,self.open_existing,self.start=repo,open_existing,start; layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18)
        header=QHBoxLayout(); labels=QVBoxLayout(); title=QLabel("Experiments"); title.setObjectName("title"); labels.addWidget(title); subtitle=QLabel("Record trials, compare results, then turn the winner into a reusable preset."); subtitle.setObjectName("subtitle"); labels.addWidget(subtitle); header.addLayout(labels); header.addStretch(); add=QPushButton("New experiment"); add.setObjectName("primary"); add.clicked.connect(start); header.addWidget(add); layout.addLayout(header)
        filters=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search objective, material, or process"); self.status=QComboBox(); self.status.addItems(["All statuses","Planned","Active","Concluded"]); filters.addWidget(self.search,stretch=1); filters.addWidget(self.status); layout.addLayout(filters); self.search.textChanged.connect(self.refresh); self.status.currentTextChanged.connect(self.refresh)
        box,inner=card(); self.summary=QLabel(); self.summary.setObjectName("subtitle"); inner.addWidget(self.summary); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Experiment","Objective","Material / process","Trials","Best score","Status"]); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); self.table.cellDoubleClicked.connect(lambda row,_:self.open_existing(self.table.item(row,0).data(Qt.ItemDataRole.UserRole))); inner.addWidget(self.table); layout.addWidget(box,stretch=1); self.refresh()
    def refresh(self):
        query=self.search.text().lower().strip(); requested=self.status.currentText(); experiments=[]
        for experiment in self.repo.list_experiments():
            material=self.repo.get_material(experiment.material_id); process=self.repo.get_process(experiment.process_id); haystack=f"{experiment.objective} {material.name if material else ''} {process.name if process else ''}".lower()
            if query and query not in haystack: continue
            if requested!="All statuses" and experiment.status.value.title()!=requested: continue
            experiments.append((experiment,material,process))
        self.summary.setText(f"{len(experiments)} recorded experiments") ; self.table.setRowCount(0)
        for number,(experiment,material,process) in enumerate(experiments,1):
            row=self.table.rowCount(); self.table.insertRow(row); scores=[DashboardPage._score(run.results) for run in experiment.runs if run.results]; best=max(scores) if scores else None; values=(f"Experiment {number}",experiment.objective,f"{material.name if material else 'Unknown'} / {process.name if process else 'Unknown'}",str(len(experiment.runs)),f"{best:.1f}/10" if best is not None else "Not scored",experiment.status.value.title())
            for column,value in enumerate(values): self.table.setItem(row,column,QTableWidgetItem(value))
            self.table.item(row,0).setData(Qt.ItemDataRole.UserRole,experiment.id)


class PresetLibraryPage(QWidget):
    """Makes established settings discoverable without reopening their experiment."""
    def __init__(self, repo):
        super().__init__(); self.repo=repo; layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18); header=QVBoxLayout(); title=QLabel("Established presets"); title.setObjectName("title"); header.addWidget(title); subtitle=QLabel("Proven parameter sets saved from scored experiment trials."); subtitle.setObjectName("subtitle"); header.addWidget(subtitle); layout.addLayout(header); self.search=QLineEdit(); self.search.setPlaceholderText("Search preset name or parameter values"); self.search.textChanged.connect(self.refresh); layout.addWidget(self.search); box,inner=card(); self.summary=QLabel(); self.summary.setObjectName("subtitle"); inner.addWidget(self.summary); self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["Preset","Source quality","Power","Speed","Passes"]); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); inner.addWidget(self.table); layout.addWidget(box,stretch=1); self.refresh()
    def refresh(self):
        query=self.search.text().lower().strip(); presets=[preset for preset in self.repo.list_presets() if query in f"{preset.name} {preset.settings_snapshot}".lower()]; self.summary.setText(f"{len(presets)} established presets"); self.table.setRowCount(0)
        for preset in presets:
            row=self.table.rowCount(); self.table.insertRow(row); settings=preset.settings_snapshot; values=(preset.name,f"{preset.source_quality:.1f}/10" if preset.source_quality is not None else "—",str(settings.get("power_percent",settings.get("power_w","—"))),str(settings.get("speed_mm_s",settings.get("speed_mm_min","—"))),str(settings.get("passes","—")))
            for column,value in enumerate(values): self.table.setItem(row,column,QTableWidgetItem(value))


class MaterialFormDialog(QDialog):
    """A durable record form: every edit is persisted until Save finalises it."""
    def __init__(self, root, parent=None, draft=None):
        super().__init__(parent); self.root=Path(root); self.setWindowTitle("Record material variables"); self.setMinimumWidth(520); self.image_path=None; self.pending=list((draft or {}).get("batch_profiles",[]))
        layout=QVBoxLayout(self); intro=QLabel("Record a tested variable set"); intro.setObjectName("title"); layout.addWidget(intro); helper=QLabel("This draft remains in Records until you save it into the library."); helper.setObjectName("subtitle"); helper.setWordWrap(True); layout.addWidget(helper)
        form=QFormLayout(); self.name=QLineEdit(); self.name.setPlaceholderText("e.g. Plywood"); self.thickness=QDoubleSpinBox(); self.thickness.setRange(0,500); self.thickness.setValue(3); self.operation=QComboBox(); self.operation.addItems(["Engrave","Cut","Mark","Score"]); self.model=QComboBox(); self.model.addItems(["Floyd","Jarvis","Atkinson","Dithering","Vectorizing","Line to Line","Threshold"]); self.speed=QSpinBox(); self.speed.setRange(1,100000); self.speed.setValue(1200); self.power=QSpinBox(); self.power.setRange(1,100); self.power.setValue(80); self.blur=QSpinBox(); self.blur.setRange(0,100); self.brightness=QSpinBox(); self.brightness.setRange(-100,100); self.contrast=QSpinBox(); self.contrast.setRange(-100,100); self.dither=QLineEdit(); self.dither.setPlaceholderText("Optional method or pattern"); self.passes=QSpinBox(); self.passes.setRange(1,100); self.passes.setValue(1); self.wattage=QLineEdit("Unspecified"); self.notes=QTextEdit(); self.notes.setMinimumHeight(72); self.image_label=QLabel("No result image selected")
        fields=(("Material name *",self.name),("Thickness (mm)",self.thickness),("Operation",self.operation),("Conversion type *",self.model),("Speed (mm/min) *",self.speed),("Power (%) *",self.power),("Blur",self.blur),("Brightness",self.brightness),("Contrast",self.contrast),("Dithering method",self.dither),("Passes",self.passes),("Laser wattage",self.wattage),("Notes",self.notes))
        for label,widget in fields: form.addRow(label,widget)
        layout.addLayout(form); choose=QPushButton("Choose result image"); choose.setObjectName("secondary"); choose.clicked.connect(self._choose_image); image_row=QHBoxLayout(); image_row.addWidget(choose); image_row.addWidget(self.image_label,stretch=1); layout.addLayout(image_row); actions=QHBoxLayout(); self.add_another=QPushButton(); self.add_another.setObjectName("secondary"); self.add_another.clicked.connect(self._queue_current); actions.addWidget(self.add_another); actions.addStretch(); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); actions.addWidget(buttons); layout.addLayout(actions); self._update_queue_label()
        if draft:self._apply_draft(draft)
        for widget in (self.name,self.thickness,self.operation,self.model,self.speed,self.power,self.blur,self.brightness,self.contrast,self.dither,self.passes,self.wattage,self.notes):
            signal=widget.textChanged if isinstance(widget,(QLineEdit,QTextEdit)) else widget.currentTextChanged if isinstance(widget,QComboBox) else widget.valueChanged
            signal.connect(self._save_draft)
    def _choose_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Choose material preview","","Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:self.image_path=Path(path); self.image_label.setText(self.image_path.name); self._save_draft()
    def _apply_draft(self,draft):
        self.name.setText(str(draft.get("material_name",""))); self.thickness.setValue(float(draft.get("thickness_mm",3))); self.operation.setCurrentText(str(draft.get("operation","Engrave"))); self.model.setCurrentText(str(draft.get("conversion_model","Floyd"))); self.speed.setValue(int(draft.get("speed_mm_min",1200))); self.power.setValue(int(draft.get("power_percent",80))); self.blur.setValue(int(draft.get("blur",0))); self.brightness.setValue(int(draft.get("brightness",0))); self.contrast.setValue(int(draft.get("contrast",0))); self.dither.setText(str(draft.get("dithering_method",""))); self.notes.setPlainText(str(draft.get("notes","")))
    def _save_draft(self):
        save_open_record(self.root,{**self.payload(),"batch_profiles":self.pending})
    def _update_queue_label(self):
        self.add_another.setText(f"+ Add another profile ({len(self.pending)} queued)")
    def _queue_current(self):
        profile=self.payload()
        if not profile["material_name"]:
            QMessageBox.information(self,"Material name required","Enter the shared material name before adding another profile."); self.name.setFocus(); return
        self.pending.append(profile); self.model.setCurrentIndex(0); self.speed.setValue(1200); self.power.setValue(80); self.blur.setValue(0); self.brightness.setValue(0); self.contrast.setValue(0); self.dither.clear(); self.notes.clear(); self.image_path=None; self.image_label.setText("No result image selected"); self._update_queue_label(); self._save_draft()
    def payload(self):
        name=self.name.text().strip()
        return {"scope":"user","material_name":name,"thickness_mm":self.thickness.value(),"operation":self.operation.currentText(),"conversion_model":self.model.currentText(),"speed_mm_min":self.speed.value(),"power_percent":self.power.value(),"blur":self.blur.value(),"brightness":self.brightness.value(),"contrast":self.contrast.value(),"dithering_method":self.dither.text().strip(),"passes":self.passes.value(),"laser_wattage":self.wattage.text().strip(),"notes":self.notes.toPlainText().strip()}
    def all_payloads(self):
        return [*self.pending,self.payload()]


class MaterialLibraryPage(QWidget):
    """Searchable browser for material packages; folders are the portable source of truth."""
    def __init__(self, repo, root=None):
        super().__init__(); self.repo,self.vault=repo,vault_path(root); self.packages=[]; layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18)
        header=QHBoxLayout(); title_box=QVBoxLayout(); title=QLabel("Library"); title.setObjectName("title"); title_box.addWidget(title); subtitle=QLabel("Search materials first. Open one to view its tested variable sets."); subtitle.setObjectName("subtitle"); title_box.addWidget(subtitle); header.addLayout(title_box); header.addStretch(); import_button=QPushButton("Import JSON / CSV"); import_button.setObjectName("secondary"); import_button.clicked.connect(self.import_file); header.addWidget(import_button); refresh=QPushButton("Sync vault"); refresh.setObjectName("secondary"); refresh.clicked.connect(self.refresh); header.addWidget(refresh); add=QPushButton("Record variables  +"); add.setToolTip("Record one or more variable profiles for a material"); add.setObjectName("primary"); add.clicked.connect(self.add_package); header.addWidget(add); layout.addLayout(header)
        self.search=QLineEdit(); self.search.setPlaceholderText("Search DB for Materials"); layout.addWidget(self.search); self.search.textChanged.connect(self._render); self.recent_row=QHBoxLayout(); layout.addLayout(self.recent_row)
        box,inner=card(); self.status=QLabel(); self.status.setObjectName("subtitle"); inner.addWidget(self.status); self.material_buttons=QVBoxLayout(); self.material_buttons.setSpacing(8); inner.addLayout(self.material_buttons); inner.addStretch(); layout.addWidget(box,stretch=1); self.refresh()
    def refresh(self):
        # The Library is the published/global view. Personal recordings belong in Records.
        self.packages=[package for package in sync_vault(self.repo,self.vault) if package.data.get("scope", "global") == "global"]; self._render_recent(); self._render()
    def _render_recent(self):
        while self.recent_row.count():
            item=self.recent_row.takeAt(0)
            if item.widget():item.widget().deleteLater()
        recent=QSettings("LaserVariableLibrary","LaserVariableLibrary").value("recent_materials",[],type=list)
        if recent:self.recent_row.addWidget(QLabel("Recently opened:"))
        for name in recent[:5]:
            button=QPushButton(name); button.setObjectName("secondary"); button.clicked.connect(lambda _,value=name:self.open_detail(value)); self.recent_row.addWidget(button)
        self.recent_row.addStretch()
    def _render(self):
        query=self.search.text().lower().strip(); grouped={}
        for package in self.packages:
            name=str(package.data.get("material_name","")).strip();
            if name and (not query or query in name.lower()): grouped.setdefault(name,[]).append(package)
        self.status.setText(f"{len(grouped)} materials · {len(self.packages)} tested variable sets")
        while self.material_buttons.count():
            item=self.material_buttons.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for name,profiles in sorted(grouped.items()):
            button=QPushButton(f"{name}   ·   {len(profiles)} saved presets"); button.setObjectName("secondary"); button.setMinimumHeight(48); button.clicked.connect(lambda _,value=name:self.open_detail(value)); self.material_buttons.addWidget(button)
    def add_package(self):
        dialog=MaterialFormDialog(self.vault.parent,self,load_open_record(self.vault.parent))
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            profiles=dialog.all_payloads()
            if not all(profile["material_name"] for profile in profiles): raise ValueError("Every queued profile needs a material name.")
            for position,profile in enumerate(profiles): write_package(self.vault,profile,dialog.image_path if position==len(profiles)-1 else None)
            clear_open_record(self.vault.parent); sync_vault(self.repo,self.vault); self.refresh(); self.status.setText(f"Saved {len(profiles)} variable sets to the library.")
        except (OSError,ValueError,RepositoryError) as error: QMessageBox.warning(self,"Could not save material",str(error))
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Import material profiles","","Profiles (*.json *.csv)")
        if not path:return
        try:
            added,skipped=import_profiles(self.repo,self.vault,Path(path)); self.refresh(); self.status.setText(f"Imported {added} profiles; skipped {skipped} duplicates or invalid rows.")
        except (OSError,ValueError) as error: QMessageBox.warning(self,"Could not import profiles",str(error))
    def open_detail(self, material_name):
        settings=QSettings("LaserVariableLibrary","LaserVariableLibrary"); recent=[name for name in settings.value("recent_materials",[],type=list) if name!=material_name]; settings.setValue("recent_materials",[material_name,*recent][:5]); self._render_recent()
        profiles=[package for package in self.packages if package.data.get("material_name")==material_name]
        dialog=QDialog(self); dialog.setWindowTitle(str(material_name)); dialog.setMinimumSize(860,460); layout=QVBoxLayout(dialog); heading=QLabel(str(material_name)); heading.setObjectName("title"); layout.addWidget(heading); helper=QLabel("Each row is a saved preset. Select one to edit, export, or delete."); helper.setObjectName("subtitle"); layout.addWidget(helper); table=QTableWidget(0,7); table.setHorizontalHeaderLabels(["Conversion","Preset","Speed","Power","Blur","Brightness","Contrast"]); table.verticalHeader().setVisible(False); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for package in profiles:
            row=table.rowCount(); table.insertRow(row); data=package.data
            for column,key in enumerate(("conversion_model","variant_name","speed_mm_min","power_percent","blur","brightness","contrast")): table.setItem(row,column,QTableWidgetItem(str(data.get(key,"—"))))
            table.item(row,0).setData(Qt.ItemDataRole.UserRole,package)
        layout.addWidget(table); actions=QHBoxLayout(); export=QPushButton("Send variables to LaserGRBL"); export.setObjectName("primary"); export.clicked.connect(lambda:self.export_grbl(table,dialog)); actions.addWidget(export); edit=QPushButton("Edit selected"); edit.setObjectName("secondary"); edit.clicked.connect(lambda:self.edit_profile(table,dialog)); actions.addWidget(edit); remove=QPushButton("Delete selected"); remove.setObjectName("secondary"); remove.clicked.connect(lambda:self.delete_profile(table,dialog)); actions.addWidget(remove); actions.addStretch(); close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(dialog.reject); actions.addWidget(close); layout.addLayout(actions); dialog.exec()
    def export_grbl(self,table,dialog):
        if table.currentRow()<0: QMessageBox.information(dialog,"Choose a version","Select a tested variable set first."); return
        package=table.item(table.currentRow(),0).data(Qt.ItemDataRole.UserRole); target,_=QFileDialog.getSaveFileName(dialog,"Save LaserGRBL settings","lasergrbl_settings.gcode","G-code (*.gcode)")
        if not target:return
        data=package.data; Path(target).write_text(f"; Laser Library: {data['material_name']} / {data['conversion_model']}\n; Speed {data['speed_mm_min']} mm/min, Power {data['power_percent']}%\nM3 S{data['power_percent'] * 10}\nG1 F{data['speed_mm_min']}\n; Import this header/settings into LaserGRBL before running your job.\n",encoding="utf-8"); QMessageBox.information(dialog,"LaserGRBL file saved",f"Saved {Path(target).name}. Review it in LaserGRBL before sending it to your machine.")
    def edit_profile(self,table,parent):
        if table.currentRow()<0: QMessageBox.information(parent,"Choose a profile","Select a variable set to edit."); return
        package=table.item(table.currentRow(),0).data(Qt.ItemDataRole.UserRole); editor=MaterialFormDialog(self.vault.parent,parent,package.data)
        if editor.exec()!=QDialog.DialogCode.Accepted:return
        try:
            payload=editor.payload(); payload["scope"]=package.data.get("scope", "global")
            update_package(package,payload,editor.image_path); self.refresh(); parent.accept()
        except (OSError,ValueError) as error: QMessageBox.warning(parent,"Could not update profile",str(error))
    def delete_profile(self,table,parent):
        if table.currentRow()<0: QMessageBox.information(parent,"Choose a profile","Select a variable set to delete."); return
        package=table.item(table.currentRow(),0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(parent,"Delete profile",f"Delete {package.data.get('material_name')} / {package.data.get('conversion_model')}? This removes its portable folder.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try: delete_package(package); self.refresh(); parent.accept()
        except OSError as error: QMessageBox.warning(parent,"Could not delete profile",str(error))


class ExperimentPage(QWidget):
    """Persistent A/B/C tests. A row captures every print parameter at its creation."""
    TOOLS=("Line To Line Tracing","1bit B/W Dithering","Vectorize!","Centerline","Passthrough")
    def __init__(self, repo, root):
        super().__init__(); self.repo,self.root=repo,Path(root); self.vault=vault_path(self.root); self.session_id=str(uuid4())
        layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18)
        title=QLabel("Experiments"); title.setObjectName("title"); layout.addWidget(title)
        subtitle=QLabel("Each A/B/C row keeps its full pre-print image and conversion settings. Batches remain open until you publish a winner or clear them."); subtitle.setObjectName("subtitle"); subtitle.setWordWrap(True); layout.addWidget(subtitle)
        form=QFormLayout(); self.profile=QComboBox(); self.material=QLineEdit(); self.material.setPlaceholderText("Type a material to start a new experiment"); self.speed=QSpinBox(); self.speed.setRange(1,100000); self.speed.setValue(1200); self.power=QSpinBox(); self.power.setRange(1,100); self.power.setValue(80); self.notes=QTextEdit(); self.notes.setMinimumHeight(60)
        form.addRow("Start from global Library (optional)",self.profile); form.addRow("Material name *",self.material); form.addRow("Test speed (mm/min)",self.speed); form.addRow("Test power (%)",self.power); layout.addLayout(form)
        image_box,image_layout=card(); image_title=QLabel("Image parameters"); image_title.setObjectName("section"); image_layout.addWidget(image_title); image_form=QFormLayout(); self.resize=QComboBox(); self.resize.addItems(["Smooth (HQ Bicubic)","Nearest neighbour","Bilinear"]); self.grayscale=QComboBox(); self.grayscale.addItems(["Weighted Average","Simple Average","Luminance"]); self.brightness=QSlider(Qt.Orientation.Horizontal); self.brightness.setRange(-100,100); self.contrast=QSlider(Qt.Orientation.Horizontal); self.contrast.setRange(-100,100); self.white_clip=QSlider(Qt.Orientation.Horizontal); self.white_clip.setRange(0,100); self.black_white=QCheckBox("B&W"); image_form.addRow("Resize",self.resize); image_form.addRow("Grayscale",self.grayscale); image_form.addRow("Brightness",self.brightness); image_form.addRow("Contrast",self.contrast); image_form.addRow("White clip",self.white_clip); image_form.addRow("",self.black_white); image_layout.addLayout(image_form); layout.addWidget(image_box)
        tool_box,tool_layout=card(); tool_title=QLabel("Conversion tool"); tool_title.setObjectName("section"); tool_layout.addWidget(tool_title); self.conversion=QComboBox(); self.conversion.addItems(self.TOOLS); tool_layout.addWidget(self.conversion); self.tool_options=QFrame(); self.tool_form=QFormLayout(self.tool_options); self.direction=QComboBox(); self.direction.addItems(["Horizontal","Vertical","Diagonal"]); self.quality=QDoubleSpinBox(); self.quality.setRange(.1,100); self.quality.setValue(15); self.line_preview=QCheckBox("Line preview"); self.line_preview.setChecked(True); self.dither_method=QComboBox(); self.dither_method.addItems(["Floyd-Steinberg","Jarvis","Atkinson","Stucki"]); self.tool_form.addRow("Direction",self.direction); self.tool_form.addRow("Quality (lines/mm)",self.quality); self.tool_form.addRow("",self.line_preview); self.tool_form.addRow("Dithering method",self.dither_method); tool_layout.addWidget(self.tool_options); layout.addWidget(tool_box)
        form.addRow("Test notes / result",self.notes); layout.addLayout(form)
        actions=QHBoxLayout(); add=QPushButton("+ Add test row"); add.setObjectName("secondary"); add.clicked.connect(self.add_test); actions.addWidget(add); copy=QPushButton("Copy selected values"); copy.setObjectName("secondary"); copy.clicked.connect(self.copy_selected); actions.addWidget(copy); save=QPushButton("Name and publish selected winner"); save.setObjectName("primary"); save.clicked.connect(self.save_preset); actions.addWidget(save); clear=QPushButton("Clear this batch"); clear.setObjectName("secondary"); clear.clicked.connect(self.clear_batch); actions.addWidget(clear); actions.addStretch(); layout.addLayout(actions)
        self.tests=QTableWidget(0,7); self.tests.setHorizontalHeaderLabels(["Tag","Material","Conversion","Speed","Power","Parameter summary","Result / comparison"]); self.tests.verticalHeader().setVisible(False); self.tests.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.tests.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked|QTableWidget.EditTrigger.SelectedClicked); self.tests.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.tests.itemChanged.connect(self._save_batch); layout.addWidget(self.tests,stretch=1)
        self.status=QLabel(); self.status.setObjectName("subtitle"); layout.addWidget(self.status); self.profile.currentIndexChanged.connect(self._load_profile); self.conversion.currentTextChanged.connect(self._tool_changed); self._tool_changed(self.conversion.currentText()); self.refresh(); self._restore_latest_batch()
    def refresh(self):
        self.packages=[package for package in scan_packages(self.vault) if package.data.get("scope", "global")=="global"]; current=self.profile.currentData(); self.profile.blockSignals(True); self.profile.clear(); self.profile.addItem("Choose a global material preset",None)
        for package in self.packages:
            data=package.data; self.profile.addItem(f"{data.get('material_name')} / {data.get('conversion_model')} / {data.get('variant_name','Base')}",package)
        index=self.profile.findData(current); self.profile.setCurrentIndex(index if index>=0 else 0); self.profile.blockSignals(False)
    def _tool_changed(self, tool):
        line=tool=="Line To Line Tracing"; dither=tool=="1bit B/W Dithering"
        for row in range(3): self.tool_form.setRowVisible(row,line)
        self.tool_form.setRowVisible(3,dither)
    def _parameters(self):
        tool=self.conversion.currentText(); data={"resize":self.resize.currentText(),"grayscale":self.grayscale.currentText(),"brightness":self.brightness.value(),"contrast":self.contrast.value(),"white_clip":self.white_clip.value(),"black_white":self.black_white.isChecked(),"conversion_model":tool,"speed_mm_min":self.speed.value(),"power_percent":self.power.value()}
        if tool=="Line To Line Tracing": data.update({"direction":self.direction.currentText(),"quality_lines_mm":self.quality.value(),"line_preview":self.line_preview.isChecked()})
        if tool=="1bit B/W Dithering": data["dithering_method"]=self.dither_method.currentText()
        return data
    def _summary(self, data):
        if data["conversion_model"]=="Line To Line Tracing": return f"{data.get('direction')} · {data.get('quality_lines_mm')} lines/mm"
        if data["conversion_model"]=="1bit B/W Dithering": return data.get("dithering_method", "Dithering")
        return f"{data['resize']} · {data['grayscale']}"
    def _load_profile(self):
        package=self.profile.currentData()
        if not package:return
        data=package.data; self.material.setText(str(data.get("material_name",""))); tool=str(data.get("conversion_model","")); self.conversion.setCurrentText(tool if tool in self.TOOLS else "1bit B/W Dithering" if tool in ("Floyd","Jarvis","Atkinson","Dithering") else "Line To Line Tracing"); self.speed.setValue(int(data.get("speed_mm_min",1200))); self.power.setValue(int(data.get("power_percent",80))); self.resize.setCurrentText(str(data.get("resize",self.resize.currentText()))); self.grayscale.setCurrentText(str(data.get("grayscale",self.grayscale.currentText()))); self.brightness.setValue(int(data.get("brightness",0))); self.contrast.setValue(int(data.get("contrast",0))); self.white_clip.setValue(int(data.get("white_clip",0))); self.black_white.setChecked(bool(data.get("black_white",False))); self.direction.setCurrentText(str(data.get("direction","Horizontal"))); self.quality.setValue(float(data.get("quality_lines_mm",15))); self.line_preview.setChecked(bool(data.get("line_preview",True))); self.dither_method.setCurrentText(str(data.get("dithering_method","Floyd-Steinberg")))
    def _batch_rows(self):
        rows=[]
        for row in range(self.tests.rowCount()):
            stored=self.tests.item(row,0).data(Qt.ItemDataRole.UserRole) or {}
            params=dict(stored.get("parameters",{})); params.update({"tag":self.tests.item(row,0).text(),"material_name":self.tests.item(row,1).text(),"conversion_model":self.tests.item(row,2).text(),"speed_mm_min":int(self.tests.item(row,3).text()),"power_percent":int(self.tests.item(row,4).text()),"notes":self.tests.item(row,6).text()})
            rows.append(params)
        return rows
    def _save_batch(self, *_):
        if not hasattr(self,"tests"): return
        rows=self._batch_rows()
        if rows: save_experiment_draft(self.root,{"id":self.session_id,"material_name":self.material.text().strip() or rows[0]["material_name"],"rows":rows})
    def _restore_latest_batch(self):
        drafts=load_experiment_drafts(self.root)
        if not drafts:return
        draft=drafts[0]; rows=draft.get("rows",[])
        if not rows:return
        self.session_id=str(draft.get("id",self.session_id)); self.material.setText(str(draft.get("material_name",rows[0].get("material_name",""))))
        self.tests.blockSignals(True)
        for data in rows: self._insert_row(data)
        self.tests.blockSignals(False); self.status.setText(f"Restored open batch with {len(rows)} test rows.")
    def _insert_row(self, data):
        row=self.tests.rowCount(); self.tests.insertRow(row); values=(data.get("tag",chr(65+row)),data.get("material_name",""),data.get("conversion_model",""),data.get("speed_mm_min",0),data.get("power_percent",0),self._summary(data),data.get("notes",""))
        for column,value in enumerate(values): self.tests.setItem(row,column,QTableWidgetItem(str(value)))
        self.tests.item(row,0).setData(Qt.ItemDataRole.UserRole,{"parameters":dict(data)})
    def add_test(self):
        material=self.material.text().strip()
        if not material:self.status.setText("Enter a material name first."); return
        data=self._parameters(); data.update({"tag":chr(65+self.tests.rowCount()),"material_name":material,"notes":self.notes.toPlainText().strip()}); self._insert_row(data); self.tests.setCurrentCell(self.tests.rowCount()-1,0); self._save_batch(); self.status.setText(f"Added Experiment {data['tag']} with its complete print parameters.")
    def save_preset(self):
        row=self.tests.currentRow()
        if row<0:self.status.setText("Add and select a test row to publish."); return
        stored=self.tests.item(row,0).data(Qt.ItemDataRole.UserRole) or {}; data=dict(stored.get("parameters",{})); data.update({"scope":"global","material_name":self.tests.item(row,1).text().strip(),"conversion_model":self.tests.item(row,2).text().strip(),"speed_mm_min":int(self.tests.item(row,3).text()),"power_percent":int(self.tests.item(row,4).text()),"notes":self.tests.item(row,6).text()})
        name,ok=QInputDialog.getText(self,"Name winning preset","Preset name (for example: Dark, Light, Fine Detail):"); name=name.strip()
        if not ok:return
        if not data["material_name"] or not data["conversion_model"] or not name:self.status.setText("Every published test needs material, conversion type, and a preset name."); return
        data["variant_name"]=name
        try:
            existing=find_profile(self.vault,data["material_name"],data["conversion_model"],name)
            if existing and QMessageBox.question(self,"Overwrite global preset?",f"{data['material_name']} / {data['conversion_model']} / {name} already exists. Replace it with this experiment?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            if existing:update_package(existing,data)
            else:write_package(self.vault,data)
            sync_vault(self.repo,self.vault); self.status.setText(f"Published {data['material_name']} / {data['conversion_model']} / {name} to the global Library."); self.refresh()
        except (OSError,ValueError,RepositoryError) as error:self.status.setText(str(error))
    def clear_batch(self):
        if self.tests.rowCount() and QMessageBox.question(self,"Clear open batch?","Remove this unfinished experiment batch? Published presets will not be deleted.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        clear_experiment_draft(self.root,self.session_id); self.tests.setRowCount(0); self.session_id=str(uuid4()); self.status.setText("Open experiment batch cleared.")
    def copy_selected(self):
        row=self.tests.currentRow()
        if row<0:self.status.setText("Select a test row to copy."); return
        data=(self.tests.item(row,0).data(Qt.ItemDataRole.UserRole) or {}).get("parameters",{}); text=" | ".join(f"{key}={value}" for key,value in data.items()); QApplication.clipboard().setText(text); self.status.setText("Complete selected test parameters copied.")


class RecordsPage(QWidget):
    """Persistent incomplete-record queue; no in-progress variables silently disappear."""
    def __init__(self, root, continue_record):
        super().__init__(); self.root,self.continue_record=Path(root),continue_record; self.vault=vault_path(self.root); layout=QVBoxLayout(self); layout.setContentsMargins(36,32,36,32); layout.setSpacing(18); title=QLabel("Records"); title.setObjectName("title"); layout.addWidget(title); self.message=QLabel(); self.message.setObjectName("subtitle"); self.message.setWordWrap(True); layout.addWidget(self.message); self.continue_button=QPushButton("Continue open record"); self.continue_button.setObjectName("primary"); self.continue_button.clicked.connect(continue_record); layout.addWidget(self.continue_button,alignment=Qt.AlignmentFlag.AlignLeft); self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Your material","Conversion","Speed","Power"]); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); layout.addWidget(self.table,stretch=1); self.refresh()
    def refresh(self):
        draft=load_open_record(self.root); exists=bool(draft and draft.get("material_name")); self.continue_button.setEnabled(exists); profiles=[package for package in scan_packages(self.vault) if package.data.get("scope")=="user"]; self.message.setText(f"Unfinished record for {draft.get('material_name')}. Continue it or save it to finalise the material profile." if exists else f"{len(profiles)} of your saved value records."); self.table.setRowCount(0)
        for package in profiles:
            row=self.table.rowCount(); self.table.insertRow(row); data=package.data
            for column,key in enumerate(("material_name","conversion_model","speed_mm_min","power_percent")):self.table.setItem(row,column,QTableWidgetItem(str(data.get(key,"—"))))


class MainWindow(QMainWindow):
    def __init__(self,repo=None):
        super().__init__(); self.setWindowTitle("Laser Variable Library"); self.setMinimumSize(680,500); self.resize(1180,760); shell=QWidget(); root=QHBoxLayout(shell); root.setContentsMargins(0,0,0,0); root.setSpacing(0); sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setMinimumWidth(150); sidebar.setMaximumWidth(220); side=QVBoxLayout(sidebar); side.setContentsMargins(18,24,18,24); brand=QLabel("Laser Material Library"); brand.setObjectName("brand"); brand.setWordWrap(True); side.addWidget(brand); sub=QLabel("Offline tested-variable database"); sub.setObjectName("muted"); side.addWidget(sub); side.addSpacing(28); self.library_button=QPushButton("Library"); self.record_button=QPushButton("Records"); self.experiment_button=QPushButton("Experiments"); self.material_button=self.library_button
        for button in (self.library_button,self.record_button,self.experiment_button):button.setObjectName("nav");button.setCheckable(True);side.addWidget(button)
        side.addStretch(); local=QLabel("LOCAL MODE\nYour data stays on this computer."); local.setObjectName("muted"); side.addWidget(local); root.addWidget(sidebar)
        if repo is None:database=DatabaseManager("sqlite:///:memory:");database.initialize();repo=SQLiteRepository(database)
        self.repo=repo;self.pages=QStackedWidget();self.materials=MaterialLibraryPage(repo);self.records=RecordsPage(Path.cwd(),self.continue_record);self.experiments=ExperimentPage(repo,Path.cwd());self.pages.addWidget(self._scrollable(self.materials));self.pages.addWidget(self._scrollable(self.records));self.pages.addWidget(self._scrollable(self.experiments));root.addWidget(self.pages,stretch=1);self.setCentralWidget(shell);self.library_button.clicked.connect(self.show_materials);self.record_button.clicked.connect(self.show_records);self.experiment_button.clicked.connect(self.show_experiments);self.show_materials(); draft=load_open_record(Path.cwd())
        if draft and draft.get("material_name") and QMessageBox.question(self,"Unfinished record",f"You have an unfinished record for {draft['material_name']}. Continue it?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.continue_record()
    def _scrollable(self,widget):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(widget); return scroll
    def show_materials(self):self.materials.refresh();self.pages.setCurrentIndex(0);self.library_button.setChecked(True);self.record_button.setChecked(False);self.experiment_button.setChecked(False)
    def show_records(self):self.records.refresh();self.pages.setCurrentIndex(1);self.library_button.setChecked(False);self.record_button.setChecked(True);self.experiment_button.setChecked(False)
    def show_experiments(self):self.experiments.refresh();self.pages.setCurrentIndex(2);self.library_button.setChecked(False);self.record_button.setChecked(False);self.experiment_button.setChecked(True)
    def continue_record(self):self.show_materials();self.materials.add_package()
    def import_block(self):
        path,_=QFileDialog.getOpenFileName(self,"Open shared experiment block","","Laser experiment blocks (*.laserblock)")
        if path:
            try:self.open_existing(import_experiment(self.repo,Path(path)).id)
            except (OSError,ValueError,RepositoryError) as error:self.workspace.feedback.setText(f"Could not open block: {error}")

def create_main_window(repo=None):
    if QApplication.instance() is None:QApplication([])
    QApplication.instance().setStyleSheet(STYLE);return MainWindow(repo)

"""Sugerencias explícitas: completar un concepto no registra ni paga un gasto."""
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QStandardItemModel,QStandardItem
from PySide6.QtWidgets import QLineEdit,QCompleter
from .completion import enable_unique_tab
from ..storage import StorageError


class ExpenseConceptEdit(QLineEdit):
    concept_selected=Signal(int)
    lookup_failed=Signal(str)

    def __init__(self,repository,parent=None):
        super().__init__(parent);self.repository=repository;self.rows=[]
        self.model=QStandardItemModel(self)
        self.suggestions=QCompleter(self.model,self)
        self.suggestions.setWidget(self)
        self.suggestions.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.suggestions.setMaxVisibleItems(6)
        self.suggestions.activated[str].connect(self._choose)
        enable_unique_tab(self,self.suggestions)
        self.textEdited.connect(self._suggest)
        self.setToolTip('Escribe al menos 3 caracteres. Elige una sugerencia para recuperar el concepto y su categoría.')

    def _suggest(self,text):
        try:self.rows=self.repository.concept_suggestions(text)
        except StorageError as error:
            self.rows=[];self.lookup_failed.emit(str(error))
        self.model.clear()
        for row in self.rows:
            item=QStandardItem(row['concept']);item.setToolTip('Categoría: '+row['category']);self.model.appendRow(item)
        if not self.rows:self.suggestions.popup().hide();return
        self.suggestions.setCompletionPrefix('')
        self.suggestions.complete()
        self.suggestions.popup().setCurrentIndex(self.suggestions.completionModel().index(0,0))

    def _choose(self,text):
        row=next((r for r in self.rows if r['concept']==text),None)
        if row is None:return
        self.setText(row['concept']);self.concept_selected.emit(row['category_id'])
        self.suggestions.popup().hide()

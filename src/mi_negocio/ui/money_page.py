"""Money dashboard, real movements and account opening balances."""
from datetime import date
import json
from pathlib import Path
from PySide6.QtCore import Signal,Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QTabWidget,QComboBox,QLineEdit,QPushButton,QTableWidgetItem,QScrollArea,QDialog,QTextEdit,QFileDialog,QMessageBox
from ..credit_cards import CreditCardsRepository
from ..storage import StorageError
from ..catalog import ValidationError
from ..expenses import comparison_period
from .sales_widgets import note,error_text
from .style import format_cop
from .expenses_page import card,change_text
from .expense_filters import ExpensePeriod
from .loans_page import table
from .money_dialogs import MoneyEntryDialog,OpeningDialog,AccountDialog
from .credit_card_dialogs import CardDetailDialog
from .money_chart import MoneyChart
from .money_report import build_money_report,write_money_pdf
from .form_validation import required_reason

class MoneyPage(QWidget):
    changed=Signal();open_source=Signal(str,int);open_settings=Signal()
    def __init__(self,repository,parent=None):
        super().__init__(parent);self.repository=repository;self.cards=CreditCardsRepository(repository.connection);self.rows=[];self.accounts=[]
        root=QVBoxLayout(self);root.setContentsMargins(28,20,28,18);root.setSpacing(12)
        heading=QHBoxLayout();heading.addWidget(note('Dinero','heading'));heading.addWidget(note('Tu dinero disponible y tus compromisos.'),1)
        transfer=QPushButton('Transferir');transfer.clicked.connect(lambda:self.new_entry('transfer'));heading.addWidget(transfer)
        self.new_button=QPushButton('+ Registrar movimiento');self.new_button.setObjectName('primary');self.new_button.clicked.connect(lambda:self.new_entry());heading.addWidget(self.new_button);root.addLayout(heading)
        filters=QHBoxLayout();self.period=ExpensePeriod();self.period.popup.setWindowTitle('Período de movimientos');self.account_filter=QComboBox()
        filters.addWidget(self.period);filters.addWidget(self.account_filter);filters.addStretch();root.addLayout(filters)
        self.error=note('','error');self.error.hide();root.addWidget(self.error)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.NoFrame);summary=QWidget();summary.setObjectName('moneySummary');summary.setStyleSheet('QWidget#moneySummary { background: #f5f7fb; }');box=QVBoxLayout(summary);box.setSpacing(14);scroll.setWidget(summary);self.tabs.addTab(scroll,'Resumen')
        metrics=QGridLayout();self.metric_labels=[]
        for i,title in enumerate(('DISPONIBLE HOY','ENTRADAS DEL PERÍODO','SALIDAS DEL PERÍODO','FLUJO NETO')):
            frame,content=card(title);label=note('—','sectionValue');label.setStyleSheet('font-size: 22px; font-weight: 700;');content.addWidget(label);metrics.addWidget(frame,0,i);self.metric_labels.append(label)
        box.addLayout(metrics);self.warning=note('');box.addWidget(self.warning)
        self.configure_balances=QPushButton('Configurar saldos iniciales →');self.configure_balances.clicked.connect(lambda:self.tabs.setCurrentIndex(2));box.addWidget(self.configure_balances)
        middle=QHBoxLayout();frame,content=card('Flujo de caja neto');self.grouping=QComboBox();self.grouping.addItems(['Semanas','Meses']);content.addWidget(self.grouping);self.chart=MoneyChart();content.addWidget(self.chart);self.comparison=note('');content.addWidget(self.comparison);content.addWidget(note('Cobros y pagos reales; no representa utilidad.'));middle.addWidget(frame,3)
        frame,content=card('Tarjetas de crédito');self.debt=note('—','sectionValue');content.addWidget(self.debt);self.card_info=note('');content.addWidget(self.card_info);self.card_picker=QComboBox();content.addWidget(self.card_picker)
        actions=QHBoxLayout();self.review=QPushButton('Revisar tarjeta');self.pay=QPushButton('Pagar');self.pay.setObjectName('primary');actions.addWidget(self.review);actions.addWidget(self.pay);content.addLayout(actions);settings=QPushButton('Configurar tarjetas');settings.setObjectName('quietAction');content.addWidget(settings);content.addStretch();middle.addWidget(frame,2);box.addLayout(middle)
        bottom=QHBoxLayout();frame,content=card('Tus cuentas');self.account_summary=note('');content.addWidget(self.account_summary);link=QPushButton('Ver cuentas →');link.clicked.connect(lambda:self.tabs.setCurrentIndex(2));content.addWidget(link);bottom.addWidget(frame,1)
        frame,content=card('Por revisar');self.notices=note('');content.addWidget(self.notices);content.addStretch();bottom.addWidget(frame,1);box.addLayout(bottom);box.addStretch()
        movements=QWidget();m=QVBoxLayout(movements);self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Buscar concepto o cuenta…');search_row=QHBoxLayout();search_row.addWidget(self.search,1);self.export_button=QPushButton('Exportar PDF');self.export_button.clicked.connect(self.export_pdf);search_row.addWidget(self.export_button);m.addLayout(search_row)
        self.export_status=note('');self.export_status.hide();m.addWidget(self.export_status)
        self.movements_table=table(['Fecha','Concepto','Cuenta','Entrada · COP','Salida · COP']);m.addWidget(self.movements_table,1)
        row=QHBoxLayout();self.filtered=note('');row.addWidget(self.filtered,1);self.view_button=QPushButton('Ver origen / detalle');self.cancel_button=QPushButton('Anular movimiento');self.cancel_button.setObjectName('removeAction');row.addWidget(self.view_button);row.addWidget(self.cancel_button);m.addLayout(row);self.tabs.addTab(movements,'Movimientos')
        accounts=QWidget();a=QVBoxLayout(accounts);a.addWidget(note('Para calcular tu dinero, configura el saldo inicial de cada cuenta: cuánto había al comienzo de la fecha elegida (puede ser cero). Haz doble clic en la cuenta para configurarlo. Las tarjetas se muestran como deuda, separadas del disponible.'))
        self.accounts_table=table(['Cuenta','Tipo','Inicio','Saldo inicial · COP','Saldo actual / deuda · COP','Saldo al cierre · COP']);a.addWidget(self.accounts_table,1)
        row=QHBoxLayout();new=QPushButton('+ Nueva cuenta');opening=QPushButton('Configurar saldo inicial');history=QPushButton('Historial');setting_accounts=QPushButton('Editar cuentas en Configuración');row.addWidget(new);row.addWidget(opening);row.addWidget(history);row.addWidget(setting_accounts);a.addLayout(row);self.tabs.addTab(accounts,'Cuentas')
        self.accounts_table.cellDoubleClicked.connect(self.open_account_balance)
        new.clicked.connect(self.new_account);opening.clicked.connect(self.opening);history.clicked.connect(self.account_history);setting_accounts.clicked.connect(self.open_settings.emit)
        self.review.clicked.connect(self.review_card);self.pay.clicked.connect(self.pay_card);settings.clicked.connect(self.open_settings.emit)
        self.view_button.clicked.connect(self.view_source);self.movements_table.cellDoubleClicked.connect(lambda *_:self.view_source());self.cancel_button.clicked.connect(self.cancel_entry)
        self.period.changed.connect(self.refresh);self.account_filter.currentIndexChanged.connect(self.refresh);self.grouping.currentIndexChanged.connect(self.refresh);self.search.textChanged.connect(self.refresh)
        self.timer=QTimer(self);self.timer.setInterval(60000);self.timer.timeout.connect(self.refresh_if_visible);self.timer.start();self.refresh()
    def export_pdf(self):
        self.export_status.hide()
        try:
            start,end,_=self.period.period()
            if start>end:raise ValueError('Revisa el rango de fechas.')
            account=self.account_filter.currentData()
            rows=self.repository.movements(start,end,account,self.search.text())
            html=build_money_report(rows,start,end,self.account_filter.currentText(),self.search.text(),account)
            path,_=QFileDialog.getSaveFileName(self,'Exportar movimientos a PDF',
                f'Nimbo-movimientos-{start}-{end}.pdf','Documento PDF (*.pdf)')
            if not path:return
            if not path.lower().endswith('.pdf'):
                path+='.pdf'
                # The native dialog only confirmed the originally entered name.
                if Path(path).exists() and QMessageBox.question(self,'Reemplazar informe',
                    'Ya existe este PDF. ¿Quieres reemplazarlo?',QMessageBox.Yes|QMessageBox.No,
                    QMessageBox.No)!=QMessageBox.Yes:return
            write_money_pdf(path,html)
            self.error.clear();self.error.hide()
            self.export_status.setText('PDF guardado en: '+path);self.export_status.show()
        except (StorageError,ValidationError,OSError,ValueError,RuntimeError) as exc:
            self.error.setText(error_text(exc));self.error.show()

    def refresh_if_visible(self):
        if self.isVisible():self.refresh()
    def refresh(self,*_):
        try:
            selected=self.account_filter.currentData();self.accounts=self.repository.balances();self.account_filter.blockSignals(True);self.account_filter.clear();self.account_filter.addItem('Todas las cuentas',None)
            for a in self.accounts:self.account_filter.addItem(a['name']+(' · Tarjeta' if a['is_card'] else ''),a['id'])
            self.account_filter.setCurrentIndex(max(0,self.account_filter.findData(selected)));self.account_filter.blockSignals(False)
            start,end,monthly=self.period.period();account=self.account_filter.currentData();result=self.repository.summary(start,end,account)
            for label,value in zip(self.metric_labels,(result['available'],result['incoming'],result['outgoing'],result['net'])):label.setText(format_cop(value))
            if result['missing'] and not any(a['configured'] for a in result['balances'] if not a['is_card'] and (account is None or a['id']==account)):
                self.metric_labels[0].setText('Sin configurar')
            if account is not None and any(a['id']==account and a['is_card'] for a in self.accounts):self.metric_labels[0].setText('Cuenta de crédito')
            if account == -1:self.metric_labels[0].setText('No disponible · retenciones')
            self.metric_labels[3].setStyleSheet('font-size:22px;font-weight:700;color:'+('#168454' if result['net']>=0 else '#c63745')+';')
            self.warning.setText(('Saldo parcial: '+str(result['missing'])+' cuenta(s) sin saldo inicial. ' if result['missing'] else '')+(f"{result['unassigned']} pagos sin cuenta asignada: no se incluyen en el flujo. " if result['unassigned'] else '')+'Disponible hoy no cambia con el filtro de fechas.')
            self.configure_balances.setVisible(bool(result['missing']))
            self.warning.setStyleSheet('color:#875500;background:#fff3d6;padding:10px;border-radius:6px;' if result['missing'] else '')
            self.warning.setToolTip('Configura el saldo inicial de cada cuenta en Dinero → Cuentas. Indica cuánto había al comienzo de la fecha elegida; puede ser cero. Las cuentas sin configurar no se incluyen en el disponible.')
            self.chart.set_rows(result['flow'],start,end,self.grouping.currentIndex()==1)
            ps,pe=comparison_period(start,end,monthly);previous=self.repository.summary(ps,pe,account)
            self.comparison.setText(f"Entradas: {change_text(result['incoming'],previous['incoming'])} · Salidas: {change_text(result['outgoing'],previous['outgoing'])}\nComparación: {ps:%d/%m/%Y} – {pe:%d/%m/%Y}")
            cards=self.cards.list_cards();old=self.card_picker.currentData();self.card_picker.clear()
            for c in cards:self.card_picker.addItem(c['name'],c['id'])
            self.card_picker.setCurrentIndex(max(0,self.card_picker.findData(old)))
            debts=[self.cards.debt(c['id']) for c in cards];known=[d['total_cents'] for d in debts if d['configured']]
            self.debt.setText(format_cop(sum(known)) if known else 'Sin deuda inicial configurada')
            provisional=any(d['provisional'] for d in debts)
            if known and len(known)<len(debts):self.debt.setText(self.debt.text()+' · parcial')
            self.card_info.setText(('Saldo provisional · pueden faltar intereses o cargos.' if provisional else 'Períodos al día conciliados.') if cards else 'Control opcional desde Configuración.');self.card_info.setStyleSheet('color:#9c6100;' if provisional else '')
            self.review.setEnabled(bool(cards));self.pay.setEnabled(bool(cards) and self.cards.enabled())
            self.account_summary.setText('\n'.join(a['name']+' · '+(format_cop(a['balance_cents']) if a['configured'] else 'Configurar saldo inicial') for a in self.accounts if not a['is_card']) or 'Agrega tus cuentas.')
            notices=[n['text'] for n in self.cards.reminders()]
            if provisional and not notices:notices.append('Hay tarjetas pendientes de conciliación. Revisa los extractos cuando estén disponibles.')
            if cards and not self.cards.enabled():notices.insert(0,'Control de tarjetas desactivado; se conserva la deuda y el historial.')
            self.notices.setText('\n\n'.join(notices) or 'No hay avisos pendientes.');self.notices.setStyleSheet('color:#9c6100;')
            self.rows=self.repository.movements(start,end,account,self.search.text());self.movements_table.setRowCount(len(self.rows))
            for i,r in enumerate(self.rows):
                for j,text in enumerate((r['date'],r['concept']+(' · Crédito' if r['is_card'] else ''),r['account'],format_cop(r['delta']) if r['delta']>0 else '—',format_cop(-r['delta']) if r['delta']<0 else '—')):
                    item=QTableWidgetItem(text);item.setToolTip(r['detail']);self.movements_table.setItem(i,j,item)
            filtered_in = sum(max(0,r['delta']) for r in self.rows)
            filtered_out = sum(max(0,-r['delta']) for r in self.rows)
            self.filtered.setText(f'{len(self.rows)} movimientos · Entradas: {format_cop(filtered_in)} · Salidas: {format_cop(filtered_out)}\nIncluye transferencias, crédito y retenciones; el resumen muestra solo flujo de efectivo/bancos.')
            self.accounts_table.setRowCount(len(self.accounts))
            closing = {a['id']: a for a in result['closing']}
            self.accounts_table.setHorizontalHeaderItem(5, QTableWidgetItem(f'Cierre {end:%d/%m/%Y} · COP'))
            for i,a in enumerate(self.accounts):
                current='Sin configurar' if not a['configured'] else format_cop(-a['balance_cents'] if a['is_card'] else a['balance_cents'])
                closed = closing[a['id']]
                closing_text = format_cop(-closed['balance_cents'] if a['is_card'] else closed['balance_cents']) if closed['configured'] else 'Sin configurar'
                for j,text in enumerate((a['name'],'Tarjeta · deuda' if a['is_card'] else 'Efectivo' if a['kind']=='cash' else 'Retención · no disponible' if a['kind']=='withholding' else 'Banco / billetera','Automático' if a['kind']=='withholding' else a['opened_on'] or 'Por configurar',format_cop(abs(a['opening_cents']) if a['is_card'] else a['opening_cents']) if a['opening_cents'] is not None else '—',current,closing_text)):
                    item=QTableWidgetItem(text)
                    if not a['configured']:
                        item.setBackground(QColor('#fff3d6'));item.setForeground(QColor('#875500'))
                        item.setToolTip('Falta configurar el saldo inicial para calcular el dinero de esta cuenta. Haz doble clic en esta fila o pulsa Configurar saldo inicial. Indica el saldo al comienzo del día elegido; puede ser cero.' if not a['opened_on'] else 'La fecha de inicio de esta cuenta es futura. Su saldo aún no se incluye. Haz doble clic para revisar el saldo inicial y la fecha.')
                    elif j==5 and not closed['configured']:
                        item.setToolTip('La fecha de cierre es anterior al saldo inicial de esta cuenta.')
                    self.accounts_table.setItem(i,j,item)
            self.error.clear();self.error.hide()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e));self.error.show()
    def watch(self,dialog,signal='saved'):
        self.dialog=dialog;getattr(dialog,signal).connect(self.updated);dialog.show()
    def updated(self):self.refresh();self.changed.emit()
    def new_entry(self,kind='contribution',card_account=None,purchase_id=None):self.watch(MoneyEntryDialog(self.repository,self,kind,card_account,purchase_id))
    def new_account(self):self.watch(AccountDialog(self.repository.connection,self))
    def open_account_balance(self,row,column):
        if 0<=row<len(self.accounts) and self.accounts[row]['kind']!='withholding':
            self.accounts_table.setCurrentCell(row,column)
            self.opening()

    def opening(self):
        row=self.accounts_table.currentRow()
        if row<0:self.error.setText('Selecciona una cuenta para configurar su saldo inicial.');self.error.show();return
        if self.accounts[row]['kind']=='withholding':
            self.error.setText('Retenciones de renta tiene saldo automático según los cobros de ventas.');self.error.show();return
        self.watch(OpeningDialog(self.repository,self.accounts[row],self))
    def review_card(self):
        key=self.card_picker.currentData()
        if key:self.watch(CardDetailDialog(self.cards,key,self),'changed')
    def pay_card(self):
        key=self.card_picker.currentData()
        if key:self.new_entry('card_payment',self.cards.get(key)['account_id'])
    def show_text(self,title,rows):
        entries = []
        for row in rows:
            data = json.loads(row['snapshot'])
            details = [f"{row['changed_at']} · {row['description']}"]
            if data.get('concept'):
                details.append(data['concept'])
            details.append('Fecha: ' + str(data.get('occurred_on', data.get('date', '—'))))
            details.append('Valor: ' + format_cop(data.get('amount_cents', data.get('amount', 0))))
            for key, caption in (('from_account', 'Desde'), ('to_account', 'Hacia')):
                if data.get(key):
                    account = next((a['name'] for a in self.accounts if a['id'] == data[key]), 'Cuenta archivada')
                    details.append(caption + ': ' + account)
            if data.get('purchase_id'):
                details.append('Compra #' + str(data['purchase_id']))
            if data.get('kind') == 'card_payment':
                for key, label in (('capital_cents', 'Capital'), ('interest_cents', 'Intereses'), ('fee_cents', 'Otros cargos')):
                    details.append(label + ': ' + format_cop(data.get(key, 0)))
            entries.append('\n'.join(details))
        self.detail=QDialog(self);self.detail.setWindowTitle(title);self.detail.resize(760,420)
        box=QVBoxLayout(self.detail);text=QTextEdit();text.setReadOnly(True)
        text.setPlainText('\n\n'.join(entries) or 'Sin registros');box.addWidget(text);self.detail.show()
    def account_history(self):
        row=self.accounts_table.currentRow()
        if row>=0:self.show_text('Historial de saldo inicial',self.repository.history('opening',self.accounts[row]['id']))
    def view_source(self):
        row=self.movements_table.currentRow()
        if row<0:return
        r=self.rows[row]
        if r['origin']=='money':self.show_text('Historial del movimiento',self.repository.history('entry',r['source_id']))
        elif r['origin']=='card':self.watch(CardDetailDialog(self.cards,r['source_id'],self),'changed')
        else:self.open_source.emit(r['origin'],r['source_id'])
    def cancel_entry(self):
        row=self.movements_table.currentRow()
        if row<0:return
        r=self.rows[row]
        if r['origin']!='money':self.error.setText('Modifica o anula este movimiento desde su registro de origen.');self.error.show();return
        reason,ok=required_reason(self,'Anular movimiento','Motivo de anulación')
        if not ok:return
        try:self.repository.cancel(r['source_id'],reason);self.updated()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e));self.error.show()

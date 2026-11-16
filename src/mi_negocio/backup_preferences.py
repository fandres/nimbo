"""Allowlisted portable preferences and device-local backup settings."""
from datetime import date,datetime
from PySide6.QtCore import QSettings
from .backup_archive import BackupError,portable_preferences

DEFAULTS = {
    'purchases/show_current_month_total':False,
    'sales/require_customer_identification':False,
    'sales/vat_enabled_default':False,
    'purchases/vat_enabled_default':False,
    'sales/require_retention_documents':True,
}


class BackupPreferences:
    def __init__(self,settings=None):
        self.settings=settings if settings is not None else QSettings('Nimbo','Nimbo')

    def export(self):
        return {key:self.settings.value(key,default,type=bool) for key,default in DEFAULTS.items()}

    def apply(self,values):
        portable_preferences(values)
        for key,default in DEFAULTS.items():self.settings.setValue(key,values.get(key,default))
        self.sync()

    def sync(self):
        self.settings.sync()
        if self.settings.status()!=QSettings.NoError:raise BackupError('No se pudieron guardar las preferencias.')

    def configure(self,enabled,folder):
        if enabled and not folder:raise BackupError('Selecciona la carpeta de respaldos automáticos.')
        self.settings.setValue('backup/enabled',bool(enabled));self.settings.setValue('backup/folder',str(folder));self.sync()

    def folder(self):return self.settings.value('backup/folder','',type=str)
    def enabled(self):return self.settings.value('backup/enabled',False,type=bool)
    def due(self,today=None):
        return self.enabled() and bool(self.folder()) and self.settings.value('backup/last_day','')!=(today or date.today()).isoformat()

    def success(self,path):
        self.settings.setValue('backup/last_day',date.today().isoformat())
        self.settings.setValue('backup/last_success',datetime.now().astimezone().isoformat(timespec='seconds'))
        self.settings.setValue('backup/last_path',str(path));self.settings.remove('backup/error');self.sync()

    def failure(self,message):
        self.settings.setValue('backup/error',str(message));self.sync()

    def status(self):
        last=self.settings.value('backup/last_success','Sin respaldos completos registrados',type=str)
        path=self.settings.value('backup/last_path','',type=str)
        error=self.settings.value('backup/error','',type=str)
        return 'Último respaldo correcto: '+last+('\n'+path if path else '')+('\nÚltimo error: '+error if error else '')

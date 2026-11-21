"""Preferencias visuales locales, independientes de los datos contables."""
from PySide6.QtCore import QSettings


class DisplayPreferences:
    def __init__(self, settings=None):
        self.settings=settings if settings is not None else QSettings('Nimbo','Nimbo')

    def show_monthly_purchases(self):
        return self.settings.value('purchases/show_current_month_total',False,type=bool)

    def set_show_monthly_purchases(self, enabled):
        self.settings.setValue('purchases/show_current_month_total',bool(enabled))
        self.settings.sync()
        if self.settings.status()!=QSettings.NoError:
            raise OSError('No se pudo guardar la preferencia de visualización.')

    def require_sale_identification(self):
        return self.settings.value('sales/require_customer_identification',False,type=bool)

    def set_require_sale_identification(self, enabled):
        self.settings.setValue('sales/require_customer_identification',bool(enabled))
        self.settings.sync()
        if self.settings.status()!=QSettings.NoError:
            raise OSError('No se pudo guardar la preferencia de ventas.')

    def vat_default(self,area):
        if area not in ('sales','purchases'):raise ValueError('Área de IVA no válida')
        return self.settings.value(area+'/vat_enabled_default',False,type=bool)

    def set_vat_default(self,area,enabled):
        if area not in ('sales','purchases'):raise ValueError('Área de IVA no válida')
        self.settings.setValue(area+'/vat_enabled_default',bool(enabled));self.settings.sync()
        if self.settings.status()!=QSettings.NoError:raise OSError('No se pudo guardar la preferencia de IVA.')

    def require_retention_documents(self):
        return self.settings.value('sales/require_retention_documents',True,type=bool)

    def set_require_retention_documents(self,enabled):
        self.settings.setValue('sales/require_retention_documents',bool(enabled));self.settings.sync()
        if self.settings.status()!=QSettings.NoError:raise OSError('No se pudo guardar la preferencia de retenciones.')

    def purchase_vat_rate(self):
        from decimal import Decimal, InvalidOperation
        from ..vat import split_vat
        from ..catalog import ValidationError
        try:
            rate=Decimal(str(self.settings.value('purchases/vat_rate','19')))
            split_vat(0,True,rate,True)
            return rate
        except (InvalidOperation,ValidationError):return Decimal('19')

    def set_purchase_vat_rate(self,rate):
        from ..vat import split_vat
        split_vat(0,True,rate,True)
        self.settings.setValue('purchases/vat_rate',str(rate));self.settings.sync()
        if self.settings.status()!=QSettings.NoError:raise OSError('No se pudo guardar la tarifa de IVA.')

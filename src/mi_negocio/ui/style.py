"""Tema claro y formato monetario sin conversiones a float."""


def format_cop(cents: int) -> str:
    whole, fraction = divmod(abs(cents), 100)
    return ('$ -' if cents < 0 else '$ ') + f'{whole:,}'.replace(',', '.') + f',{fraction:02d}'


STYLE = '''
QWidget { font-family: "Noto Sans", "DejaVu Sans", sans-serif; font-size: 13px; color: #233047; }
QMainWindow, QDialog { background: #f5f7fb; }
QFrame#sidebar { background: #ffffff; border-right: 1px solid #e3e8f0; }
QLabel#brand { font-size: 18px; font-weight: 700; color: @dark; }
QLabel#eyebrow { color: #64748b; font-size: 11px; font-weight: 600; }
QLabel#heading { font-size: 28px; font-weight: 700; color: @dark; }
QLabel#subtitle, QLabel#muted { color: #64748b; }
QLabel#nav { background: @soft; color: @primary; border-radius: 8px; padding: 12px; font-weight: 600; }
QLabel#pill { color: #39715b; background: #eaf5ef; border-radius: 7px; padding: 6px 10px; font-size: 11px; }
QFrame#card { background: white; border: 1px solid #e3e8f0; border-radius: 12px; }
QPushButton { background: #ffffff; border: 1px solid #d7dfe9; border-radius: 7px; padding: 9px 15px; font-weight: 600; }
QPushButton:hover { background: #eff3fa; border-color: #acbdd8; }
QPushButton:pressed { background: #e0e8f5; }
QPushButton:disabled { color: #97a2b3; background: #f7f9fc; border-color: #e7ecf2; }
QPushButton#primary { background: @primary; color: white; border-color: @primary; }
QPushButton#homeNewSale { background: @primary; color: white; border: 2px solid @primary; border-radius: 12px; font-size: 22px; font-weight: 700; padding: 10px 24px; }
QPushButton#homeNewSale:hover { background: @hover; border-color: @hover; }
QPushButton#homeNewSale:focus { border: 3px solid @dark; }
QPushButton#newPurchase { background: #7040b0; color: white; border-color: #7040b0; }
QPushButton#newPurchase:hover { background: #5e3496; border-color: #5e3496; }
QPushButton#newPurchase:pressed { background: #4d287e; border-color: #4d287e; }
QPushButton#newPurchase:focus { border: 2px solid #342052; }
QPushButton#newPurchase:disabled { background: #eee8f5; color: #847590; border-color: #ddd2e9; }
QPushButton#primary:hover { background: @hover; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid @focus; }
QLineEdit { placeholder-text-color: #94a0b3; }
QLineEdit, QComboBox { background: white; border: 1px solid #d7dfe9; border-radius: 7px; padding: 8px 10px; min-height: 20px; }
QFrame#shippingGroup QLineEdit, QFrame#shippingGroup QComboBox, QFrame#shippingGroup QDateEdit { padding-top: 5px; padding-bottom: 5px; min-height: 18px; }
QComboBox { padding-right: 24px; }
QComboBox QAbstractItemView { background: white; selection-background-color: @soft; selection-color: #233047; }
QLineEdit[invalid="true"] { border: 1px solid #c94444; }
QLabel#error { color: #b73333; font-size: 12px; }
QLabel#notice { color: #285c49; padding: 7px 0; }
QTableWidget { background: white; border: none; gridline-color: #eef1f5; selection-background-color: @soft; selection-color: #233047; }
QTableWidget::item { padding: 10px; border-bottom: 1px solid #eef1f5; }
QHeaderView::section { background: #f8fafd; color: #617087; border: none; border-bottom: 1px solid #e3e8f0; padding: 12px 10px; font-weight: 600; }
QTableCornerButton::section { background: #f8fafd; border: none; }
QCheckBox { spacing: 8px; }
QToolTip { background: @dark; color: white; border: none; padding: 6px; }
'''


# Brand accents and financial semantics are deliberately separate.
PALETTE = {
    'dark': '#142B50', 'primary': '#315FDA', 'soft': '#EAF0FF',
    'hover': '#244DC0', 'focus': '#537BE3', 'positive': '#287354', 'negative': '#B73333', 'near_zero': '#A36715',
}

STYLE += """
QWidget#navContent { background: white; }
QWidget#homeContent { background: #f5f7fb; }
QScrollArea { border: none; background: transparent; }
QLabel#brandMark { background: @primary; color: white; border-radius: 13px; font-size: 27px; font-weight: 700; }
QLabel#sidebarBrand { font-size: 15px; font-weight: 700; color: @dark; }
QPushButton#navButton { border-radius: 12px; padding: 8px 3px; border: none; background: transparent; font-size: 12px; font-weight: 500; }
QPushButton#navButton:checked { background: @soft; color: @primary; font-weight: 700; border-radius: 12px; }
QPushButton#navButton:hover { background: @soft; }
QPushButton#navButton:disabled { color: #8290a5; background: transparent; }
QPushButton#navButton:focus { border: 2px solid @primary; }
QLabel#navTitle { font-size: 11px; font-weight: 600; background: transparent; }
QLabel#navTitle:disabled { color: #8290a5; }
QLabel#navStatus { font-size: 9px; color: #8290a5; background: transparent; }
QPushButton#navButton { padding: 0; }
QFrame#homeCard { background: white; border: 1px solid #e8edf5; border-radius: 20px; }
QFrame#heroCard { background: @dark; border: 1px solid transparent; border-radius: 20px; }
QLabel#homeTitle { font-size: 26px; font-weight: 700; color: @dark; }
QLabel#cardTitle { font-size: 17px; font-weight: 700; color: @dark; }
QLabel#heroEyebrow { color: #b9cbe7; font-size: 13px; }
QLabel#heroValue { color: white; font-size: 24px; font-weight: 700; }
QLabel#heroHelp { color: #c4d4ec; }
QLabel#sectionValue { font-size: 20px; font-weight: 600; color: @dark; }
QLabel#countValue { font-size: 25px; font-weight: 700; color: @primary; }
QLabel#coming { color: #64748b; background: #f0f3f8; border-radius: 8px; padding: 4px 8px; font-size: 11px; }
QPushButton#futurePrimary:disabled { background: #dce6ff; border: 1px solid #cbd9ff; color: #536fba; border-radius: 16px; padding: 12px 18px; }
QPushButton#futureAction:disabled { color: @dark; border: none; text-align: left; padding: 0; background: transparent; font-size: 15px; }
QPushButton#link { border: none; color: @primary; background: @soft; border-radius: 10px; }
"""
STYLE += """
QPushButton#paymentChoice:checked { background: @soft; color: @primary; border: 2px solid @primary; }
QFrame#destinationGroup { background: #eef3fc; border: 1px solid #dbe5f5; border-radius: 10px; }
QFrame#shippingGroup { background: #f1f6f4; border: 1px solid #cedfd7; border-radius: 10px; }
QFrame#receiptGroup { background: #f2f6f5; border: 1px solid #dde8e4; border-radius: 10px; }
QLabel#fieldHeading { font-weight: 600; color: @dark; }
QFrame#chargeSummary { background: #eaf0ff; border: 1px solid #d9e3fa; border-radius: 10px; }
QFrame#expenseSummary { background: #fff4e9; border: 1px solid #f2e0cd; border-radius: 10px; }
QFrame#netSummary { background: #eaf5ef; border: 1px solid #d3e7dc; border-radius: 10px; }
QLabel#summaryAmount { color: @dark; font-weight: 700; font-size: 16px; }
QFrame#saleSection { background: white; border: 1px solid #dfe6f1; border-radius: 14px; }
QPushButton#secondaryAction { background: @soft; color: @primary; border: 1px solid #b9ccf6; }
QPushButton#removeAction { color: #ad3543; background: #fff4f4; border: 1px solid #efd4d7; }
QPushButton#removeAction:disabled { color: #97a2b3; background: #f7f9fc; border-color: #e7ecf2; }
QPushButton#catalogEdit { background: @soft; color: @primary; border-color: #b9ccf6; }
QPushButton#catalogEdit:hover { background: #dce6ff; border-color: @primary; }
QPushButton#catalogDeactivate { background: #fff4f4; color: #ad3543; border-color: #efd4d7; }
QPushButton#catalogDeactivate:hover { background: #ffe4e6; border-color: #ad3543; }
QPushButton#catalogActivate { background: #e9f6ee; color: #167347; border-color: #b8ddc8; }
QPushButton#catalogActivate:hover { background: #d3efdf; border-color: #167347; }
QPushButton#catalogEdit:disabled, QPushButton#catalogDeactivate:disabled, QPushButton#catalogActivate:disabled { color: #97a2b3; background: #f7f9fc; border-color: #e7ecf2; }
QPushButton#quietAction { color: #64748b; background: transparent; border: none; padding: 4px 0; font-size: 11px; }
QWidget#settingsEditor { background: #f5f7fb; }
QTabWidget::pane { border: 1px solid #e3e8f0; background: #f5f7fb; }
QTabBar::tab { padding: 10px 18px; background: #f5f7fb; }
QTabBar::tab:selected { background: @soft; color: @primary; }
QDateEdit, QSpinBox { background: white; border: 1px solid #d7dfe9; border-radius: 7px; padding: 5px 8px; min-height: 20px; }
QSpinBox { padding-right: 28px; }
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border; width: 24px; background: #eef3fc;
    border-left: 1px solid #d7dfe9;
}
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 7px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 7px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #dce6ff; }
QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; }

QWidget#saleBody { background: #f5f7fb; }
QLabel#saleSummary { background: @soft; color: @dark; border-radius: 12px; padding: 12px; }
QCheckBox#paymentToggle::indicator { width: 32px; height: 18px; border-radius: 9px; background: #ced7e5; border: 1px solid #a4b4cb; }
QCheckBox#paymentToggle::indicator:checked { background: @primary; border-color: @primary; }
QPushButton#futureAction:enabled { color: @primary; border: none; text-align: left; padding: 0; background: transparent; font-size: 15px; }
"""
for name, color in PALETTE.items():
    STYLE = STYLE.replace('@' + name, color)

# Keep invalid controls red even while they have keyboard focus.
STYLE += '''
QLineEdit[invalid="true"], QLineEdit[invalid="true"]:focus,
QComboBox[invalid="true"], QComboBox[invalid="true"]:focus,
QDateEdit[invalid="true"], QDateEdit[invalid="true"]:focus,
QSpinBox[invalid="true"], QSpinBox[invalid="true"]:focus,
QPushButton[invalid="true"], QPushButton[invalid="true"]:focus,
QCheckBox[invalid="true"] {
    border: 2px solid #c94444;
    background-color: #fff3f3;
}
'''


# Purchases share the same accent as the existing newPurchase button.
HOME_ACTION_COLORS = {
    'plus': PALETTE['primary'], 'purchases': '#7040b0',
    'expense': '#a35d16', 'clock': '#167347',
}
STYLE += """
QFrame#homeCard:hover { background: #f5f8ff; border-color: #b6c6df; }
QFrame#heroCard:hover { border: 1px solid #7597cb; }
QPushButton#homeAction { border: 2px solid transparent; border-radius: 20px; padding: 0; text-align: left; }
QPushButton#homeAction QLabel { background: transparent; border: none; }
QPushButton#homeAction:disabled { background: #f2f4f8; border-color: #e3e8f0; }
QPushButton#homeAction:disabled QLabel { color: #8290a5; }
"""
for action, soft, hover, pressed in [
    ('plus', '#eef3ff', '#dce6ff', '#cbd9ff'),
    ('purchases', '#f4eefb', '#e8daf7', '#dcc7f1'),
    ('expense', '#fff5e9', '#ffead0', '#ffdfb8'),
    ('clock', '#edf8f2', '#d9f1e4', '#c5e8d5'),
]:
    selector = 'QPushButton#homeAction[action="' + action + '"]'
    color = HOME_ACTION_COLORS[action]
    STYLE += f"""
{selector}:enabled {{ background: {soft}; }}
{selector}:enabled:hover, {selector}:enabled:focus {{ background: {hover}; border-color: {color}; }}
{selector}:enabled:pressed {{ background: {pressed}; border-color: {color}; }}
"""

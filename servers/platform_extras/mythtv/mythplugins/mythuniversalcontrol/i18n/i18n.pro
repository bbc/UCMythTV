include ( ../../mythconfig.mak )
include ( ../../settings.pro )

TEMPLATE = app
CONFIG -= moc qt

trans.path = $${PREFIX}/share/mythtv/i18n/
trans.files += mythuniversalcontrol_en_gb.qm

INSTALLS += trans

SOURCES += dummy.c


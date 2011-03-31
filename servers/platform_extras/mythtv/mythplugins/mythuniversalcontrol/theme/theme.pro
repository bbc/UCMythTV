include ( ../../mythconfig.mak )
include ( ../../settings.pro )

QMAKE_STRIP = echo

TARGET = themenop
TEMPLATE = app
CONFIG -= qt moc

QMAKE_COPY_DIR = sh ../../cpsvndir

defaultfiles.path = $${PREFIX}/share/mythtv/themes/default
defaultfiles.files = default/*.xml

widefiles.path = $${PREFIX}/share/mythtv/themes/default-wide
widefiles.files = default-wide/*.xml

defaultmenufiles.path  = $${PREFIX}/share/mythtv/themes/defaultmenu
defaultmenufiles.files = defaultmenu/*.xml

INSTALLS += defaultfiles widefiles defaultmenufiles

# Input
SOURCES += ../../themedummy.c

include ( ../../mythconfig.mak )
include ( ../../settings.pro )
include ( ../../programs-libs.pro )

TEMPLATE = lib
CONFIG += plugin thread
TARGET = mythuniversalcontrol

LIBS += -lmythmetadata-$$LIBVERSION

target.path = $${LIBDIR}/mythtv/plugins
INSTALLS += target

# Input
HEADERS += ucui.h
HEADERS += PairingScreen_p.h

SOURCES += main.cpp 
SOURCES += PairingScreen_p.cpp
SOURCES += ucui.cpp 

use_hidesyms {
    QMAKE_CXXFLAGS += -fvisibility=hidden
}

#The following line was inserted by qt3to4
QT += xml sql opengl dbus

include ( ../../libs-targetfix.pro )

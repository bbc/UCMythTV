# MythTV Universal Control Server - DBus module
# Copyright (C) 2011 British Broadcasting Corporation
#
# Contributors: See Contributors File
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; you may use version 2 of the licsense only
# 
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
# 
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#


"""\
Import this module to start up the dbus handling needed for the pairing screen,
feedback, and apps modules.
"""

import dbus
from UCServer.currentipaddress import currentipaddress

from dbus.mainloop.glib import DBusGMainLoop
import dbus.glib
import gobject

import threading

DBusGMainLoop(set_as_default=True)
gobject.threads_init()
dbus.glib.init_threads()

class SignalLoopThread (threading.Thread):
    """This class represents a thread which will run the glib main loop
    needed for signal listening.

    A single instance of this thread class is started whenever this module is imported."""

    loop = gobject.MainLoop()
    daemon = True

    def run(self):
        try:
            self.loop.run()
        except:
            raise

# The thread is always started whenever this module is imported, simplest that way.
SignalLoopThread().start()

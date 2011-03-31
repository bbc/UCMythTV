# MythTV Universal Control Server - Pairing Code Screen
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
This implements a MythTV screen for displaying the Universal Control
Server's pairing code.
"""

import dbus_core
import dbus
import dbus.service
from PairingCode import UCPairingCode
import UCServer

from UCServer.currentipaddress import currentipaddress

import random

from dbus.mainloop.glib import DBusGMainLoop
import dbus.glib
import gobject

sysrandom = random.SystemRandom()        

class credentialsdict(dict):
    def __init__(self,pairingscreen=None,data=None):
        self.pairingscreen = pairingscreen
        dict.__init__(self,data)

    def __setitem__(self, key, item):
        dict.__setitem__(self,key, item)
        if self.pairingscreen is not None:
            self.pairingscreen.clientListChanged()

    def __delitem__(self,key):
        dict.__delitem__(self,key)
        if self.pairingscreen is not None:
            self.pairingscreen.clientListChanged()

class UniversalControl:
    class PairingScreen(dbus.service.Object):
        def __init__(self,
                     uc_server,
                     ip_address='',
                     versioninfo=UCServer.__version__,
                     security = False,
                     bus_name = dbus.service.BusName("uk.co.bbc.UniversalControl", bus=dbus.SessionBus()),
                     object_path ="/UniversalControl/PairingScreen"):
            self.uc_server = uc_server
            self.ip_address = ip_address
            self.SSS = None
            self.versioninfo = versioninfo
            self.security = security
            self.uc_server.data['uc/credentials']['clients'] = credentialsdict(self, self.uc_server.data['uc/credentials']['clients'])
            dbus.service.Object.__init__(self,bus_name, object_path)

        @dbus.service.method("uk.co.bbc.UniversalControl.PairingScreen", in_signature='',
                             out_signature='s')
        def willOpen(self):
            self.SSS = None
            if self.security:
                self.SSS = sysrandom.getrandbits(8)
                self.uc_server.set_SSS(self.SSS)            
            if self.ip_address != '':
                ip_address = self.ip_address
            else:
                ip_address = currentipaddress()
            return UCPairingCode(ip_address, SSS=self.SSS).pairingCode()

        @dbus.service.method("uk.co.bbc.UniversalControl.PairingScreen", in_signature='',
                             out_signature='s')
        def versionInfo(self):
            return self.versioninfo

        @dbus.service.method("uk.co.bbc.UniversalControl.PairingScreen", in_signature='',
                             out_signature='')
        def willClose(self):
            self.uc_server.clear_pending_credentials()

        @dbus.service.method("uk.co.bbc.UniversalControl.PairingScreen", in_signature='',
                             out_signature='as')
        def getClientList(self):
            data = self.uc_server.data['uc/credentials']['clients']
            return [ '%s:%s' % (CID,data[CID]) for CID in data ]

        @dbus.service.method("uk.co.bbc.UniversalControl.PairingScreen", in_signature='s',
                             out_signature='')
        def deleteClient(self, CID):
            try:
                self.uc_server.remove_client_id(CID)
            except:
                pass

        @dbus.service.signal("uk.co.bbc.UniversalControl.PairingScreen",
                             signature='')
        def shouldStopDisplay(self):
            pass

        @dbus.service.signal("uk.co.bbc.UniversalControl.PairingScreen",
                             signature='')
        def clientListChanged(self):
            pass

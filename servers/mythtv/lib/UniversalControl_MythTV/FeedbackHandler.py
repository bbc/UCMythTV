# MythTV Universal Control Server - Handling of Feedback resource
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
This module provides a dbus interface for the feedback resource.

To make it work simply import this module and instantiate the Feedback class
passing in the UCServer instance as a parameter.


This module exports an object via dbus with busname uk.co.bbc.UniversalControl, object path /UniversalControl/Feedback and a single interface uk.co.bbc.UniversalControl.Feedback with a single method, setFeedbackText, which has a signature of 's' (input) and '' (output). Call this method and specify an entity-encoded string and it will be set as the data for the feedback resource, replacing whatever was present before. This triggers a notifiable change.
"""

import dbus_core
import dbus
import dbus.service
import datetime

feedback_data = {
    'resource' : 'uc/feedback',
    'timestamp' : datetime.datetime.utcnow(),
    'feedback' : ''
    }

class Feedback(dbus.service.Object):
    def __init__(self,
                 uc_server,
                 ip_address='',
                 bus_name = dbus.service.BusName("uk.co.bbc.UniversalControl", bus=dbus.SessionBus()),
                 object_path = "/UniversalControl/Feedback"):
        global feedback_data

        self.uc_server = uc_server
        self.uc_server.set_resource_data('uc/feedback', feedback_data)
        
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method("uk.co.bbc.UniversalControl.Feedback", in_signature="s", 
                         out_signature="")
    def setFeedbackText(self,feedback):
        global feedback_data
        feedback_data['feedback'] = feedback
        feedback_data['timestamp'] = datetime.datetime.utcnow()
        self.uc_server.notify_change('uc/feedback')

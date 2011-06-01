# MythTV Universal Control Server - Handling of App extension resource
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
This module provides a dbus interface for the apps resource

To make it work simply import this module and instantiate the Apps class
passing in the UCServer instance as a parameter.

This app makes an object available on dbus with the path /UniversalControl/Apps
at the well-known busname uk.co.bbc.UniversalControl which implements the dbus 
interface uk.co.bbc.UniversalControl.Apps, an interface which has several methods, which
are described in the documentation of the Apps class.

The App class also maintains a mechanism to specify content which can be launched as seperate 
processes and will be lumped into the source "externalapps". Content can either be specified
by including it in the data structure in the ManualAppMetadata python file, or by registering
it at runtime using the provided dbus methods.
"""

from UCServer.Exceptions import *

import subprocess, shlex

import MythTVUC

import dbus_core
import dbus
import dbus.service

import threading

import traceback

try:
    from ManualAppMetadata import external_metadata
except:
    external_metadata = []


class ExternalApp:
    """This object encapsulates an external application which can be launched by the server."""
    def __init__(self, aid, sid, cid, title, synopsis, launch_command=None, surpress_output=False):
        self.aid = str(aid)
        self.sid = str(sid)
        self.cid = str(cid)
        self.title = unicode(title)
        self.synopis = unicode(synopsis)
        self.launch_command = str(launch_command)

        self.surpress_output = surpress_output

        self.__external = None
        self.__running = False

        self.metadata = { 'sid' : self.sid,
                          'cid' : str(cid),
                          'title' : unicode(title),
                          'synopsis' : unicode(synopsis),
                          'interactive' : True,
                          'global-app-id' : unicode(aid),
                          }

    def launch(self, on_stop=None):
        if self.launch_command is None:
            raise ProcessingFailed

        print self.launch_command
        print shlex.split(self.launch_command)

        self.__running = True

        class AppThread(threading.Thread):
            def __init__(self,aid,command,on_stop=None):
                threading.Thread.__init__(self)
                self.aid     = aid
                self.on_stop = on_stop
                self.command = command
                self.external = None

            def run(self):
                self.external = subprocess.Popen(shlex.split(str(self.command)))
                self.external.wait()
                self.external = None
                if self.on_stop is not None:
                    self.on_stop(self.aid)

            def kill(self):
                if self.external is not None:
                    self.external.kill()
        
        self.__external=AppThread(self.aid,self.launch_command,on_stop)
        self.__external.start()

    def poll(self):
        ret = self.__external.poll()
        if ret:
            self.__running=False
            return ret
        return ret

    def kill(self):
        self.__external.kill()
        self.__running = False

        

class Apps(dbus.service.Object):
    """This object provides the functionality of this module"""
    apps_data = { 'resource' : 'uc/apps',
                  'apps' : {},
                  }

    __sid = 'externalapps'
    __next_id = 0

    __cid_lock = threading.RLock()    

    def __init__(self,
                 uc_server,
                 bus_name = dbus.service.BusName("uk.co.bbc.UniversalControl", bus=dbus.SessionBus()),
                 object_path = "/UniversalControl/Apps"):
        
        self.uc_server = uc_server
        self.mythtv_outputs = MythTVUC.mythtv_outputs
        self.output_content = None
        self.uc_server.set_resource_data('uc/apps', self.apps_data)
        self.uc_server.set_application_activater(self)
        MythTVUC.extra_sources[self.__sid] = self
        MythTVUC.mythtv_sources[self.__sid] = { 'id'    : self.__sid,
                                                'name'  : "Applications",
                                                'live'  : False,
                                                'linear': False,
                                                'follow-on' : False,
                                                'rref'  : 'uc/sources/%s' % (self.__sid,),
                                                'MYTHTV:type' : 'app' }
        MythTVUC.mythtv_source_lists['uc_default']['sources'].append(self.__sid)

        self.external_apps = {}

        for metadata in external_metadata:
            with self.__cid_lock:
                cid = '%04x' % (self.__next_id,)
                self.__next_id += 1

            self.external_apps[cid] = ExternalApp(metadata[0],
                                                  self.__sid,
                                                  cid,
                                                  metadata[1],
                                                  metadata[2],
                                                  metadata[3],
                                                  metadata[4])
        
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method("uk.co.bbc.UniversalControl.Apps", in_signature='ssssb',
                         out_signature='')
    def addLaunchableContent(self,aid,title,synopsis,launch_command,surpress_output):
        """This method can be called accross DBus, the parameters are the gaid, title, and synopsis 
        of an external application and a command which can be executed to run the application itself,
        followed by a boolean flag which indicates whether the content will launch fullscreen (True),
        or in the background (False). Windowed launching is not supported.
        """

        with self.__cid_lock:
            cid = '%04x' % (self.__next_id,)
            self.__next_id += 1

        self.external_apps[cid] = ExternalApp(aid, self.__sid, str(cid), unicode(title), unicode(synopsis), str(launch_command),bool(surpress_command))
  
    @dbus.service.method("uk.co.bbc.UniversalControl.Apps", in_signature='s',
                         out_signature='')
    def removeLaunchableContent(self,aid):
        """This method is called to remove launchable content from the maintained list of apps."""
        with self.__cid_lock:
            delete = aid in self.apps_data['apps']
            if delete:
                del self.apps_data['apps'][aid]
                
        if delete:
            self.uc_server.notify_change('uc/apps')

        cids = [ cid for cid,item in self.external_apps.items() if item.aid == aid ]
        for cid in cids:
            self.external_apps[cid].kill()
            del self.external_apps[cid]
        

    @dbus.service.method("uk.co.bbc.UniversalControl.Apps", in_signature='so',
                         out_signature='',
                         sender_keyword='sender')
    def registerExtension(self,aid,object_path,sender=None):
        """This method can be called across DBus, the parameters are the gaid of an external application 
        and the dbus object_path of an object maintained by the sender which implements the 
        uk.co.bbc.UniversalControl.AppExtension interface over dbus.

        The uk.co.bbc.UniversalControl.AppExtension interface contains a single method, request, with
        signature ssa{ss}a{sas}bs (in) and ia{ss}s (out). The parameters are (in order):

        The relative path
        The HTTP verb,
        The headers
        The query parameters
        authorisation
        the request body
        """

        cids = [ cid for cid in self.external_apps if self.external_apps[cid].aid == aid ]
        if cids:
            cid = cids[0]

            if aid not in self.apps_data['apps']:
                self.external_apps[cid].launch()

            with self.__cid_lock:
                if aid not in self.apps_data['apps']:
                    self.apps_data['apps'][aid] = { 'sid' : self.__sid,
                                                    'cid' : cid }

                self.apps_data['apps'][aid]['extension'] = Extension(self,aid,object_path,sender)
        else:
            raise Exception

        self.uc_server.notify_change('uc/apps')

    @dbus.service.method("uk.co.bbc.UniversalControl.Apps", in_signature='s',
                         out_signature='')
    def unregisterExtension(self,aid):
        """Call this method to remove an app which has been previously registered."""
        with self.__cid_lock:
            rem = aid in self.apps_data['apps'] and 'extension' in self.apps_data['apps'][aid]
            if rem:
                del self.apps_data['apps'][aid]['extension']

        if rem:
            self.uc_server.notify_change('uc/apps')

    @dbus.service.method("uk.co.bbc.UniversalControl.Apps", in_signature='ss',
                         out_signature='')
    def notifyResource(self,aid,path):
        """This method can be called to trigger a notifiable change in an extension resource for a 
        particular application."""
        self.uc_server.notify_change('uc/apps/%s/ext/%s' % (aid,path))

    def get_content(self):
        """This method is used to generate the content list"""
        return [ item.metadata for key,item in self.external_apps.items() ]

    def activate(self,sid,cid):
        """This method is called to activate an application remotely."""
        if sid != self.__sid:
            raise InvalidSyntax
        
        if cid not in self.external_apps:
            raise InvalidSyntax

        aid = self.external_apps[cid].aid
        with self.__cid_lock:
            self.apps_data['apps'][aid] = { 'sid' : self.__sid,
                                            'cid' : cid,
                                            }

        if self.external_apps[cid].surpress_output:
            output = dict((key,self.mythtv_outputs['0'][key]) for key in ('id','name',))
            output['programme'] = None
            output['app'] = (self.__sid,cid,[])
            output['component_overrides'] = []
            output['playback'] = None
            output['settings'] = {}
            output['playhead'] = None
            output['selector'] = self

            self.uc_server.set_outputs({ '0' : output })
            
            self.output_content = aid
            
        self.external_apps[cid].launch(on_stop=self.deactivate)

        return aid

    def deactivate(self,aid):
        """This method is called when an application is killed"""
        cids = [ cid for cid in self.external_apps if self.external_apps[cid].aid == aid ]
        if self.output_content is not None:
            self.output_content = None
            self.uc_server.set_outputs(MythTVUC.mythtv_outputs)
        if cids:
            rem = aid in self.apps_data['apps']
            if rem:
                with self.__cid_lock:
                    del self.apps_data['apps'][aid]
            for cid in cids:
                self.external_apps[cid].kill()

        if rem:
            self.uc_server.notify_change("uc/apps")

    def select_content(self,sid,cid):
        if self.output_content is not None:
            self.deactivate(self.output_content)
        
        MythTVUC.mythtv_outputs['0']['selector'].select_content(sid,cid)

    def select_programme(self,sid,cid,components=[]):
        if self.output_content is not None:
            self.deactivate(self.output_content)
        
        MythTVUC.mythtv_outputs['0']['selector'].select_programme(sid,cid,components)

    def select_app(self,sid,cid):
        if self.output_content is not None:
            self.deactivate(self.output_content)
        
        MythTVUC.mythtv_outputs['0']['selector'].select_app(sid,cid)

class Extension:
    def __init__(self,apps,aid,object_path,bus_name):
        self.apps        = apps
        self.aid         = aid
        self.object_path = object_path
        self.bus_name    = bus_name

    def request(self,path,method,request_headers,params,auth,body):
        try:
            (status, header, body) = dbus.SessionBus().get_object(self.bus_name,
                                                                  self.object_path).request('/'.join(path),
                                                                                            method,
                                                                                            request_headers,
                                                                                            params,
                                                                                            auth,
                                                                                            body,
                                                                                            dbus_interface='uk.co.bbc.UniversalControl.AppExtension',
                                                                                            utf8_strings=True,
                                                                                            byte_arrays=True)
            print "returning: %r" % ((status,header,body),)
            return (status,header,body)
        except:
            print traceback.format_exc()
            return (500,{},'Error!')
        
    
    

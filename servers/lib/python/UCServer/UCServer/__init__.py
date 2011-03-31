# __init__ for Universal Control Server
# Copyright (C) 2011 British Broadcasting Corporation
#
# This code may be used under the terms of either of the following
# licences:
#   
# 1) GPLv2:
# 
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
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
#
# 2) Apache 2.0:
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

"""\
The Main UCServer library

This package is a library designed to be used in implementing a Universal
Control Server compliant with v.  0.5.1 of the Universal Control spec.  When
invoked correctly by the server implementor this library will handle all of
the HTTP Server behaviour required by the UC Spec, leaving the server
implementor to concentrate on providing the necessary data to populate the
resources made available by the server and the necessary code to implement
the changes made to these resources by clients.



This package contains the following Submodule which will likely be of use to
all individual implementation developers:

-- UCServer.Exceptions
  This module contains several exceptions which are used in the processing
  of requests.  Server implementors may well benefit from making use of the
  classes in this package.

In addition this module itself contains one very important class,
UCServer.UCServer.  All server implementations will make frequent use of
this class and implementors should read the documentation for it (below) in
detail.



As well as the above this package contains a number of submodules which are
part of the internal implementation of the server and are unlikely to be of
use to implementors directly:

-- UCServer.HTTPHandling
   This module contains internal code used by the server in handling
   individual http requests, it is highly unlikely that the server
   implementor will need to make use of this module.
   
-- UCServer.ResourceHandlers
   This module contains internal code used by the server in handling
   individual resources, it is somewhat unlikely that the server implementor
   will need to make use of this module unless they are implementing complex
   out of tree resources (in which case see the documentation of that
   module).
"""

__version__ = "0.6.0"

__all__ = ["UCServer",
           "currentipaddress",
           ]
          

#Standard Python imports
import BaseHTTPServer
import SocketServer
import socket
import urllib
import time
import datetime
import threading
import xml.dom.minidom
import xml.sax.saxutils as saxutils

#imports from elsewhere in this package
from Exceptions import *
from Exceptions import UCException
from HTTPHandling import *
import ResourceHandlers

from currentipaddress import currentipaddress





#global (module scope) variables used for holding the unique instances of the UCServer and Zeroconf classes, both
#of which implement the singleton design patern.
uc_server = None
zc_server = None



# The UCServer class implements the singleton design patern and is used by the server implementor to control the server

class UCServer:
    """This class encapsulates the Universal Control Server. 

    To obtain the unique UCServer instance run UCServer.UCServer(...) with apropriate parameters.
    
    This operation will fail (with an Exception) if there is already a UCServer instance
    in existance.
    
    The parameters are as follows:
    
    address        -- takes a basestring containing an IP-address in the form "%d.%d.%d.%d". If left as
                      None will attempt to determine own address -- which usually fails.
    port           -- an int. Defaults to 48875.
    zeroconf       -- A bool. Defaults to False. If True then the server will advertise itself using the
                      pure python Zeroconf library. Otherwise Zeroconf advertising is the responsibility 
                      of the implementor.
    name           -- This is the server name which should be used by the server, as a string. It defaults
                      to "UC Server" -- which is non-ideal. Most implementors will want to set this.
    description    -- A description which will be used as part of the Zeroconf record if internal Zeroconf
                      support is on.
    uuid           -- A string containing the uuid of the server -- the deafault is "00000000-0000-0000-0000-000000000000"
    realm          -- The realm used for HTTP Digest Authentication. Leave this as None and the server will
                      set it automatically according to the Spec.
    CPUsedCallback -- A callable python object (such as a method) which will be called whenever the current 
                      pending CP is used by a client to make a request to the server. It should take no 
                      parameters and any return value will be ignored.
    options        -- A list of strings describing which optional resources the server should implement. The 
                      valid values for these strings are described in the documentation of the methods
                      UCServer.UCServer.add_option.
    handler_class  -- The class which will be used by the HTTP Server to handle HTTP Requests. The default class
                      is correct unless you are seriously rewriting the behaviour of the server.
    log_filename   -- A string containing the path of a logfile to which the server's output will be written.
                      By default all loging goes to standard out.
    nid_filename   -- A string containing the path of a file used to store the notification_id persistently.
                      By default this is notification_id.dat in the current working directory.

        
    Once this initialiser has been run you'll have access to an instance of this class. The data used by the server to
    populate the XML returned by GET requests to resources should be provided by your server instance implementation in
    the form of python objects which behave like dictionaries (in that they will respond to the standard dictionary 
    methods such as  __getitem__ __setitem__ keys etc ...). 

    The server can be told to use these dictionary-like objects you provide by passing them in as parameters to a number
    of the members of this object (as described in the documentation for those members themselves, below).

    When designing such dictionary-like objects it is essential to implement the methods __setitem__, __getitem__, __len__,
    __delitem__, __iter__, iterkeys, __contains__, keys, values, and items. It may also be useful to implement other methods.
    When calls are made to these methods (especially __setitem__ and __getitem__) as a direct consequence of an HTTP request
    it is quite possible that the individual server implementor may wish to cause the request to fail with a specific HTTP
    error code. This can be achieved by raising one of the exceptions found in the module UCServer.Exceptions . In addition 
    it is highly likely that an individual server implementor will wish to trigger a notifiable change in a particular resource
    in response to the data which backs up these dictionary-like objects changing. This can be achieved through making calls
    to this class's notify_change method -- but a word of caution should be given: it is a very bad idea to cause this method to
    be triggered every time __setitem__ is called on the dictionary-like object -- as this will happen as a result of PUT and POST
    requests even if those requests fail.



    Other members of this class are used for other purposes, such as controling which optional resources are implemented, 
    enabling or disabling the security scheme, etc ... (see the documentation of the methods for details).



    Finally, once the server has been configured correctly the individual server implementor needs to call serve_forever(),
    which causes the server to actually run. This method never returns, and will only exit with a fatal exception (such as
    a Keyboard Interrupt).
    """

    def __init__(self,
                 address=None,                 
                 port=48875, #If address is left blank then the server will 
                            #attempt to determine its own address. This often fails.
                 zeroconf=False, #By default the internal zeroconf capabilities are not used
                 name="UC Server",
                 description="Universal Control Server",
                 uuid="00000000-0000-0000-0000-000000000000",
                 realm=None,
                 CPUsedCallback=None,
                 StandbyCallback=None,
                 options=[],
                 handler_class=UCHandler,                 
                 log_filename=None,
                 nid_filename="notification_id.dat"):
        """Initialisation of the Singleton UCServer instance.
        """
        
        global uc_server
        global zc_server


        # If there already is a uc_server instance raise an Exception
        # (there doesn't seem to be any way of forcing a class initialiser
        # to return other than self)
        if uc_server is not None:
            raise Exception, "Attempt to start multiple UCServers"

        self.standby       = False
        self.StandbyCallback = StandbyCallback

        self.SSS           = None

        self.zeroconf      = zeroconf
        handler_class.authenticated_callback = self.authenticated
        self.server        = UCHTTPServer((address,port),handler_class)
        self.address       = self.server.server_name
        self.port          = self.server.server_port
        self.name          = name
        self.description   = description
        self.uuid          = uuid
        self.options       = []
        self.data          = DataSourceProxy()
        self.CPUsedCallback= CPUsedCallback
        self.outputs       = dict() 
        self.source_lists  = dict()
        self.sources       = dict()
        self.ids_for_sref  = dict()
        self.ids_for_lcn   = dict()
        self.brands        = dict()
        self.controls      = []
        self.main_output   = None
        self.content       = None
        self.categories    = dict()
        self.button_handler= None
        self.realm         = realm

        self.handler_class              = handler_class
        self.handler_class.log_filename = log_filename
        self.handler_class.realm        = realm

        self.add_pending_credentials_callback = None

        # Open the notification_id file
        self.notification_id_filename = nid_filename
        try:
            self.notification_id_file = open(nid_filename,'r+')
        except:
            self.notification_id_file = open(nid_filename,'w')

        # This mutex lock ensures that the notification_id is threadsafe
        self.notification_id_lock = threading.RLock()

        # Add the specified optional resources to the server
        for option in options:
            self.add_option(option)



        # set the value of the uc_server variables to this instance
        uc_server = self
        ResourceHandlers.uc_server = self

        # Now, if builtin zeroconf is being used activate it.

        #Notify that the server has powered on.
        self.notify_change('uc/power')

    def set_standby(self, standby=None):
        """This method should be called by any code wishing to cause the box to switch to or from standby mode.

        If the parameter is left unset then the box will toggle standby mode.

        This method will call the standby callback set when the server was initialised if one exists. The return value of this
        code is True if the call returned true and false if it returned false, the box's standby state only changes if the 
        call succeeds."""

        if standby is None:
            standby = not self.standby

        if standby == self.standby:
            return True

        if self.StandbyCallback is not None:
            if self.StandbyCallback(standby):
                if standby:
                    self.log_message("Going into standby mode")
                else:
                    self.log_message("Leaving standby mode")
                self.standby = standby
                self.handler_class.standby = standby
                return True
            else:
                return False
        else:
            if standby:
                self.log_message("Going into standby mode")
            else:
                self.log_message("Leaving standby mode")
            self.standby = standby
            self.handler_class.standby = standby
            return True        

    def ip_address(self):
        return currentipaddress()

    def set_outputs(self,outputs):
        """This method is used to set a data source which contains information about the
        box's outputs. 

        This should be a dictionary-like object conforming to the format:

           { OUTPUT ID AS STRING : { 'id'       : OUTPUT ID AS A STRING,
                                     'main'     : BOOLEAN
                                     'name'     : NAME AS A STRING,
                                     'settings' : { 
                                                   OPTIONALLY:
                                                   'volume'   : INTEGER BETWEEN 0 AND 10000,
                                                   'mute'     : BOOLEAN,
                                                   'aspect'   : ONE OF ('source','4:3','14:9','16:10','16:9','21:9')
                                                   },
                                     OPTIONALLY:
                                     'selector' : AN OBJECT DESCRIBED BELOW,

                                     'parent'   : OUTPUT ID AS A STRING,
                                     'programme': (VALID SID AS STRING, VALID CID AS A STRING, [ { 'type'  : A MEDIA COMPONENT TYPE AS A STRING,
                                                                                                   'mcid'  : A MEDIA COMPONENT ID,
                                                                                                   }, 
                                                                                                 ...]),
                                     'app'      : (VALID SID AS STRING, VALID CID AS A STRING, [ CONTROL_PROFILE_AS_STRING, ...] ),
                                     'playback' : (STRING ONE OF ('play'|'pause'|'stop'),
                                                   SPEED AS A FLOAT), 
                                     'playhead' : None or { 'absolute' : BOOLEAN,
                                                            'position' : FLOAT,
                                                            'position_precision' : INT NUMBER OF DECIMAL PLACES,
                                                            'position_timestamp' : ISO FORMAT TIME WHEN POSITION WAS CORRECT,
                                                            
                                                            OPTIONALLY,
                                                            'length'   : FLOAT,
                                                            },
                                     },
             ...}


             The 'programme' element of an output object will be set by the code of this library in response to
             PUT requests to the relevent output resource. A 'selector' MUST also respond to the calls:

               def select_content(sid,cid)
               def select_programme(sid,cid,components=[])
               def select_app(sid,cid)

             where the first method is called to select a new piece of content without specifying its type, and the second and third
             are used when the type is known. Any exception raised by these methods other than the specific UC Exceptions will result
             in a 500 error being returned to a POST request.
             """

        self.outputs = outputs

    def set_main_output(self,id):
        """This function is used to set the main output. It takes as a parameter a single string 
        which contains the output-id of the output to be used as the main one."""

        id = str(id)

        for out in self.outputs:
            if out != id and self.outputs[out]['main']:
                self.outputs[out]['main'] = False

        self.outputs[id]['main'] = True
        self.main_output = id

    def set_source_lists(self, source_lists):
        """This method is used to set a data source which contains information about the
        source-lists implemented on the box. 

        This should be a dictionary-like object conforming to the format:

                { LIST ID AS STRING : { 'id'          : LIST ID AS STRING,
                                        'description' : LIST DESCRIPTION AS A STRING,
                                        'sources'     : ( SID AS STRING,
                                                          ...
                                                          ),

                                         OPTIONALLY
                                         'logo-href'  : LOGO-HREF AS STRING,
                                       ),             
                  ... 
                }
        """
        self.source_lists = source_lists

    def set_sources(self,sources):
        """This method is used to set a data source which contains information about the
        box's known sources. 

        This should be a dictionary-like object conforming to the format:

           { SID AS STRING : { 'id'   : SID AS STRING,
                               'name' : SOURCE NAME AS STRING,
                               'rref' : URI AS STRING -- MUST BE IN CORRECT FORMAT, IE. NO LEADING /,
                               
                               OPTIONALLY
                               'sref'        : URI AS STRING,
                               'live'        : BOOL,
                               'linear'      : BOOL,
                               'follow-on'   : BOOL,
                               'owner'       : OWNER NAME AS STRING,
                               'lcn'         : LOGICAL CHANNEL NUMBER AS INTEGER,
                               'logo-href'   : URI AS STRING,
                               'owner-logo-href'  : URI AS STRING,
                               'default-cid' : PID AS STRING,
                               'links'       : ( { 'href'        : URI AS STRING,
                                                   'description' : STRING },
                                                 ... )
                             },
                             ...
            }            
        """
        self.sources = sources

    def set_controls(self,controls):
        """This method is used to set which control profiles the box responds to. The parameter must be a 
        list-like object which behaves like an object of the form:

         controls = [ PROFILE ID AS STRING,
                    ...]
        """
        self.controls = controls

    def set_content(self,content):
        """This method is used to set a source for content metadata. The parameter must be an
        object which responds to the methods:

        def get_output(term,params)
        def get_sources(term,params)
        def get_text(term,params)
        def get_gcid(term,params)
        def get_gsid(term,params)
        def get_gaid(term,params)
        def get_categories(term,params)

        where each "term" parameter is either a string id (in the case of output, gcid, gsid, gaid) or a list
        of strings (in the remaining cases) which will all have been depercentage encoded already if necessary.

        In all cases the "params" parameter is a dictionary which may contain any of the keys:
                                     'results',     # integer
                                     'offset',      # integer
                                     'sid',         # list of strings
                                     'cid',         # list of strings
                                     'series-id',   # list of ids
                                     'gcid',        # list of ids
                                     'gsid',        # list of ids
                                     'gaid',        # list of ids
                                     'category',    # list of ids
                                     'text',        # list of strings
                                     'field',       # list of strings containing either "title" or "synopsis"
                                     'interactive', # bool
                                     'AV',          # bool
                                     'start',       # datetime.datetime
                                     'end',         # datetime.datetime
                                     'days'         # integer
        each of which stores a local 
        
        The returned objects should be list of 2-tuples containing a dictionary-like objects of the form:

                        { 'sid' : A SID AS A STRING,
                          'cid' : A CID AS A STRING,
                          
                          OPTIONALLY                     
                          'synopsis' : A STRING,
                          'title' : A STRING,
                          'cref'  : URI AS A STRING,
                          'available-from' : datetime.datetime,
                          'available-until': datetime.datetime,
                          'presentable-from' : datetime.datetime,
                          'presentable-until': datetime.datetime,
                          'logo-href': A URI AS A STRING,

                          'interactive' : A BOOLEAN,
                          'presentable' : A BOOLEAN,
                          'acquirable'  : A BOOLEAN,
                          'extension'   : A BOOLEAN,

                          'start' : datetime.datetime,
                          'duration' : NUMBER OF SECONDS * 10000 AS AN INT,
                          'global-series-id' : A GLOBAL SERIES ID AS A STRING,
                          'series-id' : A SERIES ID AS A STRING,
                          'global-content-id' : A GLOBAL CONTENT ID AS A STRING,
                          'global-app-id' : A GLOBAL APP ID AS A STRING,
                          'presentation-count' : AN INTEGER
                          

                          'presentable-from'  : datetime.datetime,
                          'presentable-until' : datetime.datetime,

                          'acquirable-from'   : datetime.datetime,
                          'acquirable-until'  : datetime.datetime,

                          'last-presented' : datetime.datetime,
                          'last-position' : A DECIMAL NUMBER OF SECONDS,

                          'assosciated-sid' : A SID AS A STRING,
                          'assosciated-cid' : A CID AS A STRING,

                          'media-components' : { MCID AS A STRING : { 'id'      : MCID AS A STRING,
                                                                      'type'    : TYPE AS A STRING,
                                                                      'name'    : NAME AS STRING,
                                                                      
                                                                      OPTIONALLY
                                                                      'default'  : BOOLEAN,
                                                                      'aspect'   : AN ASPECT RATION STRING,
                                                                      'lang'     : A LANGUAGE STRING,
                                                                      'vidformat' : A FORMAT AS A STRING,
                                                                      'intent'   : AN INTENT AS A STRING,
                                                                      'colour'   : BOOLEAN,
                                                                    },
                                                  ...
                                                },
                          'controls' : [ CONTROL_PROFILE_ID AS A STRING,
                                         ... ],
                          'links'      : ( { 'href' : A URI AS A STRING,
                                             'description' : STRING,
                                             },
                                           ...
                                           ),
                          'categories' : ( CATEGORY-ID AS STRING,
                                           ...
                                           ),
                          }

        and a boolean indicating if there are more results available.
        """                      
        self.content = content

    def set_categories(self,categories):
        """This method is used to provide the information used by the "uc/categories" resource (and also the
        uc/search resource). The parameter here is a dictionary-like object of the following format:

        { CATEGORY-ID AS STRING : { 'parent'    : CATEGORY-ID AS STRING,
                                    'name'      : STRING,
                                    
                                    OPTIONALLY
                                    'id'        : CATEGORY-ID AS STRING, # PRESENT ONLY IF TO BE USED IN API,
                                    'logo-href' : URI AS STRING,
                                    },
                                    ...
          }

        All nodes here must be given a unique CATEGORY-ID string (as a key in the dictionary). Those which 
        will be considered to have a category-id according to the API must also have THE SAME string as the
        value for their 'id' key. CATEGORY-ID strings which are not used by the API may be any string, those
        which are to be used by the API (ie. those which also appear as the value for the 'id' key) must conform
        to the requirements of an id-component according to the UC Spec.
        """
        self.categories = categories

    def set_button_handler(self,button_handler):
        """This method is used to assign an object to process simulated button pushes (as used by uc/remote resource).
        It must respond to the method:

          def send_button_press(code, output=None)

        Which takes a keycode as a string as its first parameter, and as an optional second paramter takes an output-id.
        """
        self.button_handler = button_handler

    def set_acquirer(self,acquirer):
        """This method is used to set the object used by the uc/acquisitions resource to book and cancel acquisitions.

        This object MUST have methods of the form:

                  def acquire (global_content_id=None,cid=None,sid=None,series_id=None,priority=False)
                  def cancel (acquisition_id)

        which are used to book and cancel acquisitions respectively. 

        acquire MUST return None if it fails, and the acquisition-id of the newly created acquisition if it succeeds. 
        cancel need not return anything.
        """
        ResourceHandlers.UCAcquisitionsResourceHandler.acquirer = acquirer
        ResourceHandlers.UCAcquisitionsIdResourceHandler.acquirer = acquirer

    def set_application_activater(self,installer):
        """This method is used to set the object used by 'uc/apps' to activate applications.

        This object MUST have a method of the form:

        def activate(sid,cid)

        which takes a sid and cid, and returns the app-id of the newly activated app (which may be the same), or raises an
        apropriate exception. 

        It must also respond to a method:
        
        def remove(aid)

        which must either return or throw an exception.
        """

        ResourceHandlers.UCAppsResourceHandler.application_installer = installer

    def set_security_scheme(self, auth):
        """This method switches the server to operate with the security scheme if the parameter is True
        and not to do so if the parameter is False.
        """
        self.log_message("Trying to set security scheme to %s",auth)
        self.log_message("Current Security Scheme: %s", ResourceHandlers.UCBaseResourceHandler.data['security'])
        if auth != ResourceHandlers.UCBaseResourceHandler.data['security']:
            ResourceHandlers.UCBaseResourceHandler.data['security'] = auth
            self.log_message("New Security Scheme: %s", ResourceHandlers.UCBaseResourceHandler.data['security'])
            if auth:
                self.handler_class.auth = True
                self.realm = 'UCSecurity@%s' % self.uuid
                self.handler_class.realm = self.realm
            else:
                self.handler_class.auth = False

    def set_resource_data(self,rref,datum):
        """This method is used to set the data used to backup resources which don't have their own set_ methods.

        The parameters are a relative URI of a resource and a dictionary-like object which can be used by that 
        resource to provide its necessary data. 

        The formats for the various resources supported by this library are:


        'uc':

           { 'resource' : 'uc',
             'name'     : SERVER NAME AS A STRING,
             'security' : BOOLEAN,
             'id'       : A SERVER ID IN STRING FORM,
             'version'  : STRING OF FORM [0-9]+\.[0-9]+\.[0-9]+
             
             OPTIONALLY
             'logo'     : NONE OR A URI AS A STRING
             }

         The server will automatically adjust the value of the 'security' parameter if the security setting is
         switched on or off using the server's methods.


        'uc/feedback':
          
          { 'resource' : 'uc/feedback',
            'feedback' : STRING,
            }
            
         


        'uc/acquisitions':

             { 'resource' : 'uc/acquisitions',
               'content-acquisitions' : {ACQUISITION_ID AS STRING : { 'sid' : SID AS STRING,
                                                                      'id' : CID/AID AS STRING,

                                                                      OPTIONALLY
                                                                      'global-content-id' : CONTENT-ID AS STRING,
                                                                      'series-id'  : SERIES-ID AS STRING,
                                                                      'series-link': BOOL,
                                                                      'priority'   : BOOL,
                                                                      'start'      : datetime.datetime,
                                                                      'end'        : datetime.datetime,
                                                                      'speculative': BOOL
                                                                      'active'     : BOOL
                                                                      },
                                                                        ...},
               'series-acquisitions' : {ACQUISITION_ID AS STRING : { 'series-id' : SERIES-ID AS STRING,
                                                                     'id' : ACQUISITION_UD AS STRING
                                                                    
                                                                     OPTIONALLY
                                                                     'speculative' : STRING,
                                                                     'acquisition-contents' : (KEY AS A STRING,
                                                                     ...),
                                                                 },
                                    ...}
             }

        The server itself will never alter the values in this object, an individual implementor needs to update them as
        required.




    'uc/storage':

             { 'resource' : 'uc/storage',
               'items'    : {CID AS STRING : { 'cid'          : CID AS A STRING,

                                               OPTIONALLY:
                                               'sid'          : SID AS A STRING,
                                               'global-content-id'   : GLOBAL-CONTENT-ID AS STRING,
                                               'created-time' : ISO-DATETIME STRING,
                                               'size'         : INTEGER IN BYTES,
                                               },
                             ...,
                             }
               
               OPTIONALLY,
               'size'    : INTEGER IN BYTES,
               'free'    : INTEGER IN BYTES,
             }

        The server will call del object['items'][pid] in response to DELETE requests to uc/storage, so this object should 
        handle calls to __delete__(self,key) correctly.
      


     'uc/credentials':

             { 'resource' : 'uc/credentials',
               'clients'  : { CID AS STRING : CN AS STRING,
                              ...},
             }

      Entries in uc/credentials are automatically added and removed by the server as credentials are used and activated
      by the HTTP Server, so it's unlikely that the individual implementor will need to replace this objevct except to 
      monitor such changes.


      'uc/apps':
             { 'resource' : 'uc/apps',
               'apps'     : { GCID AS STRING : { 'id' : CID AS STRING,
                                                 'sid' : SID AS STRING,
                                                   
                                                 OPTIONALLY:
                                                 'extension'      : AN EXTENSION HANDLING OBJECT (SEE BELOW),
                              ...
                              }
               }

      if present the 'extension' object must be an object which responds to a method:

        def request(path,
                    verb,
                    headers,
                    parameters,
                    security,
                    body)

      where path is a tuple of strings containing the path elements of the request not counting 'uc', 'apps', '{id}', and 
      'ext', verb is a string containing an HTTP Verb, headers is a dictionary of strings referenced by strings containing
      the HTTP headers, parameters is a dictionary of lists of strings indexed by strings containing the query parameters,
      security is a boolean value (True if valid security credentials were used, False if none were required), and body is
      a string containing the request body. The method MUST return a tuple of an integer status code, a dictionary of strings 
      referenced by strings containing the response headers, and a string containing the response body.

      If an extension object is present for a particular app then that app will be listed as remote enabled, if not then it
      won't.

      
      'images':
      
            { 'resource' : 'uc/images',
              'files'    : { TUPLE OF PATH ELEMENT STRINGS : ( FILENAME AS A STRING,
                                                               MIME-TYPE AS A STRING),
                             ...},
              }
              
       Entries in the 'files' disctionary should all be indexed by tuples like ('images','foo','bar','baz') and the entries
       should be tuples like ( '/usr/share/foo-bar-baz.jpg','image/jpeg' ) which would cause any GET request to 'images/foo/bar/baz'
       to return a 200 code, a Content-Type of 'image/jpeg' and a response body equal to the content of the file 
       '/usr/share/foo-bar-baz.jpg' on the machine on which the server is running.

       The URI 'http://{server IP Address}:48875/images/foo/bar/baz' could then be set as the value of a 'logo-href' entry
       elsewhere on the server.
                                                               
        """
        self.data[rref] = datum        

    def add_option(self, option):
        """This method is used to add an optional resource to this server. 
        
        The valid values for the parameters are the standard optional resources:
        'power', 'time', 'events', 'outputs', 'remote', 'feedback', 'sources', 'source-lists', 'categories', 'search', 
        'acquisitions', 'storage', and 'credentials';
        and also one other option 'images' which adds a resource 'images' to the base of the server (outside of the 'uc' tree).
        The 'images' resource is governed by the data settings for it (which are set using 'set_resource_data' as usual) and 
        will serve files in response to GET requests. It's intended that this be used to provide logos where permitted by the
        UC spec.
        """
        # The actual details for the optional resources can be found in UCServer.ResourceHandlers in the global member
        # 'resource_options' The format of that structure is as a dictionary of 'option-names' indexing tuples of 'paths' 
        # and data structures to be inserted into the main 'resources' look-up table.
        
        if option not in ResourceHandlers.resource_options:
            print "Invalid Option: %r" % option3
            raise KeyError

        self.options.append(option)

        path   = ResourceHandlers.resource_options[option][0]
        option = ResourceHandlers.resource_options[option][1]

        tree = ResourceHandlers.resources
        for i in range(0,len(path)):
            key = path[i]
            if key in tree:
                tree = tree[key][1]
            elif i == len(path)-1:
                tree[key] = option
            else:
                raise KeyError

    def add_extra_resource(self,path,handler_class,retain=True):
        """This method is used to add an extra resource to the server which is not covered by the standard resources in
        UCServer.ResourceHandlers. 

        The first parameter is a tuple or list of strings containing the path elements. So to add a resource at 'extra/stuff'
        one would use the path tuple ['extra','stuff']. There are two special values which can be used for these path segments.
        If a path segment is '*' then the given path segment can take any value (so a class assigned to the path ['extra', '*']
        would be used to handle any request to a URI of the form 'extra/{something}', and a class assigned to the path ['extra',
        '*','cheese'] would be used to handle requests to any URI of the form 'extra/{something}/cheese'. If a path segment of 
        '**' is used as the last entry in the path to which a class is assigned then that class will be used to handle any request
        to a path which would match if that segment were a '*' *and*also*any*subresource*. So a class assigned to ['extra','**'] 
        would be used to handle any request to 'extra/{something}', and request to 'extra/{something}/{else}', any request to 
        'extra/{something}/{else}/{again}' etc ...

        The second parameter is a class which must inherit from UCServer.ResourceHandlers.UCResourceHandler. Instances of this class 
        will be created to handle all requests to resources which match the specified path.        

        The optional third parameter should be set to False to force this method to discard any subresources of the resource 
        identified by the path.


        When a new class is assigned to a resource which already has a class assigned to it any subresources already assigned for that
        resource are retained unless the optional third parameter is set.
        """
        tree = ResourceHandlers.resources
        for i in range(0,len(path)):
            key = path[i]
            if i == len(path)-1:
                subresources = dict()
                if key in tree and retain:
                    subresources = tree[key][1]
                tree[key] = (handler_class,subresources)
            else:
                if key in tree:
                    tree = tree[key][1]
                else:
                    tree[key] = (ResourceHandlers.UCResourceHandler, dict())
                    tree = tree[key][1]

    def notify_change(self,resource):
        """This method takes the relative URI of a resource as a parameter and triggers a notifiable
        change in the indicated resource. This can be used for resources which do not exist.
        """
        # All the actual notifiable change handling code is found in UCServer.ResourceHandlers.UCEventsResourceHandler
        ResourceHandlers.UCEventsResourceHandler.notify_change(resource)

    def authenticated(self,client_id):
        """This method is called by code in the HTTP Server itself to indicate that a particular pending
        client-id has been made permanent. It should never be called by individual server implementors.
        """
        client_name = dict(self.handler_class.client_list())[client_id]

        if client_id not in ResourceHandlers.UCCredentialsResourceHandler.data['clients']:
            ResourceHandlers.UCCredentialsResourceHandler.data['clients'][client_id] = client_name
        if self.CPUsedCallback is not None:
            self.CPUsedCallback()

    def add_client_id(self, client_id, LSGS, CN):
        """This method is called with a client-id, client name and LSGS. It adds them as pending
        credentials for this server.
        """

        if ResourceHandlers.UCBaseResourceHandler.data['security']:
            self.handler_class.add_client_id(client_id,LSGS,CN)
            if self.add_pending_credentials_callback is not None:
                self.add_pending_credentials_callback()
        else:
            raise Exception, "Tried to add a client-id on a sever which does not support the security model"

    def remove_client_id(self,client_id):
        """This method removes a client-id from those valid for accessing this server.
        """
        self.handler_class.remove_client_id(client_id)
        if client_id in ResourceHandlers.UCCredentialsResourceHandler.data['clients']:
            del ResourceHandlers.UCCredentialsResourceHandler.data['clients'][client_id]

    def clear_pending_credentials(self):
        """This method clears the current pending client-ids for the server, making it no longer valid for future
        connections.
        """
        self.handler_class.clear_pending_credentials()

    def set_SSS(self,SSS):
        """This method is called to set an SSS as active."""
        self.SSS = SSS

    def clear_SSS(self):
        """This method is called to remove any current SSS."""
        self.SSS = None

    def notification_id(self):
        """This method returns the server's current notification id (as a string).
        It's used internally by the code which handles the uc/events resource but it could be used elsewhere.
        """
        # The lock is used to ensure thread safety.
        with self.notification_id_lock:
            if self.notification_id_file is None:
                try:
                    self.notification_id_file = open(self.notification_id_filename,'r+')
                except:
                    self.notification_id_file = open(self.notification_id_filename,'w')
            self.notification_id_file.seek(0)
            try:
                id = self.notification_id_file.readline()
                if id == "":
                    raise ValueError
                else:
                    id = int(id,16)
            except:
                # If the reading of a valid notification id from the persistant storage
                # fails then we fall-back to using the time to set it.
                id = int(time.time())*(1 << 32)

                self.notification_id_file.seek(0)
                self.notification_id_file.write("%016x\n" % id)

        return "%016x" % id

    def increment_notification_id(self):
        """This method increments and returns the server's current notification id (as a string).
        It's used internally by the code which handles the uc/events resource but it could be used elsewhere.
        """
        with self.notification_id_lock:
            id = int(self.notification_id(),16)

            id = (id + 1)%(1 << 64)

            self.notification_id_file.seek(0)
            self.notification_id_file.write("%016x\n" % id)

        return "%016x" % id

    def serve_forever(self):
        """This method is called when the server is to be run, it will never return, and will only
        exit on an exception.
        """
        global zc_server

        try:
            # If internal Zeroconf support is being used then advertise the server using it
            if self.zeroconf:
                import Zeroconf
                
                try:
                    local_ip = socket.gethostbyname(currentipaddress())
                except:
                    local_ip = socket.gethostbyname(self.address)

                zc_server = Zeroconf.Zeroconf(bindaddress=local_ip)

                local_ip = socket.inet_aton(local_ip)

                zc_server.registerService(Zeroconf.ServiceInfo('_universalctrl._tcp.local.',
                                                               (str(self.name).replace('.','_') 
                                                                + '._universalctrl._tcp.local.'),
                                                               address=local_ip,
                                                               port=self.port,
                                                               weight=0, priority=0,
                                                               properties={'server_id'   : str(self.uuid)}
                                                               ),
                                          ttl=30
                                          )

            self.server.serve_forever()
        except:
            self.server.socket.close()
            raise

    def log_message(self, format, *args):
        """This method takes a format string and any necesary args to fill it out and logs that message to
        the logfile specified when this server was instantiated, or (if no file was specified) to standard
        out. In general this should be used for outputing debug messages and informative log messages, 
        and 'print' should not!
        """
        # We make use of the HTTPHandler class's classmethod which logs messages to the logfile.
        return self.handler_class.log_message(format, *args)





# The DataSourceProxy is used to give a convenient mechanism for the server to provide access to the data
# which underpinns the UC server. It's unlikely that this will ever be used directly by anyone, and in fact
# can probably be written out without too many changes to the UCServer code.

class DataSourceProxy:
    """This class gives access to the dictionary-like datasources of the various resources.

    Details of the formats used can be seen in the documentation for the UCServer.UCServer.set_resource_data
    """

    def __getitem__(self, key):
        """Pass in a full rref as a key and return the "data" member of the asosciated class,
        or throw a KeyError if none exists.

        Details of the formats used can be seen in the documentation for the UCServer.UCServer.set_resource_data
        """
        
        path = map(urllib.unquote,key.strip('/').split('/'))
        obj  = self.__walk_tree(path,ResourceHandlers.resources)
        if obj is None:
            raise KeyError
        return obj.data

    def __setitem__(self, key, value):
        """Pass in a full rref as a key and set the "data" member of the asosciated class,
        or throw a KeyError if none exists.

        Details of the formats used can be seen in the documentation for the UCServer.UCServer.set_resource_data
        """

        path = map(urllib.unquote,key.strip('/').split('/'))
        obj  = self.__walk_tree(path,ResourceHandlers.resources)
        if obj is None:
            raise KeyError
        obj.data = value

    def __walk_tree(self,path,tree):
        """This local function simply recursively walks the resources tree looking for the correct object."""

        if path[0] in tree:
            if len(path) == 1:
                return tree[path[0]][0]
            else:
                return self.__walk_tree(path[1:],tree[path[0]][1])
        elif '*' in tree:
            if len(path) == 1:
                return tree['*'][0]
            else:
                return self.__walk_tree(path[1:],params,tree['*'][1])
        else:
            return None

        


        

# Universal Control Server - Resource Handlers
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
Handling of requests to individual resources for the UCServer library.

This module provides the classes and data structures which the server uses
to respond to specific requests to particular resources.

The model used for modeling the resources themselves is pretty simple. Each
time a request is made to a resource an instance of a handler class is
instantiated.  The classes all inherit from the class UCResourceHandler. 
These classes should never be manually instantiated by a particular server
implementation since the instantiation is handled by the do method of the
UCServer.HTTPHandling.UCHandler class, which is itself instantiated
automatically in response to a request by the HTTP server.



Developers wishing to develope their own extra resources in addition to the
standard ones provided by this module should create classes which inherit
from UCResourceHandler -- and should consult the documentation for that
class for details on how to do so.

To add such a resource to the server make use of the UCServer.UCServer
class's "add_extra_resource" method.



The module-scope variable uc_server will always hold the current global
UCServer instance if one exists, and hence can be used to make UCServer
calls, such as "notify_change".
"""

__version__ = "0.6.0"

#Standard Python imports
import socket
import urllib
import time
import datetime
import threading
import xml.dom.minidom
import xml.sax.saxutils as saxutils
import traceback
import re
import random

#imports from elsewhere in this package
from Exceptions import *
from Exceptions import UCException


# This global data member will hold the global singleton UCServer.UCServer instance, which will be set by methods
# in UCServer.__init__ when before any methods in this module are called. 
uc_server = None

sysrandom = random.SystemRandom()

class UCResourceHandler:
    """This abstract class is used as a base from which all other resource handlers are descended. It should never
    be used directly, only subclasses of it should be instantiated, and even then only automatically by the server
    never manually.

    Every subclass will, when instantiated, have member variables handler, path, query, and params. 

      handler -- is set to the UCHandler (descended from BaseHTTPServer.BaseHTTPRequestHandler) instance which 
                 instantiated this class
      path    -- is an n-tuple of strings containing the path elements of the requested path
      query   -- is a string containing the entire original query string
      params  -- is a dictionary of lists of strings, indexed by strings. It contains all of the
                 query parameters passed to the request.

    Concrete subclasses should also fill out the class variables:

      representation -- a format string containing the template for the returned representation for a GET request.
      data           -- a dictionary containing the elements which will be used to fill in the format string.
      auth           -- a boolean -- set to True if the resource requires authentication, and to False if it doesn't
                        (digest authentication is only employed if this member AND the auth member of the server object
                        are BOTH set to True)

    Concrete subclasses may wish to override the default member functions do_GET, do_POST, do_PUT, do_DELETE,
    and notify. See below for what the default implementations do.

    The class member data can be replaced at run-time by using the UCServer.UCServer method "set_resource_data" with the
    relative URI of the resource which a particular class in bound to (to bind a new class to a resource URI use the 
    UCServer.UCServer method "add_extra_resource"), so subclasses may assume that the data element behaves like a 
    dictionary, but should not test that it actually is of type dict using isinstance."""
    
    representation = None 
    data = { 'resource' : '' }
    auth = True

    lock = threading.RLock() 

    def __init__(self,handler,path,query,params,head=False):
        """The default implementation of __init__ should almost certainly be left as is in all subclasses. It
        fills out the member variables as described above. In particular since it is called by the HTTP handling
        code all subclasses must take the same parameters for their constructors.

        The first paremetsr is the UCServer.HTTPHandling.UCHandler instance which instantiated this class. This class 
        descends from BaseHTTPServer.BaseHTTPRequestHandler, and can be assumed to respond to the interface of that 
        class (in addition to some other methods mentioned below).

        The second parameter is a list of strings containing the path elements of the URI used to make the request
        (e.g. a request to 'uc/foo/bar/baz' would give ['foo','bar','baz'] ).

        The third parameters is a dictionary of lists of strings which contain the query parameters passed in, (e.g.
        a request to 'uc/foo?bar=baz&tre=ogg&bar=pip' would give {'bar':['baz','pip'], 'tre':['ogg',]} ).

        These are then used to fill out the member variables self.handler, self.path, elf.query, and self.params. The variable
        self.resource is filled out with the value of self.data['resource'] appended with a query string reconstructed
        from the params array.
        """
        self.handler = handler
        self.path = path
        self.query = query
        self.params = params
        self.resource = self.data['resource']+self.query
        self.head = head

    def reconstructParams(self):
        """This method reconstructs the query string used to make the request.
        """
        return saxutils.escape(self.query)

    def do_GET(self):
        """This method is called by UCHandler whenever a GET request is made to this resource. 
        The default implementation checks if self.representation is None. If it is then it returns
        405 (method not implemented). If it is not then it checks authentication if self.auth is True
        and if that succeeds then it sends a 200 response along with the contents of self.representation
        filled out using the (entity-coding escaped) contents of the dictionary self.data.

        This method should be overriden in all but the simplest subclasses, all overriden versions should
        check for authentication if required using the code:

            if self.auth:
                if not self.handler.check_authentication(''):
                    return
                           
        The response body can be sent back to the client by using the following code:

            self.return_body(saxutils.escape(self.representation % escape_dict(self.data)))
            return

        Or something very similar. In the above example we use the template stored in self.representation 
        and fill it out with the entries in the dictionary self.data. This is the standard behaviour for 
        very simple requests, but for more complex ones, or ones where the dictionary contains values which
        cannot be automatically converted to strings the returned representation should be constructed by other 
        means.

        Using saxutils.escape is essential before returning any values, as this will ensure that invalid
        characters are correclt entity-encoded. escape_dict merely runs this on all the entries in a 
        dictionary.
        """

        if self.representation is not None:
            if self.auth and not self.handler.check_authentication(self.handler.realm):
                return

            self.return_body(saxutils.escape(self.representation % escape_dict(self.data)))
            return

        self.handler.send_error(405)
        return

    def do_PUT(self):
        """This method is called by UCHandler whenever a PUT request is made to this resource. The method
        implementation simply returns a 405 (method not implemented).

        This method should be overriden in all but the simplest subclasses, all overriden versions should
        check for authentication if required using the code:

            body = self.retrieve_body()
            if self.auth:
                if not self.handler.check_authentication(body):
                    return

        the request body will be stored as a string in the 'body' variable. It can be turned into
        an XML 'dom' object with the call:

            body = self.parse_body(body)
        
        which will read the request body into an xml dom object, and if there is a parsing error will 
        return a 400 code.

        A response can be sent back to the client by using the following code:

            return self.return_body(body)

        """

        self.handler.send_error(405)
        return

    def do_POST(self):
        """This method is called by UCHandler whenever a POST request is made to this resource. The method
        implementation simply returns a 405 (method not implemented).


        This method should be overriden in all but the simplest subclasses, all overriden versions should
        check for authentication if required using the code:

            body = self.retrieve_body()
            if self.auth:
                if not self.handler.check_authentication(body):
                    return

        the request body will be stored as a string in the 'body' variable. It can be turned into
        an XML 'dom' object with the call:

            body = self.parse_body(body)
        
        which will read the request body into an xml dom object, and if there is a parsing error will 
        return a 400 code.

        A response can be sent back to the client by using the following code:

            return self.return_body(body)

        """

        self.handler.send_error(405)
        return

    def do_DELETE(self):
        """This method is called by UCHandler whenever a DELETE request is made to this resource. The method
        implementation simply returns a 405 (method not implemented).

        This method should be overriden in many subclasses, all overriden versions should
        check for authentication if required using the code:

            if self.auth:
                if not self.handler.check_authentication(''):
                    return

        A response can be sent back to the client by using the following code:

            self.return_bodyless()
            return

        """

        self.handler.send_error(405)
        return

    def standby_do_GET(self):
        """This method is called by UCHandler whenever a GET request is made to this resource whilst in standby
        mode. The default implementation returns 405.
        """
        self.handler.send_error(405)
        return

    def standby_do_PUT(self):
        """This method is called by UCHandler whenever a PUT request is made to this resource whilst in standby.
        The method implementation simply returns a 405 (method not implemented).
        """
        self.handler.send_error(405)
        return

    def standby_do_POST(self):
        """This method is called by UCHandler whenever a POST request is made to this resource whilst in standby. 
        The method implementation simply returns a 405 (method not implemented).
        """
        self.handler.send_error(405)
        return

    def standby_do_DELETE(self):
        """This method is called by UCHandler whenever a DELETE request is made to this resource. whilst in standby.
        The method implementation simply returns a 405 (method not implemented).
        """
        self.handler.send_error(405)
        return

    def return_body(self,data):
        """This method returns a 200 status and the supplied string as a body. Unless the request was really a 
        HEAD, in which case no body is returned, but all headers are set as if it had been."""
        
        size = len(data)

        self.handler.send_response(200)
        self.handler.send_header('Content-Length',size)
        self.handler.send_header('Cache-Control','no-cache')
        self.handler.send_header('Content-Type','application/xml')
        self.handler.end_headers()

        if not self.head:
            self.handler.wfile.write(data)

        return        

    def return_bodyless(self):
        """This method returns a 204 status and no body."""
        
        self.handler.send_response(204)
        self.handler.send_header('Cache-Control','no-cache')
        self.handler.end_headers()
        return


    def retrieve_body(self):
        """This method retrieves the body of the request"""
        
        try:
            if "Content-Length" in self.handler.headers:
                bytes = int(self.handler.headers["Content-Length"])
                return self.handler.rfile.read(bytes)
        except:
            print traceback.format_exc()
            raise InvalidSyntax("Could not read body")
        return ''

    def parse_body(self,body):
        """This method parses the body of the request as an XML dom"""
        
        try:
            return xml.dom.minidom.parseString(body)
        except:
            raise InvalidSyntax("Could not parse XML")


    @classmethod
    def notify(cls):
        """This class method called the notify_change method of the UCEventsResourceHandler class with the 
        class variable data['resource'] as a parameter. This parameter should always be set to the relative 
        URI of this resource if this method is not being overridden (and in most cases this method does not 
        need to be overriden."""

        try:
            UCEventsResourceHandler.notify_change(cls.data['resource'])
        except:
            return


class UCBaseResourceHandler (UCResourceHandler):
    """The resource handler for the resource 'uc'.
    
    The data class variable may be replaced with a dictionary-like object of the following form:
    
    data = { 'resource' : 'uc',
             'name'     : STRING,
             'security' : BOOLEAN,
             'id'       : AN SID IN STRING FORM,
             'version'  : STRING OF FORM [0-9]\.[0-9]+\.[0-9]+
             
             OPTIONALLY
             'logo'     : NONE OR A URI AS A STRING
             }
    
    """

    representation = u"""\
<response resource="%(resource)s"><ucserver name="%(name)s" security-scheme="%(security)s" server-id="%(server-id)s" version="%(version)s"%(logo-href)s%(content)s></response>
"""

    data = { 'resource' : 'uc',
             'name'     : "UC Server",
             'security' : False,
             'id'       : "00000000-0000-0000-0000-000000000000",
             'version'  : saxutils.escape(str(__version__)),
             'logo'     : None}

    auth = False

    def do_GET(self):
        """This method does not check authentication, and inserts the logo-href attribute into the output only id the 
        'logo' key in data is set."""
        
        global uc_server
        global resource_options

        data = dict()
        data['resource'] = saxutils.escape(str(self.resource))
        data['name']     = saxutils.escape(unicode(uc_server.name))
        data['logo-href']= ''
        data['security'] = saxutils.escape(bool_to_xml_string(self.data['security']))
        data['server-id']= saxutils.escape(str(uc_server.uuid))
        data['version']  = saxutils.escape(str(self.data['version']))

        options = [ u'<resource rref="%s"/>' % saxutils.escape('/'.join(resource_options[option][0])) 
                    for option in uc_server.options 
                    if option in resource_options and resource_options[option][0][0] == 'uc' ]
        
        content = '/'
        if options:
            content = u'>%s</ucserver' % (u''.join(options),)

        if 'logo' in self.data and self.data['logo'] is not None:
            data['logo-href'] += u' logo-href="%s"' % saxutils.escape(self.data['logo'])

        data['content'] = content

        return self.return_body(self.representation % data)

    def standby_do_GET(self):
        return self.do_GET()

class UCSecurityResourceHandler (UCResourceHandler):
    """This class handles requests to the 'uc/security' resource."""

    representation = None
    data = { 'resource' : 'uc/security' }

    def do_GET(self):
        """This method checks authentication and if successful returns 204."""

        if not self.handler.check_authentication(''):
            return

        self.return_bodyless()

    def do_POST(self):
        """This method handles the handshaking mechanism for the security scheme."""

        SSS = uc_server.SSS

        if SSS is None:
            raise CannotFind

        if 'client-id' not in self.params or 'client-name' not in self.params:
            raise InvalidSyntax

        client_id   = self.params['client-id'][0]
        client_name = unpctencode(self.params['client-name'][0])

        if not re.match(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',client_id):
            raise InvalidSyntax

        LSGS = [ sysrandom.randint(0,0xFF) for _ in range(64) ]
        uc_server.add_client_id(client_id,''.join([ '%c' % x for x in LSGS]), client_name)

        body = '<response resource="%s"><security key="%s"/></response>' % (self.resource,
                                                                            ''.join([ '%02x' % (x ^ SSS) for x in LSGS ]))
        
        return self.return_body(body)
        

class UCEventsResourceHandler (UCResourceHandler):
    """This class handles the 'uc/events' resource. It maintains a local list of notified changes with notification-ids
    as a class variable and resources may be added to that list by calling its notify_change class method. All
    the multithreaded requirements for this class' behaviour are handled internally, and a calling class shouldn't
    have to worry about them.

    current notification-id is handled in fact by the UCServer object, and kept in an on-disk file in order to implement
    the sort of long-term storage which is recommended by the spec."""

    notifiable_changes = dict()

    waiting = []

    timeout = 60.0

    lock = threading.Condition(threading.RLock())

    representation = """\
<response resource="%(resource)s"><events notification-id="%(notification_id)s"%(content)s></response>
"""

    data = { 'resource' : 'uc/events' }

    def do_GET(self):
        """This method handles GET requests. It returns an error if no 'since' query parameter is present, or if
        it is incorrectly formatted. It uses the self.check_events method to check for notifiable changes since 
        the given timestamp. If any are found then it returns as normal. If none are found then the thread waits 
        until awakened by a notification, or until a timeout occurs. The length of the timeout is controlled by 
        the class variable timeout and is measured in seconds, the default value is 360.0.
        """
        
        def nid_gt(a,b):
            a = int(a,16)
            b = int(b,16)

            return ((a > b and (a-b) <= (1 << 63)) or (b > a and (b-a) > (1 << 63)))

        self.handler.log_message("Beginning GET request to 'uc/events'")

        if not self.handler.check_authentication(''):
            return

        content = ''

        now = uc_server.notification_id()
        try:
            since = self.params['since'][0]
            if nid_gt(since,now):
                self.handler.log_message("Value Error: %s > %s ",since,now)
                raise ValueError
        except:
            return self.return_body(self.representation % {'resource'       : saxutils.escape(self.resource),
                                                           'notification_id': now,
                                                           'content'        : '/' })

        with self.lock:
            self.waiting.append(str(self))
            content = self.check_events(since)

            if content == '/':
                self.lock.wait(self.timeout)
                content = self.check_events(since)
            else:
                uc_server.increment_notification_id()
            
            now = uc_server.notification_id()

            if str(self) in self.waiting:
                self.waiting.remove(str(self))

        return self.return_body(self.representation % {'resource'       : saxutils.escape(self.resource),
                                                       'notification_id': now,
                                                       'content'        : content})

    def standby_do_GET(self):
        return self.do_GET()

    @classmethod
    def check_events(cls,since):
        """This method checks the local list of notified changes and checks if any have occured since the given
        notification_id. It returns a string containing XML 'resource' elements representing the returned events."""

        global uc_server

        def nid_gt(a,b):
            a = int(a,16)
            b = int(b,16)
            
            return ((a > b and (a-b) <= (1 << 63)) or (b > a and (b-a) > (1 << 63)))

        with cls.lock:
            output = ''
            for resource in cls.notifiable_changes:
                if nid_gt(cls.notifiable_changes[resource], since):
                    if resource == "uc/power":
                        output = ('<resource rref="%(resource)s"/>' % escape_dict({ 'resource' : resource })) + output
                    elif resource == "uc":
                        output += '<resource rref="%(resource)s"/>' % escape_dict({ 'resource' : resource })
                    elif not uc_server.standby:
                        output += '<resource rref="%(resource)s"/>' % escape_dict({ 'resource' : resource })                        

        if output == '':
            return '/'
        else:
            return '>' + output + '</events'

    @classmethod
    def notify_change(cls,resource):
        """This method is called whenever a notifiable change occurs to a resource, it takes the rref of the resource
        as a parameter and adds that resource to the list of notified changes at the current notification_id. If a previous
        notification_id exists for the same resource then it is replaced with the new one. 

        When this happens all GET requests to this resource awaiting notification are woken up."""

        global uc_server

        uc_server.log_message("Received Notification For %s at %s",resource,uc_server.notification_id())

        with cls.lock:
            if len(cls.waiting) != 0:
                cls.notifiable_changes[resource] = uc_server.increment_notification_id()
                cls.lock.notifyAll()
            else:
                cls.notifiable_changes[resource] = uc_server.notification_id()

        return

class UCPowerResourceHandler (UCResourceHandler):
    """This class handles the 'uc/power' resource.
    """

    representation = """\
<response resource="%(resource)s"><power state="%(state)s"%(transitioning-to)s/></response>
"""

    data = { 'resource' : 'uc/power',}

    def do_GET(self):
        """This method checks authentication, and then returns the representation."""
        
        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        data = dict()
        data['resource'] = saxutils.escape(self.data['resource'])
        data['state']    = "on"
        data['transitioning-to'] = ''

        return self.return_body(self.representation % data)

    def standby_do_GET(self):
        """This method checks authentication, and then returns the representation."""
        
        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        data = dict()
        data['resource'] = saxutils.escape(self.data['resource'])
        data['state']    = "standby"
        data['transitioning-to'] = ''

        self.return_body(self.representation % data)
        return

    def do_PUT(self):
        """This method is called for all PUT requests made to this resource. It checks authentication,
        and then parses the given request body, changing the values in the class variable 'data' to
        represent the values sent in the request."""
        
        
        body = self.retrieve_body()
        if self.auth:
            if not self.handler.check_authentication(body):
                return

        dom = self.parse_body(body)

        list = dom.getElementsByTagName('power')

        if len(list) == 1:
            state = str(list[0].getAttribute('state'))
            dom.unlink()
            
            if state == "on":
                if not uc_server.standby:
                    return self.return_bodyless()
                elif uc_server.set_standby(False):
                    self.notify()
                    return self.return_bodyless()
                else:
                    raise ProcessingFailed()                                        
            elif state == "standby":
                if uc_server.standby:
                    return self.return_bodyless()
                elif uc_server.set_standby(True):
                    self.notify()
                    return self.return_bodyless()
                else:
                    raise ProcessingFailed()  
            elif state == "off":
                raise ProcessingFailed()
            else:
                raise ProcessingFailed()
        else:
            dom.unlink()
        raise InvalidSyntax()

    def standby_do_PUT(self):
        return self.do_PUT()
    
class UCTimeResourceHandler (UCResourceHandler):
    """This class handles requests to the 'uc/time' resource."""

    representation = u"""\
<response resource="%(resource)s"><time rcvdtime="%(rcvdtime)s" replytime="%(replytime)s"/></response>
"""
    
    data = {'resource' : 'uc/time',}

    def do_GET(self):
        """This method checks authentication and then sends the correctly formated time response according to
        the system time as accessed using datetime.datetime.now()."""

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        try:
            string = self.representation % escape_dict({'resource'  : saxutils.escape(self.resource),
                                                        'replytime' : saxutils.escape('%sZ' % datetime.datetime.utcnow().isoformat()),
                                                        'rcvdtime'  : saxutils.escape('%sZ' % self.handler.rcvdtime.isoformat())})
        except:
            uc_server.log_message(traceback.format_exc())
            raise ProcessingFailed

        self.return_body(string)
        return

    @classmethod
    def notify(cls):
        """This method does nothing. 'uc/time' is not notifiable!"""
        pass


class UCOutputsResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/outputs' resource. It acquires its data not from its own 
    data variable, but from the outputs member of the global UCServer instance."""

    representation = u"""\
<response resource="%(resource)s"><outputs%(content)s></response>
"""

    data = { 'resource' : 'uc/outputs',}

    def do_GET(self):
        """This method handles a GET request to the resource."""
        
        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        def form_output(oid):
            element = u'<output name="%(name)s" oid="%(oid)s"' % { 'name'     : saxutils.escape(uc_server.outputs[oid]['name']),
                                                                'oid'      : saxutils.escape(oid) }
            if 'main' in uc_server.outputs[oid] and uc_server.outputs[oid]['main']:
                element += u' main="true"'
            children = [ out for out in uc_server.outputs if 'parent' in uc_server.outputs[out] and uc_server.outputs[out]['parent'] == oid ]
            if children:
                element += u'>'
                for out in children:
                    element += form_output(out)
                element += u'</output>'
            else:
                element += u'/>'
                
            return element
                    

        content = u'/'
        if len(uc_server.outputs) != 0:
            content = u'>'
            for out in [ oid for oid in uc_server.outputs if 'parent' not in uc_server.outputs[oid] ]:
                content += form_output(oid)
            content += u'</outputs'

        self.return_body(self.representation % {'resource' : saxutils.escape(self.resource),
                                                'content'  : content})
        return

class UCOutputsIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/outputs/{id}' resources. It acquires its data not from its own 
    data variable, but from the outputs member of the global UCServer instance."""

    representation = u"""\
<response resource="%(resource)s"><output name="%(name)s"><settings%(attributes)s/>%(content)s</output></response>
"""

    data = { 'resource' : 'uc/outputs/%s',}

    def id_from_path(self,path):
        """This utility function extracts an output id from the path."""        

        if path[-1] == 'main':
            return uc_server.main_output
        elif re.match('^([a-zA-Z0-9_\-\.~]|%[0-9a-fA-F]{2})+$',path[-1]):
            return path[-1]
        raise InvalidSyntax("The given id (%s) is not a vaid id-component" % path[-1])

    def do_GET(self):
        """This method responds to a GET request. It checks authentication, parses the data for the output into
        the correct XML format, and then returns it."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()

        output = uc_server.outputs[id]

        
        attributes = ''
        if 'volume' in output['settings']:
            if isinstance(output['settings']['volume'], int) and 0 <= output['settings']['volume'] <= 10000:
                attributes += ' volume="%01d.%04d"' % ( int(output['settings']['volume']/10000), output['settings']['volume'] % 10000 )
        if 'mute' in output['settings']:
            if isinstance(output['settings']['mute'], bool):
                attributes += ' mute="%s"' % bool_to_xml_string(output['settings']['mute'])
        if 'aspect' in output['settings']:
            if output['settings']['aspect'] in ('source','4:3','14:9','16:9','16:10','21:9'):
                attributes += ' aspect="%s"' % saxutils.escape(output['settings']['aspect'])

        programme = ''
        if 'programme' in output and output['programme'] is not None:
            programme = '<programme sid="%s" cid="%s"' % (saxutils.escape(output['programme'][0]),
                                                          saxutils.escape(output['programme'][1]),)
            if len(output['programme']) > 2 and len(output['programme'][2]) > 0:
                programme += '>'
                for comp in output['programme'][2]:
                    programme += '<component-override type="%(type)s" mcid="%(mcid)s"/>' % escape_dict(comp)
                programme += '</programme>'
            else:
                programme += '/>'

        app = ''
        if 'app' in output and output['app'] is not None:
            app = '<app sid="%s" cid="%s"' % (saxutils.escape(output['app'][0]),
                                              saxutils.escape(output['app'][1]),
                                              )
            if len(output['app']) > 2 and len(output['app'][2]) > 0:
                app += '>'
                for profile in output['app'][2]:
                    if re.match('^(\w+(\-+\w+)*(\.\w+(\-+\w+)*)*)?:([a-zA-Z0-9_\-\.~]|%[0-9a-fA-F]{2})+$',profile):
                        app += '<controls profile="%s"/>' % (profile,)
                app += '</app>'
            else:
                app += '/>'

        if (programme != '' and
            'playback' in output and 
            isinstance(output['playback'],float)):
            playback = '<playback speed="%s"/>' % saxutils.escape('%01.2f' % float(output['playback']))
        else:
            playback = ''

        self.return_body(self.representation % {'resource'          : saxutils.escape(self.data['resource'] % (str(id),) + self.reconstructParams()),
                                                'name'              : saxutils.escape(output['name']),
                                                'attributes'        : attributes,
                                                'content'           : '%s%s%s' % (programme,app,playback)})
        return


    def do_POST(self):
        """This method handles a POST request, making changes to the dictionary-like outputs member of the global
        UCServer instance."""

        global uc_server

        body = self.retrieve_body()

        if self.auth:
            if not self.handler.check_authentication(body):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()

        output = uc_server.outputs[id]

        type = None
        sid  = ''
        cid  = ''
        components = []

        if 'sid' in self.params:
            if len(self.params['sid']) == 1:
                sid = self.params['sid'][0]
                if 'cid' in self.params:
                    if len(self.params['cid']) == 1:
                        cid = self.params['cid'][0]
                    else:
                        raise InvalidSyntax
                else:
                    cid = ''
            else:
                raise InvalidSyntax
        elif body == '':
            raise InvalidSyntax
        else:
            dom = self.parse_body(body)
            data = dict()

            list1 = dom.getElementsByTagName('programme')
            list2 = dom.getElementsByTagName('app')
            if len(list2) == 0 and len(list1) == 1:
                op = list1[0]
                type = 'programme'

                if op.hasAttribute('sid'):
                    sid = op.getAttribute('sid')
                else:
                    raise InvalidSyntax

                if op.hasAttribute('cid'):
                    cid = op.getAttribute('cid')
                else:
                    raise InvalidSyntax
            
                list1 = op.getElementsByTagName('component-override')
                for c in list1:
                    if c.hasAttribute('mcid'):
                        mcid = c.getAttribute('mcid')
                    else:
                        raise InvalidSyntax

                    if c.hasAttribute('type'):
                       components.append({ 'mcid' : mcid,
                                           'type' : c.getAttribute('type')})
                    else:
                        raise InvalidSyntax

            elif len(list2) == 1 and len(list1) == 0:
                op = list2[0]
                type = 'app'
                
                if op.hasAttribute('sid'):
                    sid = op.getAttribute('sid')
                else:
                    raise InvalidSyntax

                if op.hasAttribute('cid'):
                    cid = op.getAttribute('cid')
                else:
                    raise InvalidSyntax
            else:
                raise InvalidSyntax

            
            
        if sid not in uc_server.sources:
            raise CannotFind

        try:
            if type == 'programme':
                output['selector'].select_programme(sid,cid,components)
            elif type == 'app':
                output['selector'].select_app(sid,cid)
            else:
                output['selector'].select_content(sid,cid)
        except UCException as e:
            raise
        except:
            print traceback.format_exc()
            raise ProcessingFailed

        
        return self.return_bodyless()

    
    @classmethod
    def notify(cls,id):
        """This version of the notify method has been overridden to correctly handle the rref of this resource, which 
        varies by id."""
        UCEventsResourceHandler.notify_change(cls.data['resource'] % {'id' : id})
        

class UCOutputsIdSettingsResourceHandler(UCResourceHandler):
    """This class handles requests to the resource 'uc/outputs/{id}/settings'. It gets its data not from its own
    data member, but from the outputs member of the global UCServer instance."""

    representation = """\
<response resource="%(resource)s"><settings%(attributes)s/></response>
"""

    data = { 'resource' : u'uc/outputs/%s/settings',
             }

    def id_from_path(self,path):
        """This utility function obtains an id from the path."""

        if path[-2] == 'main':
            return uc_server.main_output
        return path[-2]

    def do_GET(self):
        """This method responds to a GET request. It checks authentication, parses the data for the output into
        the correct XML format, and then returns it."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()

        output = uc_server.outputs[id]

        attributes = ''
        if 'volume' in output['settings']:
            if isinstance(output['settings']['volume'], int) and 0 <= output['settings']['volume'] <= 10000:
                attributes += ' volume="%01d.%04d"' % ( int(output['settings']['volume']/10000), output['settings']['volume'] % 10000 )
        if 'mute' in output['settings']:
            if isinstance(output['settings']['mute'], bool):
                attributes += ' mute="%s"' % bool_to_xml_string(output['settings']['mute'])
        if 'aspect' in output['settings']:
            if output['settings']['aspect'] in ('source','4:3','14:9','16:9','16:10','21:9'):
                attributes += ' aspect="%s"' % saxutils.escape(output['settings']['aspect'])

                
        self.return_body(self.representation % {'resource'          : saxutils.escape(self.data['resource'] % (str(id),) + self.reconstructParams()),
                                                'attributes'        : attributes,})
        return

    def do_PUT(self):
        """This method handles a PUT request."""

        global uc_server


        body = self.retrieve_body()

        if self.auth:
            if not self.handler.check_authentication(body):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()

        output = uc_server.outputs[id]

        dom = self.parse_body(body)

        list = dom.getElementsByTagName('settings')
        data = dict()
        if len(list) == 1:
            if list[0].hasAttribute('volume'):
                match = re.match('^(\+|\-)?(\d*)(\.(\d+))?$',list[0].getAttribute('volume'))
                if match is None:
                    raise InvalidSyntax
                frac = (match.group(4) if match.group(4) is not None else '')
                data['volume'] = 10000*int(match.group(2)) + int((frac + '0000')[:4])
            if list[0].hasAttribute('mute'):
                mute = list[0].getAttribute('mute')
                try:
                    data['mute'] = parse_bool(mute)
                except:
                    raise InvalidSyntax
            if list[0].hasAttribute('aspect'):
                aspect = list[0].getAttribute('aspect')
                if aspect not in ('source','4:3','14:9','16:9','16:10','21:9'):
                    raise InvalidSyntax
                data['aspect'] = aspect
        else:
            raise InvalidSyntax

        for key in data:
            output['settings'][key] = data[key]
            

        return self.return_bodyless()


class UCOutputsIdPlayheadResourceHandler(UCResourceHandler):
    """This class handles requests to the resource 'uc/outputs/{id}/playhead'. It gets its data not from its own
    data member, but from the outputs member of the global UCServer instance."""

    representation = """\
<response resource="%(resource)s"><playhead timestamp="%(timestamp)s"%(attributes)s>%(aposition)s%(rposition)s%(playback)s</playhead></response>
"""

    data = { 'resource' : 'uc/outputs/%(id)s/playhead',}

    def id_from_path(self,path):
        """This utility function obtains an id from the path."""

        if path[-2] == 'main':
            return uc_server.main_output
        return path[-2]


    def do_GET(self):
        """This method responds to a GET request by checking authentication and then parsing data from the outputs
        member of the global UCServer instance."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()        

        if 'playhead' not in uc_server.outputs[id] or uc_server.outputs[id]['playhead'] is None:
            raise InvalidSyntax, "No playhead for this output"

        output = uc_server.outputs[id]

        attributes = ''
        for key in ('length',):
            if key in output['playhead']:
                attributes += ' %s="%s"' % (key,saxutils.escape('%01.3f' % float(output['playhead'][key])))

        if ('playback' in output 
            and (isinstance(output['playback'],float))):
            speed = float(output['playback'])
            playback = '<playback speed="%s"/>' % saxutils.escape('%01.2f' % (speed,))
        else:
            speed = 0.0
            playback = ''

        now = datetime.datetime.utcnow()
                
        if ('aposition' in output['playhead'] 
            and isinstance(output['playhead']['aposition'],dict)             
            and 'position' in output['playhead']['aposition']
            and isinstance(output['playhead']['aposition']['position'],float)
            and 'position_precision' in output['playhead']['aposition']
            and isinstance(output['playhead']['aposition']['position_precision'],int)
            and 'position_timestamp' in output['playhead']['aposition']
            and isinstance(output['playhead']['aposition']['position_timestamp'],datetime.datetime)):
            diff = (now - output['playhead']['aposition']['position_timestamp'])
            aposition = '<aposition position="%.*f"' % (int(output['playhead']['aposition']['position_precision']),(float(output['playhead']['aposition']['position'])
                                                                                                                    + speed*(float(diff.seconds) + 
                                                                                                                             (float(diff.microseconds)/float(10**6)))
                                                                                                                    )
                                                        ,)
            for key in ('seek-start','seek-end',):
                if key in output['playhead']['aposition'] and isinstance(output['playhead']['aposition'][key],float):
                    aposition += ' %s="%.*f"' % (int(output['playhead']['aposition']['position_precision']),float(output['playhead']['aposition'][key]),)
            aposition += '/>'
        else:
            aposition = ''

        if ('rposition' in output['playhead'] 
            and isinstance(output['playhead']['rposition'],dict)             
            and 'position' in output['playhead']['rposition']
            and isinstance(output['playhead']['rposition']['position'],float)
            and 'position_precision' in output['playhead']['rposition']
            and isinstance(output['playhead']['rposition']['position_precision'],int)):
            rposition = '<rposition position="%.*f"' % (int(output['playhead']['rposition']['position_precision']),float(output['playhead']['rposition']['position']),)
            for key in ('seek-start','seek-end',):
                if key in output['playhead']['rposition'] and isinstance(output['playhead']['rposition'][key],float):
                    rposition += ' %s="%.*f"' % (int(output['playhead']['rposition']['position_precision']),float(output['playhead']['rposition'][key]),)
            rposition += '/>'
        else:
            rposition = ''

        self.return_body(self.representation % {'resource'          : saxutils.escape(self.data['resource'] % {'id' : id} + self.reconstructParams()),
                                                'timestamp'         : '%sZ' % now.isoformat(),
                                                'attributes'        : attributes,
                                                'playback'          : playback,
                                                'aposition'         : aposition,
                                                'rposition'         : rposition,
                                                })

    def do_PUT(self):
        """This method handles a PUT request by updating the outputs member of the global UCServer instance."""
        
        global uc_server

        timestamp = datetime.datetime.utcnow()

        body = self.retrieve_body()

        if self.auth:
            if not self.handler.check_authentication(body):
                return

        id = self.id_from_path(self.path)

        if (id is None) or (id not in uc_server.outputs):
            raise CannotFind()

        output = uc_server.outputs[id]

        if 'playhead' not in uc_server.outputs[id] or uc_server.outputs[id]['playhead'] is None:
            raise InvalidSyntax

        dom = self.parse_body(body)

        list = dom.getElementsByTagName('playhead')
        if len(list) != 1:
            raise InvalidSyntax('Failed to parse playhead')

        try:
            timestamp = parse_iso(list[0].getAttribute('timestamp'))
        except:
            pass

        data = dict()
        playhead = dict()

        ph = list[0]
        list = ph.getElementsByTagName('aposition')
        if len(list) > 1:
            raise InvalidSyntax('Failed to parse position')
        elif len(list) == 1:
            try:
                playhead['aposition'] = { 'position'           : float(list[0].getAttribute('position')),
                                          'position_timestamp' : timestamp }
            except:
                raise InvalidSyntax('Failed to parse position')
        else:
            list = ph.getElementsByTagName('rposition')
            if len(list) != 1:
                raise InvalidSyntax('Failed to parse position')
            else:
                try:
                    playhead['aposition'] = { 'position'           : float(list[0].getAttribute('position')),
                                              'position_timestamp' : timestamp }
                except:
                    raise InvalidSyntax('Failed to parse position')

        list = ph.getElementsByTagName('playback')
        if len(list) == 1:
            pb = list[0]
                
            speed = 0.0
            
            if pb.hasAttribute('speed'):
                try:
                    speed = float(pb.getAttribute('speed'))
                except:
                    raise InvalidSyntax('invalid speed')

                data['playback'] = speed

        elif len(list) > 1:
            raise InvalidSyntax('too many playbacks')

        try:
            for key in ('playback',):
                if key in data:                
                    output[key] = data[key]

            output['playhead'] = playhead
        except:
            raise
        
        dom.unlink()
        return self.return_bodyless()



class UCRemoteResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/remote' resource. It makes use of the 
    object stored in the button_handler variable of the global UCServer instance, 
    which must respond to the method

    def send_button_press(code):

    which takes a button code as a string."""

    representation = """\
<response resource="%(resource)s"><remote%(content)s></response>
"""

    data = { 'resource' : 'uc/remote',}

    def do_GET(self):
        """This methods handles GET requests by checking authentication and then returning the data stored
        in the controls member of the global UCServer instance."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        controls = ''
        for profile in uc_server.controls:
            if re.match('^(\w+(\-+\w+)*(\.\w+(\-+\w+)*)*)?:([a-zA-Z0-9_\-\.~]|%[0-9a-fA-F]{2})+$',profile):
                controls += '<controls profile="%s"/>' % (profile,)

        if controls == '':
            content = '/'
        else:
            content = '>%s</remote' % controls

        self.return_body(self.representation % {'resource' : saxutils.escape(self.resource),
                                                'content'  : content})
        return

    def do_POST(self):
        """This method handles POST requests by handing the request on to the object stored in the 
        button_handler member of the global UCServer instance, if such an object exists. If no such 
        object exists then it returns a 500 error."""

        global uc_server

        body = self.retrieve_body()

        if self.auth:
            if not self.handler.check_authentication(body):
                return

        if 'button' not in self.params or len(self.params['button']) != 1:
            raise InvalidSyntax('Button missing')

        button = self.params['button'][0]

        if not re.match('^(((\w+(\-+\w+)*(\.\w+(\-+\w+)*)*)?:([a-zA-Z0-9_\-\.~]|%[0-9a-fA-F]{2})+)|:):([a-zA-Z0-9_\-\.~]|%[0-9a-fA-F]{2})+$',button):
            raise InvalidSyntax

        output = None
        if 'output' in self.params:
            if len(self.params['output']) == 1:
                output = self.params['output'][0]
            else:
                raise InvalidSyntax
        
        if uc_server.button_handler is None:
            raise ProcessingFailed()
            
        uc_server.button_handler.send_button_press(button, output=output)
        
        return self.return_bodyless()

class UCFeedbackResourceHandler(UCResourceHandler):
    """This class handles the 'uc/feedback' resource. It always acquires its returned text from the class member data
    which has a key 'feedback' which is a string. This object may be replaced with a dictionary-like object of the form

    data= { 'resource' : 'uc/feedback',
            'feedback' : STRING,
            }

    The contents of the feedback string are entity-encoded before being returned."""

    representation = """\
<response resource="%(resource)s"><feedback%(content)s></response>
"""

    data = { 'resource' : 'uc/feedback',
             'feedback' : ''}

    def do_GET(self):
        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        content = '/'
        if 'feedback' in self.data and isinstance(self.data['feedback'],basestring) and self.data['feedback'] != '':
            content = '>%s</feedback' % saxutils.escape(str(self.data['feedback']))
            
        self.return_body(self.representation % {'resource' : self.data['resource'] % {'id' : saxutils.escape(str(id))} + self.reconstructParams(),
                                                'content'  : content})
        return    

class UCSourceListsResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/source-lists' resource. Its data comes not from the data class element, 
    but from the sources member of the global UCServerinstance."""

    representation = """\
<response resource="%(resource)s"><source-lists%(content)s></response>
"""

    data = { 'resource' : 'uc/source-lists',}

    def do_GET(self):
        """This method checks authentication, then it returns a list of source-lists."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return
            
        content = '/'
        if len(uc_server.source_lists) != 0:
            content = '>'
            for id in sorted([ key for key in uc_server.source_lists.keys() if key[:2] == 'uc' ]) + sorted([ key for key in uc_server.source_lists.keys() if key[:2] != 'uc' ]):
                content += '<list list-id="%(list-id)s" name="%(name)s"' % { 'list-id'     : saxutils.escape(str(id)),
                                                                             'name' : saxutils.escape(str(uc_server.source_lists[id]['name'])),}
                for key in ('logo-href','description',):
                    if key in uc_server.source_lists[id] and isinstance(uc_server.source_lists[id][key],basestring):
                        content += ' %s="%s"' % (key,saxutils.escape(unicode(uc_server.source_lists[id][key])),)
                content += '/>'

            content += '</source-lists'

        self.return_body(self.representation % {'resource' : saxutils.escape(self.resource),
                                                'content'  : content,
                                                })
        return

class UCSourceListsIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/source-lists/{id}' resources. Its data comes not from the data class element, 
    but from the sources member of the global UCServer instance."""

    representation = """\
<response resource="%(resource)s"><sources%(content)s></response>
"""

    data = { 'resource' : 'uc/source-lists/%s',}

    def do_GET(self):
        """This method checks authentication, then it constructs the correct 
        list of sources and returns that."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return
        
        list = self.path[-1]
        if list not in uc_server.source_lists:
            raise CannotFind()

        content = '/'
        if len(uc_server.source_lists[list]['sources']) != 0:
            content = '>'
            
            def lcn(obj):
                if 'lcn' in obj:
                    return obj['lcn']
                else:
                    return -1

            src_ids = uc_server.source_lists[list]['sources']
            srcs = sorted([ uc_server.sources[id] for id in src_ids ],key=lcn)

            for src in srcs:
                content += self.parse_source(src['id'])

            content += '</sources'

        self.return_body(self.representation % {'resource' : saxutils.escape(self.data['resource'] % str(list) + self.reconstructParams()),
                                                'content'  : content})
        return

    @classmethod
    def parse_source(cls,id):
        """This helper function takes the id of a list and a source within that list and constructs an XML
        source element for it as a string."""

        src = uc_server.sources[id]

        attributes = ''
        for key in ('sref','owner','lcn','default-content-id','logo-href','owner-logo-href'):
            if key in src and isinstance(src[key],basestring) and src[key] != '':
                try:
                    attributes += ' %s="%s"' % (key,saxutils.escape(str(src[key])))
                except:
                    pass
        for key in ('live','linear','follow-on'):
            if key in src and isinstance(src[key],bool):
                try:
                    attributes += ' %s="%s"' % (key,saxutils.escape(bool_to_xml_string(src[key])))
                except:
                    pass
        for key in ('lcn',):
            if key in src and isinstance(src[key],int):
                try:
                    attributes += ' %s="%s"' % (key,saxutils.escape('%03d' % (src[key])))
                except:
                    pass

        content = '/'
        if 'links' in src and len(src['links']) != 0:
            content = '>'
            for link in src['links']:
                try:
                    content += '<link href="%s" description="%s"/>' % ( saxutils.escape(str(link['href'])), 
                                                                        saxutils.escape(str(link['description'])))
                except:
                    pass
            content += '</source'

        return  '<source sid="%(sid)s" name="%(name)s"%(attributes)s%(content)s>' % {'sid'        : saxutils.escape(id),
                                                                                     'name'       : saxutils.escape(src['name']),
                                                                                     'attributes' : attributes,
                                                                                     'content'    : content}


class UCSourcesResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/sources' resource."""

    representation = None

    data = { 'resource' : 'uc/sources',}

    def do_GET(self):
        """This method checks authentication, then returns 204"""

        if self.auth:
            if not self.handler.check_authentication(''):
                return
            
        return self.return_bodyless()

class UCSourcesSrefResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/sources/{sid}' resources. It gets its data not from its
    own data class variable but from the sources member of the global UCServer instance."""

    representation = """\
<response resource="%(resource)s">%(content)s</response>
"""

    data = { 'resource' : 'uc/sources/%(sid)s',}

    def do_GET(self):
        """This method checks authentication then constructs and returns a source representation by calling the
        parse_source method of the UCSourcesResourceHandler class."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        try:
            id = self.path[-1]
        except:
            raise CannotFind()

        if id not in uc_server.sources:
            raise CannotFind()

        content = UCSourceListsIdResourceHandler.parse_source(id)

        self.return_body(self.representation % {'resource' : saxutils.escape(uc_server.sources[id]['rref']),
                                                        'content'  : content})
        return

def encodeContent(content, no_locators=False):
    """This utility function takes a dictionary containing the data for one piece of content
    and returns a string containing the XML for it. The dictionary should be of the form:"""

    attributes = ''
    for key in ('global-content-id','global-series-id','global-app-id','series-id','title','cref','logo-href','last-watched','last-position','associated-sid','associated-id',):
        if key in content and isinstance(content[key],basestring) and content[key] != '':
            try:
                attributes += ' %s="%s"' % (key,saxutils.escape(str(content[key])))
            except:
                pass
    for key in ('interactive','presentable','acquirable','extension',):
        if key in content and isinstance(content[key],bool):
            try:
                attributes += ' %s="%s"' % (key, bool_to_xml_string(content[key]))
            except:
                pass
    for key in ('duration','last-position',):
        if key in content and isinstance(content[key],int):
            try:
                attributes += ' %s="%04.5f"' % (key,float(content[key])/10000.0)
            except:
                pass
    for key in ('start','acquirable-from','acquirable-until','presentable-from','presentable-until','last-presented',):
        if key in content and isinstance(content[key],datetime.datetime):
            try:
                attributes += ' %s="%sZ"' % (key,saxutils.escape(content[key].isoformat()))
            except:
                pass
    for key in ('presentation-count',):
        if key in content and isinstance(content[key],int):
            try:
                attributes += ' %s="%s"' % (key,saxutils.escape('%d' % (content[key])))
            except:
                pass

    string = '/'
    if (('synopsis' in content and content['synopsis'] != '') or 
        ('categories' in content and (isinstance(content['categories'],list) or isinstance(content['categories'],tuple)) and len(content['categories']) != 0) or
        ('links' in content and len(content['link']) != 0 ) or
        ('media-components' in content and len(content['media-components']) != 0) or
        ('controls' in content and len(content['controls']) != 0)):
        string = '>'
        if 'synopsis' in content and content['synopsis'] != '':
            try:
                string += '<synopsis>%s</synopsis>' % saxutils.escape(str(content['synopsis']))
            except:
                pass

        if 'categories' in content and (isinstance(content['categories'],list) or isinstance(content['categories'],tuple)) and len(content['categories']) != 0:
            for category in content['categories']:
                if isinstance(category,basestring):
                    string += '<category category-id="%s"/>' % (str(category),)

        if 'media-components' in content:
            for id in content['media-components']:
                comp = content['media-components'][id]

                componentattributes = ''
                for key in ('name','lang'):
                    if key in comp and isinstance(comp[key],basestring) and comp[key] != '':
                        try:
                            componentattributes += ' %s="%s"' % (saxutils.escape(key), saxutils.escape(str(comp[key])))
                        except:
                            pass
                for key in ('intent',):
                    if key in comp and isinstance(comp[key],basestring) and comp[key] in ('admix','hhsubs','signed','iimix','commentary'):
                        try:
                            componentattributes += ' %s="%s"' % (saxutils.escape(key), saxutils.escape(str(comp[key])))
                        except:
                            pass
                for key in ('aspect',):
                    if key in comp and isinstance(comp[key],basestring) and comp[key] in ('4:3','14:9','16:10','16:9','21:9'):
                        try:
                            componentattributes += ' %s="%s"' % (saxutils.escape(key), saxutils.escape(str(comp[key])))
                        except:
                            pass
                for key in ('vidformat',):
                    if key in comp and isinstance(comp[key],basestring) and comp[key] in ('SD','HD','S3D'):
                        try:
                            componentattributes += ' %s="%s"' % (saxutils.escape(key), saxutils.escape(str(comp[key])))
                        except:
                            pass
                for key in ('colour','default'):
                    if key in comp and isinstance(comp[key],bool):
                        try:
                            componentattributes += ' %s="%s"' % (saxutils.escape(key), bool_to_xml_string(comp[key]))
                        except:
                            pass
                string += '<media-component mcid="%(id)s" type="%(type)s"%(attributes)s/>' % { 'id'   : id,
                                                                                             'type' : saxutils.escape(str(comp['type'])),
                                                                                             'attributes' : componentattributes }
        if 'controls' in content:
            for profile in content['controls']:
                string += '<controls profile="%s"/>' % (profile,)
        
        if 'links' in content:
            for link in content['links']:
                string += '<link href="%s" description="%s"/>' % (saxutils.escape(link['href']),
                                                                   saxutils.escape(link['description']))

        string += '</content'

    return '<content sid="%(sid)s" cid="%(cid)s"%(attributes)s%(content)s>' % { 'sid' : saxutils.escape(str(content['sid'])),
                                                                                'cid' : saxutils.escape(str(content['cid'])),
                                                                                'attributes' : attributes,
                                                                                'content'    : string }


class UCSearchResourceHandler(UCResourceHandler):
    """This class handles requests for metadata made to the 'uc/search' resource. It returns a 204 response to all GET requests, but
    also includes a number of methods which can be used by the child resources to parse the data for their requests."""

    representation = """\
<response resource="%(resource)s"><results%(content)s></response>
"""

    data = { 'resource' : 'uc/search',}

    @classmethod
    def parse_query(cls,query,valid=['results',
                                     'offset',
                                     'sid',
                                     'cid',
                                     'series-id',
                                     'gcid',
                                     'gsid',
                                     'gaid',
                                     'category',
                                     'text',
                                     'field',
                                     'interactive',
                                     'AV',
                                     'start',
                                     'end',
                                     'days']):
        """This method parses the query parameters according to Section 4.18.1 of the spec"""

        global uc_server

        params = { 'results'     : (False, 1, 'int>=1'),
                   'offset'      : (False, 0, 'int'),
                   'sid'         : (True,  None, 'id'),
                   'cid'         : (True,  None, 'id'),
                   'series-id'   : (True,  None, 'id'),
                   'gcid'        : (True,  None, '%'),
                   'gsid'        : (True,  None, '%'),
                   'gaid'        : (True,  None, '%'),
                   'category'    : (True,  None, 'id'),
                   'text'        : (True,  None, '%'),
                   'field'       : (True,  None, '%'),
                   'interactive' : (False, True, 'bool'),
                   'AV'          : (False, True, 'bool'),
                   'start'       : (False, None, 'iso'),
                   'end'         : (False, None, 'iso'),
                   'days'        : (False, None, 'int>=1'),
                   }

        retvals = dict([ (key, params[key][1]) for key in params if params[key][1] is not None ])

        def casttype(x,t):
            if t[:3] == 'int':
                try:
                    r = int(x)
                except:
                    raise InvalidSyntax

                if t == 'int>=1' and r < 0:
                    raise InvalidSyntax
            elif t == 'id':
                try:
                    r = unicode(x)
                except:
                    raise InvalidSyntax
                
                if not isidtype(r):
                    raise InvalidSyntax
            elif t == '%':
                try:
                    r = unpctencode(unicode(x))
                except:
                    raise InvalidSyntax
            elif t == 'bool':
                try:
                    r = parse_bool(x)
                except:
                    raise InvalidSyntax
            elif t == 'iso':
                try:
                    r = parse_iso(x)
                except:
                    raise InvalidSyntax

            else:
                raise InvalidSyntax
            return r

        for key in params:
            if (key in valid 
                and key in query):                

                if not params[key][0]:
                    if len(query[key]) > 1:
                        raise InvalidSyntax
                    else:
                        retvals[key] = casttype(query[key][0],params[key][2])
                else:
                    retvals[key] = [ casttype(r,params[key][2]) for r in query[key] ]
                
            elif (key in valid 
                  and params[key][1] is not None):
                retvals[key] = params[key][1]

        if 'days' in retvals and 'end' in retvals:
            raise InvalidSyntax
        if 'start' not in retvals:
            retvals['start'] = datetime.datetime.utcnow()
        if 'field' not in retvals:
            retvals['field'] = ['title','synopsis']
        elif not all([ x in ['title','synopsis'] for x in retvals['field'] ]):
            raise InvalidSyntax

        if 'days' in retvals:
            retvals['end'] = datetime.datetime(retvals['start'].year,
                                               retvals['start'].month,
                                               retvals['start'].day,
                                               0,
                                               0,
                                               0,
                                               0) + datetime.timedelta(days=retvals['days'])

        return retvals

    @classmethod
    def respond(cls,resource,handler,contents, head=False):
        representation = """<response resource="%(resource)s">%(content)s</response>
"""
        
        lists = ''
        for content in contents:
            elements = ''
            for item in content[0]:
                elements += encodeContent(item)

            if elements == '':
                lists += '<results more="%s"/>' % (bool_to_xml_string(content[1]),)
            else:
                lists += '<results more="%s">%s</results>' % (bool_to_xml_string(content[1]),elements,)            

        string = representation % {'resource' : saxutils.escape(resource),
                                   'content'  : lists}
        
        handler.send_response(200)
        handler.send_header('Content-Length',len(string))
        handler.send_header('Cache-Control','no-cache')
        handler.send_header('Content-Type','application/xml')
        handler.end_headers()

        if not head:
            handler.wfile.write(string)

        return        


    def do_GET(self):
        """This method returns a 204 response."""

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        return self.return_bodyless()


class GET204Handler(UCResourceHandler):
    """This class handles GET requests by returning a 204"""

    representation = """
"""
    data = { 'resource' : '',
             }

    def do_GET(self):
        """This returns a 204"""

        if self.auth:
            if not self.handler.check_authentication(''):
                return        

        return self.return_bodyless()

class UCSearchOutputsIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/outputs/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/outputs/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        term = self.path[-1]

        if term == 'main':
            term = [out for out in uc_server.outputs if 'main' in uc_server.outputs[out]][0]
            print "Found main output id %s" % term
        
        if term not in uc_server.outputs:
            raise CannotFind

        params = UCSearchResourceHandler.parse_query(self.params,['results','offset','interactive','AV','start','end','days'])

        content = uc_server.content.get_output(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (term,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchSourcesIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/sources/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/sources/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        term = terms.split(';')

        if not all([ t in uc_server.sources for t in term ]):
            raise CannotFind

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'cid',
                                                                  'series-id',
                                                                  'gcid',
                                                                  'gsid',
                                                                  'gaid',
                                                                  'category',
                                                                  'text',
                                                                  'field',
                                                                  'interactive',
                                                                  'AV',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_sources(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchSourcelistsIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/source-lists/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/source-lists/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        lists = terms.split(';')

        if not all([ t in uc_server.source_lists for t in lists ]):
            raise CannotFind

        def __lcn(obj):
            if 'lcn' in obj:
                return obj['lcn']
            else:
                return -1

        sources = reduce(lambda x,y : x+y, 
                         [ sorted([ sid for sid in uc_server.source_lists[lid]['sources'] ], 
                                  key=lambda sid : (uc_server.sources[sid]['lcn'] if 'lcn' in uc_server.sources[sid] else -1)) 
                           for lid in uc_server.source_lists ])

        print sources
        
        term = []
        for s in sources:
            if s not in term:
                term.append(s)

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'cid',
                                                                  'series-id',
                                                                  'gcid',
                                                                  'gsid',
                                                                  'gaid',
                                                                  'category',
                                                                  'text',
                                                                  'field',
                                                                  'interactive',
                                                                  'AV',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_sources(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchTextIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/text/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/text/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        try:
            term = [ unpctencode(t) for t in terms.split('+') ]
        except:
            raise InvalidSyntax

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'sid',
                                                                  'cid',
                                                                  'series-id',
                                                                  'gcid',
                                                                  'gsid',
                                                                  'gaid',
                                                                  'category',
                                                                  'field',
                                                                  'interactive',
                                                                  'AV',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_text(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchGlobalcontentidIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/global-content-id/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/global-content-id/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        try:
            term = unpctencode(terms)
        except:
            raise InvalidSyntax

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'sid',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_gcid(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchGlobalseriesidIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/global-series-id/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/global-series-id/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        try:
            term = unpctencode(terms)
        except:
            raise InvalidSyntax

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'sid',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_gsid(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCSearchGlobalappidIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/global-app-id/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/global-app-id/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        terms = self.path[-1]

        try:
            term = unpctencode(terms)
        except:
            raise InvalidSyntax

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'sid',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_gaid(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (terms,) + self.reconstructParams(), self.handler,content,head=self.head)


class UCSearchCategoriesIdResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/search/categories/{id}' resources."""

    representation = """
"""
    data = { 'resource' : 'uc/search/categories/%s',
             }

    def do_GET(self):
        """This parses the response as expected for a request to this resource."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        term = self.path[-1]

        cats = [ catid for catid in uc_server.categories if 'category-id' in uc_server.categories[catid] ]
        if term not in cats:
            raise CannotFind

        def childcats(cat):
            children = [ catid for catid in uc_server.categories if 'parent' in uc_server.categories[catid] and uc_server.categories[catid]['parent'] == cat ]
            if not children:
                return [cat,]
            else:
                retvals = []
                for child in children:
                    retvals.extend(childcats(child))
                return retvals

        term = list(set(childcats(term)))

        params = UCSearchResourceHandler.parse_query(self.params,['results',
                                                                  'offset',
                                                                  'sid',
                                                                  'cid',
                                                                  'series-id',
                                                                  'gcid',
                                                                  'gsid',
                                                                  'gaid',
                                                                  'text',
                                                                  'field',
                                                                  'interactive',
                                                                  'AV',
                                                                  'start',
                                                                  'end',
                                                                  'days'])

        content = uc_server.content.get_categories(term,params)

        return UCSearchResourceHandler.respond(self.data['resource'] % (term,) + self.reconstructParams(), self.handler,content,head=self.head)

class UCCategoriesResourceHandler(UCResourceHandler):
    """This class handles requests to the 'uc/categories' resource. It gets its data not from its
    own data class variable but from the categories member of the global UCServer instance."""

    representation = """\
<response resource="%(resource)s"><categories%(content)s></response>
"""

    data = { 'resource' : 'uc/categories'}

    def do_GET(self):
        """This method checks authentication then constructs and returns a representation of the box's categories 
        hierarchy"""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        def generate_category_hierarchy(root):
            branches = filter(lambda x : uc_server.categories[x]['parent'] == root,
                              uc_server.categories)

            content = '/'
            if len(branches) != 0:
                content = ''
                for branch in branches:
                    attributes = ''
                    for key in ('logo-href','category-id'):
                        if key in uc_server.categories[branch] and isinstance(uc_server.categories[branch][key],basestring):
                            attributes += ' %s="%s"' % (key, saxutils.escape(str(uc_server.categories[branch][key])))
                    
                    branchcontent = generate_category_hierarchy(branch)
                    if branchcontent != '/':
                        branchcontent = '>%s</category' % branchcontent

                    content += '<category name="%(name)s"%(attributes)s%(content)s>' % { 'name'       : saxutils.escape(str(uc_server.categories[branch]['name'])),
                                                                                         'attributes' : attributes,
                                                                                         'content'    : branchcontent }
            return content


        content = generate_category_hierarchy('')
        if content != '/':
            content = '>%s</categories' % content

        self.return_body(self.representation % {'resource' : saxutils.escape(self.resource),
                                                'content'  : content})
        return

class UCAcquisitionsResourceHandler (UCResourceHandler):
    """This class handles requests for acquisition information made to the 'uc/acquisitions' resource. 
    The class member data can be replaced by a dictionary-like object.
    """

    representation = """\
<response resource="%(resource)s"><acquisitions%(content)s></response>
"""

    data = { 'resource'        : 'uc/acquisitions',
             'content-acquisitions'   : dict(),
             'series-acquisitions'    : dict()
             }

    acquirer = None

    @classmethod
    def form_content_acquisition(cls,id):
        booking = cls.data['content-acquisitions'][id]
    
        attributes = ''
        for key in ('global-content-id','series-id',):
            if key in booking and isinstance(booking[key],basestring) and booking[key] != '':
                try:
                    attributes += ' %s="%s"' % (key, saxutils.escape(str(booking[key])))
                except:
                    pass

        for key in ('start','end'):
            if key in booking and isinstance(booking[key],datetime.datetime):
                try:
                    attributes += ' %s="%sZ"' % (key, saxutils.escape(booking[key].isoformat()))
                except:
                    pass
                
        for key in ('series-linked','priority','speculative','active'):
            if key in booking and isinstance(booking[key],bool):
                try:
                    attributes += ' %s="%s"' % (key, bool_to_xml_string(booking[key]))
                except:
                    pass

        return '<content-acquisition acquisition-id="%(id)s" sid="%(sid)s" cid="%(cid)s" interactive="%(interactive)s"%(attributes)s/>' %  {
            'id'         : saxutils.escape(str(id)),
            'sid'        : saxutils.escape(str(booking['sid'])),
            'cid'        : saxutils.escape(str(booking['cid'])),
            'interactive': bool_to_xml_string(booking['interactive']),
            'attributes' : attributes }

    @classmethod
    def form_series_acquisition(cls,id):
        
        booking = cls.data['series-acquisitions'][id]

        attributes = ''

        for key in ('speculative',):
            if key in booking and isinstance(booking[key],bool):
                try:
                    attributes += ' %s="%s"' % (key, bool_to_xml_string(booking[key]))
                except:
                    pass

        return  '<series-acquisition acquisition-id="%(id)s" series-id="%(series-id)s"%(attributes)s/>' %  {
            'id'         : saxutils.escape(str(id)),
            'series-id'  : saxutils.escape(str(booking['series-id'])),
            'attributes' : attributes }
    


    def do_GET(self):
        """This method checks authentication, and then returns information about current bookings."""
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return
            
        content = '/'
        if len(self.data['content-acquisitions']) != 0 or len(self.data['series-acquisitions']) != 0:            
            content = '>'
            for acquisition_id in self.data['content-acquisitions']:
                content += self.form_content_acquisition(acquisition_id)

            for acquisition_id in self.data['series-acquisitions']:
                content += self.form_series_acquisition(acquisition_id)

            content += '</acquisitions'
        
        return self.return_body(self.representation % {'resource'    : saxutils.escape(self.resource),
                                                       'content'     : content})

    def do_POST(self):
        """This method handles a POST request with query parameters as described in the spec
        It returns a 400 if the query string is malformed. It makes use of the class variable 
        acquirer."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        priority = False
        if 'priority' in self.params:
            if len(self.params['priority']) == 1:
                priority = parse_bool(self.params['priority'][0])
            else:
                raise InvalidSyntax()

        aid = None    
        if (('sid' in self.params) and 
            ('content-id' in self.params) and
            ('global-content-id' not in self.params) and
            ('series-id' not in self.params) and
            (len(self.params['content-id']) == 1) and
            (len(self.params['sid']) == 1)):

            aid = self.acquirer.acquire(cid=self.params['content-id'][0],
                                        sid=self.params['sid'][0],
                                        priority=priority)
        elif (('sid' not in self.params) and 
              ('content-id' not in self.params) and
              ('global-content-id' in self.params) and
              ('series-id' not in self.params) and
              (len(self.params['global-content-id']) == 1)):

            aid = self.acquirer.acquire(global_content_id=unpctencode(self.params['global-content-id'][0]),
                                        priority=priority)
        elif (('sid' not in self.params) and 
              ('content-id' not in self.params) and
              ('global-content-id' not in self.params) and
              ('series-id' in self.params) and
              (len(self.params['series-id']) == 1)):
            
            aid = self.acquirer.acquire(series_id=self.params['series-id'][0],
                                        priority=priority)
        else:
            raise InvalidSyntax

        if aid is None:
            raise ProcessingFailed()

        content = '/'
        if aid in self.data['content-acquisitions']:
            content = self.form_content_acquisition(aid)
        elif aid in self.data['series-acquisitions']:
            content = self.form_series_acquisition(aid)
        else:
            raise ProcessingFailed()
            
        self.return_body(UCAcquisitionsIdResourceHandler.representation % {'resource' : saxutils.escape(UCAcquisitionsIdResourceHandler.data['resource'] % {'id' : str(aid)}),
                                                                           'content'  : content })
        return
        
class UCAcquisitionsIdResourceHandler (UCResourceHandler):
    """This class handles requests for acquisition information made to the 'uc/acquisitions/{id}' resources. 
    It makes use of the data class member of the UCAcquisitionsResourceHandler.
    """

    representation = """\
<response resource="%(resource)s">%(content)s</response>
"""

    data = { 'resource'        : 'uc/acquisitions/%(id)s',
             }

    acquirer = None

    def do_GET(self):
        """This method checks authentication, and then returns information about current bookings."""
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return
            
        id = self.path[-1]

        content = ''
        if id in UCAcquisitionsResourceHandler.data['content-acquisitions']:
            content = UCAcquisitionsResourceHandler.form_content_acquisition(id)
        elif id in UCAcquisitionsResourceHandler.data['series-acquisitions']:
            content = UCAcquisitionsResourceHandler.form_series_acquisition(id)
        else:
            raise CannotFind


        return self.return_body(self.representation % {'resource'    : saxutils.escape(self.data['resource'] % {'id' : str(id)} + self.reconstructParams()),
                                                       'content'     : content})

    def do_DELETE(self):
        """This method handles a DELETE request. It makes use of the class variable 
        acquirer which must be set to an instance of an object which responds to a method
        
          def cancel (acquisition_id)

        This method must return True if the booking is succesfully canceled and False 
        otherwise."""

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        id = self.path[-1]


        if self.acquirer is not None:
            self.acquirer.cancel(acquisition_id=id)

        if ((id not in UCAcquisitionsResourceHandler.data['content-acquisitions']) and 
            (id not in UCAcquisitionsResourceHandler.data['series-acquisitions'])):
            return self.return_bodyless()

        raise ProcessingFailed()


class UCStorageResourceHandler (UCResourceHandler):
    """This class handles requests for storage information made to the 'uc/storage' resource. 
    The class member data can be replaced by a dictionary-like object of the form:

      data = { 'resource' : 'uc/storage',
               'items'    : {PID AS STRING : { 'pid'          : PID AS A STRING,

                                               OPTIONALLY:
                                               'sid'          : SID AS A STRING,
                                               'content-id'   : CONTENT-ID AS STRING,
                                               'created-time' : ISO-DATETIME STRING,
                                               'size'         : INTEGER IN BYTES,
                                               },
                             ...,
                             }
               
               OPTIONALLY,
               'size'    : INTEGER IN BYTES,
               'free'    : INTEGER IN BYTES,
             }

    """

    representation = """\
<response resource="%(resource)s"><storage%(attributes)s%(content)s></response>
"""

    data = { 'resource'        : 'uc/acquisitions',
             'size'            : 0,
             'free'            : 0,
             'items'           : dict()
             }

    @classmethod
    def form_stored_content(cls,cid):
        progattributes = ''
        for key in ('sid','global-content-id','created-time'):
            if key in cls.data['items'][cid] and isinstance(cls.data['items'][cid][key],basestring) and cls.data['items'][cid][key] != '':
                try:
                    progattributes += ' %s="%s"' % (key,saxutils.escape(str(cls.data['items'][cid][key])))
                except:
                    pass

        for key in ('size',):
            if key in cls.data['items'][cid] and isinstance(cls.data['items'][cid][key],int):
                try:
                    progattributes += ' %s="%d"' % (key,cls.data['items'][cid][key])
                except:
                    pass
                
        return '<stored-content cid="%(cid)s"%(attributes)s/>' % { 'cid' : cid,
                                                                   'attributes' : progattributes}

    def do_GET(self):
        """This method checks authentication, and then returns information about current stored entities."""
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return

        attributes = ''
        for key in ('size','free',):
            if key in self.data and isinstance(self.data[key],int) and 0 <= self.data[key]:
                try:
                    attributes += ' %s="%s"' % (key,saxutils.escape('%09d' % self.data[key]))
                except:
                    pass

        content = '/'
        if len(self.data['items']) != 0:
            content = '>'            
            for cid in sorted(self.data['items'].keys(), key=lambda cid : '%s:::%s' % (self.data['items'][cid]['sid'],cid)):
                content += self.form_stored_content(cid)
            content += '</storage'

        return self.return_body(self.representation % {'resource'    : saxutils.escape(self.resource),
                                                       'attributes'  : attributes,
                                                       'content'     : content})


class UCStorageIdResourceHandler (UCResourceHandler):
    """This class handles requests for storage information made to the 'uc/storage/{sid}' resources. 
    It makes use of the data class member of the UCStorageResourceHandler.
    """

    representation = """\
<response resource="%(resource)s">%(content)s</response>
"""

    data = { 'resource' : 'uc/storage/%(cid)s',
             }

    def do_GET(self):
        """This method checks authentication, and then returns information about stored entities."""
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return
            
        cid = self.path[-1]

        if cid in UCStorageResourceHandler.data['items']:
            content = UCStorageResourceHandler.form_stored_programme(cid)
        else:
            raise CannotFind()

        return self.return_body(self.representation % {'resource'    : saxutils.escape(self.data['resource'] % {'cid' : str(cid)} + self.reconstructParams()),
                                                       'content'     : content})
    def do_DELETE(self):
        """This method handles a DELETE request. It removes the requested storage element by using the 
        del builtin on the dictionary element. The implementation of this for the dictionary should
        raise a ValueError exception if the deletion fails for any reason."""

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        cid = self.path[-1]

        if (cid not in UCStorageResourceHandler.data['items']):
            raise CannotFind()

        del UCStorageResourceHandler.data['items'][cid]

        if cid in UCStorageResourceHandler.data['items']:
            raise ProcessingFailed()

        return self.return_bodyless()


class UCCredentialsResourceHandler (UCResourceHandler):
    """This class handles requests made to the 'uc/credentials' resource. 
    The class member data can be replaced by a dictionary-like object of the form:

      data = { 'resource' : 'uc/credentials',
               'clients'  : { CID AS STRING : CN AS STRING,
                              ...},
             }

    """

    representation = """\
<response resource="%(resource)s"><credentials%(content)s></response>
"""

    data = { 'resource' : 'uc/credentials',
             'clients'  : dict(),
             }

    def do_GET(self):
        """This method checks authentication, and then returns information about current valid credentials."""
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return

        content = '/'
        if len(self.data['clients']) != 0:            
            content = '>'
            for CID in self.data['clients']:
                content += '<client CID="%s" name="%s"/>' % (saxutils.escape(str(CID)), 
                                                             saxutils.escape(str(self.data['clients'][CID])))
            content += '</credentials'
        
        return self.return_body(self.representation % {'resource'    : saxutils.escape(self.resource),
                                                       'content'     : content})

class UCCredentialsCIDResourceHandler (UCResourceHandler):
    """This class handles requests made to the 'uc/credentials/{CID}' resource. 
    """

    representation = None

    data = { 'resource' : 'uc/credentials/%(id)s',
             }

    def do_DELETE(self):
        """This method handles a DELETE request. It removes the requested CID by using the 
        del builtin on the dictionary element. The implementation of this for the dictionary should
        raise a ValueError exception if the deletion fails for any reason.

        This method also removes the asosciated username and password from the authentication server."""

        global uc_server

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        CID = self.path[-1]

        if (CID not in UCCredentialsResourceHandler.data['clients']):
            raise CannotFind()

        uc_server.remove_client_id(CID)

        return self.return_bodyless()




class UCAppsResourceHandler (UCResourceHandler):
    """This class handles requests made to the 'uc/apps' resource.
    """

    representation = '<response resource="%(resource)s"><apps%(content)s></response>'

    data = { 'resource' : 'uc/apps',
             'apps' : dict()
             }

    application_installer = None
    
    def do_GET(self):
        """This method handles a GET request to the 'uc/apps' resource.
        """
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return
           
        content = '/'
        aids = sorted(self.data['apps'].keys())
        if len(aids) > 0:
            content = '>'
            for aid in aids:
                content += self.generate_app_element(aid)
            content+='</apps'

        self.return_body(self.representation % { 'resource' : self.resource,
                                                 'content'  : content })
        return

    def do_POST(self):
        """This method handles a POST request to the 'uc/apps' resource.
        """
        global uc_server
        
        body = self.retrieve_body()

        if self.auth:
            if not self.handler.check_authentication(body):
                return

        if self.application_installer is None:
            raise NotImplemented

        if 'sid' not in self.params or len(self.params['sid']) != 1:
            raise InvalidSyntax

        sid = self.params['sid'][0]

        cid = ''
        if 'cid' in self.params:
            if len(self.params['cid']) != 1:
                raise InvalidSyntax
            cid = self.params['cid'][0]


        aid = self.application_installer.activate(sid,cid)

        content = self.generate_app_element(aid)

        self.return_body(UCAppsIdResourceHandler.representation % { 'resource' : (UCAppsIdResourceHandler.data['resource'] % aid)  + self.reconstructParams(),
                                                                    'content'  : content })
        return

    @classmethod
    def generate_app_element(cls, aid):
        app = cls.data['apps'][aid]
        try:
            remote_enabled = bool_to_xml_string('extension' in app)
            return '<app sid="%s" id="%s" global-app-id="%s" remote-enabled="%s"/>' % (app['sid'],
                                                                                           app['cid'],
                                                                                           aid,
                                                                                           remote_enabled,
                                                                                           )
        except:
            return ''


class UCAppsIdResourceHandler (UCResourceHandler):
    """This class handles requests made to the 'uc/apps/{id}' resources.
    """

    representation = '<response resource="%(resource)s">%(content)s</response>'

    data = { 'resource' : 'uc/apps/%s',
             }

    @classmethod
    def extract_aid(cls,path):
        if (path[0] == 'uc' and
            path[1] == 'apps' and
            path[2] in UCAppsResourceHandler.data['apps']):
            return path[2]
        else:
            raise CannotFind('invalid app-id')
    
    def do_GET(self):
        """This method handles a GET request to the 'uc/apps/{id}' resource.
        """
        
        if self.auth:
            if not self.handler.check_authentication(''):
                return

        aid = self.extract_aid(self.path)
           
        content = UCAppsResourceHandler.generate_app_element(aid)

        self.return_body(self.representation % { 'resource' : (self.data['resource'] % (aid,)) + self.reconstructParams(),
                                                 'content'  : content })
        return

    def do_DELETE(self):
        """This method handles a DELETE request to the 'uc/apps/{id}' resource.
        """

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        if UCAppsResourceHandler.application_installer is None:
            raise NotImplemented

        aid = self.extract_aid(self.path)
           
        UCAppsResourceHandler.application_installer.deactivate(aid)

        return self.return_bodyless()


class UCAppsIdExtResourceHandler (UCResourceHandler):
    """This class handles all requests to a resource of the form 'uc/apps/{id}/ext/{more_path}. It does this by handing all such requests over to another object.
    """
    representation = None
    data = { 'resource' : 'uc/apps/%s/ext/%s' }

    def do(self,method):
        """This method responds to any request at all to this resource."""

        aid = UCAppsIdResourceHandler.extract_aid(self.path)

        if 'extension' not in UCAppsResourceHandler.data['apps'][aid] or UCAppsResourceHandler.data['apps'][aid]['extension'] is None:
            raise NotImplemented

        request_headers = dict(self.handler.headers)
        if 'Authorization' in request_headers:
            del request_headers['Authorization']
        if 'X-UCClientAthorisation' in request_headers:
            del request_headers['X-UCClientAuthorisation']

        try:
            request_body = self.handler.rfile.read(int(self.handler.headers["Content-Length"]))
        except:
            request_body = ''

        (status, headers, body) = UCAppsResourceHandler.data['apps'][aid]['extension'].request(self.path[4:],
                                                                                               method,
                                                                                               request_headers,
                                                                                               self.params,
                                                                                               (not self.auth) or self.handler.check_authentication(request_body),
                                                                                               request_body)

        if status == 401 or status == 402 or 'WWW-Authenticate' in headers or 'X-UCClientAuthenticate' in headers:
            raise ProcessingFailed('Applications is being extremely naughty!')
        
        self.handler.send_response(status)        
        for (key,value) in headers.items():
            self.handler.send_header(key,value)
        self.handler.end_headers()
        self.handler.wfile.write(body)
        return
                                                                                       


class FileResourceHandler (UCResourceHandler):
    """This class handles requests by looking up the path it was invoked with in a dictionary
    stored in its data element and then serving the local file pointed to."""

    representation = None
    
    data = { 'resource' : None,
             'files'    : dict()
             }

    def do_GET(self):
        """This method handles a GET request. If the path handed in is not found in the 'files'
        dictionary then it returns a 404, otherwise it serves the file who's file-name is the 
        entry in 'files' indexed by the path."""

        if self.auth:
            if not self.handler.check_authentication(''):
                return

        if tuple(self.path) in self.data['files']:

            try:
                datafile = open(self.data['files'][tuple(self.path)][0])
            except:
                raise CannotFind

            self.handler.send_response(200)
            self.handler.send_header('Content-Type',self.data['files'][tuple(self.path)][1])
            data = datafile.read()
            datafile.close()
            self.handler.send_header('Content-Length',len(data))
            self.handler.end_headers()

            if not self.head:
                self.handler.wfile.write(data)

            return

        raise CannotFind


# The following global variable is used to represent the "filesystem" hierarchy of the server: 
# The format is at each level a 2-tuple containing a class object descended from UCResourceHandler,
# and a dictionary of subresources below the current resource. Each subresource uses it's top-most
# path element as a key, and is represented by a similar 2-tuple.
#
# For resources which can have an arbitrary id as a path element the special key '*' is used.
#
# The default tree shown below contains only the requires resources 'uc' and 'uc/security'.
#
resources = {
    'uc' : (UCBaseResourceHandler, {
            'security' : (UCSecurityResourceHandler, dict()),
            })
    }


# The followin global variable stores those elements which can be added to the resources tree 
# as options. The format is a dictionary with a key-name identifying each optional resource 
# corresponding to a 2-tuple. The first element of the 2-tuple is an n-tuple containing the 
# path elements of the resource in order, the second is a 2-tuple which is to be added to that
# point in the resources tree.
#
# The default options tree below shows the 'power', 'time', 'events', 'outputs', 'remote', 
# 'feedback', 'sources', 'programmes', 'acquisitions', 'storage', 'apps' and 'credentials' 
# options, as well as the 'images' option which is custom for this library (but rather useful).
#
resource_options = { 
    'power'   : (('uc','power'),(UCPowerResourceHandler, dict())),
    'time'    : (('uc','time'),(UCTimeResourceHandler,  dict())),
    'events'  : (('uc','events'),(UCEventsResourceHandler, dict())),
    'outputs' : (('uc','outputs'),
                (UCOutputsResourceHandler,{
                        '*' : (UCOutputsIdResourceHandler, {
                                'settings' : (UCOutputsIdSettingsResourceHandler, dict()),
                                'playhead' : (UCOutputsIdPlayheadResourceHandler, dict()),
                                }),
                })),
    'remote'  : (('uc','remote'),   (UCRemoteResourceHandler,   dict())),
    'feedback': (('uc','feedback'), (UCFeedbackResourceHandler, dict())),
    'source-lists' : (('uc','source-lists'), (UCSourceListsResourceHandler, {
                '*' : (UCSourceListsIdResourceHandler, dict()),
                })),
    'sources' : (('uc','sources'), (UCSourcesResourceHandler, {
                '*' : (UCSourcesSrefResourceHandler, dict()),
                })),
    'search' : (('uc','search'),  (UCSearchResourceHandler, {
                'outputs' : (GET204Handler, {
                        '*' : (UCSearchOutputsIdResourceHandler, dict()),
                        }),
                'sources' : (GET204Handler, {
                        '*' : (UCSearchSourcesIdResourceHandler, dict()),
                        }),
                'source-lists' : (GET204Handler, {
                        '*' : (UCSearchSourcelistsIdResourceHandler, dict()),
                        }),
                'text' : (GET204Handler, {
                        '*' : (UCSearchTextIdResourceHandler, dict()),
                        }),
                'categories' : (GET204Handler, {
                        '*' : (UCSearchCategoriesIdResourceHandler, dict()),
                        }),
                'global-content-id' : (GET204Handler, {
                        '*' : (UCSearchGlobalcontentidIdResourceHandler, dict()),
                        }),
                'global-series-id' : (GET204Handler, {
                        '*' : (UCSearchGlobalseriesidIdResourceHandler, dict()),
                        }),
                'global-app-id' : (GET204Handler, {
                        '*' : (UCSearchGlobalappidIdResourceHandler, dict()),
                        }),
                })),
    'acquisitions' : (('uc','acquisitions'), (UCAcquisitionsResourceHandler, {
                '*' : (UCAcquisitionsIdResourceHandler, dict()),
                })),
    'storage'    : (('uc', 'storage'), (UCStorageResourceHandler, {
                '*' : (UCStorageIdResourceHandler, dict()),
                })),
    'credentials' : (('uc', 'credentials'), (UCCredentialsResourceHandler, {
                '*' : (UCCredentialsCIDResourceHandler, dict()),
                })),
    'categories' : (('uc', 'categories'), (UCCategoriesResourceHandler, dict())),
    'images'     : (('images',), (FileResourceHandler, {
                '**' : (FileResourceHandler, dict()),
                })),
    'apps'       : (('uc','apps'), (UCAppsResourceHandler,
                                    { '*' : (UCAppsIdResourceHandler, 
                                             { '**' : (UCAppsIdExtResourceHandler,
                                                       dict()),}),
                                      }
                                    )
                    ),
    }

def escape_dict(input):
    """A utility function used to espace the contents of a dictionary for inclusion in XML."""
    output = dict()
    for key in input:
        output[key] = saxutils.escape(str(input[key]))
    return output


def parse_iso(ts):
    """This function takes in a timestamp in ISO-standard form, and returns a datetime.datetime object."""

    if ts.count('T') > 1:
        raise ValueException("Too many Ts")
    elif ts.count('T') == 1:
        (date,time) = ts.split('T',1)
    else:
        if ts.count(':') > 0:
            date = None
            time = ts
        else:
            date = ts
            time = None

    if date is not None:
        (year,month,day) = map(int,date.split('-'))
    else:
        (year,month,day) = (None,None,None)
    if time is not None:
        (zminute, zhour) = (0,0)
        if time[-1] == 'Z':
            time = time[:-1]
        elif time.count('+') == 1:
            (time,zone) = time.split('+',1)
            zhour = int(zone[:2])
            if len(zone) > 2:
                zminute = int(zone[-2:])
        elif time.count('-') == 1:
            (time,zone) = time.split('-',1)
            zhour = -int(zone[:2])
            if len(zone) > 2:
                zminute = -int(zone[-2:])

        if time.count('.') == 1:
            (time,micro) = time.split('.')
            micro = int((micro + '000000')[:6])
        else:
            micro = 0
        
        (hour,minute,second) = map(int,time.split(':'))
    else:
        (hour,minute,second) = (None,None,None)
        
    if hour is not None:
        tz = datetime.timedelta(hours=-zhour,minutes=-zminute)
    else:
        tz = datetime.timedelta()

    return datetime.datetime(year,month,day,hour,minute,second,micro) + tz

def parse_bool(value):
    """This function returns a boolean value based on a string as specified
    in the UC Specification"""

    try:
        return { 'true' : True,
                 '1'    : True,
                 'false': False,
                 '0'    : False }[str(value)]
    except:
        raise ValueError

def bool_to_xml_string(value):
    """This method takes a boolean value and returns a string containing either 'true' or 'false'"""

    return 'true' if value else 'false'

def unpctencode(input):
    i = 0
    output = ''
    while i < len(input):
        if input[i] == '%':
            if input[i+1] == '%':
                output += '%'
                i+=2
            elif re.match('[0-9a-fA-F]{2}',input[i+1:i+3]):
                output += '%c' % int(input[i+1:i+3],16)
                i+=3
            else:
                raise ValueError
        else:
            output += input[i]
            i+=1
    return output

def isidtype(input):
    return re.match('^([a-zA-Z0-9\-\._~]|%[0-9a-fA-F][0-9a-fA-F])+$',
                    input)

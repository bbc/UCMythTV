# Universal Control Server - HTTP Handling
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
HTTP Handling for the UCServer library

This module contains classes used by the main UCServer library to handle
individual HTTP requests.  It is not intended for use by individual
developers working of specific server implementations.  """

__version__ = "0.6.0"

__all__ = ["UCHandler",
           "UCHTTPServer"]

#Standard Python imports
import BaseHTTPServer
import SocketServer
import datetime
import traceback
from urlparse import urlparse, parse_qs, parse_qsl, ParseResult
from urllib import unquote

#imports from elsewhere in this project
import UCAuthenticationServer
import BasicCORSServer

#imports from elsewhere in this package
from Exceptions import *
from Exceptions import UCException
from ResourceHandlers import resources



class UCHTTPServer (SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer): 
    """This is simply a threaded version of the standard HTTPServer which records the timestamp for all requests before dispatching a thread."""
    
    def process_request(self, request, client_address):
        request = (datetime.datetime.utcnow(),request)
        return SocketServer.ThreadingMixIn.process_request(self, request, client_address)

    def close_request(self, request):
        return BaseHTTPServer.HTTPServer.close_request(self,request[1])

class UCHandler (BasicCORSServer.CORSRequestHandler, UCAuthenticationServer.UCAuthenticationAndRestrictionRequestHandler):
    """This class is the HTTPRequestHandler used by the Universal Control server. It descends ftom HTTPDigestAuthenticationRequestHandler because it needs to 
    support digest authentication for the security scheme.

    It behaves exactly like a normal HTTPDigestAuthenticationRequestHandler with a few tweeks:

    -- Requests will not be authenticated unless the class member 'auth' is set to True (it is False by default)
    -- This class has a member 'crossdomain_xml' which contains the response body which will be returned by a GET request to the URI 'crossdomain.xml'. By default
       this is a crossdomain xml document permitting access to the entire server.
    -- This class correctl handles CORS preflight and actual requests. The member 'max_age' can be set to a number of seconds after which a new preflight will be
       required.
    -- The class members 'allow_methods' and 'extra_headers' are used to control the CORS response headers
    -- Error messages produced by this server will be UC spec compliant XML error responses not human-readable text as is the default.
    -- Upon receiving a request (other than a crossdomain.xml request or a CORS preflight request) this class will walk the tree of resources maintained by the 
       UCServer class and the UCServer.ResourceHandlers module and instantiate the class which has been bound to the correct path. If no class has been bound
       then it will return a 405 error. This class DOES NOT check authentication on requests before doing this -- if the individual resource handling class 
       needs authentication checked then it needs to call the 'check_authentication' method of this class to do it. This method will return False and send a 402 
       challenge to the client if authentication fails. If the 'auth' member of this class is False then this method will always return True, otherwise it will 
       return True if authentication is succesful.

       Restriction checking can be handled by making a call to check_confirmation or check_authorisation, both of which will return True if the request passes the
       restriction requirements, return "failed" and return a 402 error with no challenge if the request failed the restriction, return "aborted" if the request
       was aborted, and return the nonce of the authentication check otherwise.

    log_message is a class method which logs a message either to standard out or to the specified log-file.
    """

    authenticated_callback = None

    standby = False

    server_version='UCserver/%s' % __version__

    log_file = None

    log_filename = None

    base_uri = "uc"
    realm = None
    auth = False

    #With this value set to 0 preflights are required for all CORS requests. This is useful for testing purposes. For general usage a value of 2700 (ie. 45 minutes) would be fine.
    CORS_max_age = 2700

    CORS_allow_methods = ("GET","PUT","POST","DELETE")

    crossdomain_xml = """\
<?xml version="1.0"?><!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd"><cross-domain-policy><site-control permitted-cross-domain-policies="master-only"/><allow-access-from domain="*"/></cross-domain-policy>
"""

    #This server returns error messages in XML format as specified in the Universal Control specification
    error_message_format = """\
<error code="%(code)d">%(message)s : %(explain)s.</error>
"""
    error_content_type = "application/xml"

    def __init__(self, request, client_address, server):
        if isinstance(request,tuple) and len(request) == 2:
            self.rcvdtime = request[0]
            request = request[1]
        else:
            self.rcvdtime = datetime.datetime.utcnow()
        UCAuthenticationServer.UCAuthenticationAndRestrictionRequestHandler.__init__(self, request, client_address, server)

    def authenticated(self,client_id):
        if self.authenticated_callback is not None:
            self.authenticated_callback(client_id)

    def check_authentication(self, body, iteration=None, nc_limit=None, timeout=None):
        """Unlike its parent class this class supports switching off authentication checking."""
        if self.auth:
            return UCAuthenticationServer.UCAuthenticationRequestHandler.check_authentication(self,body,iteration,nc_limit,timeout)
        else:
            return True

    def process_path(self):
        """This function is used to process the path into a n-tuple of path-component strings, the entire query string, and a dictionary indexed by strings of arrays of strings containing the query parameters."""

        params = dict()
        path = self.path
        query = ''
        try:
            parse = urlparse(path)
            path = parse.path
            query = '?' + unquote(parse.query)
            params = parse_qs(parse.query)
        except:
            pass

        return (path.strip('/').split('/'),query,params)

    def handle_one_request(self):
        """This function is overriden to dispatch slightly differently from the default.
        Whilst the default version calls do_{VERB} if it is available this version instead calls do_OPTIONS for OPTIONS requests, and do for all other requests. It also records the received time on the request."""

        self.raw_requestline = self.rfile.readline()
        if not self.raw_requestline:
            self.close_connection = 1
            return
        if not self.parse_request(): # An error code has been sent, just exit
            return

        if self.command == "OPTIONS":
            return self.do_OPTIONS()
        else:
            return self.do(self.command)

    def do_crossdomain_xml_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.crossdomain_xml)
        return

    def do(self,method):        
        """This method is used to handle all requests except for CORS preflight requests. It makes use of the global structure resources which can be found near the end of this file and manages the structure of the server's "filesystem".

        The method handle_resource is called to walk this tree and determine what the correct handler class to use is, and the apropriate 'do_{VERB}' method of this class is then executed."""

        global resources

        try:
            (path,query,params) = self.process_path()

            if ((method == "GET") and (path == ['crossdomain.xml'])):
                return self.do_crossdomain_xml_GET()

            #Allow overriding of the method using the 'method_' query variable
            if 'method_' in params:
                method = params['method_'][0]

            head = False
            if method == "HEAD":
                head = True
                method = "GET"
        
            if len(path) != 0:
                cls = self.handle_resource(path, params, resources)
                if cls is not None:                    
                    handler = cls(self,path,query,params,head=head)

                    if self.standby:
                        if hasattr(handler,'standby_do'):
                            return handler.standby_do(method)
                        else:
                            return getattr(handler,'standby_do_' + method)()
                    else:
                        if hasattr(handler,'do'):
                            return handler.do(method)
                        else:
                            return getattr(handler,'do_' + method)()
        except ProcessingFailed as e:
            self.log_message(traceback.format_exc())
            try:
                self.send_error(e.code,str(e))
            except:
                self.log_message("Tried to respond to closed connection")
            return            
        except UCException as e:
            try:
                self.send_error(e.code,str(e))
            except:
                self.log_message("Tried to respond to closed connection")
            return
        except:
            try:
                self.log_message(traceback.format_exc())
                self.send_error(500)
            except:
                self.log_message("Tried to respond to closed connection")
            raise
        else:
            try:
                self.send_error(405)
            except:
                self.log_message("Tried to respond to closed connection")

    def handle_resource(self, path, params, tree):
        """This method is called recursively to walk through the structure 'UCServer.ResourceHandlers.resources' to identify which 
        handler class to use for handling a specific request."""

        if path[0] in tree:
            if len(path) == 1:
                return tree[path[0]][0]
            else:
                return self.handle_resource(path[1:],params,tree[path[0]][1])
        elif '*' in tree:
            if len(path) == 1:
                return tree['*'][0]
            else:
                return self.handle_resource(path[1:],params,tree['*'][1])
        elif '**' in tree:
            return tree['**'][0]
        else:
            return None

    @classmethod
    def log_message(cls, format, *args):
        """Takes a format string and necessary arguments to fill it out as parameters.

        Logs the specified message to the logfile specified by the class member 'log_filename', or
        to standard error if that is None.
        """
        if cls.log_file is None:
            if cls.log_filename is not None:
                cls.log_file = open(cls.log_filename,'w')
            else:
                import sys
                cls.log_file = sys.stderr

        if len(args) > 0:
            cls.log_file.write(format % args)
        else:
            cls.log_file.write(format)
        cls.log_file.write('\n')
        cls.log_file.flush()

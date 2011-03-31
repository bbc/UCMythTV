# Basic CORS Server    
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
HTTP server with CORS support.

Contents:

- CORSRequestHandler: HTTP request handler with CORS support

For further queries contact james.barrett@bbc.co.uk
"""

__version__ = "0.1"

__all__ = ["CORSRequestHandler"]

import BaseHTTPServer

class CORSRequestHandler (BaseHTTPServer.BaseHTTPRequestHandler) :
    """An HTTP Request Handler with extra methods used to implement CORS

    The clas implements several new class variables, including:

    - CORS_max_age -- an integer which controls how often preflight requests are required. 0 means they are required every time, 2700 (the default) means they are required once every 45 minutes.

    - CORS_allow_methods -- A tuple of methods which are allowed on CORS requests, by default this is ("GET","PUT","POST","DELETE").
    
    - CORS_allow_origins -- A list of origins which are permitted. By default this is ['*',], which means that all origins are allowed.

    - CORS_allow_credentials -- A boolean, False by default, which controls whether or not credentialed requests are allowed.

    Subclasses should be careful of overriding do_OPTIONS or end_headers. Any override of end_headers must take an optional parameter CORS which can be set to a False boolean value. Subclasses of do_OPTIONS should call the parent if they want CORS preflights to be handled.
    """

    protocol_version="HTTP/1.1"
    server_version='BasicCORSServer/0.1'

    #With this value set to 0 preflights are required for all CORS requests. This is useful for testing purposes. For general usage a value of 2700 (ie. 45 minutes) would be fine.
    CORS_max_age = 2700

    CORS_allow_methods = ("GET","PUT","POST","DELETE")
    CORS_allow_origins = ['*',]
    CORS_allow_credentials = False

    def end_headers(self,CORS=True):
        """Send the blank line ending the MIME headers, as well as the headers required by CORS."""
            
        #This next section implements a work-around for a flaw in Chrome's implementation of CORS
        try:
            origin  = self.headers.getheader("Origin")
        except:
            origin = None
        if origin is None:
            try:
                origin = self.headers.getheader("Referer")
            except:
                origin = None

        if CORS:
            #The below headers need to be added in order to comply with CORS
            if origin is not None and ('*' in self.CORS_allow_origins or origin in self.CORS_allow_origins):
                self.send_header("Access-Control-Allow-Origin", origin)
            elif origin is None and '*' in self.CORS_allow_origins:
                self.send_header("Access-Control-Allow-Origin", '*')
            if self.CORS_allow_credentials:
                self.send_header("Access-Control-Allow-Credentials",'true')

        if self.request_version != 'HTTP/0.9':
            self.wfile.write("\r\n")

    def do_OPTIONS(self):
        """This function is called whenever an OPTIONS request is recieved and implements the CORS preflight request mechanism."""

        origin  = self.headers.getheader("Origin")
        #This works around a bug in Chrome's implementation of CORS
        if origin is None:
            origin = self.headers.getheader("Referer")
        headers = self.headers.getheader("Access-Control-Request-Headers")
        if headers is None:
            headers = "Origin"
        else:
            headers = headers + ", Origin"


        if origin is not None and ('*' in self.CORS_allow_origins or origin in self.CORS_allow_origins):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", origin)
        elif origin is None and '*' in self.CORS_allow_origins:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", '*')
        else:
            self.send_error(403)
            return

        if self.CORS_allow_credentials:
            self.send_header("Access-Control-Allow-Credentials",'true')

        self.send_header("Access-Control-Max-Age", self.CORS_max_age)
        self.send_header("Access-Control-Allow-Methods",', '.join(self.CORS_allow_methods))
        self.send_header("Access-Control-Allow-Headers",headers)
        self.end_headers(CORS=False)
        return

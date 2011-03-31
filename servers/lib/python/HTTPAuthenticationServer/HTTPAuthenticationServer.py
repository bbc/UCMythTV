# distutils setup script for Basic CORS Server
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

"""HTTP server with Authentication support.

Note: the class in this module doesn't implement any HTTP request; see
SimpleHTTPServer for simple implementations of GET, HEAD and POST
(including CGI scripts). It should be perfectly possible to make a 
SimpleHTTPAuthenticationHandler which inherits from both.

Contents:

- HTTPDigestAuthenticationRequestHandler: HTTP request handler with Digest Authentication support

For further queries contact james.barrett@bbc.co.uk
"""

__version__ = "0.1"

__all__ = ["HTTPDigestAuthenticationRequestHandler"]

import BaseHTTPServer

# some platforms we use lack hashlib
try:
    import hashlib
except:
    import md5py as hashlib

import rfc822

class HTTPDigestAuthenticationRequestHandler (BaseHTTPServer.BaseHTTPRequestHandler) :
    """An HTTP Request Handler with extra methods used to implement digest authentication.

    To make use of this class subclass it and implement your do_VERB methods as usual, if you 
    want to check whether the client is authenticated call self.check_authentication(realm) with 
    a realm identifying string. 

    The class method add_user is used to add a username and password pair to the authentication 
    information. There is a single authentication database for all request handlers with the same
    class -- so if you need seperate authentication databases use seperate subclasses.

    If you are subclassing this class to make use of an algorithm other than MD5 then remember to 
    set the algroithm class variable to the value which will be returned for the "algorithm" 
    parameter in the HTTP headers.
    
    The standard implementation supports only "auth" qop. If you want to support other forms of 
    qop add them to the qop class variable, which is a list of strings defaulting to ("auth",).
    In order to implement additional types of qop one must also implement a generate_HA2_{qop} method
    for that type of qop."""

    protocol_version="HTTP/1.1"
    server_version='HTTPAuthenticationServer/0.1'

    password_hashes = dict()
    pending_passwords = dict()
    algorithm = "MD5"
    qop = ("auth",)

    @classmethod
    def hash(cls,data):
        """Class method to return the hash of the given data. The default implementation returns an 
        MD5 hash using hashlib."""
        return hashlib.md5(data).hexdigest()

    def generate_opaque(self,realm):
        """This method is called by check_authentication to generate the opaque value. The default 
        implementation returns "0000000000000000000000000000000000"."""

        return "0000000000000000000000000000000000"

    def generate_nonce(self, realm):
        """This method is called by check_authentication to generate the nonce value. The default 
        implementation returns the hash of the realm value, the client address and the server instance 
        represented as a string. Override it to change this behaviour."""
        return self.hash(realm + ":" + self.client_address[0] + ":" + str(self.server))

    def check_nonce_count(self, realm, nonce_count):
        """This method is called by check_authentication to check if the nonce-count given by the client
        is valid. It returns True if the authentication should continue, and False if it should fail and
        make an authentication challenge. The default implementation simply returns True."""
        return True

    def generate_HA2_auth (self, uri=None):
        """This method generates the HA2 hash for the "auth" qop type."""
        if uri is None:
            uri = self.path
        
        return self.hash("%(request)s:%(digest_uri)s" % {'request'    : self.command,
                                                         'digest_uri' : uri})


    def check_authentication(self, realm):
        """Returns True if the request is correctly authenticated for the specified realm and False 
        otherwise. If it returns False then it also sends a 401 error with a challenge demanding that 
        the client authenticate itself."""
        
        self.username = None
        self.realm    = None

        nonce = self.generate_nonce(realm)
        stale = "false"

        auth_string = self.headers.getheader("Authorization")
        try:
            if auth_string is not None:
                if auth_string[:6] != "Digest":
                    raise Exception

                params = dict()
                for p in auth_string[7:].split(','):
                    (key,value) = map(str.strip,p.split('=',1))
                    params[key] = rfc822.unquote(value)

                if realm != params['realm']:
                    raise Exception, "Incorrect Realm"

                if params['opaque'] != self.generate_opaque(realm):
                    raise Exception, "Invalid Opaque Value"

                if params['qop'] not in self.qop:
                    raise Exception, "Invalid qop"

                mname = 'generate_HA2_' + params['qop']

                if not hasattr(self,mname):
                    raise Exception, "qop method not implemented"

                method = getattr(self,mname)
                HA2 = method(uri=params['uri'])

                if not self.check_nonce_count(realm,params['nc']):
                    raise Exception, "Invalid Nonce Count"

                username = params['username']
                self.username = username
                self.realm    = realm

                if realm not in self.password_hashes:
                    self.password_hashes[realm] = dict()

                if username in self.password_hashes[realm]:
                    request_digest = self.hash("%(HA1)s:%(nonce)s:%(nonce_count)s:%(cnonce)s:%(qop)s:%(HA2)s"
                                               % {'HA1'        : self.password_hashes[realm][username],
                                                  'nonce'      : params['nonce'],
                                                  'nonce_count': params['nc'],
                                                  'cnonce'     : params['cnonce'],
                                                  'qop'        : params['qop'],
                                                  'HA2'        : HA2,
                                                  })

                    if request_digest == params['response']:
                        if nonce != params['nonce']:
                            stale = "true"
                        else:    
                            self.authenticated(params['username'], params['nonce'], params['nc'])
                            return True

                elif realm in self.pending_passwords:
                    for password in self.pending_passwords[realm]:
                        HA1 = self.hash("%(username)s:%(realm)s:%(password)s" % {'username' : username,
                                                                                'realm'    : realm,
                                                                                'password' : password})
                        request_digest = self.hash("%(HA1)s:%(nonce)s:%(nonce_count)s:%(cnonce)s:%(qop)s:%(HA2)s"
                                                   % {'HA1'        : HA1,
                                                      'nonce'      : params['nonce'],
                                                      'nonce_count': params['nc'],
                                                      'cnonce'     : params['cnonce'],
                                                      'qop'        : params['qop'],
                                                      'HA2'        : HA2,
                                                      })

                        if request_digest == params['response']:
                            if nonce != params['nonce']:
                                stale = "true"
                            else:
                                self.add_user(realm, username, password=None, hash=HA1)
                                callback = self.pending_passwords[realm][password]
                                self.del_pending_password(realm, password)
                                self.authenticated(username, nonce, params['nc'])
                                callback(username)
                                return True
        except:
            self.log_error("Failed Authentication Attempt")
            pass

        #Check has failed
        self.send_response(401, "Unauthorized")
        self.send_header('Content-Type','text/html')
        self.send_header('WWW-Authenticate', """\
Digest
     realm="%(realm)s",
     qop="%(qop)s",
     nonce="%(nonce)s",
     opaque="%(opaque)s",
     stale="%(stale)s",
     algorithm="%(algorithm)s"
""" % {'realm' : realm,
       'qop'   : ' '.join(self.qop),
       'nonce' : nonce,
       'opaque': self.generate_opaque(realm),
       'stale' : stale,
       'algorithm' : self.algorithm})
        self.end_headers()
        return False

    def authenticated(self,username,nonce,nc):
        pass

    @classmethod
    def add_user(cls, realm, username, password=None, hash=None):
        """A class method used to add a user to the list of valid authentication details for all
        request handlers of this class."""
    
        if realm not in cls.password_hashes:
            cls.password_hashes[realm] = dict()
        
        if hash is None:
            if password is None:
                raise ValueError
            
            hash = cls.hash("%(username)s:%(realm)s:%(password)s" % {'username' : username,
                                                                     'realm'    : realm,
                                                                     'password' : password})
        cls.password_hashes[realm][username] = hash


    @classmethod
    def add_pending_password(cls, realm, password, callback=None):
        """Add a password which will be accepted for any username, and will be assosciated thenceforth
        with the first username succesfully authenticated with it.

        When this happens the callback function is called."""

        if realm not in cls.pending_passwords:
            cls.pending_passwords[realm] = dict()

        cls.pending_passwords[realm][str(password)] = callback
        self.log_message('Password: %r added to valid credentials for realm: %r', password, realm)

        return

    @classmethod
    def del_pending_password(cls, realm, password):
        if realm in cls.pending_passwords:
            if str(password) in cls.pending_passwords[realm]:
                del cls.pending_passwords[realm][str(password)]
                self.log_message('Password: %r deleted from valid credentials for realm: %r', password, realm)

    @classmethod
    def del_pending_passwords(cls, realm):
        if realm in cls.pending_passwords:
            for password in cls.pending_password[realm]:
                del cls.pending_passwords[realm][password]
                self.log_message('Password: %r deleted from valid credentials for realm: %r', password, realm)

    @classmethod
    def del_user(cls, realm, username):
        """A class method used to remove a user from the list of valid authentication details for all
        request handlers of this class"""
        
        if realm in cls.password_hashes:
            if username in cls.password_hashes[realm]:
                del cls.password_hashes[realm][username]

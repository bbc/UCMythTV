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

"""HTTP server with UC Style Authentication support.

Note: the class in this module doesn't implement any HTTP request; see
SimpleHTTPServer for simple implementations of GET, HEAD and POST
(including CGI scripts). It should be perfectly possible to make a 
SimpleHTTPAuthenticationHandler which inherits from both.

Contents:

- UCAuthenticationRequestHandler: HTTP request handler with UC Style Authentication support
- UCAuthenticationAndRestrictionHandler: HTTP request handler with UC style Authentication
  and restriction support.
- PBKDF2_HMAC: a method which can be called to execute the PBKDF2_HMAC algorithm.

For further queries contact james.barrett@bbc.co.uk
"""

__version__ = "0.1"

__all__ = ["UCAuthenticationRequestHandler",
           "UCAuthenticationAndRestrictionHandler",
           "PBKDF2_HMAC"]

import BaseHTTPServer
import re
import hashlib
import time
import threading
import random

def PBKDF2_HMAC(P,S,c,H=None):
    """This method can be called with apropriate values for P, S, and c" to 
    acquire the results of the PBKDF2_HMAC algorithm as a string of bytes. It
    does not render these bytes in hex format automatically

    The default algorithm used if none is specified is SHA1."""
    
    def __sha1(data):
        return hashlib.sha1(data).digest()

    if H is None:
        H = __sha1

    if len(P) > 64:
        K = H(P)
    else:
        K = P
        
    K += '\00'*(64-len(K))
    
    K1 = ''.join([ '%c' % (ord(x) ^ 0x5c) for x in K ])
    K2 = ''.join([ '%c' % (ord(x) ^ 0x36) for x in K ])

    U = [ H(K1 + H(K2 + S + '\00\00\00\01')), ]
    while len(U) < c:
        U.append(H(K1 + H(K2 + U[-1])))
    
    return reduce(lambda d, u : ''.join([ '%c' % (ord(x) ^ ord(y)) for (x,y) in zip(d,u) ]),
                    U)


class UCAuthenticationRequestHandler (BaseHTTPServer.BaseHTTPRequestHandler) :
    """An HTTP Request Handler with extra methods used to implement UC authentication.

    To make use of this class subclass it and implement your do_VERB methods as usual, if you 
    want to check whether the client is authenticated call self.check_authentication(body) with
    the body of the request as the parameter. This method is adequately described in its own
    docstring.

    

    You may wish to set the following class members:
    
    - nc_limit      -- the default number of times a nonce can be used. 10 by default
    - nonce_timeout -- the number of seconds which a nonce remains valid for
    - HMAC_iteration_count -- the default number of iterations for the HMAC algorithm

    - authentication_challenge_type -- the Content-Type for 402 bodies.
    - authentication_challenge_body -- the content of a 402 body.
    """

    protocol_version="HTTP/1.1"
    server_version='UCAuthenticationServer/0.1'

    nc_limit = 10
    nonce_timeout = 5.0

    authentication_challenge_type='text/html'
    authentication_challenge_body="""\
<html>
  <head>
    <title>Not Authenticated</title>
  </head>
  <body>
    <h1>Not Authenticated</h1>
    <p>Error code 402.</p>
    <p>Message: Not Authenticated.</p>
  </body>
</html>\r\n"""

    HMAC_iteration_count=10

    _rand = random.SystemRandom()

    _client_credentials = {}
    __pending_credentials = None
    _credentials_lock = threading.RLock()

    __nonce_counts = {}
    __nonce_counts_lock = threading.RLock()

    def authenticated(self, client_id):
        """This method is called whenever a pending client-id becomes a permanent
        one. It should be overridden to implement the shutting down of the pairing
        screen as specified in the spec."""
        pass

    def digest(self,P,S,c):
        """This method calculates the digest, it can be overridden if desired."""
        return ''.join([ '%02x' % ord(x) for x in PBKDF2_HMAC(P,S,c) ])

    def nonce_is_valid(self,nonce,nc,nc_limit):
        """This method returns True if the nonce is valid and current and has the
        the right count, (False,"true") if it is valid but stale, or has the wrong
        count, and (False,"false") if it was always invalid. It also checks the 
        nonce-count and updates the stored nonce-count as required. If the nc is
        greater than or equal to self.nc_limit (10 by default) then the nonce is
        removed from the list of valid nonces and True is returned (this request
        will succeed, but the next one will need authentication).

        The default implementation works with the default implementation of form_nonce
        and should be overridden if that method is.
        """

        with self.__nonce_counts_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__nonce_counts 
                       if (now > int(x[:16],16)) ]:
                del self.__nonce_counts[n]

        if not re.match(r'[0-9a-fA-F]{56}', nonce):
            return (False, "false")

        if nonce[16:] != hashlib.sha1('%s:%s:%s:%x' % (nonce[:16],
                                                       self.command,
                                                       self.path,
                                                       hash(self.server),
                                                       )
                                      ).hexdigest():
            return (False, "false")

        with self.__nonce_counts_lock:
            if (nonce not in self.__nonce_counts):
                return (False, "true")

            if (nc < self.__nonce_counts[nonce]):
                del self.__nonce_counts[nonce]
                return (False, "true")

            if nc >= nc_limit:
                del self.__nonce_counts[nonce]
            else:
                self.__nonce_counts[nonce] = nc
        
        return True

    def check_uri(self,uri):
        """This method should return True if the uri matches the resource to which
        this request was made. The default implementation uses a fairly simply
        but fairly reliable check that the path segments of the uris match."""

        return (re.split(r'/+',uri.strip('/')) == re.split(r'/+',self.path.strip('/')))
        
    def form_nonce(self, nc_limit, timeout):
        """This method can be overridden in subclasses to change how the nonce is formed.
        By default it uses the nonce formation mechanism described in the spec with the
        hash of the server instance as the private data."""
        with self.__nonce_counts_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__nonce_counts 
                       if (now > int(x[:16],16)) ]:
                del self.__nonce_counts[n]

            timestamp = int((time.time() + timeout)*1000000) % (1 << 64)
            digest = hashlib.sha1('%016x:%s:%s:%x' % (timestamp,
                                                      self.command,
                                                      self.path,
                                                      hash(self.server))
                                  ).hexdigest()
        
            nonce = "%016x%s" % (timestamp,digest)

            self.__nonce_counts[nonce] = 0

        return nonce

    def __validate_authentication_for_request(self, body, iteration, nc_limit):
        """This method will check the X-UCClientAuthorisation header for validity, and return True
        if it validates correctly, and (False,stale) otherwise, where "stale" is the value of the stale 
        parameter"""

        if 'X-UCClientAuthorisation' not in self.headers:
            return (False,"false")        

        credentials = self.headers['X-UCClientAuthorisation']

        match = re.search(r'Authenticate\s+nonce="([0-9a-fA-F]+)",\s*iteration="([0-9a-fA-F]+)",\s*uri="([^"]*)",\s*digest="([0-9a-fA-F]+)",\s*nc="([0-9a-fA-F]+)",\s*client-id="([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",\s*cnonce="([0-9a-fA-F]+)"',credentials)

        if not match:
            return (False,"false")

        try:
            nonce=match.group(1)
            citeration=int(match.group(2),16)
            uri = match.group(3)
            digest=match.group(4)
            nc = int(match.group(5),16)
            client_id = match.group(6)
            cnonce = match.group(7)
        except:
            return (False,"false")

        if not self.check_uri(uri):
            return (False,"false")

        with self._credentials_lock:
            if (self.__pending_credentials is not None 
                and self.__pending_credentials[0] == client_id):
                LSGS = self.__pending_credentials[1][0]
                CN = self.__pending_credentials[1][1]
                pending = True
            elif client_id in self._client_credentials:
                LSGS = self._client_credentials[client_id][0]
                pending = False
            else:
                return (False,"false")

            retval = self.nonce_is_valid(nonce,nc,nc_limit)
            if retval == (False,"false"):
                return retval

            if citeration != iteration:
                return (False,"false")

            new_digest = self.digest(LSGS,
                                     '%s:%s:%s:%s:%08x:%s' % (self.command,
                                                              uri,
                                                              nonce,
                                                              body,
                                                              nc,
                                                              cnonce,
                                                              ),
                                     iteration)

            if digest != new_digest:
                return (False,"false")

            if pending:
                self._client_credentials[client_id] = (LSGS, CN)
                self.__pending_credentials = None
                self.authenticated(client_id)

        return retval

    def __form_and_issue_challenge(self, iteration, stale, nc_limit, timeout):
        """This method forms the challenge headers and sends them back to the client."""
        nonce = self.form_nonce(nc_limit,timeout)

        challenge = """\
Authenticate
     nonce="%s",
     iteration="%08x",
     stale="%s"
""" % (nonce, iteration, stale)

        self.send_response(402)
        self.send_header('Content-Type',self.authentication_challenge_type)
        self.send_header('Content-Length', len(self.authentication_challenge_body))
        self.send_header('X-UCClientAuthenticate',challenge)
        self.end_headers()
        self.wfile.write(self.authentication_challenge_body)
        
    def check_authentication(self, body, iteration=None, nc_limit=None, timeout=None):
        """Returns True if the request is correctly authenticated and False otherwise. If it 
        returns False then it also sends a 402 error with a challenge demanding that the client 
        The iteration count can be manually specified, as can a nc_limit, which limits the
        number of times an individual nonce can be reused.

        authenticate itself."""
        
        if iteration is None:
            iteration = self.HMAC_iteration_count
        if nc_limit is None:
            nc_limit = self.nc_limit
        if timeout is None:
            timeout = self.nonce_timeout
        
        valid = self.__validate_authentication_for_request(body,iteration,nc_limit)
        if valid == True:
            return True

        self.__form_and_issue_challenge(iteration,valid[1],nc_limit,timeout)
        return False

    @classmethod
    def add_client_id(cls, client_id, LSGS, client_name, permanent=False):
        """This method is called to add a client-id to the valid credentials for 
        authentication. If permanet is set to True then this is added permanently
        (until removed), if not then it is set as a "pending" client-id, replacing
        any pending id currently stored.

        Only one set of credentials can be stored for a particular client-id
        at a time."""
        with cls._credentials_lock:                
            if permanent:
                cls._client_credentials[client_id] = (LSGS, client_name)
                if (cls.__pending_credentials is not None 
                    and cls.__pending_credentials[0] == client_id):
                    cls.__pending_credentials = None
            else:
                if client_id in cls._client_credentials:
                    del cls._client_credentials
                cls.__pending_credentials = (client_id,(LSGS, client_name))

    @classmethod
    def remove_client_id(cls, client_id):
        """This method is called to remove a client-id from the list of valid
        credentials for authentication."""
        with cls._credentials_lock:                
            if (cls.__pending_credentials is not None 
                and cls.__pending_credentials[0] == client_id):
                cls.__pending_credentials = None
            if client_id in cls._client_credentials:
                del cls._client_credentials[client_id]

    @classmethod
    def clear_pending_credentials(cls):
        """This method removes any client-id currently pending."""
        with cls._credentials_lock:       
            cls.__pending_credentials = None

    @classmethod
    def client_list(cls):
        """This method returns a list of all currently permanently 
        authenticated clients. The list is of elements of the form:

        (client_id, client_name)

        """
        return [ (client_id, cls._client_credentials[client_id][1]) for client_id in cls._client_credentials ]

class UCAuthenticationAndRestrictionRequestHandler (UCAuthenticationRequestHandler) :
    """This handler class can be used to implement both the Authentication scheme
    and also the Restriction mechanism described in the spec.

    To make use of this mechanism call self.check_confirmation() or 
    self.check_authorisation()."""

    restriction_abort_type='text/html'
    restriction_abort_body="""\
<html>
  <head>
    <title>Aborted</title>
  </head>
  <body>
    <h1>Aborted</h1>
    <p>Error code 410.</p>
    <p>Message: This action has been aborted.</p>
  </body>
</html>\r\n"""


    confirmation_timeout = 5.0

    authorisation_iteration = 5000

    __confirmation_nonces = []
    __confirmation_nonces_lock = threading.RLock()

    __authorisation_nonces = []
    __authorisation_nonces_lock = threading.RLock()

    def confirmation_nonce_is_valid(self,nonce):
        """This method returns True if the nonce is valid and False otherwise,
        and sets the nonce as no longer valid either way.

        The default implementation works with the default implementation of 
        form_confirmation_nonce and should be overridden if that method is.
        """

        with self.__confirmation_nonces_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__confirmation_nonces 
                       if (now > int(x[:16],16)) ]:
                self.__confirmation_nonces.remove(n)

            if nonce not in self.__confirmation_nonces:
                return False

            self.__confirmation_nonces.remove(nonce)
        
        return True

    def authorisation_nonce_is_valid(self,nonce):
        """This method returns True if the nonce is valid and False otherwise,
        and sets the nonce as no longer valid either way.

        The default implementation works with the default implementation of 
        form_authorisation_nonce and should be overridden if that method is.
        """

        with self.__authorisation_nonces_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__authorisation_nonces 
                       if (now > int(x[:16],16)) ]:
                self.__authorisation_nonces.remove(n)

            if nonce not in self.__authorisation_nonces:
                return False

            self.__authorisation_nonces.remove(nonce)
        
        return True



    def form_confirmation_nonce(self,timeout):
        """This method can be overridden in subclasses to change how the nonce is formed.
        """
        with self.__confirmation_nonces_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__confirmation_nonces 
                       if (now > int(x[:16],16)) ]:
                self.__confirmation_nonces.remove(n)

            timestamp = int((time.time() + timeout)*1000000) % (1 << 64)
            digest = hashlib.sha1('%016x:%s:%s:%s' % (timestamp,
                                                      self.command,
                                                      self.path,
                                                      ''.join([ '%02x' 
                                                                % (self._rand.randint(0,0xFF),) 
                                                                for _ in range(40) ]))
                                  ).hexdigest()        
            nonce = "%016x%s" % (timestamp,digest)

            self.__confirmation_nonces.append(nonce)

        return nonce

    def form_authorisation_nonce(self,timeout):
        """This method can be overridden in subclasses to change how the nonce is formed.
        """
        with self.__authorisation_nonces_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__authorisation_nonces 
                       if (now > int(x[:16],16)) ]:
                self.__authorisation_nonces.remove(n)

            timestamp = int((time.time() + timeout)*1000000) % (1 << 64)
            digest = hashlib.sha1('%016x:%s:%s:%s' % (timestamp,
                                                      self.command,
                                                      self.path,
                                                      ''.join([ '%02x' 
                                                                % (self._rand.randint(0,0xFF),) 
                                                                for _ in range(40) ]))
                                  ).hexdigest()        
            nonce = "%016x%s" % (timestamp,digest)

            self.__authorisation_nonces.append(nonce)

        return nonce


    def __validate_confirmation_for_request(self):
        
        if 'X-UCRestriction-Credentials' not in self.headers:
            return None 

        credentials = self.headers['X-UCRestriction-Credentials']

        match = re.search(r'(Confirm|Abort)\s+nonce="([0-9a-fA-F]+)"',credentials)

        if not match:
            return "failed"

        confirmation = (match.group(1) == "Confirm")
        nonce = match.group(2)

        if not self.confirmation_nonce_is_valid(nonce):
            return "failed"

        if confirmation:
            return "confirmed"
        else:
            return "abort"

    def check_confirmation(self, message, timeout=None):
        """This method is called by resource handlers when they wish to check
        the confirmation of the request. If the request is confirmed it returns
        True, if it failed it sends a 402 error and returns "failed", if 
        it was aborted it sends a 410 response and returns "aborted", 
        otherwise it sends a 402 challenge and returns the nonce.

        The timeout parameter is used to set a timeout (in seconds) for how
        long the confirmation window will be open for. If not set the default is
        the value of self.confirmation_timeout (5.0 by default). The nonce will be
        removed from use when the timeout runs down, but no other action will be taken
        code wishing to perform some other action will need to set its own timeout of
        some sort."""

        if timeout is None:
            timeout = self.confirmation_timeout

        retval = self.__validate_confirmation_for_request()
        if retval == "confirmed":
            return True
        elif retval == "failed":
            self.send_response(402,"Restriction Failed")
            self.send_header('Content-Type',self.authentication_challenge_type)
            self.send_header('Content-Length', len(self.authentication_challenge_body))
            self.end_headers()
            self.wfile.write(self.authentication_challenge_body)
            return "failed"
        elif retval == "abort":
            self.send_response(410,"Aborted")
            self.send_header('Content-Type',self.restriction_abort_type)
            self.send_header('Content-Length', len(self.restriction_abort_body))
            self.end_headers()
            self.wfile.write(self.restriction_abort_body)
            return "aborted"
        else:
            nonce = self.form_confirmation_nonce(timeout)

            challenge = """\
Confirm
     nonce="%s",
     message="%s",
""" % (nonce, message)

            self.send_response(402,"Restriction Challenge")
            self.send_header('Content-Type',self.authentication_challenge_type)
            self.send_header('Content-Length', len(self.authentication_challenge_body))
            self.send_header('X-UCRestriction-Challenge',challenge)
            self.end_headers()
            self.wfile.write(self.authentication_challenge_body)

            return nonce

    def __validate_authorisation_for_request(self, message, body, PIN, iteration):
        if 'X-UCRestriction-Credentials' not in self.headers:
            return None 

        credentials = self.headers['X-UCRestriction-Credentials']

        if credentials[:5] == "Abort":
            match = re.search(r'Abort\s+nonce="([0-9a-fA-F]+)"',credentials)

            if not match:
                return "failed"

            nonce = match.group(1)

            if not self.authorisation_nonce_is_valid(nonce):
                return "failed"

            return "abort"
        elif credentials[:9] == "Authorise":
            match = re.search(r'Authorise\s+nonce="([0-9a-fA-F]+)\s*iteration="([0-9a-fA-F]+)",\s*uri="([^"]*)",\s*digest="([0-9a-fA-F]+)"(?:,\s*client-id="([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")?',credentials)

            if not match:
                return "failed"

            nonce = match.group(1)
            citeration=int(match.group(2),16)
            uri=match.group(3)
            digest=match.group(4)
            client_id=match.group(5)

            
            if iteration != citeration:
                return "failed"

            if not self.check_uri(uri):
                return "failed"

            if (client_id is not None):
                with self._credentials_lock:

                    if (client_id not in self._client_credentials):                        
                        return "failed"

                    new_digest = self.digest('%s:%s' % (PIN,self._client_credentials[client_id][0]),
                                             '%s:%s:%s:%s' % (self.command,
                                                              uri,
                                                              nonce,
                                                              body,
                                                              ),
                                             iteration)
                    
            else:
                new_digest = self.digest(PIN,
                                         '%s:%s:%s:%s' % (self.command,
                                                          uri,
                                                          nonce,
                                                          body,
                                                          ),
                                         iteration)

            if new_digest != digest:
                return 'failed'                
            
            return True
        else:
            return "failed"
    
    def check_authorisation(self, message, body, PIN, iteration=None, timeout=None):
        """This method is called by resource handlers when they wish to check
        the authorisation of the request. If the request is authorised it returns
        True, if it failed it sends a 402 error and returns "failed", if it was 
        aborted it sends a 410 response and returns "aborted", otherwise it sends a 402 
        challenge and returns the nonce

        The timeout parameter is used to set a timeout (in seconds) for how
        long the authorisation window will be open for. If not set the default is
        the value of self.confirmation_timeout (5.0 by default). The nonce will be
        removed from use when the timeout runs down, but no other action will be taken
        code wishing to perform some other action will need to set its own timeout of
        some sort.

        The iteration parameter is the number of iterations to be used on the HMAC
        algorithm."""

        if timeout is None:
            timeout = self.confirmation_timeout
        if iteration is None:
            iteration = self.authorisation_iteration

        retval = self.__validate_authorisation_for_request(message,body,PIN,iteration)
        if retval == True:
            return True
        elif retval == "failed":
            self.send_response(402,"Restriction Failed")
            self.send_header('Content-Type',self.authentication_challenge_type)
            self.send_header('Content-Length', len(self.authentication_challenge_body))
            self.end_headers()
            self.wfile.write(self.authentication_challenge_body)
            return "failed"
        elif retval == "abort":
            self.send_response(410,"Aborted")
            self.send_header('Content-Type',self.restriction_abort_type)
            self.send_header('Content-Length', len(self.restriction_abort_body))
            self.end_headers()
            self.wfile.write(self.restriction_abort_body)
            return "aborted"
        else:
            nonce = self.form_authorisation_nonce(timeout)
            
            challenge = """\
Authorise
     nonce="%s",
     message="%s",
     iteration="%08x"
""" % (nonce, message, iteration)

            self.send_response(402,"Restriction Challenge")
            self.send_header('Content-Type',self.authentication_challenge_type)
            self.send_header('Content-Length', len(self.authentication_challenge_body))
            self.send_header('X-UCRestriction-Challenge',challenge)
            self.end_headers()
            self.wfile.write(self.authentication_challenge_body)

            return nonce

    @classmethod
    def cancel_ongoing_restriction_exchange(self,nonce):
        """This method can be called at any time to cancel a restriction exchange in 
        progress."""
        with self.__confirmation_nonces_lock:
            now = int(time.time()*1000000) % (1 << 64)
        
            for n in [ x for x in self.__confirmation_nonces 
                       if (now > int(x[:16],16)) ]:
                self.__confirmation_nonces.remove(n)

            if nonce in self.__confirmation_nonces:
                self.__confirmation_nonces.remove(nonce)

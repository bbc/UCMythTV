# Universal Control Server - exceptions
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
UCServer.Exceptions:

The three exception classes contained in this module
(InvalidSyntax,CannotFind, and ProcessingFailed) can be used to control the
raising of HTTP Errors by the server.  Specifically in any method which is
called by the server in the process of handling a request (including methods
written by an individual server implementor) raising one of these exceptions
will cause the server to abort processing of that request and return the
specified Error-code and message.

In all cases these exceptions can be used in one of two ways:

    raise InvalidSyntax

will trigger a 400 error with a default error message.

    raise InvalidSyntax("Special Error Message")

will trigger a 400 error with the specified error message.



If a developer wishes to define further Exceptions which trigger different
error codes then they can do so by creating classes which inherit from
UCServer.Exceptions.UCException (this class doesn't appear in the standard
pydoc documentation for this module, but the documentation for it can be
accessed directly by giving pydoc the full name of the class as a
parameter).  """

__version__ = "0.6.0"

__all__ = ["InvalidSyntax",
           "CannotFind",
           "ProcessingFailed",
           "NotImplemented"]

class UCException(Exception):
    """This class defines an exception which will cause a specified HTTP error to be returned
    by the UCServer code. 

    To create such an exception create a new class which inherits from this one and redefined
    the class-variables "name" and "code" which contain a string naming the type of error the
    exception represents and an integer containing the HTTP error code.
    """
    name = 'Universal Control Exception'
    code = 500

    def __init__(self,message=''):
        self.message = message
    def __str__(self):
        return '%s: %s' % (self.name, self.message)

class InvalidSyntax(UCException):
    """This exception can be raised to cause the currently processing request to return a 
    400 status.
    """
    name = 'Invalid Syntax'
    code = 400

class CannotFind(UCException):
    """This exception can be raised to cause the currently processing request to return a
    404 status.
    """
    name = 'Not Found'
    code = 404

class ProcessingFailed(UCException):
    """This exception can be raised to cause the currently processing request to return a
    500 status.
    """
    name = 'Failed'
    code = 500

class NotImplemented(UCException):
    """This exception can be raised to cause the currently processing request to return a
    405 status.
    """
    name = 'Not Implemented'
    code = 405
    
    



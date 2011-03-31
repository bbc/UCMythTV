# MythTV Universal Control Server - name and uuid generation
# Copyright (C) 2011 British Broadcasting Corporation
#
# Contributors: See Contributors File
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; You may use verion 2 of the license only.
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
This module provides two functions: name() and uuid(). 

If a file exists called UCServer.name or UCServer.uuid then these functions
will read and return the contents.  If no such file exists then they will
use the default name ("Example STB") and generate a new UUID and then write
the results to such a file.

This module can also be invoked directly with either the "-n" or "-u"
command-line parameter to simply print the results of said functions.
"""

from uuid import uuid1
from uuid import UUID
import os.path

def uuid(filename="UCServer.uuid",id=None):
    """Load a uuid from a file, or generate a new one and write it to the file if no such files exists.

 To override the default choice of uuid use the n parameter. To overrid the filename use the filename parameter."""
    if (id is None) and (os.path.exists(filename)):
        try:
            FILE = open(filename,"r")
            s = FILE.readline()
            id = UUID(s.strip())
        except:
            pass
        else:
            return id
        
    FILE = open(filename,"w")
    if id is None:
        id = uuid1()
    else:
        id = UUID(id)
    FILE.write(str(id) + "\n")
    FILE.close()

    return id

def name(filename="UCServer.name",n=None):
    """Load a name from a file, or use the name "Example STB" and write it to the file if no such files exists.

 To override the default choice of name use the n parameter. To overrid the filename use the filename parameter."""
    if (n is None) and (os.path.exists(filename)):
        try:
            FILE = open(filename,"r")
            n = FILE.readline()
            n = n.strip()
        except:
            pass
        else:
            return n

    FILE = open(filename,"w")
    if n is None:
        n = "Example MythTV Box"
    FILE.write(str(n) + "\n")
    FILE.close()

    return n


if __name__ == '__main__':
    from optparse import OptionParser    

    op = OptionParser()
    op.add_option("-n","--name", dest="name", action="store_true", default=False)
    op.add_option("-u","--uuid", dest="uuid", action="store_true", default=False)

    (options,args) = op.parse_args()

    if options.name:
        print name()
    if options.uuid:
        print uuid()
        
    if (not options.name) and (not options.uuid):
        print "Too Few Arguments"

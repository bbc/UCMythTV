# current ip address detection
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
A support function that attempts to deduce the IP address of the network
interface that is being used for general network/internet connectivity.

Achieves this by looking up the ip address of the gateway for the default
route (obtained by running 'netstat') and then using 'ifconfig' to enumerate
all interfaces and seeing which, when masked, matches the gateway (ie.  is
on the same subnet as it)

"""

import re
import subprocess

def _command(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    (output,err) = p.communicate()
    return output
    
_ip_re = '(\d+)\.(\d+)\.(\d+)\.(\d+)'
    
def _findThreeIpAddressesSpaceSeparated(data):
    """For parsing netstat output"""
    return re.findall(_ip_re+'\s+'+_ip_re+'\s+'+_ip_re, data)

def _findAddrAndMask(data):
    """For parsing ifconfig output"""
    return re.findall('inet addr:'+_ip_re+'.+?Mask:'+_ip_re, data)
    
def _parseIpAddr(x, n):
    """\
    Parses ip address, provided as 4 strings in a list/tuple into tuple of for
    integers. Use 'n' to specify which group.
    """
    return (int(x[4*n]), int(x[4*n+1]), int(x[4*n+2]), int(x[4*n+3]))


def currentipaddress():
    # run netstat and pick find gateway for default route (to '0.0.0.0')

    netstat_output = _command(['netstat','-nr'])
    destGatewayMasks = _findThreeIpAddressesSpaceSeparated(netstat_output)
    destGatewayMasks = [(_parseIpAddr(x,0),_parseIpAddr(x,1),_parseIpAddr(x,2)) for x in destGatewayMasks]
    defaultRoutes = [x for x in destGatewayMasks if x[0] == (0,0,0,0)]

    if not defaultRoutes:
        return '127.0.0.1'

    firstRoute = defaultRoutes[0]
    firstRouteGateway = firstRoute[1]
    
    # run ifconfig and pick up all ip address and mask pairs
    
    ifconfig_output = _command(['/sbin/ifconfig',])
    addrAndMasks = _findAddrAndMask(ifconfig_output)
    addrAndMasks = [(_parseIpAddr(x,0),_parseIpAddr(x,1)) for x in addrAndMasks]
    
    # see which ip address, when masked, matches the default route gateway (when also masked)
    # implying this must be the ip address for the interface for the default route
    
    for addr,mask in addrAndMasks:
        maskedGateway = [(x & y) for (x,y) in zip(firstRouteGateway,mask)]
        maskedAddr = [(x & y) for (x,y) in zip(addr,mask)]
        if maskedGateway == maskedAddr:
            return '%d.%d.%d.%d' % addr
    return ''


if __name__ == "__main__":
    print currentipaddress()

#!/usr/bin/env python

# --------------------------------------------------------------------------
# Copyright 2011 British Broadcasting Corporation
# 
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
# 
#        http://www.apache.org/licenses/LICENSE-2.0
# 
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
# --------------------------------------------------------------------------

"""\
PairingCode handling class.  This class is used to encapsulate the concept
of a Pairing Code as defined in the Universal Control specification.  This
code is a way of encoding an IP-address, port-number, and optional
authentication details for a Universal Control server into a relatively
short sequence of characters making use only of the digits 0-9 and the
capital letters.

Contents:

- UCPairingCode : A class encapsulating a pairing code.
"""

__version__ = "0.3"

__all__ = ["UCPairingCode"]


def __intfrombase32(data):
    l = len(data)
    return reduce(lambda x, y : x+y, 
                  [ (__chars.index(data[n]) << (l-1-n)*5) for n in range(l) ])
    
def __base32(data):
    if data == 0:
        return '0'
    out = []
    while data > 0:
        out.append(__chars[data%32])
        data = data//32
    out.reverse()
    return ''.join(out)

class UCPairingCode:
    """This class represents a Pairing Code, it can be initialised either with a Pairing Code or with the data for making a Pairing code, either way one can get the code and the data out of it."""

    __chars = [ x for x in '0123456789ABCDEFGHJKMNPQRSTVWXYZ' ]

    def __intfrombase32(self,data):
        l = len(data)
        data = data.upper()
        return reduce(lambda x, y : x+y, 
                      [ (self.__chars.index(data[n]) << (l-1-n)*5) for n in range(l) ])
    
    def __base32(self,data):
        if data == 0:
            return '0'
        out = []
        while data > 0:
            out.append(self.__chars[data%32])
            data = data//32
        out.reverse()
        return ''.join(out)

    def __init__(self,data,
                 port=48875,SSS=None,
                 shortcuts=True):
        """The required parameter data may be of several forms:
        
        UCPairingCode("192.168.0.2")
        UCPairingCode("192.168.0.2:48875")
        UCPairingCode("192.168.0.2", port=48875)
        and
        UCPairingCode("*8")
        
        are all valid, and all produce the same result.

        Note that a port number given as part of the IP adress WILL override one given as a separate parameter.

        The shortcuts parameter may be set to False when creating a pairing code from an IP Address. The resulting code will be valid in that it is decodable using the algorithm specified in the Universal Control specification, but is non-standard in that it does not make use of the recommended algorithm for generating such a code. It will never be shorter and will often be longer than the normal code for the same data."""

        if not isinstance(data,basestring):
            raise ValueError

        self.shortcuts = shortcuts
        self.__data = 0
        self.__pos  = 0

        if data.count('.') != 0:
            #If the given data is an IP address
            #Simply store the given data
            if data.count(':') != 0:
                (data,port) = data.split(':',1)
                port = int(port)
            self.__IP = map(int,data.split('.'))
            self.port = port
            self.SSS = SSS
        else:
            #If the given data is a pairing code, then decode it as specified in the specification
            
            #Start by translating the string into an integer
            try:
                self.__data = self.__intfrombase32(data)
            except:
                raise Exception, "Code contains invalid characters"
            self.__pos  = 0
            
            
            #The code below is simply an implementation of the algorithm specified in teh specification
            signal = self.__input(1)
            if signal == 1:
                print "Error: pairing code is in unknown format"
                exit(0)
            signal = self.__input(1)
            if signal == 1:
                SSS = self.__input(8)

            signal = self.__input(2)
            if signal == 0:
                A = 192
                B = 168

                signal = self.__input(2)
                if signal == 0:
                    C = 0
                elif signal == 1:
                    C = 1
                elif signal == 2:
                    C = 2
                else:
                    C = self.__input(8)

                D = self.__input(8)
    
            elif signal == 1:
                D = int(self.__input(8))
                C = int(self.__input(8))
                B = int(self.__input(4) + 16)
                A = 172
            elif signal == 2:
                D = int(self.__input(8))
                C = int(self.__input(8))
                B = int(self.__input(8))
                A = 10
            else:
                D = int(self.__input(8))
                C = int(self.__input(8))
                B = int(self.__input(8))
                A = int(self.__input(8))

            signal = self.__input(1)
            if signal == 1:
                P = self.__input(16)
            else:
                P = 48875

            self.__end()

            self.__IP = (A,B,C,D)
            self.port = P
            self.SSS = SSS

            self.__pos = None
            self.__data = None            

    def __output(self,data,bits=1):
        """This private function simply mimics the "output" command in the pseudocode in the specification."""
        mask = (1 << bits) - 1
        self.__data += (data&mask) << self.__pos
        self.__pos += bits
        
    def __input(self,bits=1):
        """This private function simply mimics the "input" command in the pseudocode in the specification."""
        out = (self.__data & (((1 << bits) - 1) << self.__pos)) >> self.__pos
        self.__pos += bits
        return out

    def __end(self):
        """This private function checks that at the end of processing the code there is no data left over."""
        if (self.__data >> self.__pos) != 0:
            raise ValueError

    def __str__(self):
        """This string representation of the code object is easily human readable."""
        if (self.SSS == None):
            SSSString = "None"
        else:
            SSSString = '"%02x"' % self.SSS
            
        return '%s  ===  %d.%d.%d.%d:%d SSS=%s' % (self.pairingCode(), 
                                                   self.__IP[0], 
                                                   self.__IP[1], 
                                                   self.__IP[2], 
                                                   self.__IP[3], 
                                                   self.port, 
                                                   SSSString)
    
    def getIP(self):
        """Returns the IP address and port number in a string"""
        return '.'.join(map(str,self.__IP)) + ':' + str(self.port)

    def IP(self,IP):
        """Set the IP address of the code."""
        if IP.count(':') != 0:
            (IP,port) = IP.split(':',1)
            self.port = int(port)

        self.__IP = map(int,IP.split('.'))

    def pairingCode(self):
        """Used to retrieve the actual pairing code"""
        (A,B,C,D) = self.__IP
        SSS = self.SSS
                    
        self.__data = 0
        self.__pos  = 0

        #The below is simply and implementation of the algorithm recommended in the specification except that at some 
        #points if the member self.shortcuts is False then the algorithm will ignore some of the mechanisms used in
        #the algorithm to assign shorter codes to common IP addresses. Either way the code produced is uniquely 
        #decodable using the decode algorithm specified by the specification.

        self.__output(0,1)
        if not(SSS is None):
            self.__output(1,1)
            self.__output(SSS,8)
        else:
            self.__output(0,1)

        if self.shortcuts and (A,B) == (192,168):
            self.__output(0,2)
            if C == 0:
                self.__output(0,2)
            elif C == 1:
                self.__output(1,2)
            elif C == 2:
                self.__output(2,2)
            else:
                self.__output(3,2)
                self.__output(C,8)
                
            self.__output(D, 8)

        elif self.shortcuts and A == 172 and 16 <= B <= 31:
            self.__output(1,2)
            self.__output(D,8)
            self.__output(C,8)
            self.__output(B-16,4)

        elif self.shortcuts and A == 10:
            self.__output(2,2)
            self.__output(D,8)
            self.__output(C,8)
            self.__output(B,8)
            
        else:
            self.__output(3,2)
            self.__output(D,8)
            self.__output(C,8)
            self.__output(B,8)
            self.__output(A,8)
            
        if self.port != 48875:
            self.__output(1,1)
            self.__output(self.port,16)

        self.__pos = None
        pc = self.__base32(self.__data)
        self.__data = None

        return pc
        

#A simple main routine which takes an ip-address or code on the commandline
#and prints the code and ip-address/port-number/CP combination it corresponds to
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-c", dest="code")
    parser.add_option("-i", dest="ipandport")
    parser.add_option("-p", dest="sss")
    (options,args) = parser.parse_args()
    
    if options.code != None:
        print UCPairingCode(options.code)
    elif options.ipandport != None:
        address = options.ipandport
        port = 48875
        SSS = None
        if address.count(':') == 1:
            (address,port) = address.split(':',1)
            port = int(port)
        if options.sss != None:
            SSS = int(options.sss,16)
        print UCPairingCode("%s:%s" % (address,port), SSS=SSS)
    else:
            print """Usage:
PairingCode -i <ip-address>[:<port>] [-p SSS]
PairingCode -c pairing_code
"""

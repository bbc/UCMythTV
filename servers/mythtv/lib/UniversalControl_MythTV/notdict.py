# MythTV Universal Control Server - Notifiable Dictionary
# Copyright (C) 2011 British Broadcasting Corporation
#
# Contributors: See Contributors File
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; you may use version 2 of the licsense only
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
Notifiable Dictionary
This module contains a single class, notdict.
"""

class notdict (dict):
    """A special kind of dictionary which can take individual setter and getter methods for keys, and provides 
    direct data access via another mechanism.

    Initialised via notdict(data=None,notify=None,setters=None,getters=None,delers=None,deler=None)

    The parameters are as follows:
    -- data    : a dictionary containing the data which will be stored in the class
    -- notify  : a callable taking a single parameter. If provided this method will be called 
                 when the data in the dictionary is changed using some of the provided methods.
    -- setters : a dictionary of callables taking two parameters. If a key is present in this
                 dictionary then any asignment of the form notdictinstance[key] = data will call
                 the callable setters[key] with the parameters (key,data). If setters[key] is None
                 then no call will be made (and no exception thrown). If key not in setters then 
                 the notdict instance will simply assign the value as if it were a normal dictionary
    -- getters : a dictionary of callables taking one parameter. If a key is present in this dictionary
                 then a request of the form notdictinstance[key] will return the return value of a call
                 to getters[key](key). Otherwise the normal dictionary data return mechanism will
                 be used.
    -- delers  : much the same as getters and setters this is a dictionary of callables which take one
                 parameter and are called when requests of the form del notdictinstance[key] are made.
    -- deler   : This takes a callable which takes one parameter. If not None this callable will be used
                 in all cases instead of the callables in delers.

    It is important that the dictionary WILL NOT assign, return, or delete data from itself if there is a 
    callabale to call instead, as such the callables should perform these operations themselves as needed.


    The notdict instance has a single instance variable self.data which is a dictionary containing the
    current data stored in the notdict. Ordinary calls such as notdictinstance.data[key] = stuff and
    del notdictinstance[key] etc ... WILL NOT call the setters, getters, delers, or notify callables.

    Similarly the notify callables are not called when the notdict itself is modified using normal dictionary
    access notation.
    """
    
    def __init__(self,data=None,notify=None,setters=None,getters=None,delers=None, deler=None):
        self.data    = dict()
        self.setters = dict()
        self.getters = dict()
        self.delers  = dict()
        self.deler   = deler

        if data is not None:
            self.data = dict(data)
        if setters is not None:
            self.setters = dict(setters)
        if getters is not None:
            self.getters = dict(getters)
        if delers is not None:
            self.delers = dict(delers)

        self.notify  = notify

    def __setitem__(self,key,item):
        if key in self.setters:
            if self.setters[key] is not None:
                try:
                    self.setters[key](key,item)
                except:
                    raise
            return

        self.set(key,item)

    def set(self,key,item):
        """This method can be used to set the value of an item in the dictionary. 
        It WILL NOT call the setters callables, but WILL call the notify ones."""
        if key not in self.data or self.data[key] != item:
            self.data[key] = item

            if self.notify is not None:
                try:
                    self.notify(key)
                except:
                    pass

    def remove(self,key):
        """This method can be used to remove an item from the dictionary. 
        It WILL NOT call the delers or deler callables, but WILL call the 
        notify ones."""
        if key not in self.data:
            raise KeyError
        
        if key in self.getters:
            del self.getters[key]
        if key in self.setters:
            del self.setters[key]
        if key in self.delers:
            del self.delers[key]
        del self.data[key]

        if self.notify is not None:
            try:
                self.notify(key)
            except:
                pass
        

    def __getitem__(self,key):
        if key in self.getters:
            if self.getters[key] is not None:
                try:
                    return self.getters[key](key)
                except:
                    raise
            return None
        
        return self.data[key]

    def __len__(self):
        return len(self.data)

    def __delitem__(self,key):
        if self.deler is not None:
            try:
                return self.deler(key)
            except:
                raise

        if key in self.delers:
            if self.delers[key] is not None:
                try:
                    return self.delers[key](key)
                except:
                    raise
            return

        self.remove(key)

    def __iter__(self):
        return self.data.__iter__()

    def iterkeys(self):
        return self.data.iterkeys()

    def __contains__(self,key):
        return (key in self.data)

    def __repr__(self):
        return 'notdict(data=%r,setters=%r,getters=%r,notify=%r)' % (self.data,
                                                                     self.setters,
                                                                     self.getters,
                                                                     self.notify)

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()

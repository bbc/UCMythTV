# MythTV Universal Control Server - MythTV interfaces
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

from MythTV import MythDB, Frontend, MythBE, Record, MythXML, Recorded, MythLog
import MythTV
import threading
import re
import math
import datetime
import time
import traceback
import os

from UCServer.Exceptions import CannotFind, InvalidSyntax, ProcessingFailed
from ManualVideoMetadata import ManualVideoMetadata

from notdict import notdict
from xtest import XTest

MythLog._setlevel('none')

# This offset exists to get around a mysterious bug whereby 
# the position within a video reported by MythTV seems to be
# out by a static number of seconds. Oddly this used to be
# 0.625s but has recently become 5.625s -- and I can't work
# out why!

FIXED_POSITION_OFFSET = 5.625

# These three classes exist to provide access to database
# tables in the MythTV database which are not accessible 
# through the python bindings by default.
#
# That making them was so easy is a tribute to how well 
# written the python bindings for MythTV are.

class ChannelScan (MythTV.DBData):
    _where='scanid=%s'
    _setwheredat='self.scanid,'

class ChannelScan_Channel (MythTV.DBData):
    _where='scanid=%s AND service_id=%s'
    _setwheredat='self.scanid,self.service_id'

class GameMetadata (MythTV.DBData):
    _where='romname=%s'
    _setwheredat='self.romname,'

class InternetContent (MythTV.DBData):
    _where='name=%s AND search=%d AND tree=%d'
    _setwheredat='self.name,self.search,self.tree'

class InternetContentArticles (MythTV.DBData):
    _where='url=%s'
    _setwheredat='self.url,'

uc_server = None

mythtv_sources = None
extra_sources = {}
mythtv_source_lists = None
mythtv_outputs = None
mythtv_button_handler = None
mythtv_acquisitions = None
mythtv_acquirer = None
mythtv_programmes = None
mythtv_menu_programmes = None
mythtv_storage = None
mythtv_power = None
mythtv_logo = None
mythtv_game_programmes = None

mythtv_images = None

update_thread = None

#This is set to a callable if something needs to be called before
#the output can be changed.
prekill_outputs = None

def sendQuery(query):
    global uc_server
    try:
        fe = MythTV.MythDB().getFrontends().next()
    except:
        uc_server.set_standby(True)
        return None
    else:
        uc_server.set_standby(False)
        try:
            return fe.sendQuery(query)
        except Exception as inst:
            uc_server.log_message(traceback.format_exc())
            return None

def sendPlay(play):
    global uc_server
    try:
        fe = MythTV.MythDB().getFrontends().next()
    except:
        uc_server.set_standby(True)
        return False
    else:
        uc_server.set_standby(False)
        try:
            fe.sendPlay(play)
            return True
        except Exception as inst:
            uc_server.log_message(traceback.format_exc())
            return False

def mythtv_power_notify(key):
    global uc_server

    uc_server.notify_change('uc/power')

def mythtv_standby_callback(standby):
    global uc_server

    if standby:
        uc_server.log_message("Killing all mythtv frontends")
        os.system('pkill mythfrontend')
        return True
    else:
        uc_server.log_message("Starting mythtv frontend")
        os.system('if [ -z `pgrep mythfrontend` ]; then mythfrontend; fi &')
        for i in range(30):
            
            lock = threading.Condition()
            with lock:
                lock.wait(1)

            try:
                MythTV.MythDB().getFrontends().next()
            except:
                continue
            else:
                return True
    return False

def mythtv_source_notify(key):
    def mythtv_source_notify_actual(subkey):
        mythtv_sources_notify(key)
    return mythtv_source_notify_actual

def mythtv_sources_notify(key):
    pass

def mythtv_output_notify(key):
    global uc_server

    if key == 'playhead':
        return

    if key == 'playback':
        uc_server.notify_change('uc/outputs/0/playhead')

    uc_server.notify_change('uc/outputs/0')

def mythtv_acquisitions_notify(key):
    global uc_server

    uc_server.notify_change('uc/acquisitions')

def mythtv_acquisition_notify(key):
    global uc_server

    uc_server.notify_change('uc/acquisitions')

def mythtv_appslist_notify(key):
    global uc_server
    uc_server.notify_change('uc/source-lists/apps')

def mythtv_netvisionlist_notify(key):
    global uc_server
    uc_server.notify_change('uc/source-lists/mythnetvision')

def mythtv_storage_notify(key):
    global uc_server
    uc_server.notify_change('uc/storage')

def mythtv_storagelist_notify(key):
    global uc_server
    uc_server.notify_change('uc/source-lists/storage')

def mythtv_storage_delete(key):
    global mythtv_storage

    try:
        retval = Recorded((mythtv_storage['items'].data[key]['MYTHTV:chanid'],mythtv_storage['items'].data[key]['MYTHTV:recstartts'])).delete()
    except:
        raise

    lock = threading.Condition()

    lock.acquire()
    lock.wait(3)
    lock.release()

    update_storage()
    

def mythtv_output_setter(key,item):
    global mythtv_outputs
    global mythtv_sources
    global mythtv_storage

    if key == 'playback':
        if not isinstance(item,float):
            raise ProcessingFailed

        speed = 'normal'
        if item < 0.0:
            speed = '%dx' % int(item)
        elif item == 0.0:
            speed = 'pause'
        else:
            sign = '' if item > 0 else '-'
            absit = abs(item)
            if 0.0 < absit <= 2.0:
                speed = '%s%1.3fx' % (sign,float(item))
            elif 2.0 < absit <= 4.0:
                speed = '%s3x' % sign
            elif 4.0 < absit <= 7.5:
                speed = '%s5x' % sign
            elif 7.5 < absit <= 15.0:
                speed = '%s10x' % sign
            else:
                speed = '%s30x' % sign

        if not sendPlay('speed %s' % speed):
            raise ProcessingFailed
        return
    elif key == 'playhead':
        if mythtv_outputs['0']['playhead'] is None:
            raise CannotFind
        
        if 'aposition' in item:
            timestamp = datetime.datetime.utcnow()
            diff = timestamp - item['aposition']['position_timestamp']

            print "REQ: %r\nSRV: %r\nDIF: %r" % (item['aposition']['position_timestamp'], timestamp, diff)

            try:
                speed = float(mythtv_outputs['0']['playhead']['playback'])
            except:
                speed = 1.0

            pos = int(item['aposition']['position'] + speed*(float(86400*diff.days) + float(diff.seconds) + float(diff.microseconds)/1000000.0)) - FIXED_POSITION_OFFSET

            print "POS: %r" % (pos,)

            if not sendPlay('seek %02d:%02d:%02d' % (pos//3600,(pos//60)%60,pos%60)):
                raise ProcessingFailed
        elif 'rposition' in item:
            query = sendQuery('location')

            m = re.search('(\d+):(\d+) of (\d+):(\d+)', query)
            if not m:
                raise ProcessingFailed
            
            length = int(m.group(3))*60 + int(m.group(4))
            
            pos = item['rposition']['position'] + length

            if not sendPlay('seek %02d:%02d:%02d' % (int(pos/3600),int(pos/60)%60,pos%60)):
                raise ProcessingFailed
        else:
            raise ProcessingFailed

    elif key == 'volume':
        volume = int((item + 5)/100)
        if volume < 0:
            volume = 0
        elif volume > 100:
            volume = 100

        if not sendPlay('volume %d%%' % volume):
            raise ProcessingFailed

    else:
        raise KeyError


def initialise(server,logo=None):
    global uc_server
    global mythtv_sources
    global mythtv_source_lists
    global mythtv_outputs
    global mythtv_button_handler
    global mythtv_acquisitions
    global mythtv_acquirer
    global mythtv_programmes
    global mythtv_menu_programmes
    global mythtv_storage
    global mythtv_images
    global mythtv_power
    global mythtv_logo
    global mythtv_game_programmes

    global update_thread
    
    uc_server = server

    mythtv_power = notdict({ 'resource' : 'uc/power',
                             'state'    : 'on' },
                           notify=mythtv_power_notify,
                           setters = { 'resource' : None,
                                       'state'    : None,
                                       },
                           )                           

    mythtv_sources = notdict(dict([ ('%04d' % channel.chanid, notdict({ 'id'   : '%04d' % channel.chanid,
                                                                        'name' : str(channel.name),
                                                                        'rref' : 'uc/sources/%04d' % channel.chanid,
                                                                        'live' : True,
                                                                        'linear' : True,
                                                                        'follow-on' : True,
                                                                        'lcn' : int(channel.channum),
                                                                        'MYTHTV:type' : 'tv',
                                                                        'MYTHTV:icon' : str(channel.icon) if channel.icon != '' else None,
                                                                        'MYTHTV:serviceid' : channel.serviceid,
                                                                        },
                                                                      notify=mythtv_source_notify('%04d' % channel.chanid))) for channel in MythTV.Channel.getAllEntries() if re.match('^\d+$',channel.channum) ]
                                  ),
                             notify=mythtv_sources_notify)

    scans = sorted([ scan for scan in ChannelScan.getAllEntries() ],key=lambda x : x.scanid)
    if len(scans) > 0:
        scan = scans[-1].scanid

        scan_channels = dict([ (chan.service_id,chan) for chan in ChannelScan_Channel.getAllEntries() if chan.scanid==scan ])
        
        for sid in mythtv_sources.data:
            if mythtv_sources.data[sid]['MYTHTV:serviceid'] in scan_channels:
                chan = scan_channels[mythtv_sources.data[sid]['MYTHTV:serviceid']]
                mythtv_sources.data[sid]['MYTHTV:type'] = ('radio' if chan.is_audio_service == 1 else 'tv')
                mythtv_sources.data[sid]['sref'] = 'dvb://%04x..%04x' % (chan.orig_netid,
                                                                     chan.service_id)

    mythtv_images = { 'resource' : 'images',
                      'files' : dict(),
                      }

    if logo is not None:
        mythtv_logo = 'http://%s:%s/images/mythtv_logo.png' % (server.ip_address(),server.port)
        mythtv_images['files'] = {('images','mythtv_logo.png') : (logo,'image/png')}
    else:
        mythtv_logo = None

    image_types  = { 'jpg'   : ('jpg','image/jpeg'),
                     'jpeg'  : ('jpg','image/jpeg'),
                     'gif'   : ('gif','image/gif'),
                     'png'   : ('png','image/png'),
                     'tiff'  : ('tiff','image/tiff'),
                     }

    for id in mythtv_sources:
        if 'MYTHTV:icon' in mythtv_sources[id] and mythtv_sources[id]['MYTHTV:icon'] is not None:
            icon = mythtv_sources[id]['MYTHTV:icon']        
            match = re.match('.+\.([^\.]+)$',icon)
            if match:
                ext = match.group(1)

                if ext in image_types:                    
                    mythtv_sources[id]['logo-href'] = 'http://%s:%d/images/sources/%s.%s' % (server.ip_address(),
                                                                                             server.port,
                                                                                             id,
                                                                                             image_types[ext][0])
                    mythtv_images['files'][('images','sources','%s.%s' % (id,image_types[ext][0]))] = (mythtv_sources[id]['MYTHTV:icon'],image_types[ext][1])

    mythtv_sources['mythtv'] = notdict({ 'id'          : 'mythtv',
                                         'name'        : 'The MythTV Menus',
                                         'live'        : False,
                                         'linear'      : False,
                                         'follow-on'   : False,
                                         'rref'        : 'uc/sources/mythtv',
                                         'default-content-id' : 'mainmenu',
                                         'MYTHTV:type' : 'menu',                                         
                                         },
                                       notify=mythtv_source_notify('mythtv'))

    mythtv_sources['mythgame'] = notdict({ 'id'          : 'mythgame',
                                           'name'        : 'Games Supported by MythGame',
                                           'live'        : False,
                                           'linear'      : False,
                                           'follow-on'   : False,
                                           'rref'        : 'uc/sources/mythgame',
                                           'MYTHTV:type' : 'MythGame'},
                                         notify=mythtv_source_notify('mythgame'))
    
    mythtv_source_lists = { 'uc_default' : { 'list-id' : 'uc_default',
                                             'name' : 'Default',
                                             'description' : "The default list of sources",
                                             'sources' : filter(lambda x : True,
                                                             mythtv_sources.keys()),
                                          },
                            'mythtv_tv'  : { 'list-id' : 'mythtv_tv',
                                             'name' : "TV",
                                             'description' : "All TV channels",
                                             'sources' : tuple(filter(lambda x : (mythtv_sources.data[x].data['MYTHTV:type'] == 'tv'),
                                                                      mythtv_sources.keys())),
                                          },
                            'mythtv_radio' : { 'list-id' : 'mythtv_radio',
                                               'name' : "Radio",
                                               'description' : "All Radio Stations",
                                               'sources' : tuple(filter(lambda x : (mythtv_sources.data[x].data['MYTHTV:type'] == 'radio'),
                                                                        mythtv_sources.keys())),
                                          },
                            'uc_storage' : notdict({ 'list-id' : 'uc_storage',
                                                     'name' : "Recordings and Videos",
                                                     'description' : "The recordings and videos on the MythTV box",
                                                     'sources' : [],
                                                     },
                                                   notify=mythtv_storagelist_notify),
                            'mythtv_apps'    : notdict({ 'list-id' : 'mythtv_apps',
                                                         'name' : "Applications",
                                                         'description' : "Interactive Applications",
                                                         'sources' : ['mythtv','mythgame'],
                                                         },
                                                       notify=mythtv_appslist_notify),
                            'mythtv_mythnetvision' : notdict({ 'list-id' : 'mythtv_mythnetvision',
                                                               'name' : 'MythNetVision',
                                                               'description' : "MythNetVision on-demand services",
                                                               'sources' : [],
                                                               },
                                                             notify=mythtv_netvisionlist_notify),
                            }

    mythtv_menu_programmes = []

    mythtv_outputs = dict([ ('0', notdict({ 'id' : '0',
                                            'tags' : ['main',],
                                            'name' : "Main Screen",
                                            'programme' : None,
                                            'app' : None,
                                            'component_overrides' : [],
                                            'playback' : None,
                                            'settings' : notdict({ 'volume' : None,
                                                                   },
                                                                 setters={ 'volume' : mythtv_output_setter,
                                                                           },
                                                                 notify=mythtv_output_notify
                                                                 ),
                                            'playhead' : None,
                                            'selector' : MythTVOutputSelector('0'),
                                            },
                                          setters={ 'programme' : mythtv_output_setter,
                                                    'app'       : mythtv_output_setter,
                                                    'playback'  : mythtv_output_setter,
                                                    'playhead'  : mythtv_output_setter,
                                                    },
                                          notify=mythtv_output_notify
                                          )), 
                            ]
                          )

    mythtv_button_handler = ButtonHandler()

    mythtv_acquisitions = { 'resource' : 'uc/acquisitions',
                            'content-acquisitions' : notdict(dict(),
                                                             notify=mythtv_acquisitions_notify),
                            'series-acquisitions'  : notdict(dict(),
                                                             notify=mythtv_acquisitions_notify),
                            }

    mythtv_storage = { 'resource' : 'uc/storage',
                       'items' : notdict(dict(),
                                         notify=mythtv_storage_notify,
                                         deler=mythtv_storage_delete),
                       }

    mythtv_game_programmes = dict()
                                         

    mythtv_acquirer = Acquirer()

    mythtv_programmes = Programmes()

    xml = MythXML()

    update_thread = UpdateThread()
    update_thread.start()


class UpdateThread (threading.Thread):

    daemon = True

    lock = threading.Condition()
    
    def run(self):
        global mythtv_outputs
        global mythtv_sources
        global mythtv_acquisitions
        global mythtv_menu_programmes

        myth_menu_locations = None

        while(True):
            self.lock.acquire()
            self.lock.wait(1)
            self.lock.release()
            
            if myth_menu_locations is None:
                try:
                    fe = MythDB().getFrontends().next()
                except:
                    uc_server.set_standby(True)
                    continue
                else:
                    uc_server.set_standby(False)
                    try:
                        myth_menu_locations = fe.getJump()
                    except:                    
                        continue

                #Manually add GameUI location
                myth_menu_locations.append(('GameUI','MythGame Game Selection UI'))
                myth_menu_locations.append(('mythbrowser','MythTV web browser'))

                mythtv_menu_programmes = [ { 'sid' : 'mythtv',
                                             'cid' : id_component(location[0]),
                                             'synopsis' : 'MythTV UI, Jump point: %s' % repr(str(location[1])),
                                             'title' : str(location[1]),
                                             'interactive' : True
                                             }
                                           for location in myth_menu_locations ]

                mythtv_menu_programmes = ([ prog for prog in mythtv_menu_programmes if prog['cid'] == 'mainmenu' ] + 
                                          [ prog for prog in mythtv_menu_programmes if prog['cid'] == 'livetv' ] + 
                                          [ prog for prog in mythtv_menu_programmes if prog['cid'] not in ('mainmenu','livetv') ])

            else:
                try:
                    fe = MythDB().getFrontends().next()
                except:
                    uc_server.set_standby(True)
                    continue
                else:
                    uc_server.set_standby(False)


            try:
                update_output(myth_menu_locations)
            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                continue

            if 'programme' not in mythtv_outputs['0'] or mythtv_outputs['0']['programme'] is None:
                mythtv_outputs['0'].data['settings'].set('volume',None)
            else:
                query = sendQuery('volume')
                if query is None:
                    mythtv_outputs['0'].data['settings'].set('volume',None)
                    continue

                match = re.match('(\d{1,3})%',query)
                if match:
                    try:
                        volume = int(match.group(1))*100
                    except:
                        mythtv_outputs['0'].data['settings'].set('volume',None)
                    else:
                        mythtv_outputs['0'].data['settings'].set('volume',volume)
                else:
                    pass

            query =  sendQuery('livetv')
            if query is None:
                continue

            lines = query.splitlines()

            for line in lines:
                match = re.match('\s*([0-9]+) ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}) ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}) (.+)',
                                 line)
                if match:
                    try:
                        sid = '%04d' % int(match.group(1))
                    except:
                        pass
                    else:
                        pid = id_component('%sZ' % match.group(2))
                        if sid in mythtv_sources:
                            if 'default-content-id' not in mythtv_sources[sid] or mythtv_sources.data[sid].data['default-content-id'] != pid:
                                mythtv_sources.data[sid].set('default-content-id',pid)

            try: 
                update_acquisitions()
            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                continue

            try:
                update_storage()
            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                continue

            try:
                update_mythnetvision()
            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                continue

def update_mythnetvision():
    global mythtv_sources
    global mythtv_source_lists

    netvisionsources = [ (id_component(data.name), notdict({ 'id'        : id_component(data.name),
                                                             'name'      : data.name,
                                                             'live'      : False,
                                                             'linear'    : False,
                                                             'follow-on' : False,
                                                             'rref'      : 'uc/sources/' + id_component(data.name),
                                                             'MYTHTV:type' : 'mythnetvision',
                                                             })) for data in InternetContent.getAllEntries() if data.tree ]
    for (sid,source) in netvisionsources:
        mythtv_sources[sid] = source

    netvisionsources = [ sid for (sid,source) in netvisionsources ]

    to_delete = [ sid for sid in mythtv_sources if mythtv_sources[sid]['MYTHTV:type'] == 'mythnetvision' and sid not in netvisionsources ]

    for sid in to_delete:
        del mythtv_sources[sid]
        mythtv_source_lists['mythtv_mythnetvision']['sources'].remove(sid)

    for sid in netvisionsources:
        if sid not in mythtv_source_lists['mythtv_mythnetvision']['sources']:
            mythtv_source_lists['mythtv_mythnetvision']['sources'].append(sid)


def update_output(myth_menu_locations):
    global mythtv_outputs
    global mythtv_storage
    global uc_server

    now = datetime.datetime.utcnow()
    query = sendQuery('location')
    if query is None:
        uc_server.set_standby(True)
        return
                
    # Format is:
    #    Playback LiveTV 6:57 of 7:03 1x 5168 2010-09-03T11:00:00 10429 /var/lib/mythtv/livetv/5168_20100903110000.mpg 25 (15:31:54.109Z) Subtitles: *0:[None]* 1:[Subtitle 1: English]
    #    Playback Video 0:03 1x myth://Videos@127.0.0.1:6543/20080531_180000_bbcone_doctor_who.ts 94 25 (15:31:54.109Z) Subtitles: *0:[None]*

    old_playhead = None
    if 'playhead' in mythtv_outputs['0'].data:
        old_playhead = mythtv_outputs['0'].data['playhead']

    if re.match('Playback ', query):
        if re.match('LiveTV ', query[9:]) or re.match('Recorded ', query[9:]) or re.match('Video ', query[9:]):

            if query[9:15] != 'Video ':
                match = re.search('(\d+):(\d+) of (\d+):(\d+) (-{,1}[0-9]+\.[0-9]+x|-{,1}[0-9]x|-{,1}[0-9]+/[0-9]+x|pause) ([0-9]+) ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}) (\d+) (\S+) (\d+) \(@(\d\d):(\d\d):(\d\d)(\.(\d+))?Z\) Subtitles: (.+)',
                                  query)
            else:
                match = re.search('(\d+):(\d+)()() (-{,1}[0-9]+\.[0-9]+x|-{,1}[0-9]x|-{,1}[0-9]+/[0-9]+x|pause) ()(\S+) (\d+)() (\d+) \((\d\d):(\d\d):(\d\d)(\.(\d+))?Z\) Subtitles: (.+)',
                                  query)
            if match:

                try:
                    hrs  = int(match.group(11))
                    mins = int(match.group(12))
                    secs = int(match.group(13))
                    micr = int((match.group(15) + '000000')[0:6])
                except:
                    pass
                else:
                    now = now.replace(hour=hrs, minute=mins, second=secs, microsecond=micr)

                substrings = []
                substring = match.group(16)
                m=re.match('\*{,1}(\d+):\[(.+?)\]\*{,1} *',substring)
                while m:
                    substrings.append((m.group(1),m.group(2),(m.group(0)[0] == '*')))
                    substring = substring[len(m.group(0)):]
                    m=re.match('\*{,1}(\d+):\[(.+?)\]\*{,1} *',substring)

                media_components = []
                if not substrings[0][2]:
                    media_components.append({'type' : 'subtitles',
                                             'mcid' : 'subtitles',})

                if match.group(6) == '':
                    try:
                        pid = id_component(match.group(7).split('/')[-1])
                    except:
                        pid = ''
                    mythtv_outputs['0'].set('programme',('SG_2',pid,media_components))
                    mythtv_outputs['0'].set('app',None)
                else:
                    try:
                        id = '%04d' % int(match.group(6))
                    except:
                        pass
                    else:
                        if re.match('LiveTV ', query[9:]):
                            pid = id_component('%sZ' % match.group(7))
                            if mythtv_outputs['0'].data['programme'] != (id,pid,media_components):
                                mythtv_outputs['0'].set('programme',(id,pid,media_components))
                                mythtv_outputs['0'].set('app',None)

                            try:
                                pos = int(match.group(1))*60 + int(match.group(2)) - int(match.group(3))*60 - int(match.group(4))
                            except:
                                mythtv_outputs['0'].set('playhead',None)
                            else:
                                mythtv_outputs['0'].set('playhead',{ 'rposition' : { 'position' : float(pos),
                                                                                     'position_precision' : 0,
                                                                                     'position_timestamp' : now,
                                                                                     },
                                                                     })
                        else:
                            pid = '%s_%s' % (id,match.group(7).replace('-','').replace(':','').replace('T',''))
                            if pid in mythtv_storage['items']:
                                if mythtv_outputs['0'].data['programme'] != (mythtv_storage['items'][pid]['sid'],pid,media_components):
                                    mythtv_outputs['0'].set('programme',(mythtv_storage['items'][pid]['sid'],pid,media_components))
                                    mythtv_outputs['0'].set('app',None)
                            else:
                                mythtv_outputs['0'].set('programme',None)
                                mythtv_outputs['0'].set('app',None)
                                mythtv_outputs['0'].set('playhead',None)

                if not re.match('LiveTV ',query[9:]):
                    try:
                        length = int(match.group(3))*60 + int(match.group(4))
                    except:
                        if ('programme' in mythtv_outputs['0']
                            and mythtv_outputs['0']['programme'] is not None
                            and mythtv_programmes is not None):
                            try:
                                contents = [ c for c in mythtv_programmes.get([mythtv_outputs['0']['programme'][0],],1,0,content_ids=[mythtv_outputs['0']['programme'][1],]) ]
                            except:
                                length = None
                            else:
                                if len(contents) > 0:
                                    length = float(contents[0]['duration']/10000)
                                else:
                                    length = None
                        else:
                            length = None

                    try:
                        pos    = float(match.group(8))/float(match.group(10)) + FIXED_POSITION_OFFSET
                    except:
                        mythtv_outputs['0'].set('playhead',None)
                    else:
                        mythtv_outputs['0'].set('playhead', { 'aposition' : { 'position' : pos,
                                                                              'position_precision' : int(math.ceil(math.log10(int(match.group(10))))),
                                                                              'position_timestamp' : now,
                                                                              },
                                                              })
                        if length is not None:
                            try:                                
                                mythtv_outputs['0']['playhead']['length'] = float(length)
                            except:
                                pass

                try:
                    if match.group(5) == 'pause':
                        speed = 0.0
                    elif re.match('-{,1}[0-9]+(\.[0-9]+){,1}x$',match.group(5)):
                        speed = float(match.group(5)[:-1])
                    else:
                        match2 = re.match('(-{,1}[0-9]+)/([0-9]+)x$',match.group(5))
                        if match2:
                            speed = float(match2.group(5))/float(match2.group(6))
                except:
                    pass
                else:
                    if speed != 0.0:
                        mythtv_outputs['0'].set('playback',speed)
                    else:
                        mythtv_outputs['0'].set('playback',0.0)
            else:
                mythtv_outputs['0'].set('programme',None)
                mythtv_outputs['0'].set('app',None)
                mythtv_outputs['0'].set('playback',None)
                mythtv_outputs['0'].set('playhead',None)                
        else:
            mythtv_outputs['0'].set('programme',None)
            mythtv_outputs['0'].set('app',None)
            mythtv_outputs['0'].set('playback',None)
            mythtv_outputs['0'].set('playhead',None)
    elif re.match('game ',query):
        match = re.match('game (.+) (.+)',query)
        games = [ pid for pid in mythtv_game_programmes if (mythtv_game_programmes[pid]['MYTHTV:gamename'] == match.group(1) 
                                                            and mythtv_game_programmes[pid]['MYTHTV:systemname'] == match.group(2)) ]
        if len(games) > 0:
            mythtv_outputs['0'].set('programme',None)
            mythtv_outputs['0'].set('app',('mythgame', games[0], []))
            mythtv_outputs['0'].set('playback',None)
            mythtv_outputs['0'].set('playhead',None)
        else:
            mythtv_outputs['0'].set('programme',None)
            mythtv_outputs['0'].set('app',None)
            mythtv_outputs['0'].set('playback',None)
            mythtv_outputs['0'].set('playhead',None)
    elif re.match('ERROR',query):
        uc_server.log_message("MythTV Query returned an error, retrying is 1s")
        return
    else:
        try:
            key = query.split(' ')[0]
        except:
            raise ValueError

        if key in dict(myth_menu_locations):
            mythtv_outputs['0'].set('programme',None)
            mythtv_outputs['0'].set('app',('mythtv',id_component(key),[':uk_keyboard',]))
            mythtv_outputs['0'].set('playback', None)
            mythtv_outputs['0'].set('playhead', None)
        else:
            mythtv_outputs['0'].set('programme',None)
            mythtv_outputs['0'].set('app',None)
            mythtv_outputs['0'].set('playback', None)
            mythtv_outputs['0'].set('playhead', None)

    value = None
    expected_value = None
    if old_playhead is None and mythtv_outputs['0'].data['playhead'] is None:
        pass
    elif (((old_playhead is None) != (mythtv_outputs['0'].data['playhead'] is None))
          or (('aposition' in old_playhead and old_playhead['aposition'] is not None) 
              != ('aposition' in mythtv_outputs['0'].data['playhead'] and mythtv_outputs['0'].data['playhead']['aposition'] is not None))
          or (('rposition' in old_playhead and old_playhead['rposition'] is not None) 
              != ('rposition' in mythtv_outputs['0'].data['playhead'] and mythtv_outputs['0'].data['playhead']['rposition'] is not None))):
        uc_server.notify_change('uc/outputs/0/playhead')
    elif ( 'aposition' in old_playhead
           and 'aposition' in mythtv_outputs['0'].data['playhead']
           and 'playback' in mythtv_outputs['0']
           and mythtv_outputs['0'].data['playback'] is not None):        
        diff = (mythtv_outputs['0'].data['playhead']['aposition']['position_timestamp'] - old_playhead['aposition']['position_timestamp'])
        expected_value = old_playhead['aposition']['position'] + float(mythtv_outputs['0'].data['playback'])*(float(diff.seconds) + (float(diff.microseconds)/float(1000000.0)))
        value = mythtv_outputs['0'].data['playhead']['aposition']['position']

        diff = abs(expected_value - value)
        
        if diff > mythtv_outputs['0'].data['playback']:
            uc_server.log_message("Playhead location: %f, expected %f ---- Difference: %f" % (value,expected_value,diff,))
            uc_server.notify_change('uc/outputs/0/playhead')
    elif ('rposition' in old_playhead
          and 'rposition' in mythtv_outputs['0'].data['playhead']
          and mythtv_outputs['0'].data['playback'] is not None):
        diff = (mythtv_outputs['0'].data['playhead']['rposition']['position_timestamp'] - old_playhead['rposition']['position_timestamp'])
        expected_value = old_playhead['rposition']['position'] + float(mythtv_outputs['0'].data['playback'] - 1.0)*(float(diff.seconds) + (float(diff.microseconds)/float(1000000.0)))
        value = mythtv_outputs['0'].data['playhead']['rposition']['position']

        diff = abs(expected_value - value)

        if diff > mythtv_outputs['0'].data['playback']:
            uc_server.notify_change('uc/outputs/0/playhead')
        

def update_storage():
    global mythtv_storage
    global mythtv_sources
    global mythtv_source_lists
    global uc_server

    try:
        groups = dict([ ('%d' % group.id,group) for group in MythDB().getStorageGroup() ])
    except:
        raise 

    sources = []
    if '1' in groups:
        group = groups['1']
        sources.append({ 'id'   : 'SG_1',
                         'name' : "Recordings Stored by MythTV",
                         'sref' : 'myth:%s@%s%s' % (group.groupname,
                                                    uc_server.ip_address(),
                                                    group.dirname,),
                         'rref' : 'uc/sources/%s' % id_component('SG_1'),
                         'live' : False,
                         'linear' : False,
                         'follow-on' : False,
                         'MYTHTV:type' : 'storagegroup',
                         'MYTHTV:groupname' : group.groupname,
                         })
    if '2' in groups:
        group = groups['2']
        sources.append({ 'id'   : 'SG_2',
                         'name' : "Videos Stored by MythTV",
                         'sref' : 'myth:%s@%s%s' % (group.groupname,
                                                    uc_server.ip_address(),
                                                    group.dirname,),
                         'rref' : 'uc/sources/%s' % id_component('SG_2'),
                         'live' : False,
                         'linear' : False,
                         'follow-on' : False,
                         'MYTHTV:type' : 'storagegroup',
                         'MYTHTV:groupname' : group.groupname,
                         })
        
    for source in sources:
        if source['id'] not in mythtv_sources.data:
            mythtv_sources.set(source['id'],source)
        if source['id'] not in mythtv_source_lists['uc_default']['sources']:
            mythtv_source_lists['uc_default']['sources'].append(source['id'])

    if [ source['id'] for source in sources ] != mythtv_source_lists['uc_storage'].data['sources']:
        mythtv_source_lists['uc_storage'].set('sources',[ source['id'] for source in sources ])

    recgroups = dict([ (source['MYTHTV:groupname'],source['id']) for source in sources ])

    try:
        (size,used) = MythBE().getFreeSpaceSummary()
    except:
        raise

    if 'size' not in mythtv_storage or mythtv_storage['size'] != size:
        mythtv_storage['size']  = int(size)
    if 'free' not in mythtv_storage or mythtv_storage['free'] != (size - used):
        mythtv_storage['free']  = int(size - used)

    try:
        recordings = MythBE().getRecordings()
    except:
        raise

    try:
        videos = MythTV.Video.getAllEntries()
    except:
        raise

    recordings = dict([ (id_component("%s_%s" % (recording.chanid,recording.recstartts.strftime('%Y%m%d%H%M%S'))),recording) for recording in recordings ])
    videos     = dict([ (id_component(vid.filename),vid) for vid in videos ])
    
    def __timecorrect():
        return datetime.timedelta(seconds=(time.timezone if time.daylight==0 else time.altzone))

    for rid in recordings:
        rec = recordings[rid]        

        if datetime.datetime.now() < rec.recendts:
            continue

        if rec.recgroup not in recgroups:
            continue

        if rid not in mythtv_storage['items'].data:
            duration = (rec.endtime - rec.starttime)
            mythtv_storage['items'].set(rid,notdict({ 'cid' : rid,
                                                      'sid' : recgroups[rec.recgroup],
                                                      'created-time' : '%sZ' % (rec.recendts + __timecorrect()).isoformat(),
                                                      'size' : int(rec.filesize),
                                                      'MYTHTV:chanid' : rec.chanid,
                                                      'MYTHTV:recstartts' : rec.recstartts + __timecorrect(),
                                                      'MYTHTV:program' : { 'sid' : recgroups[rec.recgroup],
                                                                           'cid' : rid,
                                                                           'synopsis' : str(rec.description),
                                                                           'title' : str(rec.title),
                                                                           'pref'  : str(rec.filename).replace('127.0.0.1',uc_server.ip_address()),
                                                                           'duration' : int((duration.days*86400 + duration.seconds)*10000 + duration.microseconds//100),
                                                                           'interactive' : False,
                                                                           'media-components' : {'audio' : { 'id' : 'audio',
                                                                                                             'type' : 'audio',
                                                                                                             'name' : "Primary Audio",
                                                                                                             'default' : True,
                                                                                                             },
                                                                                                 },
                                                                           },
                                                      'MYTHTV:play_command' : 'program %d %s' % (rec.chanid, rec.recstartts.isoformat()),                         
                                                      }, 
                                                    notify=mythtv_storage_notify,
                                                    setters={ 'cid' : None,
                                                              'sid' : None,
                                                              'created-time' : None,
                                                              'size' : None }))
            if '%04d' % rec.chanid in mythtv_sources and mythtv_sources['%04d' % rec.chanid]['MYTHTV:type'] == 'tv':
                try:
                    mythtv_storage['items'][rid]['MYTHTV:program']['media-components']['video'] = { 'id' : 'video',
                                                                                                    'type' : 'video',
                                                                                                    'name' : "Primary Video",
                                                                                                    'default' : True,
                                                                                                    'colour' : True,
                                                                                                    }
                except:
                    raise

                if rec.video_props is not None:
                    try:
                        mythtv_storage['items'][rid]['MYTHTV:program']['media-components']['video']['aspect'] = ('4:3','16:9','16:9','16:9')[rec.video_props]
                    except:
                        pass
                    try:
                        mythtv_storage['items'][rid]['MYTHTV:program']['media-components']['video']['vidformat'] = ('SD','SD','HD','HD')[rec.video_props]
                    except:
                        pass

            if rec.subtitle_type is not None:
                try:
                    mythtv_storage['items'][rid]['MYTHTV:program']['media-components']['subtitles'] = { 'id' : 'subtitles',
                                                                                                        'type' : 'subtitles',
                                                                                                        'name' : "Subtitles",
                                                                                                        'default' : False,
                                                                                                        }
                except:
                    pass
            
            if rec.programid is not None:
                try:
                    mythtv_storage['items'][rid]['global-content-id'] = 'crid://%s' % (rec.programid,)
                    mythtv_storage['items'][rid]['MYTHTV:program']['global-content-id'] = 'crid://%s' % (rec.programid,)
                except:
                    pass

            if rec.seriesid is not None:
                try:
                    mythtv_storage['items'][rid]['MYTHTV:program']['global-series-id'] = 'crid://%s' % (rec.seriesid)
                    mythtv_storage['items'][rid]['MYTHTV:program']['series-id'] = id_component('%s' % (rec.seriesid))
                except:
                    pass
        else:
            if int(rec.filesize) != mythtv_storage['items'][rid]['size']:
                mythtv_storage['items'][rid].set('size',int(rec.filesize))

    
    for vidid in videos:
         vid = videos[vidid]

         if vidid not in mythtv_storage['items'].data:
             mythtv_storage['items'].set(vidid,notdict({ 'id' : vidid,
                                                         'sid' : "SG_2",
                                                         'created-time' : '%sZ' % vid.insertdate.isoformat(),
                                                         'MYTHTV:program' : { 'sid' : "SG_2",
                                                                              'cid' : vidid,
                                                                              'synopsis' : str(vid.tagline),
                                                                              'title' : str(vid.title),
                                                                              'media-components' : {'audio' : { 'id' : 'audio',
                                                                                                                'type' : 'audio',
                                                                                                                'name' : "Primary Audio",
                                                                                                                'default' : True,
                                                                                                                },
                                                                                                    'video' : { 'id' : 'video',
                                                                                                                'type' : 'video',
                                                                                                                'name' : "Primary Video",
                                                                                                                'default' : True,
                                                                                                                },
                                                                                                    },                                                                             
                                                                              },
                                                         'MYTHTV:play_command' : 'file /var/lib/mythtv/videos/%s' % (vid.filename,),
                                                         }, 
                                                       notify=mythtv_storage_notify,
                                                       setters={ 'cid' : None,
                                                                 'sid' : None,
                                                                 'created-time' : None,
                                                                 'size' : None }))                
             if vidid in ManualVideoMetadata:
                 mythtv_storage['items'][vidid]['MYTHTV:program'] = ManualVideoMetadata[vidid]


             
    to_delete = []
    for rid in mythtv_storage['items'].data:
        if rid not in recordings and rid not in videos:
            to_delete.append(rid)

    for rid in to_delete:
        mythtv_storage['items'].remove(rid)

def update_acquisitions():
    global mythtv_acquisitions

    def __timecorrect():
        return datetime.timedelta(seconds=(time.timezone if time.daylight==0 else time.altzone))

    power_rules = dict([ (record.recordid, record) for record in Record.getAllEntries() if record.search == 1L ])

    programme_crids = dict()
    series_crids = dict()
    series_used_ids = []

    for rid in power_rules:
        rule = power_rules[rid]

        match = re.match("program.programid='(.+)'", rule.description)
        if match:
            programme_crids[rid] = match.group(1)
            continue
        
        match = re.match("program.seriesid='(.+)'", rule.description)
        if match:            
            mythtv_acquisitions['series-acquisitions'].set('%03d' % rid, notdict({ 'global-series-id' : 'crid://%s' % match.group(1),
                                                                                   'series-id' : id_component(match.group(1)),
                                                                                   'MYTHTV:recordid' : rid,
                                                                                   'MYTHTV:query' : rule.description,
                                                                                   },
                                                                                 notify=mythtv_acquisition_notify))
            series_used_ids.append(rid)
            series_crids[rid] = 'crid://%s' % match.group(1)
            continue

    try:
        recordings = dict([ (id_component('%s__%s__%sZ' % (str(rec.recordid), rec.chanid, rec.recstartts.isoformat())),
                             rec) 
                            for rec in MythBE().getUpcomingRecordings() ])
    except:
        recordings = {}
        
        
    used_ids = [] #list(series_used_ids)

    for rid in recordings:
        rec = recordings[rid]
        if rec.recordid in programme_crids:
            mythtv_acquisitions['content-acquisitions'].set( rid, notdict({ 'sid' : '%04d' % int(rec.chanid),
                                                                            'cid' : id_component('%sZ' % (rec.starttime + __timecorrect()).isoformat()),
                                                                            'start' : rec.starttime + __timecorrect(),
                                                                            'end' : rec.endtime + __timecorrect(),
                                                                            'global-content-id' : 'crid://%s' % programme_crids[rec.recordid],
                                                                            'active' : False,
                                                                            'interactive' : False,
                                                                            'series-linked' : False,
                                                                            'MYTHTV:query' : "program.programid='%s'" % programme_crids[rec.recordid],
                                                                            'MYTHTV:recordid' : rec.recordid,
                                                                            'MYTHTV:type' : 'global-content-id',
                                                                            },
                                                                          notify=mythtv_acquisition_notify))
        elif rec.recordid in series_used_ids:
            mythtv_acquisitions['content-acquisitions'].set( rid, notdict({ 'sid' : '%04d' % int(rec.chanid),
                                                                            'cid' : id_component('%sZ' % (rec.starttime + __timecorrect()).isoformat()),
                                                                            'start' : rec.starttime + __timecorrect(),
                                                                            'end' : rec.endtime + __timecorrect(),
                                                                            'series-id' : (mythtv_acquisitions['series-acquisitions']['%03d' % rec.recordid]['series-id']),
                                                                            'interactive' : False,
                                                                            'series-linked' : True,
                                                                            'active' : False,
                                                                            'MYTHTV:recordid' : rec.recordid,
                                                                            'MYTHTV:type' : 'series-link',
                                                                            },
                                                                          notify=mythtv_acquisition_notify))
        else:
            mythtv_acquisitions['content-acquisitions'].set(rid, notdict({ 'sid' : '%04d' % int(rec.chanid),
                                                                           'cid' : id_component('%sZ' % (rec.starttime + __timecorrect()).isoformat()),
                                                                           'start' : rec.starttime + __timecorrect(),
                                                                           'end' : rec.endtime + __timecorrect(),
                                                                           'interactive' : False,
                                                                           'series-linked' : False,
                                                                           'active' : False,
                                                                           'MYTHTV:recordid' : rec.recordid,
                                                                           'MYTHTV:type' : 'other',
                                                                           },
                                                                         notify=mythtv_acquisition_notify))
        used_ids.append(rec.recordid)

    to_delete = [ rid for rid in mythtv_acquisitions['content-acquisitions'] if mythtv_acquisitions['content-acquisitions'][rid]['MYTHTV:recordid'] not in used_ids ]
    for rid in to_delete:
        mythtv_acquisitions['content-acquisitions'].remove(rid)

    to_delete = [ rid for rid in mythtv_acquisitions['series-acquisitions'] if mythtv_acquisitions['series-acquisitions'][rid]['MYTHTV:recordid'] not in series_used_ids ]
    for rid in to_delete:
        mythtv_acquisitions['series-acquisitions'].remove(rid)

    now = datetime.datetime.utcnow()
    for rid in mythtv_acquisitions['content-acquisitions']:
        if mythtv_acquisitions['content-acquisitions'][rid]['start'] < now < mythtv_acquisitions['content-acquisitions'][rid]['end']:
            mythtv_acquisitions['content-acquisitions'][rid].set('active',True)

class MythTVOutputSelector:
    def __init__(self,oid):
        self.oid = oid

    def select_programme(self,sid,cid=None,components=[]):
        if sid in ('mythtv','mythgame'):
            raise InvalidSyntax
        self.select_content(sid,cid)

        subson = False
        if (isinstance(components,list) or isinstance(components,tuple)):
            for override in components:                
                if override['type'] == 'subtitles' and override['mcid'] != '':
                    if not sendPlay('subtitles 1'):
                        raise ProcessingFailed
                    subson = True

        if not subson and not sendPlay('subtitles'):
            raise ProcessingFailed

        return

    def select_app(self,sid,cid=None):
        global extra_sources

        if sid in ('mythtv','mythgame'):
            self.select_content(sid,cid)
        elif sid in extra_sources:
            extra_sources[sid].activate(sid,cid)
        else:
            raise InvalidSyntax

    def select_content(self,sid,cid=None):
        global mythtv_sources

        if sid not in mythtv_sources:
            raise CannotFind()

        if sid in extra_sources:
            return self.select_app(sid,cid)

        if sid in mythtv_source_lists['uc_storage']['sources']:
            if cid in mythtv_storage['items'] and mythtv_storage['items'][cid]['sid'] == sid:
                if not ('programme' in mythtv_outputs[self.oid]
                        and mythtv_outputs[self.oid]['programme'] is not None
                        and mythtv_outputs[self.oid]['programme'][0] == sid
                        and mythtv_outputs[self.oid]['programme'][1] == cid):
                    if not ('app' in mythtv_outputs[self.oid] 
                            and  mythtv_outputs[self.oid]['app'] is not None 
                            and mythtv_outputs[self.oid]['app'][0] == 'mythtv'):
                        MythDB().getFrontends().next().sendJump('mainmenu')

                        lock = threading.Condition()
                        lock.acquire()
                        lock.wait(3)
                        lock.release()
                
                    sendPlay(mythtv_storage['items'][cid]['MYTHTV:play_command'])
                else:
                    sendPlay('speed 1x')
                return
            else:
                if sid == 'SG_1':
                    try:
                        MythDB().getFrontends().next().sendJump('playbackbox')
                    except:
                        raise ProcessingFailed
                    return
                elif sid == 'SG_2':
                    try:
                        MythDB().getFrontends().next().sendJump('videobrowser')
                    except:
                        raise ProcessingFailed
                    return
                else:
                    raise CannotFind 
 
        elif sid in mythtv_source_lists['mythtv_mythnetvision']['sources']:
            
            articles = [ a.url for a in InternetContentArticles.getAllEntries() if id_component(a.url) == cid ]
            if len(articles) == 0:
                raise CannotFind
            else:
                sendPlay('url %s' % (articles[0],))
            return
        elif sid in mythtv_sources and mythtv_sources[sid]['MYTHTV:type'] in ('tv','radio'):
            if (not ('programme' in mythtv_outputs
                     and mythtv_outputs[self.oid]['programme'] is not None
                     and mythtv_outputs[self.oid]['programme'][0] in mythtv_sources 
                     and mythtv_sources[mythtv_outputs[self.oid]['programme'][0]]['MYTHTV:type'] in ('tv','radio'))):
                try:
                    MythTV.MythDB().getFrontends().next().sendJump('livetv')
                except:
                    raise ProcessingFailed

                lock = threading.Condition()
                lock.acquire()
                lock.wait(3)
                lock.release()

                sendPlay('chanid %s' % sid)
            elif not ('programme' in mythtv_outputs[self.oid]
                      and mythtv_outputs[self.oid]['programme'] is not None
                      and mythtv_outputs[self.oid]['programme'][0] == sid):
                sendPlay('chanid %s' % sid)
            mythtv_outputs[self.oid].set('programme',(sid,'',[]))
            mythtv_outputs[self.oid].set('app',None)
            return
        elif sid == 'mythtv':
            cids = [ programme['cid'] for programme in mythtv_menu_programmes ]
            if cid in cids:
                try:
                    MythTV.MythDB().getFrontends().next().sendJump(cid)
                except:
                    raise ProcessingFailed
            else:
                try:
                    MythTV.MythDB().getFrontends().next().sendJump('mainmenu')
                except:
                    raise ProcessingFailed
            return
        elif sid == 'mythgame':
            if cid in mythtv_game_programmes:
                if not ('app' in mythtv_outputs[self.oid] 
                        and mythtv_outputs[self.oid]['app'] is not None
                        and mythtv_outputs[self.oid]['app'][0] == 'mythtv'):
                    MythDB().getFrontends().next().sendJump('mainmenu')

                    lock = threading.Condition()
                    lock.acquire()
                    lock.wait(1)
                    lock.release()

                if not sendPlay('game %s %s' % (mythtv_game_programmes[cid]['MYTHTV:gamename'],
                                                mythtv_game_programmes[cid]['MYTHTV:systemname'],
                                                )):
                    raise ProcessingFailed
            elif cid == '':
                try:
                    MythTV.MythDB().getFrontends().next().sendJump('MythGame')
                except:
                    raise ProcessingFailed
            else:
                raise CannotFind("Cannot find given programme")
            return

        raise CannotFind("Cannot find given source")
        

class Acquirer:
    def acquire (self,global_content_id=None,cid=None,sid=None,series_id=None,priority=False):
        global mythtv_sources

        def __timecorrect():
            return datetime.timedelta(seconds=(time.timezone if time.daylight==0 else time.altzone))

        if cid is not None and sid is None:
            return None
        elif sid is not None:
            if cid is None:
                return None

            if (sid not in mythtv_sources
                or mythtv_sources[sid]['MYTHTV:type'] not in ('tv','radio')):
                raise ProcessingFailed

            try:
                start = parse_iso(unpctencode(cid))
            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                raise

            try:
                guides = [ prog for prog in MythDB().searchGuide(chanid=sid,
                                                                 starttime=start - __timecorrect()) ]

            except Exception as inst:
                uc_server.log_message(traceback.format_exc())
                guides = [ prog for prog in MythDB().searchGuide(chanid=sid,
                                                                 starttime=start - __timecorrect()) ]
                
            global_content_ids = [ guide.programid for guide in guides if guide.programid is not None ]
            if len(global_content_ids) > 0 :
                global_content_id = 'crid://%s' % global_content_ids[0]
            elif len(guides) > 0:
                Record.fromGuide(guides[0])
                return True
            else:
                raise CannotFind

        if global_content_id is None and series_id is None:
            raise CannotFind
        elif global_content_id is not None:
            match = re.match('crid://(.+)', global_content_id)
            if match:
                query = "program.programid='%s'" % match.group(1)
            else:
                raise ProcessingFailed
            
            type = Record.kFindOneRecord

        else:
            query = "program.seriesid='%s'" % unpctencode(series_id)
            
            type = Record.kAllRecord
            
        try:
            rec = Record()
        except:
            raise

        rec.title       = 'UC Power Rule: %s' % datetime.datetime.now()
        rec.description = query
        rec.search      = 1L
        rec.type        = type
        rec.create()

        c = threading.Condition()
        with c:
            c.wait(3)

        update_acquisitions()

        acq = [ aid for aid in mythtv_acquisitions['content-acquisitions'] if 'MYTHTV:query' in mythtv_acquisitions['content-acquisitions'][aid] and mythtv_acquisitions['content-acquisitions'][aid]['MYTHTV:query'] == query ]
        if len(acq) != 0:
            return acq[0]

        acq = [ aid for aid in mythtv_acquisitions['series-acquisitions'] if mythtv_acquisitions['series-acquisitions'][aid]['MYTHTV:query'] == query ]
        if len(acq) != 0:
            return acq[0]
            
        raise ProcessingFailed

    def cancel(self,acquisition_id):
        global mythtv_acquisitions

        update_acquisitions()

        if acquisition_id in mythtv_acquisitions['content-acquisitions']:

            if mythtv_acquisitions['content-acquisitions'][acquisition_id]['MYTHTV:type'] == 'global-content-id':
                recording_rules = [ record for record in Record.getAllEntries() if record.recordid == mythtv_acquisitions['content-acquisitions'][acquisition_id]['MYTHTV:recordid'] ]
                if len(recording_rules) != 0:
                    recording_rules[0].delete()
            else:
                raise ProcessingFailed
        elif acquisition_id in mythtv_acquisitions['series-acquisitions']:
            recording_rules = [ record for record in Record.getAllEntries() if record.recordid == mythtv_acquisitions['series-acquisitions'][acquisition_id]['MYTHTV:recordid'] ]
            if len(recording_rules) != 0:
                recording_rules[0].delete()                        
        else:
            raise CannotFind

        c = threading.Condition()
        with c:
            c.wait(1)

        update_acquisitions()
        return True
            

class Programmes:

    def __timecorrect(self):
        return datetime.timedelta(seconds=(time.timezone if time.daylight==0 else time.altzone))

    def filterprogrammes(self,generator,params, timestrict=False, textstrict=False):
        if 'text' in params:
            params['text'] = [ item.upper() for item in params['text'] ]

        keys = (('sid','sid'),
                ('cid','cid'),
                ('series-id','series-id'),
                ('gcid','global-content-id'),
                ('gsid','global-series-id'),
                ('gaid','global-app-id'),
                )

        count = 0
        for prog in generator:

            if any([ key[0] in params and key[1] in prog and prog[key[1]] not in params[key[0]] for key in keys ]):
                continue

            if 'category' in params and ( 'categories' not in prog or not [ cat for cat in prog['categories'] if cat in params['category'] ]):
                continue

            if not params['interactive'] and 'interactive' in prog and prog['interactive']:
                continue

            if not params['AV'] and 'interactive' in prog and not prog['interactive']:
                continue

            if timestrict and 'start' in params and 'presentable-until' not in prog and 'acquireable-until' not in prog:
                continue
            
            if ('start' in params 
                and (('presentable-until' in prog and prog['presentable-until'] < params['start'])
                     or ('presentable-until' not in prog and 'acquirable-until' in prog and prog['acquirable-until'] < params['start']))):
                continue

            if timestrict and 'end' in params and 'presentable-from' not in prog and 'acquireable-from' not in prog and 'start' not in prog:
                continue
            
            if ('end' in params
                and (('start' not in prog and 'presentable-from' in prog and prog['presentable-from'] >= params['end'])
                     or ('presentable-from' not in prog and 'start' not in prog and 'acquirable-from' in prog and prog['acquirable-from'] >= params['end'])
                     or ('start' in prog and prog['start'] >= params['end']))):
                continue
            
            if textstrict and 'text' in params and ('field' not in params or ('title' in params['field'] and 'title' not in prog)):
                continue

            if textstrict and 'text' in params and ('field' not in params or ('synopsis' in params['field'] and 'synopsis' not in prog)):
                continue

            if 'text' in params:
                if (('field' in params and 'title' in params['field'] and 'synopsis' in params['field'])
                    and not all([ ((('title' in prog and (prog['title'].upper().count(item.upper()) != 0)) 
                                    or ('synopsis' in prog and (prog['synopsis'].upper().count(item.upper()) != 0)))
                                   or ('title' not in prog and 'synopsis' not in prog)) 
                                  for item in params['text'] ])):
                    continue
                
                elif (('field' in params and 'title' in params['field'] and 'synopsis' not in params['field'])
                      and not ('title' not in prog or all([ (prog['title'].upper().count(item.upper()) != 0) for item in params['text'] ]))):
                    continue
                elif (('field' in params and 'synopsis' in params['field'] and 'title' not in params['field'])
                      and not ('synopsis' not in prog or all([ (prog['synopsis'].upper().count(item.upper()) != 0) for item in params['text'] ]))):
                    continue

            if count < params['offset']:
                count += 1
                continue

#            if count >= params['results'] + params['offset']:
#                break
                
            count += 1
            yield prog

    def select_results(self,generator,results):
        generator = ( x for x in generator )
        res = []
        for i in range(0,results):
            try:
                val = generator.next()        
                res.append(val)
            except:
                break
        try:
            generator.next()
        except:
            more = False
        else:
            more = True

        return (res,more)


    def get_output(self,output,params):
        global mythtv_outputs

        if output not in mythtv_outputs:
            raise ProcessingFailed()

        if (('programme' not in mythtv_outputs[output] or mythtv_outputs[output]['programme'] is None or mythtv_outputs[output]['programme'][0] == '') and
            ('app' not in mythtv_outputs[output] or mythtv_outputs[output]['app'] is None or mythtv_outputs[output]['app'][0] == '')):
            return [([],False),]

        app = None
        if 'interactive' not in params or params['interactive']:
            if 'app' in mythtv_outputs[output] and mythtv_outputs[output]['app'] is not None and len(mythtv_outputs[output]['app']) > 0:
                if mythtv_outputs[output]['app'][0] == 'mythtv':
                    app = [ prog for prog in mythtv_menu_programmes if prog['cid'] == mythtv_outputs[output]['app'][1] ]
                elif mythtv_outputs[output]['app'][0] == 'mythgame':
                    app = [ mythtv_game_programmes[prog] for prog in mythtv_game_programmes if mythtv_game_programmes[prog]['cid'] == mythtv_outputs[output]['app'][1] ]

                if len(app) == 0:
                    app = None
                else:
                    app = app[0]

        generator = []
        if 'AV' not in params or params['AV']:
            if 'programme' in mythtv_outputs[output] and mythtv_outputs[output]['programme'] is not None and len(mythtv_outputs[output]['programme']) > 0:

                if mythtv_outputs[output]['programme'][0] in mythtv_source_lists['uc_storage']['sources']:
                    if mythtv_outputs[output]['programme'][1] in mythtv_storage['items']:
                        generator = [ mythtv_storage['items'][mythtv_outputs[output]['programme'][1]]['MYTHTV:program'], ]
                    else:
                        return [([],False),]

                if (mythtv_outputs[output]['programme'][0] in mythtv_sources 
                    and 'live' in mythtv_sources[mythtv_outputs[output]['programme'][0]]
                    and mythtv_sources[mythtv_outputs[output]['programme'][0]]['live']):
                    if ('playhead' in mythtv_outputs[output] 
                        and mythtv_outputs[output]['playhead'] is not None
                        and 'positition' in mythtv_outputs[output]['playhead']
                        and isinstance(mythtv_outputs[output]['playhead']['position'],float)):
                        if 'start' in params:
                            params['start'] += datetime.timedelta(seconds=mythtv_outputs[output]['playhead']['position'])
                        if 'end' in params:
                            params['end']   += datetime.timedelta(seconds=mythtv_outputs[output]['playhead']['position'])

                    generator = self.programme_metadata_for_channel(mythtv_outputs[output]['programme'][0],params['start'],( params['end'] if 'end' in params else None))

        def gen(a,g):
            if a is not None:
                yield a
            for prog in g:
                yield prog

        return [self.select_results(self.filterprogrammes(gen(app,generator),params),params['results']),]


    def get_sources(self,sources,params):
        global extra_sources
        generators = []

        for source in sources:            
            if source == 'mythtv':
                if 'interactive' in params and not params['interactive']:
                    continue
                generator = [ prog for prog in mythtv_menu_programmes ]
            elif source in extra_sources:
                generator = [ prog for prog in extra_sources[source].get_content() ]
            elif source == 'mythgame':
                if 'interactive' in params and not params['interactive']:
                    continue
                generator = [ mythtv_game_programmes[prog] for prog in mythtv_game_programmes ]
            elif source in mythtv_source_lists['uc_storage']['sources']:
                if 'AV' in params and not params['AV']:
                    continue
                generator = [ mythtv_storage['items'][cid]['MYTHTV:program'] for cid in mythtv_storage['items'] if mythtv_storage['items'][cid]['sid'] == source ]
            elif (source in mythtv_sources 
                  and 'live' in mythtv_sources[source]
                  and mythtv_sources[source]['live']):
                if mythtv_sources[source]['MYTHTV:type'] in ('tv','radio') and 'AV' in params and not params['AV']:
                    continue
                generator = self.programme_metadata_for_channel(source,params['start'],( params['end'] if 'end' in params else None))                    
            elif (source in mythtv_source_lists['mythtv_mythnetvision']['sources']):
                if 'AV' in params and not params['AV']:
                    continue
                generator = self.programme_metadata_for_netvision(source,params['start'],(params['end'] if 'end' in params else None))
            else:
                raise CannotFind()

            generators.append(generator)

        return  [ self.select_results(self.filterprogrammes(generator,params),params['results'])
                  for generator in generators ]


    def get_text(self,text,params):
        generators = []
        
        for source in extra_sources:
            if 'sid' not in params or source in params['sid']:
                generators.append([ prog for prog in extra_sources[source].get_content() ])
        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythtv' in params['sid']):
            generators.append([ prog for prog in mythtv_menu_programmes ])
        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythgame' in params['sid']):
            generators.append([ mythtv_game_programmes[prog] for prog in mythtv_game_programmes ])
        if not('AV' in params and not params['AV']):
            for source in mythtv_source_lists['uc_storage']['sources']:
                if ('sid' not in params or source in params['sid']):
                    generators.append([ mythtv_storage['items'][cid]['MYTHTV:program'] for cid in mythtv_storage['items'] if mythtv_storage['items'][cid]['sid'] == source ])
            for source in mythtv_sources:
                if ('sid' not in params or source in params['sid']):
                    generators.append(self.programme_metadata_for_channel(source,params['start'],( params['end'] if 'end' in params else None)))
            for source in mythtv_source_lists['mythtv_mythnetvision']['sources']:
                if ('sid' not in params or source in params['sid']):
                    generator = self.programme_metadata_for_netvision(source,params['start'],(params['end'] if 'end' in params else None))

        params['text'] = text

        def streak(lists):
            gens = [ (x for x in l) for l in lists ]
            while gens:
                todel = []
                for g in gens:
                    try:
                        yield g.next()
                    except:
                        todel.append(g)
                for d in todel:
                    gens.remove(d)

        return  [ self.select_results(self.filterprogrammes(streak(generators),params, textstrict=True), params['results']), ]

    def get_categories(self,categories,params):
        generators = []
        
###        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythtv' in params['sid']):
###            generators.append([ prog for prog in mythtv_menu_programmes ])
###        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythgame' in params['sid']):
###            generators.append([ mythtv_game_programmes[prog] for prog in mythtv_game_programmes ])
        for source in extra_sources:
            if 'sid' not in params or source in params['sid']:
                generators.append([ prog for prog in extra_sources[source].get_content() ])
        if not('AV' in params and not params['AV']):
            for source in mythtv_source_lists['uc_storage']['sources']:
                if ('sid' not in params or source in params['sid']):
                    generators.append([ mythtv_storage['items'][cid]['MYTHTV:program'] for cid in mythtv_storage['items'] if mythtv_storage['items'][cid]['sid'] == source ])
            for source in mythtv_source_lists['mythtv_mythnetvision']['sources']:
                if ('sid' not in params or source in params['sid']):
                    generator = self.programme_metadata_for_netvision(source,params['start'],(params['end'] if 'end' in params else None))
            for source in mythtv_sources:
                if ('sid' not in params or source in params['sid']):
                    generators.append(self.programme_metadata_for_channel(source,params['start'],( params['end'] if 'end' in params else None)))

        params['category'] = categories

        def streak(lists):
            gens = [ (x for x in l) for l in lists ]
            while gens:
                todel = []
                for g in gens:
                    try:
                        yield g.next()
                    except:
                        todel.append(g)
                for d in todel:
                    gens.remove(d)

        return  [ self.select_results(self.filterprogrammes(streak(generators),params), params['results']), ]

    def get_gcid(self,gcid,params):
        generators = []

#        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythtv' in params['sid']):
#            generators.append([ prog for prog in mythtv_menu_programmes ])
#        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythgame' in params['sid']):
#            generators.append([ mythtv_game_programmes[prog] for prog in mythtv_game_programmes ])
        for source in extra_sources:
            if 'sid' not in params or source in params['sid']:
                generators.append([ prog for prog in extra_sources[source].get_content() ])
        if not('AV' in params and not params['AV']):
            for source in mythtv_source_lists['uc_storage']['sources']:
                if ('sid' not in params or source in params['sid']):
                    gen = [ mythtv_storage['items'][cid]['MYTHTV:program'] for cid in mythtv_storage['items'] if mythtv_storage['items'][cid]['sid'] == source and 'global-content-id' in mythtv_storage['items'][cid]['MYTHTV:program'] and mythtv_storage['items'][cid]['MYTHTV:program']['global-content-id'] == gcid]
                    generators.append(gen)
#            for source in mythtv_source_lists['mythtv_mythnetvision']['sources']:
#                if ('sid' not in params or source in params['sid']):
#                    generator = self.programme_metadata_for_netvision(source,params['start'],(params['end'] if 'end' in params else None))
            generators.append(self.programme_metadata_for_gids(gcid=gcid,start=params['start'],end=( params['end'] if 'end' in params else None)))

        params['gcid'] = [gcid,]

        def streak(lists):
            gens = [ (x for x in l) for l in lists ]
            while gens:
                todel = []
                for g in gens:
                    try:
                        yield g.next()
                    except:
                        todel.append(g)
                for d in todel:
                    gens.remove(d)

        return  [ self.select_results(self.filterprogrammes(streak(generators),params), params['results']), ]

    def get_gsid(self,gsid,params):
        generators = []
        
#        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythtv' in params['sid']):
#            generators.append([ prog for prog in mythtv_menu_programmes ])
#        if not('interactive' in params and not params['interactive']) and ('sid' not in params or 'mythgame' in params['sid']):
#            generators.append([ mythtv_game_programmes[prog] for prog in mythtv_game_programmes ])
        for source in extra_sources:
            if 'sid' not in params or source in params['sid']:
                generators.append([ prog for prog in extra_sources[source].get_content() ])
        if not('AV' in params and not params['AV']):
            for source in mythtv_source_lists['uc_storage']['sources']:
                if ('sid' not in params or source in params['sid']):
                    generators.append([ mythtv_storage['items'][cid]['MYTHTV:program'] for cid in mythtv_storage['items'] if mythtv_storage['items'][cid]['sid'] == source and 'global-series-id' in mythtv_storage['items'][cid]['MYTHTV:program'] and mythtv_storage['items'][cid]['MYTHTV:program']['global-series-id'] == gsid])
#            for source in mythtv_source_lists['mythtv_mythnetvision']['sources']:
#                if ('sid' not in params or source in params['sid']):
#                    generator = self.programme_metadata_for_netvision(source,params['start'],(params['end'] if 'end' in params else None))
            items = [ x for x in self.programme_metadata_for_gids(gsid=gsid,start=params['start'],end=( params['end'] if 'end' in params else None)) ]
            generators.append(items)

        params['gsid'] = [gsid,]

        def streak(lists):
            gens = [ (x for x in l) for l in lists ]
            while gens:
                todel = []
                for g in gens:
                    try:
                        yield g.next()
                    except:
                        todel.append(g)
                for d in todel:
                    gens.remove(d)

        return  [ self.select_results(self.filterprogrammes(streak(generators),params), params['results']), ]

    def get_gaid(self,gaid,params):
        generators = []
        
        for source in extra_sources:
            if 'sid' not in params or source in params['sid']:
                generators.append([ prog for prog in extra_sources[source].get_content() ])
        if ('sid' not in params or 'mythtv' in params['sid']):
            generators.append([ prog for prog in mythtv_menu_programmes 
                                if 'global-app-id' in prog and prog['global-app-id'] == gaid ])
        if ('sid' not in params or 'mythgame' in params['sid']):
            generators.append([ mythtv_game_programmes[prog] for prog in mythtv_game_programmes 
                                if 'global-app-id' in mythtv_game_programmes[prog] and mythtv_game_programmes[prog]['global-app-id'] == gaid ])

        params['gaid'] = [gaid,]

        def streak(lists):
            gens = [ (x for x in l) for l in lists ]
            while gens:
                todel = []
                for g in gens:
                    try:
                        yield g.next()
                    except:
                        todel.append(g)
                for d in todel:
                    gens.remove(d)

        return  [ self.select_results(self.filterprogrammes(streak(generators),params), params['results']), ]


    def programme_metadata_for_netvision(self,source,start,end):
        for article in [ a for a in InternetContentArticles.getAllEntries() if id_component(a.feedtitle) == source ]:
            yield { 'sid' : id_component(article.feedtitle),
                    'cid' : id_component(article.url),
                    'title' : article.title,
                    'synopsis' : article.description,
                    'logo-href' : article.thumbnail,
                    'media-components' : {'audio' : {'id' : 'audio',
                                                     'type' : 'audio',
                                                     'name' : 'Primary Audio',
                                                     'default' : True,
                                                     },
                                          },
                    'pref' : article.url,
                    'interactive' : False,
                    }

    def programme_metadata_for_gids(self,gcid=None,gsid=None,start=None,end=None):
        if gcid is not None:
            gcid = gcid[7:]
        if gsid is not None:
            gsid = gsid[7:]

        try:
            guides = MythDB().searchGuide(endafter=start,startbefore=end,
                                          programid=gcid,
                                          seriesid=gsid)
        except:
            print traceback.format_exc()
            guides = []        

        for guide in guides:
            yield self.programme_from_guide(guide)

    def programme_metadata_for_channel(self,channel,start,end):
        def programme_metadata_for_channel_actual(channel,start,end):
            
            start = start - self.__timecorrect()
            if end is not None:
                end = end - self.__timecorrect()
            
            tempstart = start

            if end is None:
                tempend = tempstart
            else:
                tempend = end

            try:
                guides = MythDB().searchGuide(endafter=tempstart,startbefore=tempend,chanid=channel)
            except:
                guides = []

            while True:
                n = 0
                for guide in guides:
                    n+=1
                    tempstart = guide.endtime
                    yield self.programme_from_guide(guide)
        
                if end is None and n != 0:
                    tempend = tempstart + datetime.timedelta(days=1)
                    try:
                        guides = sorted(MythDB().searchGuide(endafter=tempstart,startbefore=tempend,chanid=channel), key=lambda guide : guide.starttime)
                    except:
                        guides = []
                else:
                    break                    
        return programme_metadata_for_channel_actual(channel,start,end)

    def programme_from_guide(self,guide):
        """This method takes a MythTV Guide object and returns a UCServer compatible dictionary
        containing the programme data."""

        src = "%04d" % guide.chanid

        programme = { 'sid' : src,
                      'cid' : id_component('%sZ' % (guide.starttime + self.__timecorrect()).isoformat()),
                      'synopsis' : guide.description,
                      'title' : guide.title,
                      'start' : guide.starttime + self.__timecorrect(),
                      'presentable-from'   : guide.starttime + self.__timecorrect(),
                      'presentable-until'   : guide.endtime + self.__timecorrect(),
                      'acquirable-until'   : guide.starttime + self.__timecorrect(),
                      'media-components' : {'audio' : { 'id' : 'audio',
                                                        'type' : 'audio',
                                                        'name' : "Primary Audio",
                                                        'default' : True,
                                                        },
                                            },
                      'interactive' : False,
                      }

        duration = (guide.endtime - guide.starttime)
        programme['duration'] = int((duration.days*86400 + duration.seconds)*10000 + duration.microseconds//100)

        if mythtv_sources[src]['MYTHTV:type'] == 'tv':
            programme['media-components']['video'] = { 'id'   : 'video',
                                                       'type' : 'video',
                                                       'name' : "Primary Video",
                                                       'default' : True,
                                                       }
            videoprops = guide.videoprop.split(',') if guide.videoprop != '' else []
            if 'WIDESCREEN' in videoprops :
                programme['media-components']['video']['aspect'] = "16:9"
            else:
                programme['media-components']['video']['aspect'] = "4:3"
                
                if 'HDTV' in videoprops :
                    programme['media-components']['video']['vidformat'] = 'HD'
                else:
                    programme['media-components']['video']['vidformat'] = 'SD'
                
        if guide.subtitletypes is not None and guide.subtitletypes in ('NORMAL','HARDHEAR'):
            subtitle_names = { 'NORMAL'   : "Primary Subtitles",
                               'HARDHEAR' : "Hard of hearing subtitles"}
            programme['media-components']['subtitles'] = { 'id'      : 'subtitles',
                                                           'type'    : 'subtitles',
                                                           'name'    : subtitle_names[guide.subtitletypes],
                                                           'default' : False,
                                                           }
            if guide.subtitletypes == 'HARDHEAR':
                programme['media-components']['subtitles']['intent'] = 'hhsubs'

        audioprops = guide.audioprop.split(',') if guide.audioprop != '' else []
        if 'STEREO' in audioprops :
            # DO SOMETHING?
            pass
        if 'VISUALIMPAIR' in audioprops :
            programme['media-components']['AD'] = { 'id' : 'AD',
                                                    'type' : 'audio',
                                                    'name' : "Audio Description Track",
                                                    'intent' : 'admix',
                                                    }
        if 'HARDHEAR' in audioprops :
            programme['media-components']['iiaudio'] = { 'id' : 'iiaudio',
                                                         'type' : 'audio',
                                                         'name' : "Improved Intelligibility Audio Mix",
                                                         'intent' : 'iimix',
                                                         }                                                                   
            
        if guide.category is not None and guide.category in category_lookup:
            programme['categories'] = [category_lookup[guide.category][0],]
            
        if guide.programid is not None and guide.programid != '':
            programme['global-content-id'] = 'crid://%s' % str(guide.programid)
        if guide.seriesid is not None and guide.seriesid != '':
            programme['series-id'] = id_component('%s' % str(guide.seriesid))
            programme['global-series-id'] = 'crid://%s' % str(guide.seriesid)

        return programme


keycodes = {
    ':uk_keyboard:0'                     : '0',                               
    ':uk_keyboard:1'                     : '1',                               
    ':uk_keyboard:2'                     : '2',                               
    ':uk_keyboard:3'                     : '3',                               
    ':uk_keyboard:4'                     : '4',                               
    ':uk_keyboard:5'                     : '5',                               
    ':uk_keyboard:6'                     : '6',                               
    ':uk_keyboard:7'                     : '7',                               
    ':uk_keyboard:8'                     : '8',                               
    ':uk_keyboard:9'                     : '9',                               
    ':uk_keyboard:AMPERSAND'             : 'ampersand',                                
    ':uk_keyboard:ASTERISK'              : 'asterisk',                                
    ':uk_keyboard:BACKSLASH'             : 'backslash',                                
    ':uk_keyboard:BACKSPACE'             : 'Backspace',                                
    ':uk_keyboard:CAPITAL_A'             : 'A',                               
    ':uk_keyboard:CAPITAL_B'             : 'B',                               
    ':uk_keyboard:CAPITAL_C'             : 'C',                               
    ':uk_keyboard:CAPITAL_D'             : 'D',                               
    ':uk_keyboard:CAPITAL_E'             : 'E',                               
    ':uk_keyboard:CAPITAL_F'             : 'F',                               
    ':uk_keyboard:CAPITAL_G'             : 'G',                               
    ':uk_keyboard:CAPITAL_H'             : 'H',                               
    ':uk_keyboard:CAPITAL_I'             : 'I',                               
    ':uk_keyboard:CAPITAL_J'             : 'J',                               
    ':uk_keyboard:CAPITAL_K'             : 'K',                               
    ':uk_keyboard:CAPITAL_L'             : 'L',                               
    ':uk_keyboard:CAPITAL_M'             : 'M',                               
    ':uk_keyboard:CAPITAL_N'             : 'N',                               
    ':uk_keyboard:CAPITAL_O'             : 'O',                               
    ':uk_keyboard:CAPITAL_P'             : 'P',                               
    ':uk_keyboard:CAPITAL_Q'             : 'Q',                               
    ':uk_keyboard:CAPITAL_R'             : 'R',                               
    ':uk_keyboard:CAPITAL_S'             : 'S',                               
    ':uk_keyboard:CAPITAL_T'             : 'T',                               
    ':uk_keyboard:CAPITAL_U'             : 'U',                               
    ':uk_keyboard:CAPITAL_V'             : 'V',                               
    ':uk_keyboard:CAPITAL_W'             : 'W',                               
    ':uk_keyboard:CAPITAL_X'             : 'X',                               
    ':uk_keyboard:CAPITAL_Y'             : 'Y',                               
    ':uk_keyboard:CAPITAL_Z'             : 'Z',                               
    ':uk_keyboard:COLON'                 : 'colon',
    ':uk_keyboard:COMMA'                 : 'comma',                                
    ':uk_keyboard:CURLY_BRACKET_LEFT'    : 'bracketleft',                                
    ':uk_keyboard:CURLY_BRACKET_RIGHT'   : 'bracketright',                                
    ':uk_keyboard:CURSOR_DOWN'           : 'Down',
    ':uk_keyboard:CURSOR_LEFT'           : 'Left',
    ':uk_keyboard:CURSOR_RIGHT'          : 'Right',
    ':uk_keyboard:CURSOR_UP'             : 'Up',
    ':uk_keyboard:DELETE'                : 'Delete',
    ':uk_keyboard:DOLLAR_SIGN'           : 'dollar',
    ':uk_keyboard:END'                   : 'End',
    ':uk_keyboard:EQUALS_SIGN'           : 'Equal',
    ':uk_keyboard:ESCAPE'                : 'Escape',
    ':uk_keyboard:GREATER_THAN_SIGN'     : 'greater',
    ':uk_keyboard:HOME'                  : 'Home',
    ':uk_keyboard:INSERT'                : 'Insert',
    ':uk_keyboard:LESS_THAN_SIGN'        : 'less',
    ':uk_keyboard:MINUS_SIGN'            : 'minus',
    ':uk_keyboard:NUMBER_SIGN'           : 'numbersign',
    ':uk_keyboard:PAGE_DOWN'             : 'Page_Down',
    ':uk_keyboard:PAGE_UP'               : 'Page_Up',
    ':uk_keyboard:PARENTHESIS_LEFT'      : 'parenleft',
    ':uk_keyboard:PARENTHESIS_RIGHT'     : 'parenright',
    ':uk_keyboard:PERCENT_SIGN'          : 'percent',
    ':uk_keyboard:PERIOD'                : 'period',
    ':uk_keyboard:PLUS_SIGN'             : 'plus',
    ':uk_keyboard:QUESTION_MARK'         : 'question',
    ':uk_keyboard:RETURN'                : 'Return',
    ':uk_keyboard:SEMICOLON'             : 'semicolon',
    ':uk_keyboard:SLASH'                 : 'slash',
    ':uk_keyboard:SMALL_A'               : 'a',
    ':uk_keyboard:SMALL_B'               : 'b',
    ':uk_keyboard:SMALL_C'               : 'c',
    ':uk_keyboard:SMALL_D'               : 'd',
    ':uk_keyboard:SMALL_E'               : 'e',
    ':uk_keyboard:SMALL_F'               : 'f',
    ':uk_keyboard:SMALL_G'               : 'g',
    ':uk_keyboard:SMALL_H'               : 'h',
    ':uk_keyboard:SMALL_I'               : 'i',
    ':uk_keyboard:SMALL_J'               : 'j',
    ':uk_keyboard:SMALL_K'               : 'k',
    ':uk_keyboard:SMALL_L'               : 'l',
    ':uk_keyboard:SMALL_M'               : 'm',
    ':uk_keyboard:SMALL_N'               : 'n',
    ':uk_keyboard:SMALL_O'               : 'o',
    ':uk_keyboard:SMALL_P'               : 'p',
    ':uk_keyboard:SMALL_Q'               : 'q',
    ':uk_keyboard:SMALL_R'               : 'r',
    ':uk_keyboard:SMALL_S'               : 's',
    ':uk_keyboard:SMALL_T'               : 't',
    ':uk_keyboard:SMALL_U'               : 'u',
    ':uk_keyboard:SMALL_V'               : 'v',
    ':uk_keyboard:SMALL_W'               : 'w',
    ':uk_keyboard:SMALL_X'               : 'x',
    ':uk_keyboard:SMALL_Y'               : 'y',
    ':uk_keyboard:SMALL_Z'               : 'z',
    ':uk_keyboard:SPACE'                 : 'space',
    ':uk_keyboard:SQUARE_BRACKET_LEFT'   : 'bracketleft',
    ':uk_keyboard:SQUARE_BRACKET_RIGHT'  : 'bracketright',
    ':uk_keyboard:TAB'                   : 'Tab',
    ':uk_keyboard:VERTICAL_BAR'          : 'bar',
    '::0'                     : '0',
    '::1'                     : '1',
    '::2'                     : '2',
    '::3'                     : '3',
    '::4'                     : '4',
    '::5'                     : '5',
    '::6'                     : '6',
    '::7'                     : '7',
    '::8'                     : '8',
    '::9'                     : '9',
    '::MENU'                  : 'm',
    '::CURSOR_UP'             : 'Up',
    '::CURSOR_DOWN'           : 'Down',
    '::CURSOR_LEFT'           : 'Left',
    '::CURSOR_RIGHT'          : 'Right',
    '::OK'                    : 'Return',
    '::BACK'                  : 'Escape',
    '::VOLUME_UP'             : 'bracketright',
    '::VOLUME_DOWN'           : 'bracketleft',
    '::CHANNEL_UP'            : 'Page_Up',
    '::CHANNEL_DOWN'          : 'Page_Down',    
    '::CHANNEL_MUTE'          : 'backslash',    
    }

class ButtonHandler:
    xt = XTest()

    def send_button_press(self,code, output=None):

        global keycodes

        if code not in keycodes:
            raise ProcessingFailed
        
        self.xt.fakeKeyEvent(keycodes[code])
        
# This dictionary is keyed by the MythTV string categories
# and the elements are a tuple of a UC category id and a human 
# readable name
category_lookup = { 'Movie'              : ('mov','Movie'),
                    'News'               : ('new','News and Factual'),
                    'Entertainment'      : ('sho','Show/Game Show'),
                    'Sports'             : ('spo','Sport'),
                    'Kids'               : ('chi','Children\'s'),
                    'Music/Ballet/Dance' : ('ent','Entertainment'),
                    'Arts/Culture'       : ('new','News and Factual'),
                    'Social/Political/Economics' : ('new','News and Factual'),
                    'Education/Science/Factual' : ('edu','Educational'),
                    'Leisure/Hobbies'    : ('lif','Lifestyle'),
                    'Drama'              : ('dra','Drama'),
                    }

# This dictionary is the data for the Categories Resource
mythtv_categories = { '_gen' : { 'parent' : '',
                                 'name'   : 'Genres',
                                 'MYTHTV:children' : ['chi',
                                                      'sho',
                                                      'mov',
                                                      'edu',
                                                      'ent',
                                                      'spo',
                                                      'dra',
                                                      'lif',
                                                      'new',
                                                      ],
                                 },
                      'chi' : { 'name': "Children's", 
                                'parent': '_gen', 
                                'category-id': 'chi'},
                      'sho' : { 'name': 'Show/Game Show', 
                                'parent': '_gen', 
                                'category-id': 'sho'},
                      'mov' : { 'name': 'Movie', 
                                'parent': '_gen', 
                                'category-id': 'mov'},
                      'edu' : { 'name': 'Educational', 
                                'parent': '_gen', 
                                'category-id': 'edu'},
                      'ent' : { 'name': 'Entertainment', 
                                'parent': '_gen', 
                                'category-id': 'ent'},
                      'spo' : { 'name': 'Sport', 
                                'parent': '_gen', 
                                'category-id': 'spo'},
                      'dra' : { 'name': 'Drama', 
                                'parent': '_gen', 
                                'category-id': 'dra'},
                      'lif' : { 'name': 'Lifestyle', 
                                'parent': '_gen', 
                                'category-id': 'lif'},
                      'new' : { 'name': 'News and Factual', 
                                'parent': '_gen', 
                                'category-id': 'new'},
                      }
                      

valid_id_chars = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9','-','.','_','~')

def id_component(input):
    def shift(c):
        global valid_id_chars
        if c in valid_id_chars:
            return c
        return '%%%02x' % ord(c)

    return ''.join(map(shift,input))
                            

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


def parse_iso(input):
    match = re.match('(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.(\d+)){,1}',input)
    if not match:
        raise ValueError
    micro = 0
    if match.group(8) is not None:
        micro = int((match.group(8) + '000000')[:6])
    return datetime.datetime(int(match.group(1)),
                             int(match.group(2)),
                             int(match.group(3)),
                             int(match.group(4)),
                             int(match.group(5)),
                             int(match.group(6)),
                             micro)

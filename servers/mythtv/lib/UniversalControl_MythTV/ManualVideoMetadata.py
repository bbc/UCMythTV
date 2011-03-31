# MythTV Universal Control Server - Manual Video Metadata
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
This source file is used to specify manually hard coded metadata for stored
videos.

It provides a quick and easy way to test clients that try to access stored
videos by allowing a video file to be given fake metadata when it may not
actually contain any metadata itself that mythtv can itself extract.

The variable ManualVideoMetadata is a dictionary where the keys are the
filenames of video files, and the values are dictionaries containing the
metadata, following the UC API data model for content items.

  sid = source id
  cid = content id - eg. filename of the file is usually sufficient
  

"""

###
### not enabled by default - see end of this file
###

ManualVideoMetadata = {
    'my_video_file_that_needs_metadata.avi' : {                                     
        'sid' : "SG_2",
        'cid' : 'my_video_file_that_needs_metadata.avi',
        'title' : "My Home Videos",
        'synopsis' : "A programme I made about all kinds of things I like",
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
        'global-content-id' : 'crid://NOTACRID',
        'global-series-id'  : 'crid://NOTACRID',
        'interactive' : False,
        },
    }


###
### remove the following line to enable the metadata specified above
###
ManualVideoMetadata = {}

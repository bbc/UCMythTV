#!/usr/bin/python

# Main executable script for UC MythTV Server
# Copyright (C) 2011 British Broadcasting Corporation
#
# Contributors: See Contributors File
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; you may use version 2 of the license only
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
The main executable file of the example Universal Control Server for a
MythTV box.

For more details of this and the other files in this package see the README
in this directory and the comments in the code below.

This file implements almost nothing except for command-line parameter
parsing, specifying which configuration options are to be used, and linking
the MythTVUC library classes to the resource handlers from UCServer.
"""

if __name__ == "__main__":
    # Import material for the UCServer
    import UCServer
    from UCServer.ResourceHandlers import UCResourceHandler, resources

    # Import other code from this package
    from UniversalControl_MythTV import FeedbackHandler
    from UniversalControl_MythTV import AppHandler
    from UniversalControl_MythTV import MythTVUC
    from UniversalControl_MythTV.genName_and_UUID import uuid,name
    from UniversalControl_MythTV.PairingScreen import UniversalControl

    # Standard Python Imports
    import sys
    import time
    from optparse import OptionParser
    import datetime
    import re


    # Parse Commandline Parameters
    op = OptionParser()
    op.add_option("-p","--port", dest="port", type="int",    default=48875, 
                  help="Port number to serve on",   metavar="PORT")
    op.add_option("-b","--bind", dest="bind", type="string", default="",   
                  help="Address to serve from",     metavar="IP")
    op.add_option("-n","--name", dest="name", type="string", default=None, 
                  help="Name of Server",            metavar="NAME")
    op.add_option("-u","--uuid", dest="uuid", type="string", default=None, 
                  help="UUID of Server",            metavar="UUID")
    op.add_option("-L","--logo", dest="logo", type="string", default=None, 
                  help="file path for  a logo for the box", metavar="LOGO_HREF")
    op.add_option("-z","--zeroconf", dest="zeroconf_on", action="store_false", default=True, 
                  help="Turn off inbuilt mDNS/DNS-SD support")
    op.add_option("-a","--authentication", dest="auth_on", action="store_true", default=False, 
                  help="Turn on HTTP digest authentication")
    op.add_option("-l","--log-file", dest="log_filename", type="string", default=None,   
                  help="Filename for logging information",  metavar="filename")
    (options,args) = op.parse_args()


    #Check if there is currently a valid network address to use:
    while (options.bind == '' and 
           UCServer.currentipaddress() == '127.0.0.1'):
        print "Waiting for a valid network connection"
        time.sleep(5)


    #Create the server itself.
    port = options.port
    server = UCServer.UCServer(options.bind, 
                               options.port, 
                               options.zeroconf_on, 
                               name(), 
                               "Universal Control Server",
                               uuid(),
                               StandbyCallback=MythTVUC.mythtv_standby_callback,
                               options=['power',
                                        'time',
                                        'events',
                                        'sources',
                                        'source-lists',
                                        'outputs',
                                        'feedback',
                                        'remote',
                                        'acquisitions',
                                        'search',
                                        'storage',
                                        'images',
                                        'credentials',
                                        'categories',
                                        'apps',
                                        ],
                               log_filename=options.log_filename)

    #Inform the user of which toggleable parameters were selected
    timestring = datetime.datetime.utcnow().isoformat()
    server.log_message("\n"
                       "----------------------%s-\n"
                       "Server Starting up at %sZ\n"
                       "----------------------%s-\n"                       
                       "\n"
                       "Options:\n"
                       "[%s] Built-in mDNS/DNS-SD\n"
                       "[%s] HTTP Digest Authentication", 
                       '-'*(len(timestring)),
                       timestring,
                       '-'*(len(timestring)),
                       ('x' if options.zeroconf_on else ' '),
                       ('x' if options.auth_on     else ' '))


    #Initialise the MythTV interface
    MythTVUC.initialise(server, options.logo)

    #Set the correct data for the various resources
    server.set_resource_data('uc', {'resource' : 'uc', 
                                    'security' : False, 
                                    'name' : name(n=options.name), 
                                    'id' :   uuid(id=options.uuid),
                                    'version' : UCServer.__version__,
                                    'logo' : MythTVUC.mythtv_logo,
                                    })
    server.set_resource_data('uc/power', MythTVUC.mythtv_power)
    server.set_sources(MythTVUC.mythtv_sources)
    server.set_source_lists(MythTVUC.mythtv_source_lists)
    server.set_outputs(MythTVUC.mythtv_outputs)
    server.set_main_output('0')
    server.set_controls([ ':uk_keyboard',])
    server.set_button_handler(MythTVUC.mythtv_button_handler)
    server.set_resource_data('uc/acquisitions', MythTVUC.mythtv_acquisitions)
    server.set_acquirer(MythTVUC.mythtv_acquirer)
    server.set_content(MythTVUC.mythtv_programmes)
    server.set_resource_data('uc/storage', MythTVUC.mythtv_storage)
    server.set_resource_data('images', MythTVUC.mythtv_images)
    server.set_categories(MythTVUC.mythtv_categories)

    #Check the authentication settings.
    if options.auth_on:
        server.set_security_scheme(True)

    #Set up the Pairing Screen interface
    versioninfo = UCServer.__version__
    try:
        vifile=open("version_info")
    except:
        pass
    else:
        try:
            versioninfo = "%s@r%d" % (versioninfo, 
                                      int(re.search("Revision: (\d+)",vifile.read()).group(1)),)
        except:
            pass
        
    PairingScreen = UniversalControl.PairingScreen(server,options.bind,versioninfo=versioninfo,security=options.auth_on)
    server.add_pending_credentials_callback = PairingScreen.shouldStopDisplay


    #Add the feedback handling to the server
    feedback = FeedbackHandler.Feedback(server)

    #Add support for the apps resource
    apps = AppHandler.Apps(server)

    #Finally inform the user that the server has started, and start it.
    server.log_message('Started Server on %s port %s\n\n',server.address, server.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit()
    except:
        raise
 

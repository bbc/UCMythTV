#!/bin/bash

# Setup /opt/uc directory
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


OCTET=`/sbin/ifconfig | grep "inet addr:" | perl -ne 'print if not /127\.0\.0\.1/;' | perl -pe 's/.*addr:(\d+\.\d+\.\d+\.(\d+)).*/\2/'`

# Creating the /opt/uc directory
echo ""
echo ""
echo "----------------"
echo "CREATING /opt/uc"
echo "----------------"
echo ""
echo ""
mkdir -vp /opt/uc
chmod -v a+rwx /opt/uc
cp -v optuc/ucserver /opt/uc
cp -vn optuc/* /opt/uc
chmod -v -R a+rw /opt/uc
chmod -v a+x /opt/uc/ucserver

touch /opt/uc/UCServer.name
touch /opt/uc/UCServer.uuid
touch /opt/uc/notification_id.dat
echo "MythTV Server " $OCTET > /opt/uc/UCServer.name
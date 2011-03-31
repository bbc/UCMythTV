#!/bin/bash

# Script for acquiring MythTV source code
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


URL=git://github.com/MythTV/mythtv.git 
REVISION=ad3c81f086aafc32477163d7b40117aefac55d76


# Check if the source tree exists, and install it if it doesn't
echo ""
echo ""
echo "-----------------------------"
echo "CHECKING MYTHTV SOURCE EXISTS" 
echo "-----------------------------"
echo ""
echo ""
if [[ -d mythtv-source ]]
then
    echo "Using existing source directory. If this compile"
    echo "fails try deleting ./mythtv-source"
else
# Checkout the desired mythtv revision
    echo ""
    echo ""
    echo "--------------------------------------------"
    echo "CHECKING OUT MYTHTV " $REVISION
    echo "--------------------------------------------"
    echo ""
    echo ""
    git clone -b fixes/0.24 $URL mythtv-source || ( echo "  CHECKOUT FAILED! PLEASE INSTALL A COPY OF THE MYTHTV SOURCE CODE REVISION " $REVISION " IN mythtv-source"  && exit 1 )
    cd mythtv-source || exit 1
    git branch uc $REVISION || exit 1
    git checkout uc || exit 1
    cd ..
fi


# Check if it's already been patched
if [[ -f mythtv-source/UC_PATCHES_APPLIED ]]
then
    echo "Patches already applied, ignoring."
else
    # Patch it with the necessary patches in the patches subdirectory
    echo ""
    echo ""
    echo "-----------------------------------------"
    echo "     PATCHING TO ADD UC CAPABILITIES"
    echo "-----------------------------------------"
    echo ""
    echo ""

    cd mythtv-source || exit 1

    patch -l -f -p1 < ../patches/BrowserNetworkControl.patch || exit 1
    git add mythplugins/mythbrowser/mythbrowser/browserlauncher.cpp
    git add mythplugins/mythbrowser/mythbrowser/browserlauncher.h
    git commit -a -m "Network Control launch of Browser"

    patch -l -f -p1 < ../patches/GameNetworkControl.patch || exit 1
    git add mythplugins/mythgame/mythgame/gamelauncher.cpp 
    git add mythplugins/mythgame/mythgame/gamelauncher.h
    git commit -a -m "Network Control launch of Games"

    patch -l -f -p1 < ../patches/Query_Subtitles.patch || exit 1
    git commit -a -m "Network Control query of subtitles"
    patch -l -f -p1 < ../patches/Timestamp.patch || exit 1
    git commit -a -m "Network Control timestamp data"
    patch -l -f -p1 < ../patches/NoPopups.patch || exit 1
    git commit -a -m "Switch to remove Popups"

    patch -l -f -p1 < ../patches/configure_mythplugins_without_mythtv_installed.patch || exit 1
    git commit -a -m "MythBuntu Patch to allow out of tree compilation"

    cd .. || exit 1
    
    touch mythtv-source/UC_PATCHES_APPLIED || exit 1
fi


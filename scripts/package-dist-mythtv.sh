#!/bin/bash

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

# This script packages up the tarball containing the modified and compiled
# myth tv and other tarballs needed for the Universal Control server into a
# single tarball with an installation shell script

# It automatically runs the other packaging scripts needed to package up all
# the individual components, with the exception of the one for packaging up
# MythTV

if [ "$1" != "create" ]; then
	(
		echo "Creates tarball containing python UC Server module. Filepath+name of tarball"
		echo "returned via stdout"
		echo "Usage:"
		echo "   $0 create [<version-spec>]"
		echo ""
		echo "       <version-spec> ... optional. Actively try to build for a specific"
		echo "                          spec version. May cause abort if requirement cannot"
		echo "                          be fulfilled."
		echo ""
	) >&2
	exit 1;
fi

if [ $# -eq 2 ]; then
	VERSION_SPEC="$2"
else
	VERSION_SPEC=
fi


# determine the parent directory
THIS_DIR=`dirname "$0"` 1>&2
REPO_ROOT="$THIS_DIR/.."


function fail () {
	echo "Failed on $1 ..." >&2;
	exit 1;
}

# invoke packaging scripts for all sub packages. They all return the filename
# of the tarball they create via stdout.

AUTH="`$THIS_DIR/package-server-lib-py-ucauth.sh create $VERSION_SPEC`" || fail "uc auth library"
CORS="`$THIS_DIR/package-server-lib-py-cors.sh     create $VERSION_SPEC`" || fail "CORS library"
ZERO="`$THIS_DIR/package-server-lib-py-zeroconf.sh create $VERSION_SPEC`" || fail "zeroconf library"
UCSV="`$THIS_DIR/package-server-lib-py-ucserver.sh create $VERSION_SPEC`" || fail "uc server library"
XTST="`$THIS_DIR/package-server-lib-py-xtest.sh    create $VERSION_SPEC`" || fail "xtest library"
UCMT="`$THIS_DIR/package-server-mythtv.sh          create $VERSION_SPEC`" || fail "uc server for myth tv"

VERSION=`mktemp /tmp/uc-packaging.XXXXXXXXXX`
(
	echo "MythTV+UC Server distribution package.";
	echo "Created using: $0"
	if [ "$VERSION_SPEC" != "" ]; then echo "Specifically built to spec version: $$VERSION_SPEC"; fi        
	echo "";
	"$THIS_DIR/codebase_version_detect.sh" detect;
) > "$VERSION"

MYTH="$REPO_ROOT/servers/platform_extras/mythtv"

for F in "$MYTH/UCMythTV-MythTV-"*"-bin.tar.gz"; do
    MYTHTARBALL="$F"
done

PKGNAME=UC-mythtv-install-`date +%Y%m%d`

# assemble this package
"$THIS_DIR/_part-packager.sh" create "$PKGNAME" \
    "$AUTH" "$PKGNAME/" \
    "$CORS" "$PKGNAME/" \
    "$ZERO" "$PKGNAME/" \
    "$UCSV" "$PKGNAME/" \
    "$XTST" "$PKGNAME/" \
    "$UCMT" "$PKGNAME/" \
    "$MYTH/scripts/shutdown-mythtv.sh"           "$PKGNAME/scripts/" \
    "$MYTH/scripts/apt-get-dependencies.sh"      "$PKGNAME/scripts/" \
    "$MYTH/scripts/install-autostart-scripts.sh" "$PKGNAME/scripts/" \
    "$MYTH/scripts/setup_hdmi_audio.sh"          "$PKGNAME/scripts/" \
    "$MYTH/scripts/enable_network_control.sh"    "$PKGNAME/scripts/" \
    "$MYTH/autostart_scripts/MythTV Frontend.desktop"  "$PKGNAME/autostart_scripts/" \
    "$MYTH/autostart_scripts/UniversalControl.desktop" "$PKGNAME/autostart_scripts/" \
    "$MYTHTARBALL"              "$PKGNAME/" \
    "$VERSION"                  "$PKGNAME/version_info" \
    "$THIS_DIR/packaging-res/mythtv-setup.sh" "$PKGNAME/setup.sh"


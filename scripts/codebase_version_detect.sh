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

# This script attempts to detect and dump useful information about the
# revision of the codebase (if it is a subversion working copy)

if [ "$1" != "detect" ]; then
	(
		echo "Dumps to standard output information about the working copy (eg. revision number) and the current date."
		echo "The idea being that this info can be bundled into a file included in a distribution package."
		echo ""
		echo "Usage:"
		echo "   $0 detect"
		echo ""
	) >&2
	exit 1;
fi

# determine the parent directory
THIS_DIR=`dirname "$0"` 1>&2
REPO_ROOT="$THIS_DIR/.."


cd $REPO_ROOT;

echo "Generated on: `date`"
echo "By: `whoami` on `hostname`"
echo ""

svn info > /dev/null 2>&1
if [ $? -eq 0 ]; then
	echo "From repository working copy:"
	echo "    `svn info | grep '^URL:'`"
	echo "    `svn info | grep '^Revision:'`"
	echo ""
	
	if [ `svn status | wc -l` -gt 0 ]; then
		echo "Working copy had following uncommitted changes and unversioned files:"
		svn status
	fi
else
    git svn info > /dev/null 2>&1
    if [ $? -eq 0 ]; then
	echo "From repository working copy:"
	echo "    `git svn info | grep '^URL:'`"
	echo "    `git svn info | grep '^Revision:'`"
	echo ""
	
	if [ `git status | wc -l` -gt 0 ]; then
		echo "Working copy had following uncommitted changes and unversioned files:"
		git status
	fi
    else
	echo "Not generated from a repository working copy."
    fi
fi

echo ""
echo "----"


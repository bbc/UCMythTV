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

# This script packages up the MythTV Universal Control server code into a
# tarball.  This does not include the libraries it relies on (including the
# UC server library).  See separate packaging scripts for those.

if [ "$1" != "create" ]; then
	(
		echo "Creates tarball containing python MythTV UC Server. Filepath+name of tarball returned via stdout"
		echo "Usage:"
		echo "   $0 create [<version-spec>]"
		echo ""
	) >&2
	exit 1;
fi

# determine the parent directory
THIS_DIR="$( cd "$( dirname "$0" )" && pwd )"
REPO_ROOT="$THIS_DIR/.."

CODE_ROOT="$REPO_ROOT/servers/mythtv"
export PYTHONPATH=$REPO_ROOT/servers/lib/python/UCAuthenticationServer/:$REPO_ROOT/servers/lib/python/UCServer/:$REPO_ROOT/servers/lib/python/Zeroconf/

if [ $# -ge 2 ]; then
	$THIS_DIR/uc_version_check.sh "$CODE_ROOT" "$2" > /dev/null || exit 1;
fi


(
	cd "$CODE_ROOT"
	rm -rf dist build MANIFEST
	python setup.py sdist
) >&2

ls -1 "$CODE_ROOT"/dist/*.tar.gz



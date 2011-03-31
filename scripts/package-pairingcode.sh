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

# this script packages up the Universal Control API Pairing code
# generating/decoding utility into a tarball.

if [ "$1" != "create" ]; then
	(
		echo "Creates tarball containing pairing code generator/decoder tool. Filepath+name of tarball returned via stdout"
		echo "Usage:"
		echo "   $0 create"
		echo ""
	) >&2
	exit 1;
fi

# determine the parent directory
THIS_DIR=`dirname "$0"` 1>&2
REPO_ROOT="$THIS_DIR/.."

"$THIS_DIR/_part-packager.sh" create "pairingcode" "$REPO_ROOT/utilities/PairingCode.py" "/"


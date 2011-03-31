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

# Helper script for checking the version of the UC spec that a given library
# or other component complies with.  It does the check by looking at the
# UC_VERSION file present in the directory in question.

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
	(
		echo "UC_VERSION checker. Reports and/or checks the UC-spec-version asserted for the code in the specified directory."
		echo ""
		echo "Usage:"
		echo ""
		echo "    $0 <code-directory>"
		echo "    $0 <code-directory> <version-spec>"
		echo ""
		echo "Outputs detected UC spec version to std out."
		echo "Outputs error to stderr if <version-spec> supplied does not match the one found."
		echo ""
		echo "Exit status:"
		echo "    non-zero if any of:"
		echo "      * no UC-VERSION information file in the specified directory"
		echo "      * 'version-spec' argument supplied, but does not match"
		echo "        what is in the UC-VERSION info in the specified dir."
		echo "    else zero."
		echo ""
		echo "Arguments:"
		echo ""
		echo "    <code-directory> ... dir for the relevant component of the"
		echo "                         project, and containing a UC_VERSION file"
		echo ""
		echo "    <version-spec> ... optional. UC_VERSION will be checked to"
		echo "                       see if it matches (string match) this."
		echo ""
	) 1>&2;
	exit -1;
		
fi

UC_VERSION_FILE="$1/UC_VERSION"

DETECTED_VERSIONS=`cat "$UC_VERSION_FILE" 2>/dev/null` || ( echo "File not found: $UC_VERSION_FILE" 1>&2; exit 1; )

for VERSION in $DETECTED_VERSIONS; do
	echo $VERSION;
done

if [ $# -eq 2 ]; then
	VERSION_SPEC="$2"
	for VERSION in $DETECTED_VERSIONS; do
		if [ "$VERSION" == "$VERSION_SPEC" ]; then
			exit 0;
		fi;
	done;
	echo "Support for required version $VERSION_SPEC not found" 1>&2
	exit 1;
else
	exit 0;
fi
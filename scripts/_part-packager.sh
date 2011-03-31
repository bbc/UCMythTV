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

# This is a packaging script used by several of the other packaging scripts
# to build tarballs, with certain files in certain subdirectories


if [ "$1" != "create" ]; then
	(
		echo "Generic packaging tarballer. Filepath+name of tarball returned via stdout"
		echo "Makes it easy to assemble a tarball containing stuff from multiple locations,"
		echo "and lets you specify a new directory name and/or filename for each thing."
		echo ""
		echo "Usage:"
		echo "   $0 create <packaging-name> <source> <dest> <source> <dest> ..."
		echo ""
		echo "   <packaging-name> - forms part of the name of the final tarball produced"
		echo ""
		echo "   <source> - absolute path to file/directory to be put in the tarball."
		echo ""
		echo "   <dest> - path and/or filename, to be given to the <source>. When the"
		echo "            tarball is assembled. '/' is the root of the tarball."
		echo "            Use a trailing '/' to hint that <dest> is a directory name."
		echo ""
		echo "Examples:"
		echo ""
		echo "  $0 create myapp /home/$USER/trunk/client/foo/myapp myapp/"
		echo ""
		echo "   ... creates a myapp.tar.gz where the files in /home/$USER/trunk/client/foo/myapp/"
		echo "       are in a directory named 'myapp' in the tarball"
		echo ""
		echo "  $0 create myapp /home/$USER/trunk/client/foo/myapp/x86 myapp/intel /home/$USER/trunk/client/foo/myapp/arm myapp/arm"
		echo ""
		echo "   ... creates a myapp.tar.gz where the files in /home/$USER/trunk/client/foo/myapp/x86"
		echo "       are in a directory named 'myapp/intel' in the tarball and those in ....../arm are"
		echo "       in a directory named 'myapp/arm' in the tarball."
		echo ""
		echo ""
	) >&2
	exit 1;
fi

shift
NAME="$1"
shift



# determine the parent directory
THIS_DIR=`dirname "$0"` 1>&2
ROOT="$THIS_DIR/.."

# make dist dir
mkdir -p "$ROOT/dist" 1>&2

# create tarball assembly temp dir
BUILD_DIR=`mktemp -d /tmp/uc-packaging.XXXXXXXXXX` 1>&2

# detect whether using GNU tar or BSD tar, and whether it is tar 1.19 or later
# GNU tar 1.19 onwards supports --exclude-vcs but earlier versions and BSD tar does not, so we need to do manual equivalent

# Extra fun: syntax is different between GNU tar and BSD tar for GNU tar prior to 1.19 - one requires '--exclude ARG' and the
# other uses'--exclude=ARG'
if [ `tar --version | grep '(GNU tar)' | wc -l` -gt 0 ]; then
	USING_GNUTAR=true;
else
	USING_GNUTAR=false;
fi

USING_NEW_GNUTAR=false;
if $USING_GNUTAR; then
	if ! [ "tar (GNU tar) 1.19" \> "`tar --version | grep '(GNU tar)'`" ]; then
		USING_NEW_GNUTAR=true;
	fi
fi

if $USING_GNUTAR && $USING_NEW_GNUTAR; then
	TAR_EXCLUDES="\
                --exclude-vcs \
                --exclude *.uuid \
                --exclude *.name \
                --exclude *~ \
                --exclude *.pyc \
        "
else
	# This list is derived from the exclusions listed under the documentation for
	# "--exclude-vcs" at http://www.gnu.org/software/tar/manual/html_section/exclude.html#SEC108
	TAR_EXCLUDES="\
		--exclude CVS/  \
		--exclude RCS/  \
		--exclude SCCS/  \
		--exclude .git/  \
		--exclude .gitignore  \
		--exclude .cvsignore  \
		--exclude .svn/  \
		--exclude .arch-ids/  \
		--exclude {arch}/  \
		--exclude =RELEASE-ID  \
		--exclude =meta-update  \
		--exclude =update  \
		--exclude .bzr  \
		--exclude .bzrignore  \
		--exclude .bzrtags  \
		--exclude .hg  \
		--exclude .hgignore  \
		--exclude .hgrags  \
		--exclude _darcs  \
                --exclude *.uuid \
                --exclude *.name \
                --exclude *~ \
                --exclude *.pyc \
	"
fi

# old tar needs '=' between '--exclude' and its argument
if $USING_GNUTAR && ! $USING_NEW_GNUTAR; then
	# replace '--exclude ' with '--exclude='
	TAR_EXCLUDES=`echo $TAR_EXCLUDES | sed 's/--exclude \+/--exclude=/g'`
fi



# all output to stderr to not interfere with echoing final output filename to stdout
(

	# go through list of source-dest pairs, copying files to the directory where we're building
	# up the tarball contents
	while [ $# -ge 2 ]; do

		SRC="$1"
		DST="$2"

		if [ -d "$SRC" ]; then
			# source is a dir, so dest must be too, make sure it exists before copying
			mkdir -p "$BUILD_DIR/$DST"
			cp -R "$SRC/"* "$BUILD_DIR/$DST"
		else 
			# source is a file. if dest is a dir, ensure it exists before copying
			if [ "${DST: -1}" == "/" ]; then
				mkdir -p "$BUILD_DIR/$DST"
			else
				# dest is not a dir, so make sure the dir path of it exists before copying
				D=`dirname $DST`
				mkdir -p "$BUILD_DIR/$D"
			fi
			cp "$SRC" "$BUILD_DIR/$DST"
		fi


		# ready for next loop
		shift; shift;
	done;	

	# build a list of the files/dirs in the root of the tar
	FILE_LIST_FILE=`mktemp /tmp/uc-packaging.XXXXXXXXXX`
	ls -1 "$BUILD_DIR" > $FILE_LIST_FILE	

	# create the tarball, with paths of files within it rooted at $BUILD_DIR
	tar -czf "$ROOT/dist/$NAME.tar.gz" $TAR_EXCLUDES --directory "$BUILD_DIR" --files-from="$FILE_LIST_FILE"

	# clean up
	rm "$FILE_LIST_FILE"
	rm -rf "$BUILD_DIR"
) 1>&2  

echo "$ROOT/dist/$NAME.tar.gz"


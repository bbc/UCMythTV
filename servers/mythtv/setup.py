#!/usr/bin/python

# distutils setup script for MythTV UC Server
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


from distutils.core import setup

setup(name='ucserver-mythtv',
      version='0.6.0',
      description='A UC Server for mythtv',
      author='James P. Barrett',
      author_email='james.barrett@bbc.co.uk',
      url='http://www.bbc.co.uk/rd',
      package_dir={'' : 'lib' },
      packages=['UniversalControl_MythTV',],
      scripts=['scripts/ucserver_mythtv.py',],
      )

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

# This script is used to unpack and install a mythtv+UC server packaged tarball

if [ "`whoami`" = "root" ]; then
  echo "Error - this script must not be run as root."
  exit 1
fi

OCTET=`/sbin/ifconfig | grep "inet addr:" | perl -ne 'print if not /127\.0\.0\.1/;' | perl -pe 's/.*addr:(\d+\.\d+\.\d+\.(\d+)).*/\2/'`

sudo ./scripts/shutdown-mythtv.sh
sudo ./scripts/apt-get-dependencies.sh

SETUP_DIR=`pwd`

cd /
sudo tar -xvzpf "$SETUP_DIR/UCMythTV-MythTV-"*"-bin.tar.gz"
cd $SETUP_DIR

#./scripts/install-autostart-scripts.sh

tar -xvzpf UCAuthenticationServer-*.tar.gz
cd UCAuthenticationServer-*/
sudo python setup.py install
cd ..

tar -xvzpf BasicCORSServer-*.tar.gz
cd BasicCORSServer-*/
sudo python setup.py install
cd ..

tar -xvzpf Zeroconf-*.tar.gz
cd Zeroconf-*/
sudo python setup.py install
cd ..

tar -xvzpf xtest-*.tar.gz
cd xtest-*/
sudo python setup.py install
cd ..

tar -xvzpf UCServer-*.tar.gz
cd UCServer-*/
sudo python setup.py install
cd ..

tar -xvzpf ucserver-mythtv-*.tar.gz
cd ucserver-mythtv-*/
sudo python setup.py install
cd ..

sudo start mysql
sudo start mythtv-backend

MYSQLPWD=`grep DBPassword ~/.mythtv/mysql.txt | perl -pe "s/DBPassword=(.+)/\1/"`
if [ "`echo 'SELECT data FROM settings WHERE value="DBSchemaVer"' | mysql --user=mythtv --password=$MYSQLPWD mythconverg | grep -c 1264`" = "0" ]
then

    echo " "
    echo "---------------------------------------------------------"
    echo "---------------------------------------------------------"
    echo "In a moment, the MythFrontend will be started."
    echo ""
    echo "When asked: confirm (depite any warnings) that you do"
    echo "want to upgrade the database."
    echo ""
    echo "Then press ESC and choose to quit mythtv."
    echo " "
    echo "... Press ENTER/RETURN to begin this step ..."
    read

    mythfrontend -u
fi

./scripts/enable_network_control.sh

sudo ./scripts/install-autostart-scripts.sh 

sudo echo "MythTVBox-"$OCTET > /opt/uc/UCServer.name

sudo cp ./version_info /opt/uc/version_info

sudo chown -R mythtv:mythtv /var/lib/mythtv

echo "Press ENTER/RETURN to reboot and complete setup"
read

sudo reboot

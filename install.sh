#!/bin/sh

OUTPUT=$(cat /etc/*release)
if  echo $OUTPUT | grep -q "CentOS Linux 7" ; then
        echo "Checking and installing curl and wget"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
                SERVER_OS="CentOS"
elif echo $OUTPUT | grep -q "CentOS Linux 8" ; then
        echo -e "\nDetecting Centos 8...\n"
        SERVER_OS="CentOS8"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
elif echo $OUTPUT | grep -q "AlmaLinux 8" ; then
        echo -e "\nDetecting AlmaLinux 8...\n"
        SERVER_OS="CentOS8"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
elif echo $OUTPUT | grep -q "AlmaLinux 9" ; then
        echo -e "\nDetecting AlmaLinux 9...\n"
        SERVER_OS="CentOS8"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
elif echo $OUTPUT | grep -q "CloudLinux 7" ; then
        echo "Checking and installing curl and wget"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
                SERVER_OS="CloudLinux"
elif echo $OUTPUT | grep -q "CloudLinux 8" ; then
        echo "Checking and installing curl and wget"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
                SERVER_OS="CloudLinux"
elif echo $OUTPUT | grep -q "Ubuntu 18.04" ; then
apt install -y -qq wget curl
                SERVER_OS="Ubuntu"
elif echo $OUTPUT | grep -q "Ubuntu 20.04" ; then
apt install -y -qq wget curl
                SERVER_OS="Ubuntu"
elif echo $OUTPUT | grep -q "Ubuntu 22.04" ; then
apt install -y -qq wget curl
                SERVER_OS="Ubuntu"
elif echo $OUTPUT | grep -q "openEuler 20.03" ; then
        echo -e "\nDetecting openEuler 20.03...\n"
        SERVER_OS="openEuler"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
elif echo $OUTPUT | grep -q "openEuler 22.03" ; then
        echo -e "\nDetecting openEuler 22.03...\n"
        SERVER_OS="openEuler"
yum install curl wget -y 1> /dev/null
yum update curl wget ca-certificates -y 1> /dev/null
else

                echo -e "\nUnable to detect your OS...\n"
                echo -e "\nCyberPanel is supported on Ubuntu 18.04, Ubuntu 20.04 Ubuntu 22.04, AlmaLinux 8, AlmaLinux 9 and CloudLinux 7.x...\n"
                exit 1
fi

rm -f cyberpanel.sh
rm -f install.tar.gz
curl --silent -o cyberpanel.sh "https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/cyberpanel.sh" 2>/dev/null
chmod +x cyberpanel.sh
./cyberpanel.sh $@
#!/bin/sh

BRANCH_NAME=v$(curl -s https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/version.txt | sed -e 's|{"version":"||g' -e 's|","build":|.|g'| sed 's:}*$::')

rm -f /usr/local/autoCyberpanel_upgrade.sh
wget -O /usr/local/autoCyberpanel_upgrade.sh https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/$BRANCH_NAME/autoCyberpanel_upgrade.sh 2>/dev/null
chmod 700 /usr/local/autoCyberpanel_upgrade.sh
/usr/local/autoCyberpanel_upgrade.sh
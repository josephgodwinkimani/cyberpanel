#!/bin/sh

rm -f /usr/local/cyberpanel_upgrade.sh
wget -O /usr/local/cyberpanel_upgrade.sh https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/25072021/cyberpanel_upgrade.sh 2>/dev/null
chmod 700 /usr/local/cyberpanel_upgrade.sh
/usr/local/cyberpanel_upgrade.sh

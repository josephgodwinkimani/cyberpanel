#!/usr/local/CyberCP/bin/python
import sys

sys.path.append('/usr/local/CyberCP')
from plogical import CyberCPLogFileWriter as logging
import subprocess
import shlex
import argparse
import os
import threading as multi
from plogical.processUtilities import ProcessUtilities


class CSF(multi.Thread):
    installLogPath = "/home/cyberpanel/csfInstallLog"
    csfURL = 'https://download.configserver.com/csf.tgz'

    def __init__(self, installApp, extraArgs):
        multi.Thread.__init__(self)
        self.installApp = installApp
        self.extraArgs = extraArgs

    def run(self):
        try:
            if self.installApp == 'installCSF':
                self.installCSF()
            elif self.installApp == 'removeCSF':
                self.removeCSF()
        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + ' [CSF.run]')

    @staticmethod
    def installCSF():
        try:
            ##

            logging.CyberCPLogFileWriter.statusWriter(CSF.installLogPath, 'Downloading CSF..\n', 1)

            command = 'wget ' + CSF.csfURL
            ProcessUtilities.normalExecutioner(command)

            ##

            logging.CyberCPLogFileWriter.statusWriter(CSF.installLogPath, 'Extracting CSF..\n', 1)

            command = 'tar -xzf csf.tgz'
            ProcessUtilities.normalExecutioner(command)

            ##

            logging.CyberCPLogFileWriter.statusWriter(CSF.installLogPath, 'Installing CSF..\n', 1)

            os.chdir('csf')

            ### manually update csf views.py because it does not load CyberPanel properly in default configurations

            content = '''
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import os.path
import sys
import django

sys.path.append('/usr/local/CyberCP')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CyberCP.settings")
django.setup()
from plogical.acl import ACLManager

from plogical.processUtilities import ProcessUtilities
from django.views.decorators.csrf import csrf_exempt
import tempfile
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from plogical.httpProc import httpProc

def configservercsf(request):
    proc = httpProc(request, 'configservercsf/index.html',
                             None, 'admin')
    return proc.render()

@csrf_exempt
@xframe_options_exempt
def configservercsfiframe(request):
    userID = request.session['userID']
    currentACL = ACLManager.loadedACL(userID)

    if currentACL['admin'] == 1:
        pass
    else:
        return ACLManager.loadError()

    if request.method == 'GET':
        qs = request.GET.urlencode()
    elif request.method == 'POST':
        qs = request.POST.urlencode()

    try:
        tmp = tempfile.NamedTemporaryFile(mode = "w", delete=False)
        tmp.write(qs)
        tmp.close()
        command = "/usr/local/csf/bin/cyberpanel.pl '" + tmp.name + "'"

        try:
            output = ProcessUtilities.outputExecutioner(command)
        except:
            output = "Output Error from csf UI script"

        os.unlink(tmp.name)
    except:
        output = "Unable to create csf UI temp file"

    return HttpResponse(output)
'''

            WriteToFile = open('cyberpanel/configservercsf/views.py', 'w')
            WriteToFile.write(content)
            WriteToFile.close()

            ### now update content of signals.py
            WriteToFile = open('cyberpanel/configservercsf/signals.py', 'w')
            WriteToFile.close()

            ### now update content of apps.py

            content = '''
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig

class configservercsfConfig(AppConfig):
    name = 'configservercsf'
'''

            WriteToFile = open('cyberpanel/configservercsf/apps.py', 'w')
            WriteToFile.write(content)
            WriteToFile.close()


            ### now update content of urls.py

            content = '''
from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.configservercsf, name='configservercsf'),
    path('iframe/', views.configservercsfiframe, name='configservercsfiframe'),
]
'''

            WriteToFile = open('cyberpanel/configservercsf/urls.py', 'w')
            WriteToFile.write(content)
            WriteToFile.close()

            ### content of the actual install file

            content = '''
#!/bin/sh
###############################################################################
# Copyright 2006-2018, Way to the Web Limited
# URL: http://www.configserver.com
# Email: sales@waytotheweb.com
###############################################################################

umask 0177

if [ -e "/usr/local/cpanel/version" ]; then
	echo "Running csf cPanel installer"
	echo
	sh install.cpanel.sh
	exit 0
elif [ -e "/usr/local/directadmin/directadmin" ]; then
	echo "Running csf DirectAdmin installer"
	echo
	sh install.directadmin.sh
	exit 0
fi

echo "Installing csf and lfd"
echo

echo "Check we're running as root"
if [ ! `id -u` = 0 ]; then
	echo
	echo "FAILED: You have to be logged in as root (UID:0) to install csf"
	exit
fi
echo

mkdir -v -m 0600 /etc/csf
cp -avf install.txt /etc/csf/

echo "Checking Perl modules..."
chmod 700 os.pl
RETURN=`./os.pl`
if [ "$RETURN" = 1 ]; then
	echo
	echo "FAILED: You MUST install the missing perl modules above before you can install csf. See /etc/csf/install.txt for installation details."
    echo
	exit
else
    echo "...Perl modules OK"
    echo
fi

mkdir -v -m 0600 /etc/csf
mkdir -v -m 0600 /var/lib/csf
mkdir -v -m 0600 /var/lib/csf/backup
mkdir -v -m 0600 /var/lib/csf/Geo
mkdir -v -m 0600 /var/lib/csf/ui
mkdir -v -m 0600 /var/lib/csf/stats
mkdir -v -m 0600 /var/lib/csf/lock
mkdir -v -m 0600 /var/lib/csf/webmin
mkdir -v -m 0600 /var/lib/csf/zone
mkdir -v -m 0600 /usr/local/csf
mkdir -v -m 0600 /usr/local/csf/bin
mkdir -v -m 0600 /usr/local/csf/lib
mkdir -v -m 0600 /usr/local/csf/tpl

if [ -e "/etc/csf/alert.txt" ]; then
	sh migratedata.sh
fi

if [ ! -e "/etc/csf/csf.conf" ]; then
	cp -avf csf.cyberpanel.conf /etc/csf/csf.conf
fi

if [ ! -d /var/lib/csf ]; then
	mkdir -v -p -m 0600 /var/lib/csf
fi
if [ ! -d /usr/local/csf/lib ]; then
	mkdir -v -p -m 0600 /usr/local/csf/lib
fi
if [ ! -d /usr/local/csf/bin ]; then
	mkdir -v -p -m 0600 /usr/local/csf/bin
fi
if [ ! -d /usr/local/csf/tpl ]; then
	mkdir -v -p -m 0600 /usr/local/csf/tpl
fi

if [ ! -e "/etc/csf/csf.allow" ]; then
	cp -avf csf.cyberpanel.allow /etc/csf/csf.allow
fi
if [ ! -e "/etc/csf/csf.deny" ]; then
	cp -avf csf.deny /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.redirect" ]; then
	cp -avf csf.redirect /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.resellers" ]; then
	cp -avf csf.resellers /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.dirwatch" ]; then
	cp -avf csf.dirwatch /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.syslogs" ]; then
	cp -avf csf.syslogs /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.logfiles" ]; then
	cp -avf csf.logfiles /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.logignore" ]; then
	cp -avf csf.logignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.blocklists" ]; then
	cp -avf csf.blocklists /etc/csf/.
else
	cp -avf csf.blocklists /etc/csf/csf.blocklists.new
fi
if [ ! -e "/etc/csf/csf.ignore" ]; then
	cp -avf csf.cyberpanel.ignore /etc/csf/csf.ignore
fi
if [ ! -e "/etc/csf/csf.pignore" ]; then
	cp -avf csf.cyberpanel.pignore /etc/csf/csf.pignore
fi
if [ ! -e "/etc/csf/csf.rignore" ]; then
	cp -avf csf.rignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.fignore" ]; then
	cp -avf csf.fignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.signore" ]; then
	cp -avf csf.signore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.suignore" ]; then
	cp -avf csf.suignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.uidignore" ]; then
	cp -avf csf.uidignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.mignore" ]; then
	cp -avf csf.mignore /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.sips" ]; then
	cp -avf csf.sips /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.dyndns" ]; then
	cp -avf csf.dyndns /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.syslogusers" ]; then
	cp -avf csf.syslogusers /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.smtpauth" ]; then
	cp -avf csf.smtpauth /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.rblconf" ]; then
	cp -avf csf.rblconf /etc/csf/.
fi
if [ ! -e "/etc/csf/csf.cloudflare" ]; then
	cp -avf csf.cloudflare /etc/csf/.
fi

if [ ! -e "/usr/local/csf/tpl/alert.txt" ]; then
	cp -avf alert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/reselleralert.txt" ]; then
	cp -avf reselleralert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/logalert.txt" ]; then
	cp -avf logalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/logfloodalert.txt" ]; then
	cp -avf logfloodalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/syslogalert.txt" ]; then
	cp -avf syslogalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/integrityalert.txt" ]; then
	cp -avf integrityalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/exploitalert.txt" ]; then
	cp -avf exploitalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/queuealert.txt" ]; then
	cp -avf queuealert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/modsecipdbalert.txt" ]; then
	cp -avf modsecipdbalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/tracking.txt" ]; then
	cp -avf tracking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/connectiontracking.txt" ]; then
	cp -avf connectiontracking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/processtracking.txt" ]; then
	cp -avf processtracking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/accounttracking.txt" ]; then
	cp -avf accounttracking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/usertracking.txt" ]; then
	cp -avf usertracking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/sshalert.txt" ]; then
	cp -avf sshalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/webminalert.txt" ]; then
	cp -avf webminalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/sualert.txt" ]; then
	cp -avf sualert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/sudoalert.txt" ]; then
	cp -avf sudoalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/consolealert.txt" ]; then
	cp -avf consolealert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/uialert.txt" ]; then
	cp -avf uialert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/cpanelalert.txt" ]; then
	cp -avf cpanelalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/scriptalert.txt" ]; then
	cp -avf scriptalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/relayalert.txt" ]; then
	cp -avf relayalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/filealert.txt" ]; then
	cp -avf filealert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/watchalert.txt" ]; then
	cp -avf watchalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/loadalert.txt" ]; then
	cp -avf loadalert.txt /usr/local/csf/tpl/.
else
	cp -avf loadalert.txt /usr/local/csf/tpl/loadalert.txt.new
fi
if [ ! -e "/usr/local/csf/tpl/resalert.txt" ]; then
	cp -avf resalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/portscan.txt" ]; then
	cp -avf portscan.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/uidscan.txt" ]; then
	cp -avf uidscan.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/permblock.txt" ]; then
	cp -avf permblock.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/netblock.txt" ]; then
	cp -avf netblock.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/portknocking.txt" ]; then
	cp -avf portknocking.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/forkbombalert.txt" ]; then
	cp -avf forkbombalert.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/recaptcha.txt" ]; then
	cp -avf recaptcha.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/apache.main.txt" ]; then
	cp -avf apache.main.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/apache.http.txt" ]; then
	cp -avf apache.http.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/apache.https.txt" ]; then
	cp -avf apache.https.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/litespeed.main.txt" ]; then
	cp -avf litespeed.main.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/litespeed.http.txt" ]; then
	cp -avf litespeed.http.txt /usr/local/csf/tpl/.
fi
if [ ! -e "/usr/local/csf/tpl/litespeed.https.txt" ]; then
	cp -avf litespeed.https.txt /usr/local/csf/tpl/.
fi
cp -avf x-arf.txt /usr/local/csf/tpl/.

if [ ! -e "/usr/local/csf/bin/regex.custom.pm" ]; then
	cp -avf regex.custom.pm /usr/local/csf/bin/.
fi
if [ ! -e "/usr/local/csf/bin/pt_deleted_action.pl" ]; then
	cp -avf pt_deleted_action.pl /usr/local/csf/bin/.
fi
if [ ! -e "/etc/csf/messenger" ]; then
	cp -avf messenger /etc/csf/.
fi
if [ ! -e "/etc/csf/messenger/index.recaptcha.html" ]; then
	cp -avf messenger/index.recaptcha.html /etc/csf/messenger/.
fi
if [ ! -e "/etc/csf/ui" ]; then
	cp -avf ui /etc/csf/.
fi
if [ -e "/etc/cron.d/csfcron.sh" ]; then
	mv -fv /etc/cron.d/csfcron.sh /etc/cron.d/csf-cron
fi
if [ ! -e "/etc/cron.d/csf-cron" ]; then
	cp -avf csfcron.sh /etc/cron.d/csf-cron
fi
if [ -e "/etc/cron.d/lfdcron.sh" ]; then
	mv -fv /etc/cron.d/lfdcron.sh /etc/cron.d/lfd-cron
fi
if [ ! -e "/etc/cron.d/lfd-cron" ]; then
	cp -avf lfdcron.sh /etc/cron.d/lfd-cron
fi
sed -i "s%/etc/init.d/lfd restart%/usr/sbin/csf --lfd restart%" /etc/cron.d/lfd-cron
if [ -e "/usr/local/csf/bin/servercheck.pm" ]; then
	rm -f /usr/local/csf/bin/servercheck.pm
fi
if [ -e "/etc/csf/cseui.pl" ]; then
	rm -f /etc/csf/cseui.pl
fi
if [ -e "/etc/csf/csfui.pl" ]; then
	rm -f /etc/csf/csfui.pl
fi
if [ -e "/etc/csf/csfuir.pl" ]; then
	rm -f /etc/csf/csfuir.pl
fi
if [ -e "/usr/local/csf/bin/cseui.pl" ]; then
	rm -f /usr/local/csf/bin/cseui.pl
fi
if [ -e "/usr/local/csf/bin/csfui.pl" ]; then
	rm -f /usr/local/csf/bin/csfui.pl
fi
if [ -e "/usr/local/csf/bin/csfuir.pl" ]; then
	rm -f /usr/local/csf/bin/csfuir.pl
fi
if [ -e "/usr/local/csf/bin/regex.pm" ]; then
	rm -f /usr/local/csf/bin/regex.pm
fi

OLDVERSION=0
if [ -e "/etc/csf/version.txt" ]; then
    OLDVERSION=`head -n 1 /etc/csf/version.txt`
fi

rm -f /etc/csf/csf.pl /usr/sbin/csf /etc/csf/lfd.pl /usr/sbin/lfd
chmod 700 csf.pl lfd.pl
cp -avf csf.pl /usr/sbin/csf
cp -avf lfd.pl /usr/sbin/lfd
chmod 700 /usr/sbin/csf /usr/sbin/lfd
ln -svf /usr/sbin/csf /etc/csf/csf.pl
ln -svf /usr/sbin/lfd /etc/csf/lfd.pl
ln -svf /usr/local/csf/bin/csftest.pl /etc/csf/
ln -svf /usr/local/csf/bin/pt_deleted_action.pl /etc/csf/
ln -svf /usr/local/csf/bin/remove_apf_bfd.sh /etc/csf/
ln -svf /usr/local/csf/bin/uninstall.sh /etc/csf/
ln -svf /usr/local/csf/bin/regex.custom.pm /etc/csf/
ln -svf /usr/local/csf/lib/webmin /etc/csf/
if [ ! -e "/etc/csf/alerts" ]; then
    ln -svf /usr/local/csf/tpl /etc/csf/alerts
fi
chcon -h system_u:object_r:bin_t:s0 /usr/sbin/lfd
chcon -h system_u:object_r:bin_t:s0 /usr/sbin/csf

mkdir webmin/csf/images
mkdir ui/images
mkdir da/images
mkdir interworx/images

cp -avf csf/* webmin/csf/images/
cp -avf csf/* ui/images/
cp -avf csf/* da/images/
cp -avf csf/* interworx/images/

cp -avf messenger/*.php /etc/csf/messenger/
cp -avf uninstall.cyberpanel.sh /usr/local/csf/bin/uninstall.sh
cp -avf csftest.pl /usr/local/csf/bin/
cp -avf remove_apf_bfd.sh /usr/local/csf/bin/
cp -avf readme.txt /etc/csf/
cp -avf sanity.txt /usr/local/csf/lib/
cp -avf csf.rbls /usr/local/csf/lib/
cp -avf restricted.txt /usr/local/csf/lib/
cp -avf changelog.txt /etc/csf/
cp -avf downloadservers /etc/csf/
cp -avf install.txt /etc/csf/
cp -avf version.txt /etc/csf/
cp -avf license.txt /etc/csf/
cp -avf webmin /usr/local/csf/lib/
cp -avf ConfigServer /usr/local/csf/lib/
cp -avf Net /usr/local/csf/lib/
cp -avf Geo /usr/local/csf/lib/
cp -avf Crypt /usr/local/csf/lib/
cp -avf HTTP /usr/local/csf/lib/
cp -avf JSON /usr/local/csf/lib/
cp -avf version/* /usr/local/csf/lib/
cp -avf csf.div /usr/local/csf/lib/
cp -avf csfajaxtail.js /usr/local/csf/lib/
cp -avf ui/images /etc/csf/ui/.
cp -avf profiles /usr/local/csf/
cp -avf csf.conf /usr/local/csf/profiles/reset_to_defaults.conf
cp -avf lfd.logrotate /etc/logrotate.d/lfd
chcon --reference /etc/logrotate.d /etc/logrotate.d/lfd
cp -avf apf_stub.pl /etc/csf/

rm -fv /etc/csf/csf.spamhaus /etc/csf/csf.dshield /etc/csf/csf.tor /etc/csf/csf.bogon

mkdir -p /usr/local/man/man1/
cp -avf csf.1.txt /usr/local/man/man1/csf.1
cp -avf csf.help /usr/local/csf/lib/
chmod 755 /usr/local/man/
chmod 755 /usr/local/man/man1/
chmod 644 /usr/local/man/man1/csf.1

chmod -R 600 /etc/csf
chmod -R 600 /var/lib/csf
chmod -R 600 /usr/local/csf/bin
chmod -R 600 /usr/local/csf/lib
chmod -R 600 /usr/local/csf/tpl
chmod -R 600 /usr/local/csf/profiles
chmod 600 /var/log/lfd.log*

chmod -v 700 /usr/local/csf/bin/*.pl /usr/local/csf/bin/*.sh /usr/local/csf/bin/*.pm
chmod -v 700 /etc/csf/*.pl /etc/csf/*.cgi /etc/csf/*.sh /etc/csf/*.php /etc/csf/*.py
chmod -v 700 /etc/csf/webmin/csf/index.cgi
chmod -v 644 /etc/cron.d/lfd-cron
chmod -v 644 /etc/cron.d/csf-cron

cp -avf csget.pl /etc/cron.daily/csget
chmod 700 /etc/cron.daily/csget
/etc/cron.daily/csget --nosleep

chmod -v 700 auto.cyberpanel.pl
./auto.cyberpanel.pl $OLDVERSION

if test `cat /proc/1/comm` = "systemd"
then
    if [ -e /etc/init.d/lfd ]; then
        if [ -f /etc/redhat-release ]; then
            /sbin/chkconfig csf off
            /sbin/chkconfig lfd off
            /sbin/chkconfig csf --del
            /sbin/chkconfig lfd --del
        elif [ -f /etc/debian_version ] || [ -f /etc/lsb-release ]; then
            update-rc.d -f lfd remove
            update-rc.d -f csf remove
        elif [ -f /etc/gentoo-release ]; then
            rc-update del lfd default
            rc-update del csf default
        elif [ -f /etc/slackware-version ]; then
            rm -vf /etc/rc.d/rc3.d/S80csf
            rm -vf /etc/rc.d/rc4.d/S80csf
            rm -vf /etc/rc.d/rc5.d/S80csf
            rm -vf /etc/rc.d/rc3.d/S85lfd
            rm -vf /etc/rc.d/rc4.d/S85lfd
            rm -vf /etc/rc.d/rc5.d/S85lfd
        else
            /sbin/chkconfig csf off
            /sbin/chkconfig lfd off
            /sbin/chkconfig csf --del
            /sbin/chkconfig lfd --del
        fi
        rm -fv /etc/init.d/csf
        rm -fv /etc/init.d/lfd
    fi

    mkdir -p /etc/systemd/system/
    mkdir -p /usr/lib/systemd/system/
    cp -avf lfd.service /usr/lib/systemd/system/
    cp -avf csf.service /usr/lib/systemd/system/

    chcon -h system_u:object_r:systemd_unit_file_t:s0 /usr/lib/systemd/system/lfd.service
    chcon -h system_u:object_r:systemd_unit_file_t:s0 /usr/lib/systemd/system/csf.service

    systemctl daemon-reload

    systemctl enable csf.service
    systemctl enable lfd.service

    systemctl disable firewalld
    systemctl stop firewalld
    systemctl mask firewalld
else
    cp -avf lfd.sh /etc/init.d/lfd
    cp -avf csf.sh /etc/init.d/csf
    chmod -v 755 /etc/init.d/lfd
    chmod -v 755 /etc/init.d/csf

    if [ -f /etc/redhat-release ]; then
        /sbin/chkconfig lfd on
        /sbin/chkconfig csf on
    elif [ -f /etc/debian_version ] || [ -f /etc/lsb-release ]; then
        update-rc.d -f lfd remove
        update-rc.d -f csf remove
        update-rc.d lfd defaults 80 20
        update-rc.d csf defaults 20 80
    elif [ -f /etc/gentoo-release ]; then
        rc-update add lfd default
        rc-update add csf default
    elif [ -f /etc/slackware-version ]; then
        ln -svf /etc/init.d/csf /etc/rc.d/rc3.d/S80csf
        ln -svf /etc/init.d/csf /etc/rc.d/rc4.d/S80csf
        ln -svf /etc/init.d/csf /etc/rc.d/rc5.d/S80csf
        ln -svf /etc/init.d/lfd /etc/rc.d/rc3.d/S85lfd
        ln -svf /etc/init.d/lfd /etc/rc.d/rc4.d/S85lfd
        ln -svf /etc/init.d/lfd /etc/rc.d/rc5.d/S85lfd
    else
        /sbin/chkconfig lfd on
        /sbin/chkconfig csf on
    fi
fi

chown -Rf root:root /etc/csf /var/lib/csf /usr/local/csf
chown -f root:root /usr/sbin/csf /usr/sbin/lfd /etc/logrotate.d/lfd /etc/cron.d/csf-cron /etc/cron.d/lfd-cron /usr/local/man/man1/csf.1 /usr/lib/systemd/system/lfd.service /usr/lib/systemd/system/csf.service /etc/init.d/lfd /etc/init.d/csf

mkdir -vp /usr/local/CyberCP/public/static/configservercsf/
cp -avf csf/* /usr/local/CyberCP/public/static/configservercsf/
cp -avf csf/* cyberpanel/configservercsf/static/configservercsf/
chmod 755 /usr/local/CyberCP/public/static/configservercsf/

cp cyberpanel/cyberpanel.pl /usr/local/csf/bin/
chmod 700 /usr/local/csf/bin/cyberpanel.pl
cp -avf cyberpanel/configservercsf /usr/local/CyberCP/

mkdir /home/cyberpanel/plugins
touch /home/cyberpanel/plugins/configservercsf

if ! cat /usr/local/CyberCP/CyberCP/settings.py | grep -q configservercsf; then
    sed -i "/pluginHolder/ i \ \ \ \ 'configservercsf'," /usr/local/CyberCP/CyberCP/settings.py
fi
if ! cat /usr/local/CyberCP/CyberCP/urls.py | grep -q configservercsf; then
    sed -i "/pluginHolder/ i \ \ \ \ path('configservercsf/',include('configservercsf.urls'))," /usr/local/CyberCP/CyberCP/urls.py
fi
#if ! cat /usr/local/CyberCP/baseTemplate/templates/baseTemplate/index.html | grep -q configservercsf; then
#    sed -i "/url 'csf'/ i <li><a href='/configservercsf/' title='ConfigServer Security and Firewall'><span>ConfigServer Security \&amp; Firewall</span></a></li>" /usr/local/CyberCP/baseTemplate/templates/baseTemplate/index.html
#fi
#if ! cat /usr/local/CyberCP/baseTemplate/templates/baseTemplate/index.html | grep -q configserver; then
#    sed -i "/trans 'Plugins'/ i \{\% include \"/usr/local/CyberCP/configservercsf/templates/configservercsf/menu.html\" \%\}" /usr/local/CyberCP/baseTemplate/templates/baseTemplate/index.html
#fi

service lscpd restart

echo
echo "Installation Completed"
echo
'''

            WriteToFile = open('install.cyberpanel.sh', 'w')
            WriteToFile.write(content)
            WriteToFile.close()


            command = "chmod +x install.sh"
            ProcessUtilities.normalExecutioner(command)

            command = 'bash install.sh'
            ProcessUtilities.normalExecutioner(command)

            command = 'mv /etc/csf/ui/server.crt /etc/csf/ui/server.crt-bak'
            ProcessUtilities.normalExecutioner(command)

            command = 'mv /etc/csf/ui/server.key /etc/csf/ui/server.key-bak'
            ProcessUtilities.normalExecutioner(command)

            command = 'ln -s /usr/local/lscp/conf/cert.pem /etc/csf/ui/server.crt'
            ProcessUtilities.normalExecutioner(command)

            command = 'ln -s /usr/local/lscp/conf/key.pem /etc/csf/ui/server.key'
            ProcessUtilities.normalExecutioner(command)

            ######

            # install required packages for CSF perl and /usr/bin/host
            if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:
                command = 'yum install bind-utils net-tools perl-libwww-perl.noarch perl-LWP-Protocol-https.noarch perl-GDGraph ipset -y'
                ProcessUtilities.normalExecutioner(command)
            elif ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu or ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu20:
                command = 'apt-get install dnsutils libwww-perl liblwp-protocol-https-perl libgd-graph-perl net-tools ipset -y'
                ProcessUtilities.normalExecutioner(command)
                command = 'ln -s /bin/systemctl /usr/bin/systemctl'
                ProcessUtilities.normalExecutioner(command)
            else:
                logging.CyberCPLogFileWriter.statusWriter(CSF.installLogPath,
                                                          'CSF required packages successfully Installed.[200]\n', 1)

            # Some initial configurations

            try:
                cPort = open(ProcessUtilities.portPath, 'r').read().split(':')[1].rstrip('\n')
            except:
                cPort = '8090'

            data = open('/etc/csf/csf.conf', 'r').readlines()
            writeToConf = open('/etc/csf/csf.conf', 'w')

            for items in data:
                if items.find('TCP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines(
                        f'TCP_IN = "20,21,22,25,53,80,110,995,143,443,465,587,993,995,1025,7080,{cPort},40110:40210,8088,5678"\n')
                elif items.find('TCP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines(
                        f'TCP_OUT = "20,21,22,25,43,53,80,110,113,443,587,993,995,{cPort},40110:40210,8088,5678"\n')
                elif items.find('UDP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('UDP_IN = "20,21,53,443"\n')
                elif items.find('UDP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('UDP_OUT = "20,21,53,113,123,443"\n')
                elif items.find('TESTING =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('TESTING = "0"\n')
                # setting RESTRICT_SYSLOG to "3" for use with option RESTRICT_SYSLOG_GROUP
                elif items.find('RESTRICT_SYSLOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RESTRICT_SYSLOG = "3"\n')

                #  Send an email alert if an IP address is blocked by one of the [*] triggers: disabled
                elif items.find('LF_EMAIL_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_EMAIL_ALERT = "0"\n')

                # Set LF_PERMBLOCK_ALERT to "0" to disable this feature
                elif items.find('LF_PERMBLOCK_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_PERMBLOCK_ALERT = "0"\n')

                #  Set LF_NETBLOCK_ALERT to "0" to disable this feature
                elif items.find('LF_NETBLOCK_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_NETBLOCK_ALERT = "0"\n')

                # Login Failure Blocking and Alerts
                # LF_TRIGGER_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_TRIGGER_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_TRIGGER_PERM = "1800"\n')

                #  Enable login failure detection of sshd connections: 10 failures triggers
                elif items.find('LF_SSHD =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_SSHD = "10"\n')

                #  LF_SSHD_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_SSHD_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_SSHD_PERM = "1800"\n')

                #  Enable login failure detection of ftp connections: 10 failures triggers
                elif items.find('LF_FTPD =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_FTPD = "10"\n')

                #  LF_FTPD_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_FTPD_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_FTPD_PERM = "1800"\n')

                #  Enable login failure detection of SMTP AUTH connections: 10 failures triggers
                elif items.find('LF_SMTPAUTH =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_SMTPAUTH = "10"\n')

                #  LF_SMTPAUTH_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_SMTPAUTH_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_SMTPAUTH_PERM = "1800"\n')

                #  Enable login failure detection of pop3 connections: 10 failures triggers
                elif items.find('LF_POP3D =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_POP3D = "10"\n')

                #  LF_POP3D_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_POP3D_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_POP3D_PERM = "1800"\n')

                #  Enable login failure detection of imap connections: 10 failures triggers
                elif items.find('LF_IMAPD =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_IMAPD = "10"\n')

                #  LF_IMAPD_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_IMAPD_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_IMAPD_PERM = "1800"\n')

                #  LF_HTACCESS_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_HTACCESS_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_HTACCESS_PERM = "1800"\n')

                #  Enable failure detection of repeated Apache mod_security rule triggers: 10 failures triggers
                elif items.find('LF_MODSEC =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_MODSEC = "10"\n')

                #  LF_MODSEC_PERM = "1800" => the IP is blocked temporarily for 30 minutes
                elif items.find('LF_MODSEC_PERM') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_MODSEC_PERM = "1800"\n')

                #  MODSEC_LOG location
                elif items.find('MODSEC_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('MODSEC_LOG = "/usr/local/lsws/logs/auditmodsec.log"\n')

                #  Send an email alert if anyone logs in successfully using SSH: Disabled
                elif items.find('LF_SSH_EMAIL_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_SSH_EMAIL_ALERT = "0"\n')

                #  Send an email alert if anyone accesses webmin: Disabled not applicable
                elif items.find('LF_WEBMIN_EMAIL_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_WEBMIN_EMAIL_ALERT = "0"\n')

                #  LF_QUEUE_ALERT disabled
                elif items.find('LF_QUEUE_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_QUEUE_ALERT = "0"\n')

                #  LF_QUEUE_INTERVAL disabled
                elif items.find('LF_QUEUE_INTERVAL = "0"') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_TRIGGER_PERM = "1800"\n')

                #  Relay Tracking. This allows you to track email that is relayed through the server. Disabled
                elif items.find('RT_RELAY_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_RELAY_ALERT = "0"\n')

                #  RT_[relay type]_LIMIT: the limit/hour afterwhich an email alert will be sent
                elif items.find('RT_RELAY_LIMIT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_RELAY_LIMIT = "500"\n')

                #  RT_[relay type]_BLOCK: 0 = no block;1 = perm block;nn=temp block for nn secs
                elif items.find('RT_RELAY_BLOCK') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_RELAY_BLOCK = "0"\n')

                #   This option triggers for email authenticated by SMTP AUTH disabled
                elif items.find('RT_AUTHRELAY_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_AUTHRELAY_ALERT = "0"\n')

                #  RT_AUTHRELAY_LIMIT set to 100
                elif items.find('RT_AUTHRELAY_LIMIT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_AUTHRELAY_LIMIT = "100"\n')

                #  RT_AUTHRELAY_LIMIT set to 0
                elif items.find('RT_AUTHRELAY_BLOCK') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_AUTHRELAY_BLOCK = "0"\n')

                #   This option triggers for email authenticated by POP before SMTP
                elif items.find('RT_POPRELAY_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_POPRELAY_ALERT = "0"\n')

                #   This option triggers for email authenticated by POP before SMTP
                elif items.find('RT_POPRELAY_LIMIT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_POPRELAY_LIMIT = "100"\n')

                #  RT_POPRELAY_BLOCK disabled
                elif items.find('RT_POPRELAY_BLOCK') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_POPRELAY_BLOCK = "0"\n')

                #   This option triggers for email sent via /usr/sbin/sendmail or /usr/sbin/exim: Disabled
                elif items.find('RT_LOCALRELAY_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_LOCALRELAY_ALERT = "0"\n')

                #   This option triggers for email sent via a local IP addresses
                elif items.find('RT_LOCALRELAY_LIMIT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_LOCALRELAY_LIMIT = "100"\n')

                #   This option triggers for email sent via a local IP addresses
                elif items.find('RT_LOCALHOSTRELAY_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_LOCALHOSTRELAY_ALERT = "0"\n')

                #   This option triggers for email sent via a local IP addresses disabled
                elif items.find('RT_LOCALHOSTRELAY_LIMIT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_LOCALHOSTRELAY_LIMIT = "100"\n')

                #  If an RT_* event is triggered, then if the following contains the path to a script
                elif items.find('RT_ACTION') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('RT_ACTION = ""\n')

                #   Send an email alert if an IP address is blocked due to connection tracking disabled
                elif items.find('CT_EMAIL_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('CT_EMAIL_ALERT = "0"\n')

                #  User Process Tracking.  Set to 0 to disable this feature
                elif items.find('PT_USERPROC =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_USERPROC = "0"\n')

                #  This User Process Tracking option sends an alert if any user process exceeds the virtual memory usage set (MB)
                elif items.find('PT_USERMEM =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_USERMEM = "0"\n')

                #  This User Process Tracking option sends an alert if any user process exceeds the RSS memory usage set (MB) - RAM used, not virtual.
                elif items.find('PT_USERRSS =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_USERRSS = "0"\n')

                #  If this option is set then processes detected by PT_USERMEM, PT_USERTIME or PT_USERPROC are killed. Disabled
                elif items.find('PT_USERTIME =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_USERTIME = "0"\n')

                #  If you want to disable email alerts if PT_USERKILL is triggered, then set this option to 0. Disabled
                elif items.find('PT_USERKILL_ALERT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_USERKILL_ALERT = "0"\n')

                #  Check the PT_LOAD_AVG minute Load Average (can be set to 1 5 or 15 and defaults to 5 if set otherwise) on the server every PT_LOAD seconds. Disabled
                elif items.find('PT_LOAD =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('PT_LOAD = "0"\n')

                #  Enable LF_IPSET for CSF for more efficient ipables rules with ipset
                elif items.find('LF_IPSET =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('LF_IPSET = "1"\n')

                #  HTACCESS_LOG is ins main error.log
                elif items.find('HTACCESS_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('HTACCESS_LOG = "/usr/local/lsws/logs/error.log"\n')

                #  SYSLOG_CHECK Check whether syslog is running
                elif items.find('SYSLOG_CHECK =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    writeToConf.writelines('SYSLOG_CHECK = "300"\n')

                #  CSF UI enable
                # elif items.find('UI = "0"') > -1 and items.find('=') > -1 and (items[0] != '#'):
                #    writeToConf.writelines('UI = "1"\n')
                # elif items.find('UI_ALLOW') > -1 and items.find('=') > -1 and (items[0] != '#'):
                #    writeToConf.writelines('UI_ALLOW = "0"\n')
                # elif items.find('UI_PORT =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                #    writeToConf.writelines('UI_PORT = "1025"\n')
                # elif items.find('UI_USER') > -1 and items.find('=') > -1 and (items[0] != '#'):
                #    writeToConf.writelines('UI_USER = "cyberpanel"\n')
                # elif items.find('UI_PASS') > -1 and items.find('=') > -1 and (items[0] != '#'):
                #    writeToConf.writelines('UI_PASS = "csfadmin1234567"\n')
                else:
                    writeToConf.writelines(items)

            writeToConf.close()

            ##

            # Some Ubuntu initial configurations
            if ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu or ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu20:
                data = open('/etc/csf/csf.conf', 'r').readlines()
                writeToConf = open('/etc/csf/csf.conf', 'w')

                for items in data:
                    if items.find('SSHD_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('SSHD_LOG = "/var/log/auth.log"\n')
                    elif items.find('SU_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('SU_LOG = "/var/log/auth.log"\n')
                    elif items.find('SMTPAUTH_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('SMTPAUTH_LOG = "/var/log/mail.log"\n')
                    elif items.find('POP3D_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('POP3D_LOG = "/var/log/mail.log"\n')
                    elif items.find('IMAPD_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('IMAPD_LOG = "/var/log/mail.log"\n')
                    elif items.find('IPTABLES_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('IPTABLES_LOG = "/var/log/kern.log"\n')
                    elif items.find('SYSLOG_LOG =') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToConf.writelines('SYSLOG_LOG = "/var/log/syslog"\n')
                    else:
                        writeToConf.writelines(items)
                writeToConf.close()

                ##

            command = 'csf -s'
            ProcessUtilities.normalExecutioner(command)

            command = 'sleep 5'
            ProcessUtilities.normalExecutioner(command)

            command = 'csf -ra'
            ProcessUtilities.normalExecutioner(command)

            ##### update csf views file

            logging.CyberCPLogFileWriter.statusWriter(CSF.installLogPath, 'CSF successfully Installed.[200]\n', 1)

            try:
                os.remove('csf.tgz')
                os.removedirs('csf')
            except:
                pass

            return 1
        except BaseException as msg:
            try:
                os.remove('csf.tgz')
                os.removedirs('csf')
            except:
                pass
            writeToFile = open(CSF.installLogPath, 'a')
            writeToFile.writelines(str(msg) + " [404]")
            writeToFile.close()
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[installCSF]")

    def removeCSF(self):
        try:

            ##

            os.chdir('/etc/csf')

            command = './uninstall.sh'
            cmd = shlex.split(command)
            subprocess.call(cmd)

            os.chdir('/usr/local/CyberCP')

            #

            command = 'systemctl unmask firewalld'
            subprocess.call(shlex.split(command))

            #

            command = 'systemctl start firewalld'
            subprocess.call(shlex.split(command))

            ##

            command = 'systemctl enable firewalld'
            subprocess.call(shlex.split(command))

            return 1
        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[removeCSF]")

    @staticmethod
    def fetchCSFSettings():
        try:

            currentSettings = {}

            command = 'sudo cat /etc/csf/csf.conf'
            output = ProcessUtilities.outputExecutioner(command).splitlines()

            for items in output:
                if items.find('TESTING') > -1 and items.find('=') > -1 and (items[0] != '#') and items.find(
                        'TESTING_INTERVAL') == -1:
                    if items.find('0') > -1:
                        currentSettings['TESTING'] = 0
                    else:
                        currentSettings['TESTING'] = 1
                elif items.find('TCP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    tcpIN = items[items.find('"'):]
                    currentSettings['tcpIN'] = tcpIN.strip('"')
                elif items.find('TCP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    tcpOUT = items[items.find('"'):]
                    currentSettings['tcpOUT'] = tcpOUT.strip('"')
                elif items.find('UDP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    udpIN = items[items.find('"'):]
                    currentSettings['udpIN'] = udpIN.strip('"')
                elif items.find('UDP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                    udpOUT = items[items.find('"'):]
                    currentSettings['udpOUT'] = udpOUT.strip('"')

            ### Check if rules are applied

            currentSettings['firewallStatus'] = 0

            command = 'sudo iptables -nv -L'
            output = ProcessUtilities.outputExecutioner(command)

            if output.find('0.0.0.0/0') > -1:
                currentSettings['firewallStatus'] = 1

            return currentSettings

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + " [fetchCSFSettings]")

    @staticmethod
    def changeStatus(controller, status):
        try:
            if controller == 'csf':
                if status == 'enable':
                    command = 'csf -s'
                    subprocess.call(shlex.split(command))
                    print('1,None')
                else:
                    command = 'csf -f'
                    subprocess.call(shlex.split(command))
                    print('1,None')

            elif controller == 'testingMode':
                data = open('/etc/csf/csf.conf', 'r').readlines()
                writeToFile = open('/etc/csf/csf.conf', 'w')

                for items in data:
                    if items.find('TESTING') > -1 and items.find('=') > -1 and (items[0] != '#') and items.find(
                            'TESTING_INTERVAL') == -1:
                        if status == 'enable':
                            writeToFile.writelines('TESTING = "1"\n')
                        else:
                            writeToFile.writelines('TESTING = "0"\n')
                    else:
                        writeToFile.writelines(items)
                writeToFile.close()
                print('1,None')

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[changeStatus]")
            print('0', str(msg))

    @staticmethod
    def modifyPorts(protocol, portsPath):
        try:

            data = open('/etc/csf/csf.conf', 'r').readlines()
            writeToFile = open('/etc/csf/csf.conf', 'w')

            ports = open(portsPath, 'r').read()

            if protocol == 'TCP_IN':
                for items in data:
                    if items.find('TCP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        if ports.find(',') > -1:
                            writeToFile.writelines('TCP_IN = "' + ports + '"\n')
                        else:
                            content = '%s,%s"\n' % (items.rstrip('\n"'), ports)
                            writeToFile.writelines(content)
                    else:
                        writeToFile.writelines(items)
                writeToFile.close()
            elif protocol == 'TCP_OUT':
                for items in data:
                    if items.find('TCP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        if ports.find(',') > -1:
                            writeToFile.writelines('TCP_OUT = "' + ports + '"\n')
                        else:
                            content = '%s,%s"\n' % (items.rstrip('\n"'), ports)
                            writeToFile.writelines(content)
                    else:
                        writeToFile.writelines(items)
                writeToFile.close()
            elif protocol == 'UDP_IN':
                for items in data:
                    if items.find('UDP_IN') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToFile.writelines('UDP_IN = "' + ports + '"\n')
                    else:
                        writeToFile.writelines(items)
                writeToFile.close()
            elif protocol == 'UDP_OUT':
                for items in data:
                    if items.find('UDP_OUT') > -1 and items.find('=') > -1 and (items[0] != '#'):
                        writeToFile.writelines('UDP_OUT = "' + ports + '"\n')
                    else:
                        writeToFile.writelines(items)
                writeToFile.close()

            command = 'csf -r'
            subprocess.call(shlex.split(command))

            try:
                os.remove(portsPath)
            except:
                pass

            print('1,None')

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[modifyPorts]")
            print('0', str(msg))

    @staticmethod
    def allowIP(ipAddress):
        try:
            command = 'sudo csf -dr ' + ipAddress
            ProcessUtilities.executioner(command)

            command = 'sudo csf -a ' + ipAddress
            ProcessUtilities.executioner(command)

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[allowIP]")

    @staticmethod
    def blockIP(ipAddress):
        try:

            command = 'sudo csf -tr ' + ipAddress
            ProcessUtilities.executioner(command)

            command = 'sudo csf -d ' + ipAddress
            ProcessUtilities.executioner(command)

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[blockIP]")

    @staticmethod
    def checkIP(ipAddress):
        try:
            command = 'sudo csf -g ' + ipAddress
            ProcessUtilities.executioner(command)

        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg) + "[checkIP]")


def main():
    parser = argparse.ArgumentParser(description='CSF Manager')
    parser.add_argument('function', help='Specific a function to call!')

    parser.add_argument('--controller', help='Controller selection!')
    parser.add_argument('--status', help='Controller status!')
    parser.add_argument('--protocol', help='Protocol Modifications!')
    parser.add_argument('--ports', help='Ports!')

    args = parser.parse_args()

    if args.function == "installCSF":
        CSF.installCSF()
    elif args.function == 'removeCSF':
        controller = CSF(args.function, {})
        controller.run()
    elif args.function == 'changeStatus':
        CSF.changeStatus(args.controller, args.status)
    elif args.function == 'modifyPorts':
        CSF.modifyPorts(args.protocol, args.ports)


if __name__ == "__main__":
    main()

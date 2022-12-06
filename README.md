# CyberPanel

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/04d6ab6bb42c45739ef98c172bb466d2)](https://www.codacy.com/gh/josephgodwinkimani/cyberpanel/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=josephgodwinkimani/cyberpanel&amp;utm_campaign=Badge_Grade)

Web Hosting Control Panel that uses OpenLiteSpeed as the underlying Web Server.

## Features & Services

* Different User Access Levels (via ACLs).
* Auto SSL.
* FTP Server.
* Light-weight DNS Server (PowerDNS).
* phpMyAdmin to manage DBs (MariaDB).
* Email Support (SnappyMail).
* File Manager.
* PHP Managment.
* Firewall (FirewallD & ConfigServer Firewall Integration).
* One-click Backups and Restores.

## [Extra Features & Services](https://github.com/josephgodwinkimani/cyberpanel/blob/main/CHANGELOG.MD)

* Count vmail folder size to disk usage by [@tbaldur](https://github.com/tbaldur)
* 

# Supported PHP Versions

* PHP 8.1
* PHP 8.0
* PHP 7.4
* PHP 7.3
* PHP 7.2
* PHP 7.1
* PHP 7.0
* PHP 5.6
* PHP 5.5
* PHP 5.4
* PHP 5.3


# Installation Instructions


```bash
sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh)
```

# Upgrading CyberPanel


```bash
sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh)
```

# Add additional logs for CrowdSec

```bash
nano /etc/crowdsec/acquis.yaml
```
Add at the end:

```
...
#https://doc.crowdsec.net/docs/data_sources/file
source: file
filenames:
 - /home/cyberpanel/error-logs.txt
 - /usr/local/lsws/logs/error.log
 - /usr/local/lsws/logs/access.log #useless
 - /var/log/maillog
 - /var/log/messages
 - /var/log/mysql/error.log #https://community.cyberpanel.net/t/how-to-check-database-logs/37979/2
labels:
 type: syslog
 ```

You can also acquire logs from journalctl files e.g.

```
...
source: journalctl
journalctl_filter:
 - "_SYSTEMD_UNIT=ssh.service"
labels:
  type: journald
 ```

# Enroll your CrowdSec instance on https://app.crowdsec.net/

```bash
$ sudo cscli console enroll 1234567890abcdef1234567890
```

# How to protect your CyberPanel server:

* [Configure your Firewall](https://community.cyberpanel.net/docs?search=firewall&topic=132) 
* [Secure SSH by disabling root access](https://community.cyberpanel.net/docs?search=ssh&topic=131) 
* [Setup Backups for your client’s data](https://community.cyberpanel.net/docs?category=15&topic=122) 
* [Install Imunify360](https://community.cyberpanel.net/docs?category=&search=imunify&topic=172)
* [Setup Custom ACL for your users disallowing specific services per account](https://community.cyberpanel.net/docs?category=&search=ACL&tags=&topic=84#custom-acls-3)

# Resources

* [Getting started after Installation](https://community.cyberpanel.net/t/cant-access-website-show-cyberpanel-installed-page/38018/2)
* [How to setup DNS configurations for CyberPanel](https://community.cyberpanel.net/t/tutorial-how-to-setup-dns-configurations-for-cyberpanel/38094)
* [How to install any PHP modules using PEAR Package Manager](https://community.cyberpanel.net/t/tutorial-how-to-install-any-php-modules-using-pear-package-manager/37785)
* [How to remove port 8090](https://community.cyberpanel.net/t/how-to-remove-port-8090-from-cyberpanel/30648)
* [Setting up Fully qualified domain name for SnappyMail](https://community.cyberpanel.net/t/tutorial-setting-up-fully-qualified-domain-name-for-snappymail/37898)
* [How to install SSL certificate from external sources](https://community.cyberpanel.net/t/the-same-domain-for-website-and-e-mail/38322/2)
* [How to change website domain or subdomain](https://community.cyberpanel.net/t/tutorial-how-to-change-website-domain-or-subdomain/37917)
* [Setting up NodeJS for your apps](https://community.cyberpanel.net/t/deploy-nodejs-app-doesnnt-work/36389/2)
* [Change MariaDB log configuration for your own purposes](https://community.cyberpanel.net/t/how-to-check-database-logs/37979/2)
* [How to allow your SnappyMail users to change their mailbox passwords](https://community.cyberpanel.net/t/tutorial-how-to-allow-your-snappymail-users-to-change-their-mailbox-passwords/38084)
* [Script to Install Ioncube in PHP 7.2 - 8.1](https://community.cyberpanel.net/t/how-to-install-ioncube-loader-extension-on-php-8-1/38145/9)
* [How to clean PHP Sessions](https://community.cyberpanel.net/t/high-cpu-usage-4cpu-8gb-ram/37904/2)
* [Cannot Delete a Website/ Remove remnants from a deleted Website](https://community.cyberpanel.net/t/404-error-in-one-only-website-after-deleting-some-child-domain-sites/38352/3)
* [Imunify ERROR: Can’t connect to agent. Check php part of application](https://community.cyberpanel.net/t/cant-connect-to-agent-check-php-part-of-application/38601)

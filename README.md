# CyberPanel

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/04d6ab6bb42c45739ef98c172bb466d2)](https://www.codacy.com/gh/josephgodwinkimani/cyberpanel/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=josephgodwinkimani/cyberpanel&amp;utm_campaign=Badge_Grade)

Web Hosting Control Panel that uses OpenLiteSpeed as the underlying Web Server. 

## Features & Services

* Different User Access Levels (via ACLs).
* Auto SSL.
* FTP Server.
* Light-weight DNS Server (PowerDNS).
* phpMyAdmin will manage DBs (MariaDB).
* Email Support (SnappyMail).
* File Manager.
* PHP Management.
* Firewall (FirewallD & ConfigServer Firewall Integration).
* One-click Backups and Restores.

### Added Features

* Protects from Brute-force attacks (Fail2ban)
* Advanced Threat detection (DDoS Mitigation, Port Scanning Detection, Log Monitoring, HTTP/ Brute Force Protection using Crowdsec)
* Advanced Backups from terminal with Encryption and File Synchronisation (Rclone)
* 

# Supported PHP Versions

* PHP 8.3 (will reach end of life (EOL) on 31 Dec, 2027.)
* PHP 8.2 (will reach end of life (EOL) on 31 Dec, 2026.)
* PHP 8.1 (will reach end of life (EOL) on 31 Dec, 2025.)
* PHP 8.0 (will reach end of life (EOL) on 26 Nov, 2023.)
* PHP 7.4 (Ubuntu 22.04 and Almalinux 9.x and up does not support php below this version.) (will reach end of life (EOL) on 28 Nov 2022.)
* PHP 7.3 (will reach end of life (EOL) on 6 Dec, 2021.)
* PHP 7.2 (will reach end of life (EOL) on 30 Nov, 2020.)
* PHP 7.1 (Almalinux 8.x and up does not support php below this version.),(will reach end of life (EOL) on 1 Dec, 2019.)
* PHP 7.0 (will reach end of life (EOL) on 10 Jan, 2019.)
* PHP 5.6 (will reach end of life (EOL) on 31 Dec, 2018.)
* PHP 5.5 (will reach end of life (EOL) on 21 Jul, 2016.)
* PHP 5.4 (will reach end of life (EOL) on 3 Sep, 2015.)
* PHP 5.3 (will reach end of life (EOL) on 14 Aug, 2014.)

# Supported OS Versions

* CyberPanel is supported on x86_64 based
* Ubuntu 18.04 (will reach end of life (EOL) on 31 May, 2023.)
* Ubuntu 20.04 (will reach end of life (EOL) on April, 2025.)
* Ubuntu 20.10 (will reach end of life (EOL) on 22 July, 2021.)
* Ubuntu 22.04 (will reach end of life (EOL) on Apr 2022 - Apr 2027.)
* CentOS 7 (will reach end of life (EOL) on 30 June, 2024.)
* CentOS 8 (will reach end of life (EOL) on 31 December, 2021.)
* CentOS 9 (will reach end of life (EOL) on 31 May, 2027.)
* RHEL 8 (will reach end of life (EOL) on 31 May, 2029.)
* RHEL 9 (will reach end of life (EOL) on 31 May, 2032.)
* AlmaLinux 8 (will reach end of life (EOL) on 01 May, 2024).)
* AlmaLinux 9 (will reach end of life (EOL) on 31 May, 2027.)
* RockyLinux 8 (will reach end of life (EOL) on 31 May, 2029.)
* CloudLinux 7 (will reach end of life (EOL) on 01 July, 2024.)
* CloudLinux 8 (will reach end of life (EOL) on 31 May, 2029.)
* openEuler 20.03 (will reach end of life (EOL) on April, 2022.)
* openEuler 22.03 (will reach end of life (EOL) on March, 2024.)

# Installation Instructions

```bash
sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh)
```

OR for Non-root user

```bash
sudo su - -c "sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/install.sh)"
```

# Upgrading CyberPanel

```bash
sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh)
```

OR for Non-root user

```bash
sudo su - -c "sh <(curl https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh || wget -O - https://raw.githubusercontent.com/josephgodwinkimani/cyberpanel/main/preUpgrade.sh)"
```

# Enroll your CrowdSec instance on https://app.crowdsec.net/

```bash
$ sudo cscli console enroll 1234567890abcdef1234567890
```

# Setup rclone backups

1. Go to `https://SERVER_URL/backup/backupDestinations` add local path as `/home/backup`

2. Go to `https://SERVER_URL/backup/scheduleBackup` and select destination as `backup`

3. Add backup frequency (daily, weekly) and backup retention (0 = unlimited)

4. A cronjob will run every day to copy these backups to remote backup 

You can [drop in a sql backup script](https://github.com/josephgodwinkimani/cyberpanel-mods/blob/main/rclone_sqlbackup_cronjob.sh), edit it and add it to `/var/spool/cron/crontabs/root` to run once everyday to backup all your databases to a remote location(s).


# How this fork keeps up with [main repo](https://github.com/usmannasir/cyberpanel/tree/stable)

1. Changes are released on stable branch of main repo

2. After 30 days if there no reported issues all changes from main repo are adopted for testing

3. A proper update is released here for use

# What this fork takes from the main repo

This fork is not a mirror of [usmannasir/cyberpanel](https://github.com/usmannasir/cyberpanel). It started from release 2.3.8 of the main repo and adopts only selected changes. Each change is its own pull request with its own test script in `CPScripts/`. Changes are never merged wholesale from the main repo.

Adopted or added here:

* Security fixes for the logs page, database deletion, backups and backup cancelling, user and ACL changes by non-admins, the cron worker and the PHP pool tuning page. Passwords and tokens are generated with the `secrets` module.
* Safer upgrades: an installed CrowdSec and the rclone backup script are left untouched, system package updates are opt-in, only missing prerequisites are installed, the Python requirement files go into the virtual environments, and the panel environments are restored when an upgrade fails.
* Fixes for the Cloudflare DNS sync and for the GhettoForge repository address used by the mail installers.
* The installed version is recorded in the database after an upgrade and the version management page follows the selected branch.
* Check and mitigation scripts for the PHP2Shell vulnerabilities (`CPScripts/php2shell_check.sh` and `CPScripts/php2shell_mitigate.sh`).

Not taken from the main repo:

* Paid add-ons and every page or endpoint that asks their licence service are removed. This covers the WordPress site manager, the wildcard SSL add-on, Email Debugger, Rspamd Manager, the Cloud API, the Google Drive and snapshot based backup add-ons, the Apache backend page and the high availability app.
* Other upstream changes are reviewed one at a time and adopted only when they fix a defect or a security problem without changing how existing installations behave.

# Releases and checks

* Release branches are named like `v3.0.0`. The upgrade command above reads `version.txt` on `main` and downloads the upgrade script from the branch that file names.
* Run `bash CPScripts/port_check.sh` on a branch before it becomes a pull request. Every test script in `CPScripts/` can be run on its own.

# How to protect your CyberPanel server:

* [Configure your Firewall](https://community.cyberpanel.net/t/1-firewall/132) 
* [Secure SSH by disabling root access](https://community.cyberpanel.net/t/2-secure-ssh/131) 
* [Setup Backups for your client’s data](https://community.cyberpanel.net/t/backup-to-google-drive/116) 
* [Install Imunify360](https://community.cyberpanel.net/t/how-to-install-and-use-imunify360-on-cyberpanel/172)
* [Setup Custom ACL for your users disallowing specific services per account](https://community.cyberpanel.net/t/1-managing-users/84)

# Resources

* [Wiki](https://github.com/josephgodwinkimani/cyberpanel/wiki)
* [PHP SDK for CyberPanel](https://github.com/josephgodwinkimani/cyberpanel-php)
* [Useful Bash scripts and Files](https://github.com/josephgodwinkimani/cyberpanel-mods)
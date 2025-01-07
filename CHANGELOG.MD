Nitpick branch
------------------------------------------------------------------------------

## Release 2.3 build 9 
### CyberPanel Version [6f28d39a591b5e08aac6adfcc59b642a58622ea2](https://github.com/usmannasir/cyberpanel/commit/6f28d39a591b5e08aac6adfcc59b642a58622ea2)
------------------------------------------------------------------------------

**General:**
* Unattended auto-upgrades are scheduled via the cron job `0 1 * * * /usr/local/CyberCP/autoPreUpgrade.sh >> /var/log/upgradeLogs.txt`. You may disable this job if necessary. It is strongly recommended to back up or create a snapshot of your server prior to executing this cron job in your cron job order.
* 

**Security:**

**Bug Fixes:**


## Release 2.3 build 2 
### CyberPanel Version [7427667c14c2ddbc2fcb7bfa35870155d4a343dc](https://github.com/usmannasir/cyberpanel/commit/85596f08cfb31393d548de76d33859b9517a383a)
------------------------------------------------------------------------------

**General:**
* [Set defaults for creating domain, website, installing wordpress, adding domain alias](https://github.com/josephgodwinkimani/cyberpanel/commit/ca71e55c784679fe0f57f7d75049220f047a9efb) 
* [Setup crowdsec crowd-based cybersecurity suite](https://github.com/josephgodwinkimani/cyberpanel/commit/2869f5016a0c7353335609e7bce6e0df5ba554b0) Author: [tmoore](https://community.cyberpanel.net/u/tmoore)
* [add sink for let's encrypt cronjob](https://github.com/josephgodwinkimani/cyberpanel/commit/b563d9edf6e6188f1deb8668564d40c993c758be)

**Security:**
*

**Bug Fixes:**
* [Change cleansessions (Fix session issues on CyberPanel and standardized session paths) to run twice per hour.](https://github.com/josephgodwinkimani/cyberpanel/commit/0af08466bd9584f087ea26be37b0a91ff16f91d4) Author: [tmoore](https://community.cyberpanel.net/u/tmoore)
* [Add Disk usage updater cron job to run every 15 minutes. It counts vmail to total disk usage](https://github.com/josephgodwinkimani/cyberpanel/commit/2869f5016a0c7353335609e7bce6e0df5ba554b0) Author: [tmoore](https://community.cyberpanel.net/u/tmoore)
* [OLS default settings tuning - Get real IPs from cloudflare by default, Symbolic links protection for shared environments](https://github.com/josephgodwinkimani/cyberpanel/commit/17e0592d37df44bb87da88fbf5e038285705643d) Author: [tmoore](https://community.cyberpanel.net/u/tmoore)
* [Wrong/Missing php processors to compile at OLS panel](https://github.com/josephgodwinkimani/cyberpanel/commit/dadfc18209aec416fe3bc2088a24e8a5a30c8076)
* [Add CrowdSec scenarios, parsers, collections and patch needed features](https://github.com/josephgodwinkimani/cyberpanel/commit/31aa77e6c7481475c03025499adc7e3d41c3ce63)
* [Fix install script, add Comodo Modsecurity rules v1.233](https://github.com/josephgodwinkimani/cyberpanel/commit/0e8ffd43b1e0214da44d3ec5f84a452d8c7ad7fe)
* [workaround for missing 'CyberCP' module](https://github.com/josephgodwinkimani/cyberpanel/commit/09b12d8e86cdc42d09c2fd335c04a8a2d6bbe85b)
* [fix install and add almalinux installation](https://github.com/josephgodwinkimani/cyberpanel/commit/12ed05d83a8881cfef21bac3e9f2ea3b5f67691e)
* [fix unable to fetch repo branch](https://github.com/josephgodwinkimani/cyberpanel/commit/10f558294523be094118ddfe1c350c8ef93c7dc7)
* [fix 500 error on version management page](https://github.com/josephgodwinkimani/cyberpanel/commit/6a0b58b14fa573a703113b9cdde0d2cfd7a4f203)
* [fix: upgrade rclone with precompiled binary](https://github.com/josephgodwinkimani/cyberpanel/commit/e506cc197ef29d38d5fa90baf664679ef655b115)
"""Tests that the paid WordPress site manager (deploy and list pages, plugin buckets, staging, remote backups and restore, auto login, the
pricing page and their ajax endpoints) is removed from the web layer without touching the free one click WordPress install, the other
application installers, the free staging and clone pages or any other site page: 42 manager methods, 42 views and 42 routes, 13 templates,
6 script controllers with their helpers, the controller of the pricing page, the sidebar menu and the staging list helper are gone, nothing
reverses or calls them, and the free methods and views are byte for byte what they were (pinned by hash). The database models stay.
Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_wordpress_site_manager_removed.py"""
import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def fp(src):
    return hashlib.sha256(src.encode()).hexdigest()[:16]


METHODS = ['WPCreate', 'ListWPSites', 'WPHome', 'RestoreHome', 'RemoteBackupConfig', 'BackupfileConfig', 'AddRemoteBackupsite', 'WordpressPricing',
           'RestoreBackups', 'AutoLogin', 'ConfigurePlugins', 'Addnewplugin', 'SearchOnkeyupPlugin', 'AddNewpluginAjax', 'EidtPlugin', 'deletesPlgin',
           'Addplugineidt', 'FetchWPdata', 'GetCurrentPlugins', 'GetCurrentThemes', 'fetchstaging', 'fetchDatabase', 'SaveUpdateConfig',
           'DeploytoProduction', 'WPCreateBackup', 'RestoreWPbackupNow', 'SaveBackupConfig', 'SaveBackupSchedule', 'AddWPsiteforRemoteBackup',
           'UpdateRemoteschedules', 'ScanWordpressSite', 'installwpcore', 'dataintegrity', 'UpdatePlugins', 'UpdateThemes', 'DeletePlugins',
           'DeleteThemes', 'ChangeStatus', 'ChangeStatusThemes', 'CreateStagingNow', 'UpdateWPSettings', 'submitWorpressCreation']
ROUTE_NAMES = ['createWordpress', 'ListWPSites', 'WPHome', 'RestoreBackups', 'RestoreHome', 'AutoLogin', 'RemoteBackupConfig', 'BackupfileConfig',
               'AddRemoteBackupsite', 'pricing', 'submitWorpressCreation', 'FetchWPdata', 'GetCurrentPlugins', 'GetCurrentThemes', 'UpdateWPSettings',
               'UpdatePlugins', 'DeletePlugins', 'ChangeStatus', 'UpdateThemes', 'DeleteThemes', 'StatusThemes', 'CreateStagingNow', 'fetchstaging',
               'fetchDatabase', 'SaveUpdateConfig', 'DeploytoProduction', 'WPCreateBackup', 'RestoreWPbackupNow', 'dataintegrity', 'installwpcore',
               'SaveBackupConfig', 'SaveBackupSchedule', 'AddWPsiteforRemoteBackup', 'UpdateRemoteschedules', 'ScanWordpressSite', 'ConfigurePlugins',
               'Addnewplugin', 'EidtPlugin', 'SearchOnkeyupPlugin', 'AddNewpluginAjax', 'deletesPlgin', 'Addplugineidt']
VIEW_NAMES = sorted(set(METHODS) - {'ChangeStatusThemes'} | {'StatusThemes', 'WPCreate'})
TEMPLATES = ['AddRemoteBackupSite', 'AutoLogin', 'BackupfileConfig', 'CyberpanelPricing', 'RemoteBackupConfig', 'RestoreBackups', 'WPAddNewPlugin',
             'WPConfigurePlugins', 'WPCreate', 'WPEidtPlugin', 'WPRestoreHome', 'WPsiteHome', 'WPsitesList']
CONTROLLERS = ['WPAddNewPlugin', 'createWordpress', 'WPsiteHome', 'RestoreWPBackup', 'RemoteBackupConfig', 'BackupSchedule', 'BuyAddons']
HELPERS = ['selectpluginJs', 'DeletePluginBuucket', 'FinalDeletePluginBuucket', 'DeleteWPNow', 'FinalDeleteWPNow', 'DeployToProductionInitial',
           'create_staging_checkbox_function', 'AddPluginToArray', 'AddThemeToArray', 'AppendToTable', 'DeleteBackupConfigNow',
           'DeleteRemoteBackupsiteNow', 'DeleteBackupfileConfigNow', 'checkbox_function', 'domain_check', 'PluginsList', 'ThemesList']
WEBSITE, VIEWS, URLS, JS, INDEX, PHPU = (read('websiteFunctions/website.py'), read('websiteFunctions/views.py'), read('websiteFunctions/urls.py'),
                                         read('websiteFunctions/static/websiteFunctions/websiteFunctions.js'),
                                         read('baseTemplate/templates/baseTemplate/index.html'), read('plogical/phpUtilities.py'))

# manager methods
mtree = ast.parse(WEBSITE)
manager = next(n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')
methods = {n.name: n for n in manager.body if isinstance(n, ast.FunctionDef)}
check('none of the 42 manager methods is left', sorted(set(METHODS) & set(methods)), [])
MPIN = {'wordpressInstall': 'f2624f59552d444c', 'installWordpress': 'f592559693c97c85', 'installWordpressStatus': '296117642d2d981e',
        'joomlaInstall': '11647ae95dc29b98', 'installJoomla': 'd772d41772d7c3fa', 'setupStaging': 'ce60260109e3803f', 'startCloning': 'eefe6c6ec4954b28',
        'syncToMaster': '310d922b418e1c9e', 'startSync': 'e65dc2c1a643f8ca', 'modifyWebsite': 'f98ea286e109201c', 'deleteWebsite': '1da24203f6703c00',
        'siteState': '45f14b6a44524f93', 'listWebsites': '0d7686a9cc11d6dd', 'listChildDomains': 'c6f772ec5dcc4f48', 'listCron': 'f9a2f508142358ae',
        'domainAlias': 'ec4ccd935ba44e34', 'fetchDomains': 'a12c84cba4776767', 'searchWebsites': '67cf4e44745f5f78', 'fetchWebsitesList': 'fd243b2a429d90e7',
        'loadDomainHome': '45cbc150dd5b15e7', 'installPrestaShop': '55add7b751c8f6fb', 'installMagento': 'eb9b2b870c9eb6bc', 'installMautic': '322db19e6e1c3f55',
        'setupGit': '33a0bc44ec563a20', 'changePHP': '7b51bb3ca9dddb72', 'saveSSL': 'a2ba409814a65ea6', 'sshAccess': '04191e026039a761'}
check('the free manager methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(WEBSITE, methods[n])) if n in methods else None for n in MPIN}, MPIN)
check('the free one click install methods are all there', [n for n in ('wordpressInstall', 'installWordpress', 'installWordpressStatus') if n in methods], ['wordpressInstall', 'installWordpress', 'installWordpressStatus'])

# views
vtree = ast.parse(VIEWS)
vfuncs = {n.name: n for n in vtree.body if isinstance(n, ast.FunctionDef)}
check('none of the removed views is left', sorted(set(VIEW_NAMES) & set(vfuncs)), [])
VPIN = {'wordpressInstall': '5480ac33d3d1925e', 'installWordpress': '3c797bca3788b316', 'installWordpressStatus': 'd243912ced3c14cd',
        'joomlaInstall': '58c7ba5b1c2a847c', 'installJoomla': '43e5f51109f5d378', 'setupStaging': 'a877ddc2986ae54e', 'startCloning': 'bdb7774a11f7c67c',
        'syncToMaster': '27f3e0c698e2d437', 'startSync': 'f521e40f0ae85c56', 'modifyWebsite': '3e54791374354257', 'deleteWebsite': '69e34877eff62354',
        'siteState': '203d8b9faa4e3627', 'listWebsites': '754542a257c72559', 'listChildDomains': 'a621397dcf5bca14', 'listCron': '9e8b81a3fbe0c94b',
        'domainAlias': '4659932883ddd54d', 'fetchDomains': '2cd9a338e957b14c', 'searchWebsites': 'e5fee6da7251878e', 'fetchWebsitesList': '4e71507821c16c03',
        'installPrestaShop': 'd7768db1ffb57f56', 'installMagento': 'dba5bed40f384ffc', 'installMautic': '7a8f1f1bd5469720', 'setupGit': '076da5a31d52b4d3',
        'changePHP': '44e7493f004f1aa7', 'saveSSL': 'ae0d3af68b2bc2d6', 'sshAccess': '9a7d3c926075e6c5', 'tuneSettings': '648bf26d6593952a',
        'loadWebsitesHome': '78448ca0757e6eff', 'createWebsite': 'a87a42b128ee6202'}
check('the free views are exactly as they were',
      {n: fp(ast.get_source_segment(VIEWS, vfuncs[n])) if n in vfuncs else None for n in VPIN}, VPIN)


# routes
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((n.args[0].value, view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
names = [r[2] for r in table]
check('none of the 42 routes is left', sorted(set(ROUTE_NAMES) & set(names)), [])
check('no route points at a view that does not exist', [r for r in table if r[1] not in vfuncs], [])
check('the free install and staging routes are kept', [n for n in ('wordpressInstall', 'installWordpressStatus', 'installWordpress', 'setupStaging', 'createWebsite', 'listWebsites', 'submitWebsiteCreation', 'CreateNewDomain') if n in names],
      ['wordpressInstall', 'installWordpressStatus', 'installWordpress', 'setupStaging', 'createWebsite', 'listWebsites', 'submitWebsiteCreation', 'CreateNewDomain'])
bad = URLS.replace('    # Website modification', "    path('x', views.WPHome, name='x'),\n    # Website modification")
check('control: a route put back is reported as dangling', [r[1] for r in routes(bad) if r[1] not in vfuncs], ['WPHome'])

# tree-wide
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
REVERSE = re.compile(r"reverse\(\s*['\"]([A-Za-z0-9_:.-]+)['\"]")
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
tag_left, rev_left, call_left, tmpl_left, helper_left, templates = [], [], [], [], [], 0
tmpl_names = ['websiteFunctions/' + t + '.html' for t in TEMPLATES]
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if '.bak' in f or f.startswith('test_') or f.endswith('.min.js') or not f.endswith(('.py', '.html', '.js')):
            continue
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
        if f.endswith('.html'):
            templates += 1
            for line in text.split('\n'):
                if not line.lstrip().startswith('{#'):
                    tag_left += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in ROUTE_NAMES]
            for helper in HELPERS:
                if re.search(r'\b' + helper + r'\b', text):
                    helper_left.append((rel, helper))
        if f.endswith('.py'):
            rev_left += [(rel, m.group(1)) for m in REVERSE.finditer(text) if m.group(1) in ROUTE_NAMES]
            for m in METHODS:
                if re.search(r'\bwm\.' + m + r'\b', text) or re.search(r'WebsiteManager\(\)\.' + m + r'\b', text):
                    call_left.append((rel, m))
            if 'GetStagingInJson' in text:
                call_left.append((rel, 'GetStagingInJson'))
        for t in tmpl_names:
            if t in text:
                tmpl_left.append((rel, t))
        if f.endswith('.js'):
            for helper in HELPERS:
                if re.search(r'\b' + helper + r'\b', text):
                    helper_left.append((rel, helper))
check('no template reverses a removed route outside comments', tag_left, [])
check('the templates were scanned across the tree', templates > 100, True)
check('no code reverses a removed route', rev_left, [])
check('nothing calls a removed manager method or the staging list helper', call_left, [])
check('no code names a removed template', tmpl_left, [])
check('no remaining script or template uses the removed script helpers', helper_left, [])
check('control: a reverse of a removed route would be reported', [m.group(1) for m in REVERSE.finditer("redirect(reverse('pricing'))")], ['pricing'])
check('the 13 templates are gone and the free ones are kept', ([os.path.exists(os.path.join(ROOT, 'websiteFunctions/templates/websiteFunctions/%s.html' % t)) for t in TEMPLATES].count(True),
                                                             all(os.path.exists(os.path.join(ROOT, 'websiteFunctions/templates/websiteFunctions/%s.html' % t)) for t in ('installWordPress', 'setupStaging', 'createWebsite', 'listWebsites', 'website', 'applicationInstaller', 'installJoomla'))), (0, True))
check('the models stay so no upgrade drops data', [m for m in ('WPSites', 'WPStaging', 'WPSitesBackup', 'wpplugins', 'RemoteBackupConfig', 'RemoteBackupSchedule', 'RemoteBackupsites') if 'class ' + m + '(' in read('websiteFunctions/models.py')],
      ['WPSites', 'WPStaging', 'WPSitesBackup', 'wpplugins', 'RemoteBackupConfig', 'RemoteBackupSchedule', 'RemoteBackupsites'])

# helper class
ptree = ast.parse(PHPU)
pcls = next(n for n in ptree.body if isinstance(n, ast.ClassDef) and n.name == 'phpUtilities')
pf = {n.name: n for n in pcls.body if isinstance(n, ast.FunctionDef)}
PPIN = {'installPHPExtension': '51137bd1c25af95f', 'unInstallPHPExtension': 'ddcfd29a51c1b61b', 'initiateInstall': 'cceb39b7d28eb89d', 'initiateRemoval': '42e7e33bdcda86ab',
        'savePHPConfigBasic': 'b92e75634bae5e12', 'savePHPConfigAdvance': '0abf9c43287e861f', 'GetPHPVersionFromFile': '47fbd3176a48d9ea',
        'WrapGetPHPVersionFromFileToGetVersionWithPHP': '7176d744b464d34a', 'FindIfSaidPHPIsAvaiableOtherwiseMaketheNextOneAvailableToUse': '1c4d340ac8af5606',
        'InstallSaidPHP': '8602b81c2821e040'}
check('the staging list helper is gone and the ten PHP helpers are exactly as they were', ('GetStagingInJson' in pf, {n: fp(ast.get_source_segment(PHPU, pf[n])) if n in pf else None for n in PPIN}), (False, PPIN))

# scripts
found = re.findall(r"app\.controller\('([A-Za-z0-9_]+)'", JS)
check('the script keeps exactly the free controllers in order (the Apache page controller is removed in its own change)', [c for c in found if c != 'ApacheManager'],
      ['createWebsite', 'listWebsites', 'listChildDomainsMain', 'deleteWebsiteControl', 'modifyWebsitesController', 'websitePages', 'suspendWebsiteControl',
       'manageCronController', 'manageAliasController', 'launchChild', 'installWordPressCTRL', 'installJoomlaCTRL', 'setupGit', 'installPrestaShopCTRL',
       'installMauticCTRL', 'sshAccess', 'cloneWebsite', 'syncWebsite', 'installMagentoCTRL', 'manageGIT', 'createDockerPackage',
       'AssignPackage', 'createDockerSite', 'listDockersite', 'ListDockersitecontainer'])
check('the removed controllers and the billing redirect are gone and the cookie helper stays',
      ([c for c in CONTROLLERS if "app.controller('" + c + "'" in JS], 'platform.cyber' + 'persons.com' in JS, 'DeployAccount' in JS, 'function getCookie(name)' in JS), ([], False, False, True))
check('the script ends cleanly with one closing line', JS.endswith('})\n') or JS.endswith('});\n'), True)
node = shutil.which('node')
if node:
    check('websiteFunctions.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'websiteFunctions/static/websiteFunctions/websiteFunctions.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

# sidebar
check('the sidebar has no WordPress menu and keeps the neighbours',
      ('sidebar-menu-item-wordpress' in INDEX, "url 'createWordpress'" in INDEX, 'sidebar-menu-item-dockersite' in INDEX, "url 'loadWebsitesHome'" in INDEX, "url 'ListDockerSites'" in INDEX),
      (False, False, True, True, True))
check('control: a left-over reverse in the sidebar would be reported', [m.group(1) for m in URL_TAG.finditer("<a href=\"{% url 'ListWPSites' %}\">") if m.group(1) in ROUTE_NAMES], ['ListWPSites'])

# syntax, endings
for rel in ('websiteFunctions/website.py', 'websiteFunctions/views.py', 'websiteFunctions/urls.py', 'plogical/phpUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('websiteFunctions/website.py', 'websiteFunctions/views.py', 'websiteFunctions/urls.py', 'plogical/phpUtilities.py',
            'websiteFunctions/static/websiteFunctions/websiteFunctions.js', 'baseTemplate/templates/baseTemplate/index.html'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)

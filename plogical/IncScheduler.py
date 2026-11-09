#!/usr/local/CyberCP/bin/python
import os.path
import sys

import paramiko

sys.path.append('/usr/local/CyberCP')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CyberCP.settings")
import django
django.setup()
from plogical.getSystemInformation import SystemInformation
from IncBackups.IncBackupsControl import IncJobs
from IncBackups.models import BackupJob
from random import randint
import argparse
import json
from websiteFunctions.models import GitLogs, Websites
from websiteFunctions.website import WebsiteManager
import time
import datetime
import google.oauth2.credentials
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from plogical.backupSchedule import backupSchedule
import requests
import socket
from websiteFunctions.models import NormalBackupJobs, NormalBackupJobLogs
from boto3.s3.transfer import TransferConfig

try:
    from s3Backups.models import BackupPlan, BackupLogs
    import boto3
    from plogical.virtualHostUtilities import virtualHostUtilities
    from plogical.mailUtilities import mailUtilities
    from plogical.CyberCPLogFileWriter import CyberCPLogFileWriter as logging
    from plogical.processUtilities import ProcessUtilities
except:
    pass
import threading as multi

class IncScheduler(multi.Thread):
    logPath = '/home/cyberpanel/incbackuplogs'
    gitFolder = '/home/cyberpanel/git'

    timeFormat = time.strftime("%m.%d.%Y_%H-%M-%S")

    ### Normal scheduled backups constants

    frequency = 'frequency'
    allSites = 'allSites'
    currentStatus = 'currentStatus'
    lastRun = 'lastRun'

    def __init__(self, function, extraArgs):
        multi.Thread.__init__(self)
        self.function = function
        self.data = extraArgs

    def run(self):
        if self.function == "startBackup":
            IncScheduler.startBackup(self.data['freq'])
        elif self.function == "CalculateAndUpdateDiskUsage":
            IncScheduler.CalculateAndUpdateDiskUsage()

    @staticmethod
    def startBackup(type):
        try:
            logging.statusWriter(IncScheduler.logPath, 'Starting Incremental Backup job..', 1)
            tempPath = "/home/cyberpanel/" + str(randint(1000, 9999))
            for job in BackupJob.objects.all():
                logging.statusWriter(IncScheduler.logPath, 'Job Description:\n\n Destination: %s, Frequency: %s.\n ' % (
                    job.destination, job.frequency), 1)
                if job.frequency == type:


                    ### now run backups
                    for web in job.jobsites_set.all():

                        logging.statusWriter(IncScheduler.logPath, 'Backing up %s.' % (web.website), 1)

                        extraArgs = {}
                        extraArgs['website'] = web.website
                        extraArgs['tempPath'] = tempPath
                        extraArgs['backupDestinations'] = job.destination

                        if job.websiteData == 1:
                            extraArgs['websiteData'] = True
                        else:
                            extraArgs['websiteData'] = False

                        if job.websiteDatabases == 1:
                            extraArgs['websiteDatabases'] = True
                        else:
                            extraArgs['websiteDatabases'] = False

                        if job.websiteDataEmails == 1:
                            extraArgs['websiteEmails'] = True
                        else:
                            extraArgs['websiteEmails'] = False

                        extraArgs['websiteSSLs'] = False

                        startJob = IncJobs('createBackup', extraArgs)
                        startJob.start()

                        ### Checking status

                        while True:
                            if os.path.exists(tempPath):
                                result = open(tempPath, 'r').read()

                                if result.find("Completed") > -1:

                                    ### Removing Files

                                    os.remove(tempPath)

                                    logging.statusWriter(IncScheduler.logPath, 'Backed up %s.' % (web.website), 1)
                                    break
                                elif result.find("[5009]") > -1:
                                    ## removing status file, so that backup can re-runn
                                    try:
                                        os.remove(tempPath)
                                    except:
                                        pass

                                    logging.statusWriter(IncScheduler.logPath,
                                                         'Failed backup for %s, error: %s.' % (web.website, result), 1)
                                    break

        except BaseException as msg:
            logging.writeToFile( "%s [startBackup]"%str(msg))

    @staticmethod
    def git(type):
        try:
            for website in os.listdir(IncScheduler.gitFolder):
                finalText = ''
                web = Websites.objects.get(domain=website)

                message = '[%s Cron] Checking if %s has any pending commits on %s.' % (
                    type, website, time.strftime("%m.%d.%Y_%H-%M-%S"))
                finalText = '%s\n' % (message)
                GitLogs(owner=web, type='INFO', message=message).save()

                finalPathInside = '%s/%s' % (IncScheduler.gitFolder, website)

                for file in os.listdir(finalPathInside):

                    try:

                        ##
                        finalPathConf = '%s/%s' % (finalPathInside, file)

                        gitConf = json.loads(open(finalPathConf, 'r').read())

                        data = {}
                        data['domain'] = gitConf['domain']
                        data['folder'] = gitConf['folder']
                        data['commitMessage'] = 'Auto commit by CyberPanel %s cron on %s' % (
                            type, time.strftime('%m-%d-%Y_%H-%M-%S'))

                        if gitConf['autoCommit'] == type:

                            wm = WebsiteManager()
                            resp = wm.commitChanges(1, data)
                            resp = json.loads(resp.content)

                            if resp['status'] == 1:
                                message = 'Folder: %s, Status: %s' % (gitConf['folder'], resp['commandStatus'])
                                finalText = '%s\n%s' % (finalText, message)
                                GitLogs(owner=web, type='INFO', message=message).save()
                            else:
                                message = 'Folder: %s, Status: %s' % (gitConf['folder'], resp['commandStatus'])
                                finalText = '%s\n%s' % (finalText, message)
                                GitLogs(owner=web, type='ERROR', message=message).save()

                        if gitConf['autoPush'] == type:

                            wm = WebsiteManager()
                            resp = wm.gitPush(1, data)
                            resp = json.loads(resp.content)

                            if resp['status'] == 1:
                                GitLogs(owner=web, type='INFO', message=resp['commandStatus']).save()
                                finalText = '%s\n%s' % (finalText, resp['commandStatus'])
                            else:
                                GitLogs(owner=web, type='ERROR', message=resp['commandStatus']).save()
                                finalText = '%s\n%s' % (finalText, resp['commandStatus'])
                    except BaseException as msg:
                        message = 'File: %s, Status: %s' % (file, str(msg))
                        finalText = '%s\n%s' % (finalText, message)

                message = '[%s Cron] Finished checking for %s on %s.' % (
                    type, website, time.strftime("%m.%d.%Y_%H-%M-%S"))
                finalText = '%s\n%s' % (finalText, message)
                logging.SendEmail(web.adminEmail, web.adminEmail, finalText, 'Git report for %s.' % (web.domain))
                GitLogs(owner=web, type='INFO', message=message).save()

        except BaseException as msg:
            logging.writeToFile('%s. [IncScheduler.git:90]' % (str(msg)))

    @staticmethod
    def checkDiskUsage():
        sender_email = 'root@%s' % (socket.gethostname())

        try:

            import psutil, math
            from websiteFunctions.models import Administrator
            admin = Administrator.objects.get(pk=1)

            diskUsage = math.floor(psutil.disk_usage('/')[3])

            from plogical.acl import ACLManager
            message = '%s - Disk Usage Warning - CyberPanel' % (ACLManager.fetchIP())

            if diskUsage >= 50 and diskUsage <= 60:

                finalText = 'Current disk usage at "/" is %s percent. No action required.' % (str(diskUsage))
                logging.SendEmail(sender_email, admin.email, finalText, message)

            elif diskUsage >= 60 and diskUsage <= 80:

                finalText = 'Current disk usage at "/" is %s percent. We recommend clearing log directory by running \n\n rm -rf /usr/local/lsws/logs/*. \n\n When disk usage go above 80 percent we will automatically run this command.' % (
                    str(diskUsage))
                logging.SendEmail(sender_email, admin.email, finalText, message)

            elif diskUsage > 80:

                finalText = 'Current disk usage at "/" is %s percent. We are going to run below command to free up space, If disk usage is still high, manual action is required by the system administrator. \n\n rm -rf /usr/local/lsws/logs/*.' % (
                    str(diskUsage))
                logging.SendEmail(sender_email, admin.email, finalText, message)

                command = 'rm -rf /usr/local/lsws/logs/*'
                import subprocess
                subprocess.call(command, shell=True)

        except BaseException as msg:
            logging.writeToFile('[IncScheduler:193:checkDiskUsage] %s.' % str(msg))

    @staticmethod
    def startNormalBackups(type):

        from plogical.processUtilities import ProcessUtilities
        from plogical.backupSchedule import backupSchedule
        import socket

        ## SFTP Destination Config sample
        ## {"type": "SFTP", "ip": "ip", "username": "root", "port": "22", "path": "/home/backup"}

        ## Local Destination config sample
        ## {"type": "local", "path": "/home/backup"}

        ## Backup jobs config

        ## {"frequency": "Daily", "allSites": "Selected Only"}
        ## {"frequency": "Daily"}

        for backupjob in NormalBackupJobs.objects.all():

            jobConfig = json.loads(backupjob.config)
            destinationConfig = json.loads(backupjob.owner.config)

            currentTime = time.strftime("%m.%d.%Y_%H-%M-%S")
            print(destinationConfig['type'])

            if destinationConfig['type'] == 'local':


                if jobConfig[IncScheduler.frequency] == type:

                    finalPath = '%s/%s' % (destinationConfig['path'].rstrip('/'), currentTime)
                    command = 'mkdir -p %s' % (finalPath)
                    ProcessUtilities.executioner(command)

                    ### Check if an old job prematurely killed, then start from there.
                    try:
                        oldJobContinue = 1
                        pid = jobConfig['pid']
                        stuckDomain = jobConfig['website']
                        finalPath = jobConfig['finalPath']
                        jobConfig['pid'] = str(os.getpid())

                        command = 'ps aux'
                        result = ProcessUtilities.outputExecutioner(command)

                        if result.find(pid) > -1 and result.find('IncScheduler.py') > -1:
                            quit(1)

                    except:
                        ### Save some important info in backup config
                        oldJobContinue = 0
                        jobConfig['pid'] = str(os.getpid())
                        jobConfig['finalPath'] = finalPath

                    NormalBackupJobLogs.objects.filter(owner=backupjob).delete()
                    NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                        message='Starting %s backup on %s..' % (
                                            type, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                    if oldJobContinue:
                        NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                            message='Will continue old killed job starting from %s.' % (
                                                stuckDomain)).save()

                    actualDomain = 0
                    try:
                        if jobConfig[IncScheduler.allSites] == 'all':
                            websites = Websites.objects.all().order_by('domain')
                            actualDomain = 1
                        else:
                            websites = backupjob.normalbackupsites_set.all().order_by('domain__domain')
                    except:
                        websites = backupjob.normalbackupsites_set.all().order_by('domain__domain')

                    doit = 0

                    for site in websites:
                        if actualDomain:
                            domain = site.domain
                        else:
                            domain = site.domain.domain

                        ## Save currently backing domain in db, so that i can restart from here when prematurely killed

                        jobConfig['website'] = domain
                        jobConfig[IncScheduler.lastRun] = time.strftime("%d %b %Y, %I:%M %p")
                        jobConfig[IncScheduler.currentStatus] = 'Running..'
                        backupjob.config = json.dumps(jobConfig)
                        backupjob.save()

                        if oldJobContinue and not doit:
                            if domain == stuckDomain:
                                doit = 1
                                continue
                            else:
                                continue

                        retValues = backupSchedule.createLocalBackup(domain, '/dev/null')

                        if retValues[0] == 0:
                            NormalBackupJobLogs(owner=backupjob, status=backupSchedule.ERROR,
                                                message='Backup failed for %s on %s.' % (
                                                    domain, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                            SUBJECT = "Automatic backup failed for %s on %s." % (domain, currentTime)
                            adminEmailPath = '/home/cyberpanel/adminEmail'
                            adminEmail = open(adminEmailPath, 'r').read().rstrip('\n')
                            sender = 'root@%s' % (socket.gethostname())
                            TO = [adminEmail]
                            message = """\
From: %s
To: %s
Subject: %s

Automatic backup failed for %s on %s.
""" % (sender, ", ".join(TO), SUBJECT, domain, currentTime)

                            logging.SendEmail(sender, TO, message)
                        else:
                            backupPath = retValues[1] + ".tar.gz"

                            command = 'mv %s %s' % (backupPath, finalPath)
                            ProcessUtilities.executioner(command)

                            NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                                message='Backup completed for %s on %s.' % (
                                                    domain, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                    jobConfig = json.loads(backupjob.config)
                    try:
                        if jobConfig['pid']:
                            del jobConfig['pid']
                    except:
                        pass
                    jobConfig[IncScheduler.currentStatus] = 'Not running'
                    backupjob.config = json.dumps(jobConfig)
                    backupjob.save()
            else:
                if jobConfig[IncScheduler.frequency] == type:
                    print(jobConfig[IncScheduler.frequency])
                    finalPath = '%s/%s' % (destinationConfig['path'].rstrip('/'), currentTime)

                    # import subprocess
                    # import shlex
                    # command = "ssh -o StrictHostKeyChecking=no -p " + destinationConfig[
                    #     'port'] + " -i /root/.ssh/cyberpanel " + destinationConfig['username'] + "@" + \
                    #           destinationConfig[
                    #               'ip'] + " mkdir -p %s" % (finalPath)
                    # subprocess.call(shlex.split(command))

                    ### improved paramiko code
                    private_key_path = '/root/.ssh/cyberpanel'

                    # Create an SSH client
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                    # Load the private key
                    private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

                    # Connect to the server using the private key
                    try:
                        ssh.connect(destinationConfig['ip'], port=int(destinationConfig['port']), username=destinationConfig['username'], pkey=private_key)
                    except BaseException as msg:
                        NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                            message=f'Failed to make sftp connection {str(msg)}').save()

                        print(str(msg))
                        continue

                    try:
                        command = f'find cpbackups -type f -mtime +{jobConfig["retention"]} -exec rm -f {{}} \\;'
                        logging.writeToFile(command)
                        ssh.exec_command(command)
                        command = 'find cpbackups -type d -empty -delete'
                        ssh.exec_command(command)

                    except BaseException as msg:
                        logging.writeToFile(f'Failed to delete old backups, Error {str(msg)}')
                        pass

                    # Execute the command to create the remote directory
                    command = f'mkdir -p {finalPath}'
                    stdin, stdout, stderr = ssh.exec_command(command)

                    # Wait for the command to finish and check for any errors
                    stdout.channel.recv_exit_status()
                    error_message = stderr.read().decode('utf-8')
                    print(error_message)
                    if error_message:
                        NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                            message=f'Error while creating directory on remote server {error_message.strip()}').save()
                        continue
                    else:
                        pass


                    ### Check if an old job prematurely killed, then start from there.
                    # try:
                    #     oldJobContinue = 1
                    #     pid = jobConfig['pid']
                    #     stuckDomain = jobConfig['website']
                    #     finalPath = jobConfig['finalPath']
                    #     jobConfig['pid'] = str(os.getpid())
                    #
                    #     command = 'ps aux'
                    #     result = ProcessUtilities.outputExecutioner(command)
                    #
                    #     if result.find(pid) > -1 and result.find('IncScheduler.py') > -1:
                    #         quit(1)
                    #
                    #
                    # except:
                    #     ### Save some important info in backup config
                    #     oldJobContinue = 0
                    #     jobConfig['pid'] = str(os.getpid())
                    #     jobConfig['finalPath'] = finalPath

                    oldJobContinue = 0
                    jobConfig['pid'] = str(os.getpid())
                    jobConfig['finalPath'] = finalPath

                    NormalBackupJobLogs.objects.filter(owner=backupjob).delete()
                    NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                        message='Starting %s backup on %s..' % (
                                            type, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                    if oldJobContinue:
                        NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                            message='Will continue old killed job starting from %s.' % (
                                                stuckDomain)).save()

                    actualDomain = 0
                    try:
                        if jobConfig[IncScheduler.allSites] == 'all':
                            websites = Websites.objects.all().order_by('domain')
                            actualDomain = 1
                        else:
                            websites = backupjob.normalbackupsites_set.all().order_by('domain__domain')
                    except:
                        websites = backupjob.normalbackupsites_set.all().order_by('domain__domain')

                    doit = 0

                    for site in websites:

                        if actualDomain:
                            domain = site.domain
                        else:
                            domain = site.domain.domain

                        ### If  this website dont exists continue

                        try:
                            Websites.objects.get(domain=domain)
                        except:
                            continue

                        ##

                        ## Save currently backing domain in db, so that i can restart from here when prematurely killed

                        jobConfig['website'] = domain
                        jobConfig[IncScheduler.lastRun] = time.strftime("%d %b %Y, %I:%M %p")
                        jobConfig[IncScheduler.currentStatus] = 'Running..'
                        backupjob.config = json.dumps(jobConfig)
                        backupjob.save()

                        if oldJobContinue and not doit:
                            if domain == stuckDomain:
                                doit = 1
                                continue
                            else:
                                continue

                        retValues = backupSchedule.createLocalBackup(domain, '/dev/null')

                        if retValues[0] == 0:
                            NormalBackupJobLogs(owner=backupjob, status=backupSchedule.ERROR,
                                                message='Backup failed for %s on %s.' % (
                                                    domain, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                            SUBJECT = "Automatic backup failed for %s on %s." % (domain, currentTime)
                            adminEmailPath = '/home/cyberpanel/adminEmail'
                            adminEmail = open(adminEmailPath, 'r').read().rstrip('\n')
                            sender = 'root@%s' % (socket.gethostname())
                            TO = [adminEmail]
                            message = """\
From: %s
To: %s
Subject: %s
Automatic backup failed for %s on %s.
""" % (sender, ", ".join(TO), SUBJECT, domain, currentTime)

                            logging.SendEmail(sender, TO, message)
                        else:
                            backupPath = retValues[1] + ".tar.gz"

                            command = "scp -o StrictHostKeyChecking=no -P " + destinationConfig[
                                'port'] + " -i /root/.ssh/cyberpanel " + backupPath + " " + destinationConfig[
                                          'username'] + "@" + destinationConfig['ip'] + ":%s" % (finalPath)
                            ProcessUtilities.executioner(command)

                            try:
                                os.remove(backupPath)
                            except:
                                pass

                            NormalBackupJobLogs(owner=backupjob, status=backupSchedule.INFO,
                                                message='Backup completed for %s on %s.' % (
                                                    domain, time.strftime("%m.%d.%Y_%H-%M-%S"))).save()

                    jobConfig = json.loads(backupjob.config)
                    try:
                        if jobConfig['pid']:
                            del jobConfig['pid']
                    except:
                        pass
                    jobConfig[IncScheduler.currentStatus] = 'Not running'
                    backupjob.config = json.dumps(jobConfig)
                    backupjob.save()



    @staticmethod
    def fetchAWSKeys():
        path = '/home/cyberpanel/.aws'
        credentials = path + '/credentials'

        data = open(credentials, 'r').readlines()

        aws_access_key_id = data[1].split(' ')[2].strip(' ').strip('\n')
        aws_secret_access_key = data[2].split(' ')[2].strip(' ').strip('\n')
        region = data[3].split(' ')[2].strip(' ').strip('\n')

        return aws_access_key_id, aws_secret_access_key, region

    @staticmethod
    def forceRunAWSBackup(planName):
        try:

            plan = BackupPlan.objects.get(name=planName)
            bucketName = plan.bucket.strip('\n').strip(' ')
            runTime = time.strftime("%d:%m:%Y")

            config = TransferConfig(multipart_threshold=1024 * 25, max_concurrency=10,
                                    multipart_chunksize=1024 * 25, use_threads=True)

            ##

            aws_access_key_id, aws_secret_access_key, region = IncScheduler.fetchAWSKeys()

            ts = time.time()
            retentionSeconds = 86400 * plan.retention

            if region.find('http') > -1:
                s3 = boto3.resource(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    endpoint_url=region
                )
            else:
                s3 = boto3.resource(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                )

            bucket = s3.Bucket(plan.bucket)

            for file in bucket.objects.all():
                result = float(ts - file.last_modified.timestamp())
                if result > retentionSeconds:
                    BackupLogs(owner=plan, level='INFO', timeStamp=time.strftime("%b %d %Y, %H:%M:%S"),
                               msg='File %s expired and deleted according to your retention settings.' % (
                                   file.key)).save()
                    file.delete()

            ###

            if region.find('http') > -1:
                client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    endpoint_url=region
                )
            else:
                client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                )

            ##

            BackupLogs(owner=plan, level='INFO', timeStamp=time.strftime("%b %d %Y, %H:%M:%S"),
                       msg='Starting backup process..').save()

            PlanConfig = json.loads(plan.config)

            for items in plan.websitesinplan_set.all():

                from plogical.backupUtilities import backupUtilities
                tempStatusPath = "/home/cyberpanel/" + str(randint(1000, 9999))
                extraArgs = {}
                extraArgs['domain'] = items.domain
                extraArgs['tempStatusPath'] = tempStatusPath
                extraArgs['data'] = int(PlanConfig['data'])
                extraArgs['emails'] = int(PlanConfig['emails'])
                extraArgs['databases'] = int(PlanConfig['databases'])
                extraArgs['port'] = '0'
                extraArgs['ip'] = '0'
                extraArgs['destinationDomain'] = 'None'
                extraArgs['path'] = '/home/cyberpanel/backups/%s/backup-' % (
                    items.domain) + items.domain + "-" + time.strftime("%m.%d.%Y_%H-%M-%S")

                bu = backupUtilities(extraArgs)
                result, fileName = bu.CloudBackups()

                finalResult = open(tempStatusPath, 'r').read()

                if result == 1:
                    key = plan.name + '/' + items.domain + '/' + fileName.split('/')[-1]
                    client.upload_file(
                        fileName,
                        bucketName,
                        key,
                        Config=config
                    )

                    command = 'rm -f ' + fileName
                    ProcessUtilities.executioner(command)

                    BackupLogs(owner=plan, level='INFO', timeStamp=time.strftime("%b %d %Y, %H:%M:%S"),
                               msg='Backup successful for ' + items.domain + '.').save()
                else:
                    BackupLogs(owner=plan, level='ERROR', timeStamp=time.strftime("%b %d %Y, %H:%M:%S"),
                               msg='Backup failed for ' + items.domain + '. Error: ' + finalResult).save()

            plan.lastRun = runTime
            plan.save()

            BackupLogs(owner=plan, level='INFO', timeStamp=time.strftime("%b %d %Y, %H:%M:%S"),
                       msg='Backup Process Finished.').save()

        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [S3Backups.runBackupPlan]')
            plan = BackupPlan.objects.get(name=planName)
            BackupLogs(owner=plan, timeStamp=time.strftime("%b %d %Y, %H:%M:%S"), level='ERROR', msg=str(msg)).save()

    @staticmethod
    def runAWSBackups(freq):
        try:
            for plan in BackupPlan.objects.all():
                if plan.freq == 'Daily' == freq:
                    IncScheduler.forceRunAWSBackup(plan.name)
        except BaseException as msg:
            logging.writeToFile(str(msg) + ' [S3Backups.runAWSBackups]')

    @staticmethod
    def CalculateAndUpdateDiskUsage():
        for website in Websites.objects.all():
            try:
                try:
                    config = json.loads(website.config)
                except:
                    config = {}

                eDomains = website.domains_set.all()

                for eDomain in eDomains:
                    for email in eDomain.eusers_set.all():
                        emailPath = '/home/vmail/%s/%s' % (website.domain, email.email.split('@')[0])
                        email.DiskUsage = virtualHostUtilities.getDiskUsageofPath(emailPath)
                        email.save()
                        print('Disk Usage of %s is %s' % (email.email, email.DiskUsage))

                config['DiskUsage'], config['DiskUsagePercentage'] = virtualHostUtilities.getDiskUsage(
                    "/home/" + website.domain, website.package.diskSpace)

                # if website.package.enforceDiskLimits:
                #     spaceString = f'{website.package.diskSpace}M {website.package.diskSpace}M'
                #     command = f'setquota -u {website.externalApp} {spaceString} 0 0 /'
                #     ProcessUtilities.executioner(command)
                #     if config['DiskUsagePercentage'] >= 100:
                #         command = 'chattr -R +i /home/%s/' % (website.domain)
                #         ProcessUtilities.executioner(command)
                #
                #         command = 'chattr -R -i /home/%s/logs/' % (website.domain)
                #         ProcessUtilities.executioner(command)
                #
                #         command = 'chattr -R -i /home/%s/.trash/' % (website.domain)
                #         ProcessUtilities.executioner(command)
                #
                #         command = 'chattr -R -i /home/%s/backup/' % (website.domain)
                #         ProcessUtilities.executioner(command)
                #
                #         command = 'chattr -R -i /home/%s/incbackup/' % (website.domain)
                #         ProcessUtilities.executioner(command)
                #     else:
                #         command = 'chattr -R -i /home/%s/' % (website.domain)
                #         ProcessUtilities.executioner(command)

                ## Calculate bw usage

                from plogical.vhost import vhost
                config['bwInMB'], config['bwUsage'] = vhost.findDomainBW(website.domain, int(website.package.bandwidth))

                website.config = json.dumps(config)
                website.save()

            except BaseException as msg:
                logging.writeToFile('%s. [CalculateAndUpdateDiskUsage:753]' % (str(msg)))

    @staticmethod
    def CheckHostName():
        try:
            from loginSystem.models import Administrator
            admin = Administrator.objects.get(pk=1)
            try:
                config = json.loads(admin.config)
            except:
                config = {}

            ### probably need to add temporary dns resolver nameserver here - pending

            try:
                CurrentHostName = config['hostname']
                skipRDNSCheck = config['skipRDNSCheck']
            except:
                CurrentHostName = mailUtilities.FetchPostfixHostname()
                skipRDNSCheck = 1

            virtualHostUtilities.OnBoardingHostName(CurrentHostName, '/home/cyberpanel/onboarding_temp_path', skipRDNSCheck)
        except BaseException as msg:
            logging.writeToFile(f'{str(msg)}. [Cron.CheckHostName]')

def main():
    parser = argparse.ArgumentParser(description='CyberPanel Installer')
    parser.add_argument('function', help='Specific a function to call!')
    parser.add_argument('--planName', help='Plan name for AWS!')
    args = parser.parse_args()

    if args.function == 'UpdateDiskUsageForce':
        IncScheduler.CalculateAndUpdateDiskUsage()
        return 0

    if args.function == '30 Minutes' or args.function == '1 Hour' or args.function == '6 Hours' or args.function == '12 Hours' or args.function == '1 Day' or args.function == '3 Days' or args.function == '1 Week':
        # IncScheduler.refresh_access_token()

        return 0

    if args.function == 'forceRunAWSBackup':
        IncScheduler.forceRunAWSBackup(args.planName)
        return 0

    IncScheduler.CalculateAndUpdateDiskUsage()

    if args.function == 'Weekly':
        try:
            IncScheduler.FixMailSSL()
        except:
            pass

    ### Run incremental backups in sep thread

    ib = IncScheduler('startBackup', {'freq': args.function})
    ib.start()

    ###

    IncScheduler.startBackup(args.function)

    IncScheduler.git(args.function)
    IncScheduler.checkDiskUsage()
    IncScheduler.startNormalBackups(args.function)
    IncScheduler.runAWSBackups(args.function)
    IncScheduler.CheckHostName()

    ib.join()



if __name__ == "__main__":
    main()

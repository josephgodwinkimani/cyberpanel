#!/usr/local/CyberCP/bin/python
import os.path
import sys
import django
sys.path.append('/usr/local/CyberCP')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CyberCP.settings")
django.setup()
from django.http import HttpResponse
import json
from plogical.acl import ACLManager
import plogical.CyberCPLogFileWriter as logging
from plogical.mysqlUtilities import mysqlUtilities
from websiteFunctions.models import Websites
from databases.models import Databases, DBMeta
import argparse
from loginSystem.models import Administrator
import plogical.randomPassword as randomPassword
from plogical.httpProc import httpProc
from backup.models import DBUsers

class DatabaseManager:

    REMOTE_ACCESS = 'remote_access'

    def loadDatabaseHome(self, request = None, userID = None):
        template = 'databases/index.html'
        proc = httpProc(request, template, None, 'createDatabase')
        return proc.render()

    def phpMyAdmin(self, request = None, userID = None):
        template = 'databases/phpMyAdmin.html'
        proc = httpProc(request, template, None, 'createDatabase')
        return proc.render()

    def createDatabase(self, request = None, userID = None):
        currentACL = ACLManager.loadedACL(userID)
        websitesName = ACLManager.findAllSites(currentACL, userID)
        template = 'databases/createDatabase.html'
        proc = httpProc(request, template, {'websitesList': websitesName}, 'createDatabase')
        return proc.render()

    def submitDBCreation(self, userID = None, data = None, rAPI = None):
        try:

            currentACL = ACLManager.loadedACL(userID)
            admin = Administrator.objects.get(pk=userID)
            if ACLManager.currentContextPermission(currentACL, 'createDatabase') == 0:
                return ACLManager.loadErrorJson('createDBStatus', 0)

            databaseWebsite = data['databaseWebsite']
            dbName = data['dbName']
            dbUsername = data['dbUsername']
            dbPassword = data['dbPassword']
            webUsername = data['webUserName']

            if ACLManager.checkOwnership(databaseWebsite, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            if rAPI == None:
                dbName = webUsername + "_" + dbName
                dbUsername = webUsername + "_" + dbUsername

            result = mysqlUtilities.submitDBCreation(dbName, dbUsername, dbPassword, databaseWebsite)

            if result[0] == 1:
                data_ret = {'status': 1, 'createDBStatus': 1, 'error_message': "None"}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)
            else:
                data_ret = {'status': 0, 'createDBStatus': 0, 'error_message': result[1]}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)
        except BaseException as msg:
            data_ret = {'status': 0, 'createDBStatus': 0, 'error_message': str(msg)}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

    def deleteDatabase(self, request = None, userID = None):
        currentACL = ACLManager.loadedACL(userID)
        websitesName = ACLManager.findAllSites(currentACL, userID)
        template = 'databases/deleteDatabase.html'
        proc = httpProc(request, template, {'websitesList': websitesName}, 'deleteDatabase')
        return proc.render()

    def fetchDatabases(self, userID = None, data = None):
        try:

            currentACL = ACLManager.loadedACL(userID)
            if ACLManager.currentContextPermission(currentACL, 'deleteDatabase') == 0:
                return ACLManager.loadErrorJson('fetchStatus', 0)

            databaseWebsite = data['databaseWebsite']

            admin = Administrator.objects.get(pk=userID)
            if ACLManager.checkOwnership(databaseWebsite, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            website = Websites.objects.get(domain=databaseWebsite)
            databases = Databases.objects.filter(website=website)

            json_data = "["
            checker = 0

            for items in databases:
                dic = {'id': items.pk,
                       'dbName': items.dbName,
                       'dbUser': items.dbUser, }

                if checker == 0:
                    json_data = json_data + json.dumps(dic)
                    checker = 1
                else:
                    json_data = json_data + ',' + json.dumps(dic)

            json_data = json_data + ']'

            final_json = json.dumps({'status': 1, 'fetchStatus': 1, 'error_message': "None", "data": json_data})

            return HttpResponse(final_json)
        except BaseException as msg:
            logging.CyberCPLogFileWriter.writeToFile(str(msg))
            final_json = json.dumps({'status': 0, 'fetchStatus': 0, 'error_message': str(msg)})
            return HttpResponse(final_json)

    def submitDatabaseDeletion(self, userID = None, data = None):
        try:
            currentACL = ACLManager.loadedACL(userID)
            admin = Administrator.objects.get(pk=userID)
            if ACLManager.currentContextPermission(currentACL, 'deleteDatabase') == 0:
                return ACLManager.loadErrorJson('deleteStatus', 0)

            dbName = data['dbName']
            db = Databases.objects.get(dbName=dbName)

            if ACLManager.checkOwnership(db.website.domain, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            result = mysqlUtilities.submitDBDeletion(dbName)

            if result[0] == 1:
                data_ret = {'status': 1, 'deleteStatus': 1, 'error_message': "None"}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)
            else:
                data_ret = {'status': 0, 'deleteStatus': 0, 'error_message': result[1]}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)

        except BaseException as msg:
            data_ret = {'status': 0, 'deleteStatus': 0, 'error_message': str(msg)}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

    def listDBs(self, request = None, userID = None):
        currentACL = ACLManager.loadedACL(userID)
        AllWebsites = ACLManager.findAllSites(currentACL, userID)
        template = 'databases/listDataBases.html'
        proc = httpProc(request, template, {'AllWebsites': AllWebsites}, 'listDatabases')
        return proc.render()

    def changePassword(self, userID = None, data = None):
        try:
            currentACL = ACLManager.loadedACL(userID)

            if ACLManager.currentContextPermission(currentACL, 'listDatabases') == 0:
                return ACLManager.loadErrorJson('changePasswordStatus', 0)

            userName = data['dbUserName']
            dbPassword = data['dbPassword']

            db = Databases.objects.filter(dbUser=userName)

            admin = Administrator.objects.get(pk=userID)

            if ACLManager.checkOwnership(db[0].website.domain, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            try:
                meta = DBMeta.objects.get(database=db[0], key=DatabaseManager.REMOTE_ACCESS)
                host = json.loads(meta.value)['remoteIP']
            except:
                host = None

            res = mysqlUtilities.changePassword(userName, dbPassword, None, host)

            if res == 0:
                data_ret = {'status': 0, 'changePasswordStatus': 0,'error_message': "Please see CyberPanel main log file."}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)

            data_ret = {'status': 1, 'changePasswordStatus': 1, 'error_message': "None"}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

        except BaseException as msg:
            data_ret = {'status': 0, 'changePasswordStatus': 0, 'error_message': str(msg)}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

    def remoteAccess(self, userID = None, data = None):
        try:
            currentACL = ACLManager.loadedACL(userID)

            if ACLManager.currentContextPermission(currentACL, 'listDatabases') == 0:
                return ACLManager.loadErrorJson('changePasswordStatus', 0)

            userName = data['dbUserName']

            db = Databases.objects.filter(dbUser=userName)

            admin = Administrator.objects.get(pk=userID)
            if ACLManager.checkOwnership(db[0].website.domain, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            try:
                meta = DBMeta.objects.get(database=db[0], key=DatabaseManager.REMOTE_ACCESS)
                data_ret = {'status': 1, 'dbHost': json.loads(meta.value)['remoteIP']}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)

            except BaseException as msg:
                data_ret = {'status': 1, 'dbHost': 'localhost'}
                json_data = json.dumps(data_ret)
                return HttpResponse(json_data)

        except BaseException as msg:
            data_ret = {'status': 0,'error_message': str(msg)}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

    def allowRemoteIP(self, userID = None, data = None):
        try:
            currentACL = ACLManager.loadedACL(userID)

            if ACLManager.currentContextPermission(currentACL, 'listDatabases') == 0:
                return ACLManager.loadErrorJson('changePasswordStatus', 0)

            userName = data['dbUserName']
            remoteIP = data['remoteIP']

            db = Databases.objects.filter(dbUser=userName)

            admin = Administrator.objects.get(pk=userID)

            if ACLManager.checkOwnership(db[0].website.domain, admin, currentACL) == 1:
                pass
            else:
                return ACLManager.loadErrorJson()

            mysqlUtilities.allowRemoteAccess(db[0].dbName, userName, remoteIP)
            mysqlUtilities.createDatabase(db[0].dbName, userName, 'cyberpanel', 0, remoteIP)
            dbUserInMysql = DBUsers.objects.get(user=userName, host='localhost')
            mysqlUtilities.changePassword(userName, dbUserInMysql.password, 1, remoteIP)

            metaData = {'remoteIP': remoteIP}

            try:
                meta = DBMeta.objects.get(database=db[0], key=DatabaseManager.REMOTE_ACCESS)
                meta.value = json.dumps(metaData)
                meta.save()
            except:
                DBMeta(database=db[0], value = json.dumps(metaData), key=DatabaseManager.REMOTE_ACCESS).save()

            data_ret = {'status': 1}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

        except BaseException as msg:
            data_ret = {'status': 0,'error_message': str(msg)}
            json_data = json.dumps(data_ret)
            return HttpResponse(json_data)

    @staticmethod
    def generatePHPMYAdminData(userID):
        try:

            admin = Administrator.objects.get(id=userID)
            path = '/etc/cyberpanel/' + admin.userName


            currentACL = ACLManager.loadedACL(userID)
            websiteOBJs = ACLManager.findWebsiteObjects(currentACL, userID)
            finalUserPassword = randomPassword.generate_pass()

            writeToFile = open(path, 'w')
            writeToFile.write(finalUserPassword)
            writeToFile.close()

            mysqlUtilities.createDBUser(admin.userName, finalUserPassword)
            mysqlUtilities.changePassword(admin.userName, finalUserPassword)

            for webs in websiteOBJs:
                for db in webs.databases_set.all():
                    mysqlUtilities.allowGlobalUserAccess(admin.userName, db.dbName)

            print("1," + finalUserPassword)

        except BaseException as msg:
            print("0," + str(msg))

def main():

    parser = argparse.ArgumentParser(description='CyberPanel Installer')
    parser.add_argument('function', help='Specific a function to call!')

    parser.add_argument('--userID', help='Logged in user ID')


    args = parser.parse_args()

    if args.function == "generatePHPMYAdminData":
        DatabaseManager.generatePHPMYAdminData(int(args.userID))


if __name__ == "__main__":
    main()
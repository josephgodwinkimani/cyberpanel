from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.serverStatusHome, name='serverStatusHome'),
    url(r'^litespeedStatus$', views.litespeedStatus, name='litespeedStatus'),
    url(r'^startorstopLitespeed$', views.stopOrRestartLitespeed, name='startorstopLitespeed'),
    url(r'^cyberCPMainLogFile$', views.cyberCPMainLogFile, name='cyberCPMainLogFile'),
    url(r'^getFurtherDataFromLogFile$',views.getFurtherDataFromLogFile,name='getFurtherDataFromLogFile'),

    url(r'^servicesStatus$', views.servicesStatus, name='servicesStatus'),
    url(r'^servicesAction$', views.servicesAction, name='servicesAction'),
    url(r'^services$', views.services, name='services'),
    url(r'^switchTOLSWS$', views.switchTOLSWS, name='switchTOLSWS'),
    url(r'^switchTOLSWSStatus$', views.switchTOLSWSStatus, name='switchTOLSWSStatus'),
    url(r'^licenseStatus$', views.licenseStatus, name='licenseStatus'),
    url(r'^changeLicense$', views.changeLicense, name='changeLicense'),
    url(r'^refreshLicense$', views.refreshLicense, name='refreshLicense'),
    url(r'^topProcesses$', views.topProcesses, name='topProcesses'),
    url(r'^topProcessesStatus$', views.topProcessesStatus, name='topProcessesStatus'),
    url(r'^killProcess$', views.killProcess, name='killProcess'),
    url(r'^packageManager$', views.packageManager, name='packageManager'),
    url(r'^fetchPackages$', views.fetchPackages, name='fetchPackages'),
    url(r'^fetchPackageDetails$', views.fetchPackageDetails, name='fetchPackageDetails'),
    url(r'^updatePackage$', views.updatePackage, name='updatePackage'),
    url(r'^lockStatus$', views.lockStatus, name='lockStatus'),
    url(r'^CyberPanelPort$', views.CyberPanelPort, name='CyberPanelPort'),
    url(r'^submitPortChange$', views.submitPortChange, name='submitPortChange'),

]
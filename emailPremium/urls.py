from django.urls import path, re_path
from . import views

urlpatterns = [
    path('emailPolicyServer', views.emailPolicyServer, name='emailPolicyServer'),
    path('listDomains', views.listDomains, name='listDomains'),
    path('getFurtherDomains', views.getFurtherDomains, name='getFurtherDomains'),
    path('enableDisableEmailLimits', views.enableDisableEmailLimits, name='enableDisableEmailLimits'),
    path('changeDomainLimit', views.changeDomainLimit, name='changeDomainLimit'),
    path('getFurtherEmail', views.getFurtherEmail, name='getFurtherEmail'),
    path('enableDisableIndividualEmailLimits', views.enableDisableIndividualEmailLimits, name='enableDisableIndividualEmailLimits'),
    re_path(r'(?P<emailAddress>\w+@.+)', views.emailPage, name='emailPage'),
    path('getEmailStats', views.getEmailStats, name='getEmailStats'),
    path('enableDisableIndividualEmailLogs', views.enableDisableIndividualEmailLogs, name='enableDisableIndividualEmailLogs'),
    path('changeDomainEmailLimitsIndividual', views.changeDomainEmailLimitsIndividual, name='changeDomainEmailLimitsIndividual'),
    path('getEmailLogs', views.getEmailLogs, name='getEmailLogs'),
    path('flushEmailLogs', views.flushEmailLogs, name='flushEmailLogs'),

    # SpamAssassin
    path('SpamAssassin', views.spamAssassinHome, name='SpamAssassin'),
    path('installSpamAssassin', views.installSpamAssassin, name='installSpamAssassin'),
    path('installStatusSpamAssassin', views.installStatusSpamAssassin, name='installStatusSpamAssassin'),
    path('fetchSpamAssassinSettings', views.fetchSpamAssassinSettings, name='fetchSpamAssassinSettings'),
    path('saveSpamAssassinConfigurations', views.saveSpamAssassinConfigurations, name='saveSpamAssassinConfigurations'),
    path('fetchPolicyServerStatus', views.fetchPolicyServerStatus, name='fetchPolicyServerStatus'),
    path('savePolicyServerStatus', views.savePolicyServerStatus, name='savePolicyServerStatus'),
    path('mailQueue', views.mailQueue, name='mailQueue'),
    path('fetchMailQueue', views.fetchMailQueue, name='fetchMailQueue'),
    path('fetchMessage', views.fetchMessage, name='fetchMessage'),
    path('flushQueue', views.flushQueue, name='flushQueue'),
    path('delete', views.delete, name='delete'),
    path('MailScanner', views.MailScanner, name='MailScanner'),
    path('installMailScanner', views.installMailScanner, name='installMailScanner'),
    path('installStatusMailScanner', views.installStatusMailScanner, name='installStatusMailScanner'),


    path('statusFunc', views.statusFunc, name='statusFunc'),
    re_path(r'^(?P<domain>.*)$', views.emailLimits, name='emailLimits'),
]

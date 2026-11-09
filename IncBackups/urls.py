from django.urls import path
from . import views

urlpatterns = [
    path('createBackup', views.create_backup, name='createBackupInc'),
    path('restoreRemoteBackups', views.restore_remote_backups, name='restoreRemoteBackupsInc'),
    path('backupDestinations', views.backup_destinations, name='backupDestinationsInc'),
    path('addDestination', views.add_destination, name='addDestinationInc'),
    path('populateCurrentRecords', views.populate_current_records, name='populateCurrentRecordsInc'),
    path('removeDestination', views.remove_destination, name='removeDestinationInc'),
    path('fetchCurrentBackups', views.fetch_current_backups, name='fetchCurrentBackupsInc'),
    path('submitBackupCreation', views.submit_backup_creation, name='submitBackupCreationInc'),
    path('getBackupStatus', views.get_backup_status, name='getBackupStatusInc'),
    path('deleteBackup', views.delete_backup, name='deleteBackupInc'),
    path('fetchRestorePoints', views.fetch_restore_points, name='fetchRestorePointsInc'),
    path('restorePoint', views.restore_point, name='restorePointInc'),
    path('scheduleBackups', views.schedule_backups, name='scheduleBackupsInc'),
    path('submitBackupSchedule', views.submit_backup_schedule, name='submitBackupScheduleInc'),
    path('scheduleDelete', views.schedule_delete, name='scheduleDeleteInc'),
    path('getCurrentBackupSchedules', views.get_current_backup_schedules, name='getCurrentBackupSchedulesInc'),
    path('fetchSites', views.fetch_sites, name='fetchSites'),
    path('saveChanges', views.save_changes, name='saveChanges'),
    path('removeSite', views.remove_site, name='removeSite'),
    path('addWebsite', views.add_website, name='addWebsite'),
]

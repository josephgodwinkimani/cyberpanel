from django.urls import path
from . import views

urlpatterns = [
    path('upload', views.upload, name='upload'),
    path('changePermissions', views.changePermissions, name='changePermissions'),
    path('controller', views.controller, name='controller'),
    path('downloadFile', views.downloadFile, name='downloadFile'),
    path('editFile', views.editFile, name='editFile'),
    path('<domain>', views.loadFileManagerHome, name='loadFileManagerHome'),
]

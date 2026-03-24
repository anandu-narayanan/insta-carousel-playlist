from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/process/', views.process, name='process'),
    path('download/<str:session_id>/<str:filename>/', views.download_file, name='download'),
]

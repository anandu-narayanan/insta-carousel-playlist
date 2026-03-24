from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/process/', views.process, name='process'),
    path('api/status/<str:job_id>/', views.job_status, name='job_status'),
    path('download/<str:session_id>/<path:filepath>/', views.download_file, name='download'),
]


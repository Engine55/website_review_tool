from django.urls import path
from search_link import views

urlpatterns = [
    # path('', views.search, name='search'),
    path('search_link/', views.search_link, name='search_link'),  # Search page
    path('results/<uuid:job_id>/', views.results, name='results'),
    path('job_status/<str:job_id>/', views.job_status, name='job_status'),
]
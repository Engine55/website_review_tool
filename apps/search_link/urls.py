from django.urls import path
from search_link import views

urlpatterns = [
    # path('', views.search, name='search'),
    path('search_link/', views.search_link, name='search_link'),  # Search page
]
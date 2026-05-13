from django.urls import path
from EMSwebsite.controllers.positions import positions, add_position, update_position, delete_position

urlpatterns = [
    path('positions/', positions, name='positions'),
    path('positions/add/', add_position, name='add_position'),
    path('positions/update/<int:pk>/', update_position, name='update_position'),
    path('positions/delete/<int:pk>/', delete_position, name='delete_position'),
]

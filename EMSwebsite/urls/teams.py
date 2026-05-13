from django.urls import path
from EMSwebsite.views.teams import (
    team, add_team, team_details, team_members_attendance, update_team,
    add_team_members, remove_team_member, available_employees, add_project,
    delete_team, employee_details,
)

urlpatterns = [
    path('team/', team, name='team'),
    path('teams/', team, name='teams'),
    path('teams/add/', add_team, name='add_team'),
    path('teams/<int:team_id>/details/', team_details, name='team_details'),
    path('teams/<int:team_id>/attendance/', team_members_attendance, name='team_members_attendance'),
    path('teams/update/', update_team, name='update_team'),
    path('teams/add-members/', add_team_members, name='add_team_members'),
    path('teams/remove-member/', remove_team_member, name='remove_team_member'),
    path('teams/<int:team_id>/delete/', delete_team, name='delete_team'),
    path('teams/add-project/', add_project, name='add_project'),
    path('employees/available/', available_employees, name='available_employees'),
]

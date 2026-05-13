from django.urls import path
from EMSwebsite.controllers.ai_assistant import ai_assistant, ai_chat_api
from EMSwebsite.controllers.complaints import policy_management, submit_complaint, view_complaints, respond_to_complaint

urlpatterns = [
    # AI Assistant
    path('ai-assistant/', ai_assistant, name='ai_assistant'),
    path('api/ai-chat/', ai_chat_api, name='ai_chat_api'),

    # Policy Management
    path('policies/', policy_management, name='policy_management'),

    # Complaints
    path('complaints/', view_complaints, name='view_complaints'),
    path('complaints/submit/', submit_complaint, name='submit_complaint'),
    path('complaints/<int:complaint_id>/respond/', respond_to_complaint, name='respond_to_complaint'),
]

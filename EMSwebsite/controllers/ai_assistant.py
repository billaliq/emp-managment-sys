from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta, date, time
from django.views.decorators.http import require_http_methods, require_POST
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
import json
import csv
import re
import logging

logger = logging.getLogger(__name__)

from EMSwebsite.models import (
    Employees, Department, Position, Attendance, AttendanceSettings, LeaveRequest, HolidayDate,
    Team, TeamMember, Project, Payroll, PayrollRecord, SalaryIncrement, SystemSettings,
    Loan, LoanRepayment, LoanPool, LoanPoolTransaction, UserProfile, SalaryDisbursement, SalaryDisbursementRecord,
    IncrementSettings, Notification, EmployeeAdditionalDocument, SalarySlipRequest,
    Policy, Complaint, AIChatMessage, ZKDevice, AttendanceLog,
    Report, ReportTemplate, ReportSchedule,
)
from .helpers import (
    validate_date, get_current_employee, scope_by_user, only_me_employee_qs,
    role_required, admin_required, hr_or_admin_required, finance_or_admin_required,
    has_valid_attendance_exception, auto_mark_absent_for_date, sync_attendance_with_holidays,
)
from EMSwebsite.context_processors import get_notifications


def ai_assistant(request):
    """Main AI assistant chat interface"""
    from django.db import ProgrammingError

    user = request.user
    try:
        profile = user.profile
        user_role = profile.role
    except UserProfile.DoesNotExist:
        user_role = 'employee'

    # Get recent chat history (last 20 messages)
    # Handle case where AIChatMessage table doesn't exist
    try:
        recent_messages = AIChatMessage.objects.filter(user=user).order_by('-created_at')[:20]
        recent_messages = list(reversed(recent_messages))
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (migration not run)
        recent_messages = []

    # Get available policies for reference
    try:
        policies = Policy.objects.filter(is_active=True).order_by('-effective_date')
    except (ProgrammingError, Exception):
        # Policy table might not exist either
        policies = []

    context = {
        'user_role': user_role,
        'recent_messages': recent_messages,
        'policies': policies,
    }
    return render(request, 'pages/ai_assistant.html', context)


@login_required
@require_POST
def ai_chat_api(request):
    """API endpoint for AI chat responses"""
    import os
    from django.conf import settings

    # Try to import OpenAI (optional dependency)
    try:
        import openai  # type: ignore
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False

    user = request.user
    try:
        profile = user.profile
        user_role = profile.role
    except UserProfile.DoesNotExist:
        user_role = 'employee'

    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Message is required'}, status=400)

    # Get user's employee record if exists
    employee = None
    try:
        employee = user.employee
    except:
        pass

    # Build system prompt based on user role and employee context
    system_prompt = build_ai_system_prompt(user_role, employee)

    # Get compact, structured policies context to keep prompts efficient
    policies_context = get_policies_context(max_items=10)

    # Get recent conversation history
    # Handle case where AIChatMessage table doesn't exist
    from django.db import ProgrammingError
    try:
        recent_history = AIChatMessage.objects.filter(user=user).order_by('-created_at')[:10]
        conversation_history = []
        for msg in reversed(recent_history):
            conversation_history.append({
                'role': 'user' if msg.message_type == 'user' else 'assistant',
                'content': msg.message if msg.message_type == 'user' else msg.response
            })
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (migration not run)
        conversation_history = []

    # Add current message
    conversation_history.append({'role': 'user', 'content': message})

    try:
        # Try to use OpenAI API if configured
        api_key = os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)

        if api_key and OPENAI_AVAILABLE:
            try:
                client = openai.OpenAI(api_key=api_key)

                messages = [
                    {
                        'role': 'system',
                        'content': system_prompt + '\n\n' + policies_context
                    }
                ] + conversation_history

                response = client.chat.completions.create(
                    # Prefer a stronger reasoning model if configured, with sensible default
                    model=os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
                    messages=messages,
                    # Slightly lower temperature for more consistent, policy-aligned answers
                    temperature=0.5,
                    # Keep responses focused and efficient
                    max_tokens=700
                )

                ai_response = response.choices[0].message.content
            except Exception as openai_error:
                logger.warning(f"OpenAI API error: {openai_error}, falling back to rule-based response")
                ai_response = generate_rule_based_response(message, user_role, policies_context)
        else:
            # Fallback to rule-based responses if OpenAI is not configured
            ai_response = generate_rule_based_response(message, user_role, policies_context)

        # Save conversation (if table exists)
        try:
            AIChatMessage.objects.create(
                user=user,
                message=message,
                response=ai_response,
                message_type='user',
                context={'role': user_role}
            )
        except (ProgrammingError, Exception):
            # Table doesn't exist yet (migration not run) - skip saving
            pass

        return JsonResponse({
            'response': ai_response,
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error in AI chat API: {e}")
        # Fallback to rule-based response
        ai_response = generate_rule_based_response(message, user_role, policies_context)

        # Save conversation (if table exists)
        try:
            AIChatMessage.objects.create(
                user=user,
                message=message,
                response=ai_response,
                message_type='user',
                context={'role': user_role, 'error': str(e)}
            )
        except (ProgrammingError, Exception):
            # Table doesn't exist yet (migration not run) - skip saving
            pass

        return JsonResponse({
            'response': ai_response,
            'status': 'success'
        })


def build_ai_system_prompt(user_role, employee=None):
    """
    Build a compact but expressive system prompt based on user role and employee context.

    The goal is:
    - Strong reasoning and problem-solving
    - Clear, efficient answers (no unnecessary fluff)
    - Role-aware behavior (admin/hr vs employee)
    """
    # Basic employee context to help the model personalize and reason better
    employee_context = ""
    if employee is not None:
        emp_name = f"{employee.firstname} {employee.lastname or ''}".strip()
        emp_dept = getattr(getattr(employee, "department", None), "name", None)
        emp_pos = getattr(getattr(employee, "position", None), "name", None)
        context_bits = [f"Name: {emp_name or 'N/A'}", f"Code: {employee.code or employee.pk}"]
        if emp_dept:
            context_bits.append(f"Department: {emp_dept}")
        if emp_pos:
            context_bits.append(f"Position: {emp_pos}")
        employee_context = "Current logged-in employee context: " + ", ".join(context_bits) + "."

    base_prompt = (
        "You are an advanced AI Employee Support Assistant integrated into an Employee Information System.\n"
        "You must: reason carefully about company policies and HR processes, ask clarifying questions when the request\n"
        "is ambiguous, and give step-by-step guidance in a concise, business-appropriate way.\n\n"
        f"{employee_context}\n\n"
        "General behavior rules:\n"
        "- Prefer short, clear paragraphs and bullet points over long essays.\n"
        "- When rules or policies might conflict, explain the trade-offs and suggest what the employee should verify with HR.\n"
        "- When you are unsure or information is missing, explicitly say so and propose what the user should check next.\n"
        "- Do NOT invent company-specific data that is not in the policies context; instead, state assumptions clearly.\n"
    )

    if user_role in ['admin', 'hr']:
        prompt = base_prompt + """
Role: Admin / HR / Super User

You can:
- Explain and reference existing company policies.
- Help plan how to update or add policies, but you do NOT actually perform database changes.
- Suggest what information to collect for new policies (title, category, effective date, summary, key rules).
- Help structure announcements and internal communication to employees about policies, leave, loans, and benefits.

When an admin/HR user is drafting or changing a policy:
- Ask follow-up questions to clarify missing details.
- Propose a clean, structured summary and 3–7 bullet key points.
- Highlight any edge cases employees commonly misunderstand.

When responding:
- Be pragmatic and action-oriented.
- If the request sounds like it needs legal/HR approval, clearly say that final decision belongs to HR/management.
"""
    else:
        prompt = base_prompt + """
Role: Employee Assistant (regular employee user)

You can:
- Answer questions about company policies using the provided policy context.
- Explain leave types, basic loan concepts, and benefits at a high level.
- Guide employees on how to submit complaints and who usually handles them.
- Help employees reason about what to do in tricky situations (e.g., conflicts, attendance or leave issues) while
  reminding them that final decisions belong to HR/management.

You CANNOT:
- Add or modify policies.
- Approve or deny loans, benefits, or complaints.
- Access or reveal confidential employee data.

Response style:
- Professional, respectful, and supportive.
- Focus on the concrete next steps the employee should take in the system or with HR/management.
"""

    # Encourage internal reasoning without exposing chain-of-thought
    prompt += (
        "\nInternal reasoning guidelines (do NOT show this directly to the user):\n"
        "- Break down complex questions into smaller parts, reason step-by-step internally, and then give a polished answer.\n"
        "- If a question mixes multiple topics (e.g., leave + loans), address them in a structured way.\n"
        "- Prefer deterministic answers aligned with policies over creative writing.\n"
    )

    return prompt


def get_policies_context(max_items=10):
    """
    Get a compact, structured policies context for the AI.

    To keep prompts efficient, we only include up to `max_items` of the most recent active policies,
    with short summaries that are easy for the model to use for reasoning.
    """
    policies = Policy.objects.filter(is_active=True).order_by('-effective_date')[:max_items]
    if not policies:
        return "Policies context: No active policies are currently defined in the system."

    context_lines = ["Policies context (for AI reasoning, not shown directly to the user):"]
    for idx, policy in enumerate(policies, start=1):
        category = getattr(policy, "get_category_display_name", None)
        category_name = category() if callable(category) else getattr(policy, "category", "Unspecified")
        summary = (policy.summary or "").strip()
        short_summary = summary[:220] + ("..." if len(summary) > 220 else "")
        context_lines.append(
            f"{idx}. {policy.title} "
            f"(Category: {category_name}, Effective: {policy.effective_date}): {short_summary}"
        )

    return "\n".join(context_lines)


def generate_rule_based_response(message, user_role, policies_context):
    """Generate rule-based response when AI API is not available"""
    message_lower = message.lower()

    # Policy-related queries
    if any(word in message_lower for word in ['policy', 'policies', 'rule', 'rules', 'regulation']):
        policies = Policy.objects.filter(is_active=True)
        if policies.exists():
            response = "Here are the available company policies:\n\n"
            for policy in policies[:5]:
                response += f"• {policy.title} ({policy.get_category_display_name()})\n"
                response += f"  Effective: {policy.effective_date}\n"
                response += f"  Summary: {policy.summary[:150]}...\n\n"
            response += "Would you like more details about any specific policy?"
        else:
            response = "No policies are currently available. Please contact HR for policy information."

    # Loan-related queries
    elif any(word in message_lower for word in ['loan', 'borrow', 'lending']):
        response = """Loan Information:
- Loan eligibility: Up to 1.5x your monthly salary
- Required documents: Application form, salary slip
- Repayment: Monthly installments as per agreement
- Approval: Handled by HR/Finance department

For specific loan applications, please contact HR or Finance department."""

    # Leave-related queries
    elif any(word in message_lower for word in ['leave', 'vacation', 'holiday', 'time off']):
        response = """Leave Policy Information:
- Leave types: Sick, Casual, Annual, Maternity, Paternity, Emergency, Unpaid
- Application: Submit leave request through the system
- Approval: Requires manager/HR approval
- For detailed leave policy, please check the Leave Policy document or contact HR."""

    # Complaint-related queries
    elif any(word in message_lower for word in ['complaint', 'grievance', 'issue', 'problem']):
        response = """I can help you submit a complaint. Please provide:
1. Complaint title
2. Description of the issue
3. Related department (if applicable)

Would you like to submit a complaint now?"""

    # Benefits-related queries
    elif any(word in message_lower for word in ['benefit', 'benefits', 'perk', 'perks']):
        response = """Benefits Information:
- Benefits are managed by HR department
- Common benefits may include: Health insurance, Retirement plans, Professional development
- For specific benefits information, please contact HR or check the Benefits Policy document."""

    # Default response
    else:
        response = """I'm here to help you with:
- Company policies and rules
- Leave information
- Loan information
- Benefits information
- Submitting complaints

How can I assist you today?"""

    return response
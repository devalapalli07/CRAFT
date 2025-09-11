from django import forms
from django.shortcuts import  redirect, render
from django.http import JsonResponse
from django.db.models import Prefetch,Q
from collections import defaultdict
import re
import requests
from .models import Studentlist,Enrollment,Assignment,Submission
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.paginator import Paginator
import requests
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
import time

class CustomLoginView(LoginView):
    template_name = 'students/login.html'

 # Make sure the model name is correct

@login_required
def home(request):
    students = Studentlist.objects.all().order_by('name')
    sections = Studentlist.objects.values_list('section_name', flat=True).distinct()
    trimmed_sections = [re.match(r"(CGS\d+\.\d+)", section).group(1) if re.match(r"(CGS\d+\.\d+)", section) else section for section in sections]

    return render(request, 'students/home.html', {
        'sections': trimmed_sections,
        'students': students,
    })

def filter_students(request):
    name = request.GET.get('name', '')
    email = request.GET.get('email', '')
    sections = request.GET.get('sections', '').split(',')

    query = Q()
    if name:
        query &= Q(name__icontains=name)
    if email:
        query &= Q(email__icontains=email)


    # Apply section filters if provided
    if sections:
        section_query = Q()
        for section in sections:
            if section:
                section_query |= Q(section_name__startswith=section)
        query &= section_query

    # Fetch students grouped by section and sorted by name
    students = Studentlist.objects.filter(query).order_by('name')

    return JsonResponse({'students': list(students.values('name', 'email', 'sis_id', 'section_name'))})





# Canvas Conversations endpoint
CANVAS_CONV_URL = "https://usflearn.instructure.com/api/v1/conversations"

# ---------------------------
# Helper functions for bulk send
# ---------------------------

def _send_conversation_batch(token: str, payload: dict, timeout: int = 30):
    """
    Sends one batch to Canvas Conversations API.
    Must use form-encoded payload (not JSON).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        # Do NOT set Content-Type to application/json; Canvas expects form-data for bulk
    }
    r = requests.post(CANVAS_CONV_URL, headers=headers, data=payload, timeout=timeout)
    return r


def send_bulk_by_user_ids(token: str, user_ids, subject: str, body: str,
                          chunk_size: int = 100, async_mode: bool = True):
    """
    Sends a single group conversation to batches of users with Canvas bulk semantics.
    Canvas behaves best with recipients[] + group_conversation + bulk_message (+ async for big audiences).
    """
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    results = []
    for batch in chunks(list(user_ids), chunk_size):
        payload = {
            "recipients[]": [str(u) for u in batch],
            "subject": subject,
            "body": body,
            "group_conversation": True,
            "bulk_message": True,
        }
        if async_mode:
            payload["mode"] = "async"
        resp = _send_conversation_batch(token, payload)
        results.append((batch, resp.status_code, resp.text))
        # gentle pause to be kind to rate limits
        time.sleep(0.2)
    return results

@csrf_exempt
def send_email_home(request):
    YOUR_ACCESS_TOKEN = "13~z9rZFUBQVkNnCrHctw4KBDHauRA43DWVEuzNKrHW2Pe8EtfMZDThaLRNZu63xyDJ"

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            student_ids = data.get("student_ids", [])
            custom_message = data.get("custom_message", "")
            subject = data.get("subject") or "Reminder for CGS2100"

            # Default generic body if professor doesn't provide one
            if not custom_message.strip():
                custom_message = (
                    "Hello,\n\n"
                    "This is a reminder to check Canvas for your latest assignments and updates. "
                    "Please make sure to stay on top of your coursework.\n\n"
                    "Best regards,\nYour Instructor"
                )

            enrollments = Enrollment.objects.select_related("student").filter(student__sis_id__in=student_ids)
            user_ids = [e.student.student_id for e in enrollments if e.student and e.student.student_id]

            if not user_ids:
                return JsonResponse({"status": "failure", "error": "No valid user_ids found"}, status=400)

            # Bulk send
            results = send_bulk_by_user_ids(
                token=YOUR_ACCESS_TOKEN,
                user_ids=user_ids,
                subject=subject,
                body=custom_message,
                chunk_size=100,
                async_mode=True,
            )

            summary = [{"batch_size": len(b), "status": s, "body": t[:200]} for (b, s, t) in results]
            all_ok = all(s == 201 for (_, s, _) in results)

            return JsonResponse({"status": "success" if all_ok else "partial", "details": summary})

        except Exception as e:
            return JsonResponse({"status": "failure", "error": str(e)}, status=500)

    return JsonResponse({"status": "failure"}, status=400)

# def send_email_home(request):
#     YOUR_ACCESS_TOKEN = '13~2tK79VnPeQEWwWcuHVe2WQwKyK87TXBvrUmBMKe2VtJUfT7rJmKmZvBHcwu4VU2w'

#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body.decode('utf-8'))
#             student_ids = data.get('student_ids', [])
#             custom_message = data.get('custom_message', '')
#             subject = data.get('subject') or 'Reminder for CGS2100'  # subject from frontend
            
            

#             print(f"Received data: {data}")
#             # students = Enrollment.objects.filter(student_id__in=student_ids)
            
#             students = Enrollment.objects.filter(student__sis_id__in=student_ids)

#             for enrollment in students:
#                 student = enrollment.student

#                 data_payload = {
#                     "recipients": [student.student_id],
#                     "subject": subject,
#                     "body": custom_message.format(student_name=student.name),
#                     "group_conversation": False
#                 }

#                 print(f"Sending Data Payload: {data_payload}")

#                 response = requests.post(
#                     "https://usflearn.instructure.com/api/v1/conversations",
#                     headers={
#                         "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
#                         "Content-Type": "application/json"
#                     },
#                     json=data_payload
#                 )

#                 print(f"API Response: {response.text}")
#                 if response.status_code != 201:
#                     print(f"Failed to send message to {student.email}. Status code: {response.status_code}")
#                 else:
#                     print(f"Message sent to {student.email}")

#             return JsonResponse({'status': 'success'})

#         except json.JSONDecodeError as e:
#             print(f"JSON decode error: {e}")
#             return JsonResponse({'status': 'failure', 'error': 'Invalid JSON'}, status=400)
#         except Exception as e:
#             print(f"An error occurred: {e}")
#             return JsonResponse({'status': 'failure', 'error': str(e)}, status=500)

#     return JsonResponse({'status': 'failure'}, status=400)



@login_required
@csrf_exempt
def last_login(request):
    today = timezone.now().date()

    #Adding CALENDAR based filter
    from datetime import datetime

    inactive_since = request.GET.get('inactive_since', '')
    base_query = Enrollment.objects.select_related('student').all()

    if inactive_since:
        try:
            selected_date = datetime.strptime(inactive_since, "%Y-%m-%d").date()
            base_query = base_query.filter(last_activity_at__date__lte=selected_date)
        except ValueError:
            pass  # Ignore invalid date inputs

    enrollments = base_query.order_by('-inactive_days')

    context = {
        'enrollments': enrollments,
        'inactive_since': inactive_since,
    }
    return render(request, 'students/last_login.html', context)



@csrf_exempt
def send_email(request):
    YOUR_ACCESS_TOKEN = "13~z9rZFUBQVkNnCrHctw4KBDHauRA43DWVEuzNKrHW2Pe8EtfMZDThaLRNZu63xyDJ"

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            student_ids = data.get("student_ids", [])
            custom_message = data.get("custom_message", "")

            students = Enrollment.objects.filter(student_id__in=student_ids)
            results = []
            batch_size = 20

            for i, enrollment in enumerate(students, 1):
                student = enrollment.student
                if not student or not student.student_id:
                    continue

                # Personalization for inactivity reminders
                body = custom_message.format(
                    student_name=student.name,
                    inactive_days=enrollment.inactive_days,
                )

                payload = {
                    "recipients": [student.student_id],
                    "subject": "Reminder for Login Inactivity",
                    "body": body,
                    "group_conversation": False,
                }

                response = requests.post(
                    CANVAS_CONV_URL,
                    headers={
                        "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                results.append({
                    "email": student.email,
                    "status": response.status_code,
                    "response": response.text[:200],
                })

                # throttle every batch_size students
                if i % batch_size == 0:
                    time.sleep(1)

            success_count = sum(1 for r in results if r["status"] == 201)
            fail_count = len(results) - success_count

            return JsonResponse({
                "status": "success" if fail_count == 0 else "partial",
                "sent": success_count,
                "failed": fail_count,
            })

        except Exception as e:
            return JsonResponse({"status": "failure", "error": str(e)}, status=500)

    return JsonResponse({"status": "failure"}, status=400)
# def send_email(request):
#     YOUR_ACCESS_TOKEN = '13~2tK79VnPeQEWwWcuHVe2WQwKyK87TXBvrUmBMKe2VtJUfT7rJmKmZvBHcwu4VU2w'
#     if request.method == 'POST':
#         try:
#             # Parse the JSON body
#             data = json.loads(request.body.decode('utf-8'))
#             student_ids = data.get('student_ids', [])
#             custom_message = data.get('custom_message', '')

#             # Log the received data
#             print(f"Received data: {data}")

#             students = Enrollment.objects.filter(student_id__in=student_ids)

#             for enrollment in students:
#                 student = enrollment.student  # This is the related student instance

#                 # Log the student information
#                 #print(f"Student: {student.name}, Student ID: {student.student_id}, Email: {student.email}")

#                 personalized_subject = "Reminder for Login Inactivity"
#                 data_payload = {
#                     "recipients": [student.student_id],  # Use student_id from Studentlist model
#                     "subject": personalized_subject,
#                     "body": custom_message.format(student_name=student.name, inactive_days=enrollment.inactive_days),
#                     "group_conversation": False,
#                 }

#                 # Log the payload before sending
#                 print(f"Sending Data Payload: {data_payload}")

#                 response = requests.post(
#                     "https://usflearn.instructure.com/api/v1/conversations",
#                     headers={
#                         "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
#                         "Content-Type": "application/json"
#                     },
#                     json=data_payload
#                 )

#                 # Log the response from the API
#                 print(f"API Response: {response.text}")

#                 if response.status_code != 201:
#                     print(f"Failed to send message to {student.email}. Status code: {response.status_code}")
#                 else:
#                     print(f"Message sent to {student.email}")

#             return JsonResponse({'status': 'success'})
#         except json.JSONDecodeError as e:
#             print(f"JSON decode error: {e}")
#             return JsonResponse({'status': 'failure', 'error': 'Invalid JSON'}, status=400)
#         except Exception as e:
#             print(f"An error occurred: {e}")
#             return JsonResponse({'status': 'failure', 'error': str(e)}, status=500)

#     return JsonResponse({'status': 'failure'}, status=400)

@login_required
@csrf_exempt
def assignments_page(request):
    import re

    def natural_sort_key(title):
    # Split string into list of parts: ['Bellini #', 1, '', 12, ' more']
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', title)]

    assignments = sorted(Assignment.objects.all(), key=lambda a: natural_sort_key(a.title))

    # assignments = Assignment.objects.all().order_by('title')
    students = Submission.objects.order_by('student__name').values_list(
        'student__name', flat=True
    ).distinct()
    selected_assignments = request.GET.getlist('assignments')
    context = {
        'assignments': assignments,
        'students': students,
        'selected_assignments': selected_assignments,
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Get all filter parameters
        student_name = request.GET.get('student', '')
        status_filter = request.GET.get('status')
        score_filter = request.GET.get('score')
        page_number = request.GET.get('page', 1)

        # Build query
        submissions = Submission.objects.select_related('student', 'assignment')
        
        # Student name filter
        if student_name:
            submissions = submissions.filter(student__name=student_name)
        
        # Assignment filter
        if selected_assignments:
            submissions = submissions.filter(assignment_id__in=selected_assignments)
        
        # Status filter
        if status_filter:
            submissions = submissions.filter(status=status_filter)
        
        # Score filter
        if score_filter:
            if '<' in score_filter:
                max_score = int(score_filter.split('<')[1])
                submissions = submissions.filter(score__lt=max_score)
            elif '>' in score_filter:
                min_score = int(score_filter.split('>')[1])
                submissions = submissions.filter(score__gt=min_score)
            else:
                try:
                    score_range = score_filter.split('-')
                    if len(score_range) == 2:
                        min_score, max_score = map(int, score_range)
                        submissions = submissions.filter(score__gte=min_score, score__lte=max_score)
                except (ValueError, IndexError):
                    pass

        # Paginate results
        paginator = Paginator(submissions.order_by('student__name'), 20)
        page = paginator.get_page(page_number)
        
        # Serialize data
        submissions_data = [{
            'name': sub.student.name,
            'assignment': sub.assignment.title,
            'status': sub.get_status_display(),  # Show display value
            'score': sub.score
        } for sub in page]
        
        return JsonResponse({
            'submissions': submissions_data,
            'has_next': page.has_next()
        })
    
    return render(request, 'students/assignments.html', context)
class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea)







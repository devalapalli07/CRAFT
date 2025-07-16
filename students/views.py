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
    YOUR_ACCESS_TOKEN = '13~WE6aXzRMrPTheVDUVn6cfQtV2VP7EtvDvfPJkt9fDEH9h9MY8JAJQQtB7a786mWu'
    if request.method == 'POST':
        try:
            # Parse the JSON body
            data = json.loads(request.body.decode('utf-8'))
            student_ids = data.get('student_ids', [])
            custom_message = data.get('custom_message', '')

            # Log the received data
            print(f"Received data: {data}")

            students = Enrollment.objects.filter(student_id__in=student_ids)

            for enrollment in students:
                student = enrollment.student  # This is the related student instance

                # Log the student information
                print(f"Student: {student.name}, Student ID: {student.student_id}, Email: {student.email}")

                personalized_subject = "Reminder for Login Inactivity"
                data_payload = {
                    "recipients": [student.student_id],  # Use student_id from Studentlist model
                    "subject": personalized_subject,
                    "body": custom_message.format(student_name=student.name, inactive_days=enrollment.inactive_days),
                    "group_conversation": False,
                }

                # Log the payload before sending
                print(f"Sending Data Payload: {data_payload}")

                response = requests.post(
                    "https://usflearn.instructure.com/api/v1/conversations",
                    headers={
                        "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
                        "Content-Type": "application/json"
                    },
                    json=data_payload
                )

                # Log the response from the API
                print(f"API Response: {response.text}")

                if response.status_code != 201:
                    print(f"Failed to send message to {student.email}. Status code: {response.status_code}")
                else:
                    print(f"Message sent to {student.email}")

            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse({'status': 'failure', 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"An error occurred: {e}")
            return JsonResponse({'status': 'failure', 'error': str(e)}, status=500)

    return JsonResponse({'status': 'failure'}, status=400)




# def send_assignment_email(request):
#     YOUR_ACCESS_TOKEN = '13~FT9GuNvrtD9NEHXhf6mwNwVcMZDUf4wFQHyUGYwkcr3FNHD7ATU7ka6uULcDBkR9'
#     if request.method == 'POST':
#         try:
#             Parse the JSON body
#             data = json.loads(request.body.decode('utf-8'))
#             student_ids = data.get('student_ids', [])
#             custom_message = data.get('custom_message', '')
#             assignment_ids = data.get('assignments', [])

#             Log the received data
#             print(f"Received data: {data}")

#             Get the assignment titles based on the selected assignment IDs
#             assignments = Assignment.objects.filter(id__in=assignment_ids)
#             assignment_titles = ', '.join([assignment.title for assignment in assignments])

#             Log the assignment titles
#             print(f"Assignment Titles: {assignment_titles}")

#             students = Enrollment.objects.filter(student_id__in=student_ids)

#             for enrollment in students:
#                 student = enrollment.student  # This is the related student instance

#                 Log the student information
#                 print(f"Student: {student.name}, Student ID: {student.student_id}, Email: {student.email}")

#                 Ensure the subject and body are set correctly
#                 personalized_subject = "Reminder for Assignment Completion"
#                 personalized_body = custom_message.format(
#                     student_name=student.name,
#                     assignments=assignment_titles
#                 )

#                 data_payload = {
#                     "recipients": [student.student_id],  # Use student_id from Studentlist model
#                     "subject": personalized_subject,
#                     "body": personalized_body,
#                     "group_conversation": False,
#                 }

#                 Log the payload before sending
#                 print(f"Sending Data Payload: {data_payload}")

#                 response = requests.post(
#                     "https://usflearn.instructure.com/api/v1/conversations",
#                     headers={
#                         "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
#                         "Content-Type": "application/json"
#                     },
#                     json=data_payload
#                 )

#                 Log the response from the API
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


def assignments_page(request):
    assignments = Assignment.objects.all()
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







from django import forms
from django.shortcuts import  redirect, render
from django.http import JsonResponse
from django.db.models import Q
from collections import defaultdict
import re
import requests
from .models import Studentlist,Enrollment,Assignment,Student 
from .forms import StudentFilterForm
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json

 # Make sure the model name is correct


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
    inactive_days_parameter = request.GET.get('inactive_days', '')

    base_query = Enrollment.objects.all()

    if inactive_days_parameter:
        if 'week' in inactive_days_parameter:
            weeks_count = int(inactive_days_parameter.split()[1])
            min_days = 5 + (weeks_count - 1) * 7
            max_days = 5 + weeks_count * 7
            if weeks_count == 4:
                base_query = base_query.filter(inactive_days__gt=27)
            else:
                base_query = base_query.filter(inactive_days__gt=min_days, inactive_days__lte=max_days)
        else:
            days = int(inactive_days_parameter)
            base_query = base_query.filter(inactive_days=days)

    enrollments = base_query.order_by('-inactive_days')

    context = {
        'enrollments': enrollments,
        'inactive_days_options': [
            '1', '2', '3', '4', '5',
            'Over 1 week', 'Over 2 weeks', 'Over 3 weeks', 'Over 4 weeks'
        ],
        'inactive_days_parameter': inactive_days_parameter,
    }
    return render(request, 'students/last_login.html', context)



@csrf_exempt
def send_email(request):
    YOUR_ACCESS_TOKEN = '13~WmvQhDfNzYraCcCxn4MFEx2mAaxxPXenykwuZ24NJQQPFXz4P6v4W7hJXJ2NyzBz'
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


def select_assignments(request):
    students = Studentlist.objects.all().prefetch_related('assignments')

    # Retrieve necessary data for filtering
    assignments = Assignment.objects.all()
    sections = Studentlist.objects.values_list('section_name', flat=True).distinct()
    statuses = Assignment.objects.values_list('status', flat=True).distinct()

    trimmed_sections = [
        re.match(r"(CGS\d+\.\d+)", section).group(1) if re.match(r"(CGS\d+\.\d+)", section) else section
        for section in sections
    ]

    # Initialize filter values
    selected_sections = []
    selected_assignment_titles = []
    selected_status = 'all'

    filter_form = StudentFilterForm(request.POST or None, sections=trimmed_sections, statuses=statuses)
    if request.method == 'POST':
        if filter_form.is_valid():
            selected_sections = filter_form.cleaned_data['section']
            selected_assignment_titles = list(filter_form.cleaned_data['assignments'].values_list('title', flat=True))
            selected_status = filter_form.cleaned_data['status']
            
            print(f"Selected Sections: {selected_sections}")  # Debug statement
            print(f"Selected Assignment Titles: {selected_assignment_titles}")  # Debug statement
            print(f"Selected Status: {selected_status}")  # Debug statement

            # Initialize the query with all students
            students = Studentlist.objects.all().prefetch_related('assignments')

            # Create Q objects for each filter
            queries = Q()
            if selected_sections:
                section_queries = Q()
                for section in selected_sections:
                    section_queries |= Q(section_name__icontains=section)
                queries &= section_queries
            if selected_status and selected_status != 'all':
                queries &= Q(assignments__status=selected_status)
            if selected_assignment_titles:
                queries &= Q(assignments__title__in=selected_assignment_titles)

            # Apply the combined filters
            students = students.filter(queries).distinct()
            print(f"Filtered Students: {students.count()}")  # Debug statement
            print(students.query)  # Print the actual SQL query being executed

    # Prepare a dictionary to store assignments and statuses for each student
    student_assignments = {}
    for student in students:
        student_info = {
            'name': student.name,
            'email': student.email,
        }
        # Fetch assignments and statuses for the current student that match the selected criteria
        assignments_queryset = Assignment.objects.filter(student_id=student)

        # Apply the same filtering logic to the assignments
        assignment_queries = Q()
        if selected_status and selected_status != 'all':
            assignment_queries &= Q(status=selected_status)
        if selected_assignment_titles:
            assignment_queries &= Q(title__in=selected_assignment_titles)

        # Filter assignments based on the combined criteria
        assignments_queryset = assignments_queryset.filter(assignment_queries).distinct()
        assignments_and_statuses = [(assignment.title, assignment.status) for assignment in assignments_queryset]

        # Combine student info with assignments and statuses
        student_info['assignments'] = assignments_and_statuses

        # Store in the dictionary using student_id as the key
        student_assignments[student.student_id] = student_info

    return render(request, 'students/select_assignments.html', {
        'students': students,
        'filter_form': filter_form,
        'assignments': assignments,
        'sections': trimmed_sections,
        'statuses': statuses,
        'student_assignments': student_assignments,
        'selected_sections': selected_sections,
        'selected_assignments': selected_assignment_titles,
        'selected_status': selected_status,
    })



class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea)







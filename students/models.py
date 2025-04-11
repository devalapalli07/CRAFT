# students/models.py

from django.db import models
from django.core.validators import EmailValidator

    
class Studentlist(models.Model):
    name = models.CharField(max_length=255)
    student_id = models.CharField(max_length=100, primary_key=True, unique=True, db_index=True)
    sis_id = models.CharField(max_length=100, unique=True)
    email = models.EmailField(validators=[EmailValidator()])
    section_name = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.email})"
    

class Assignment(models.Model):
    title = models.CharField(max_length=200, db_index=True)
    due_date = models.DateTimeField(null=True)

    def __str__(self):
        return self.title

class Submission(models.Model):
    student = models.ForeignKey(Studentlist, on_delete=models.CASCADE, related_name='submissions',to_field='student_id',db_column='student_id')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True, db_index=True)
    
    STATUS_CHOICES = [
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('missing', 'Missing'),
        ('floating','Floating')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)

    class Meta:
        unique_together = ('student', 'assignment')  # Ensure each student has one submission per assignment

    def __str__(self):
        return f"{self.student.name} - {self.assignment.title}"



class Enrollment(models.Model):
    student = models.ForeignKey(Studentlist, on_delete=models.CASCADE, related_name='enrollments', to_field='student_id',db_column='student_id')
    type = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    total_activity_time = models.FloatField(null=True, blank=True)
    sis_course_id = models.CharField(max_length=100, null=True, blank=True)
    sis_section_id = models.CharField(max_length=100, null=True, blank=True)
    sis_user_id = models.CharField(max_length=100)
    inactive_days = models.IntegerField(null=True, blank=True)
    current_grade = models.FloatField(null=True, blank=True)
    current_score = models.FloatField(null=True, blank=True)
    final_grade = models.FloatField(null=True, blank=True)
    final_score = models.FloatField(null=True, blank=True)
    unposted_current_score = models.FloatField(null=True, blank=True)
    unposted_current_grade = models.FloatField(null=True, blank=True)
    unposted_final_score = models.FloatField(null=True, blank=True)
    unposted_final_grade = models.FloatField(null=True, blank=True)

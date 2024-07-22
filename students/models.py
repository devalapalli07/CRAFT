# students/models.py

from django.db import models
from django.core.validators import EmailValidator

    
class Student(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.name

class Studentlist(models.Model):
    name = models.CharField(max_length=255)
    student_id = models.CharField(max_length=100, unique=True)
    sis_id = models.CharField(max_length=100, unique=True)
    email = models.EmailField(validators=[EmailValidator()])
    section_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} ({self.email})"
    
class Assignment(models.Model):
    student_id= models.ForeignKey(Studentlist, on_delete=models.CASCADE, related_name='assignments', to_field='student_id')
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=100, default='default_status')

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    student = models.ForeignKey(Studentlist, on_delete=models.CASCADE, related_name='enrollments', to_field='student_id', db_column='student_id')
    type = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    last_activity_at = models.DateTimeField()
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

from django.db import models


class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    SUPERADMIN = "superadmin", "Superadmin"
    OPERATIONADMIN = "operationadmin", "Operation Admin"
    SCHOOLADMIN = "schooladmin", "School Admin"
    SCHOOLOPSADMIN = "schoolopsadmin", "School Ops Admin"

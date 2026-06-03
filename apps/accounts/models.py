import random
import uuid
from datetime import timedelta
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.db.models import Q
from django.utils import timezone
from utils.jwt import generate_jwt_token
from .dtos import UserDTO
from .roles import UserRole

SUPPORTED_CURRENCIES = ("INR", "USD", "EUR", "AED")


class School(models.Model):
    name = models.CharField(max_length=200)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=200, blank=True, null=True)
    state = models.CharField(max_length=200, blank=True, null=True)
    country = models.CharField(max_length=200, blank=True, null=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=30, blank=True, null=True)
    currency = models.CharField(max_length=10, null=True, blank=True)  # NULL = INR default
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ModuleName(models.TextChoices):
    """Single source of truth for all module identifiers and their display names."""
    # ESSAY_BRAINSTORMER = "essay_brainstormer", "Essay Brainstormer"
    # ESSAY_EVALUATOR = "essay_evaluator", "Essay Evaluator"
    COLLEGE_SELECTOR = "college_selector", "College Selector"
    # DEGREE_SELECTOR = "degree_selector", "Degree Selector"
    # INTERVIEW_PREP = "interview_prep", "Interview Prep"
    # RESUME_BUILDER = "resume_builder", "Resume Builder"
    CAREER_DISCOVERY = "career_discovery", "Career & Degree Selection"
    DOMAIN_DISCOVERY = "domain_discovery", "Stream & Subject Selection"


# Presentation metadata keyed by ModuleName value.
# Keep this next to the enum so it stays in sync.
MODULE_META: dict[str, dict[str, str]] = {
    # ModuleName.ESSAY_BRAINSTORMER: {"icon": "brain-circuit", "color": "bg-blue-100 text-blue-700"},
    # ModuleName.ESSAY_EVALUATOR:    {"icon": "list-check",    "color": "bg-indigo-100 text-indigo-700"},
    ModuleName.COLLEGE_SELECTOR:     {"icon": "school",        "color": "bg-green-100 text-green-700"},
    # ModuleName.DEGREE_SELECTOR:    {"icon": "graduation-cap","color": "bg-teal-100 text-teal-700"},
    # ModuleName.INTERVIEW_PREP:     {"icon": "videoconference","color": "bg-orange-100 text-orange-700"},
    # ModuleName.RESUME_BUILDER:     {"icon": "CV",            "color": "bg-pink-100 text-pink-700"},
    ModuleName.CAREER_DISCOVERY:     {"icon": "briefcase",     "color": "bg-purple-100 text-purple-700"},
    ModuleName.DOMAIN_DISCOVERY:     {"icon": "world",         "color": "bg-cyan-100 text-cyan-700"},
}


class SchoolModuleSubscription(models.Model):
    # Expose top-level ModuleName here for backward-compatible access via SchoolModuleSubscription.ModuleName
    ModuleName = ModuleName

    class Source(models.TextChoices):
        ADMIN = "admin", "Admin"
        PAYMENT = "payment", "Payment"
        OTHER = "other", "Other"

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="subscriptions"
    )
    payment = models.ForeignKey(
        "SchoolPayment", on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions"
    )
    module_name = models.CharField(max_length=30, choices=ModuleName.choices)
    max_students = models.IntegerField(null=True, blank=True)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.school.name} - {self.get_module_name_display()}"


class UserModuleSubscription(models.Model):
    """Direct module subscription for individual users (B2C purchase or B2B school assignment)."""

    class Source(models.TextChoices):
        ADMIN = "admin", "Admin"
        PAYMENT = "payment", "Payment"
        SCHOOL_ASSIGNMENT = "school_assignment", "School Assignment"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="subscriptions"
    )
    payment = models.ForeignKey(
        "UserPayment", on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions"
    )
    school_subscription = models.ForeignKey(
        "SchoolModuleSubscription", on_delete=models.SET_NULL, null=True, blank=True, related_name="student_assignments"
    )
    module_name = models.CharField(
        max_length=30, choices=ModuleName.choices
    )
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ADMIN)
    assigned_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True, related_name="module_assignments_made"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_module_name_display()}"


class GradeModuleAutoAssignment(models.Model):
    """Auto-assign rule: when a student is added to a school with a matching grade,
    automatically create a UserModuleSubscription for the specified module."""

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="grade_auto_assignments"
    )
    grade_level = models.CharField(max_length=20)
    module_name = models.CharField(max_length=30, choices=ModuleName.choices)
    school_subscription = models.ForeignKey(
        SchoolModuleSubscription, on_delete=models.CASCADE, related_name="auto_assignments"
    )
    created_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True, related_name="auto_assignments_created"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("school", "grade_level", "module_name")

    def __str__(self) -> str:
        return f"{self.school.name} - {self.grade_level} - {self.get_module_name_display()}"


class User(models.Model):
    # Expose UserRole as User.Role for convenient access
    Role = UserRole

    class AcademicLevel(models.TextChoices):
        HIGH_SCHOOL = "high_school", "High School (8th–12th grade)"
        UNDERGRADUATE = "undergraduate", "College/Undergraduate"
        POSTGRADUATE = "postgraduate", "Postgraduate"
        PROFESSIONAL = "professional", "Working/Completed College"

    GRADE_LEVELS = {
        "high_school": ["Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
        "undergraduate": ["Year 1", "Year 2", "Year 3", "Year 4"],
        "postgraduate": ["Year 1", "Year 2"],
        "professional": ["1-3 years", "3-5 years", "5+ years"],
    }

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    password = models.CharField(
        max_length=128, default=""
    )  # Use Django's password hashing
    token = models.CharField(max_length=255, blank=True, null=True)  # JWT token
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT
    )
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    academic_level = models.CharField(
        max_length=20,
        choices=AcademicLevel.choices,
        blank=True,
        null=True,
    )
    grade_level = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    terms_accepted = models.BooleanField(default=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    force_password_change = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)  # Only True after OTP verification
    last_login = models.DateTimeField(null=True, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    counselor_comment = models.TextField(blank=True, default="")
    counselor_comment_updated_at = models.DateTimeField(null=True, blank=True)
    parent_student_comment = models.TextField(blank=True, default="")
    parent_student_comment_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password: str) -> None:
        """Hashes and sets the password."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Validates a raw password against the stored hash."""
        return check_password(raw_password, self.password)

    def generate_token(self) -> str:
        """Generates a JWT token."""
        # uuid
        if self.token is None or len(self.token) == 0:
            unique_id = str(uuid.uuid4())
            self.token = unique_id
            self.save()
        return generate_jwt_token(self.email, self.token)

    def accept_terms(self) -> None:
        """Accepts terms and sets the acceptance date."""
        self.terms_accepted = True
        self.terms_accepted_at = timezone.now()
        self.save()

    @classmethod
    def from_dto(cls, dto: UserDTO) -> "User":
        # load from DB
        user = cls.objects.filter(email=dto.email).first()
        if user:
            return user
        return cls(
            email=dto.email,
            is_active=dto.is_active,
        )

    def to_dto(self) -> UserDTO:
        return UserDTO(
            id=self.id,
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=self.is_active,
            role=self.role,
            school_id=self.school_id,
            school_name=self.school.name if self.school else None,
            terms_accepted=self.terms_accepted,
            force_password_change=self.force_password_change,
        )


class UserPayment(models.Model):
    """Records a payment made by a B2C user for module subscriptions."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="payments"
    )
    modules_purchased = models.JSONField(default=list, blank=True)  # [{"module": "name", "quantity": N}]
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_gateway = models.CharField(max_length=50, blank=True, default="")
    gateway_transaction_id = models.CharField(max_length=200, blank=True, default="")
    order_id = models.CharField(max_length=200, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_status(self, new_status: str) -> None:
        """Update status and append to metadata history."""
        history = self.metadata.get("history", [])
        history.append({"status": new_status, "timestamp": timezone.now().isoformat()})
        self.metadata["history"] = history
        self.status = new_status

    def __str__(self) -> str:
        return f"{self.user.email} - {self.amount}"


class SchoolPayment(models.Model):
    """Records a payment made by a school for module subscriptions."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_gateway = models.CharField(max_length=50, blank=True, default="")
    gateway_transaction_id = models.CharField(max_length=200, blank=True, default="")
    order_id = models.CharField(max_length=200, blank=True, default="")
    modules_purchased = models.JSONField(default=list, blank=True)  # [{"module": "name", "quantity": N}]
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_status(self, new_status: str) -> None:
        """Update status and append to metadata history."""
        history = self.metadata.get("history", [])
        history.append({"status": new_status, "timestamp": timezone.now().isoformat()})
        self.metadata["history"] = history
        self.status = new_status

    def __str__(self) -> str:
        return f"{self.school.name} - {self.amount}"


class EmailOTP(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_valid(self, user_entered: str, check_only: bool = False) -> tuple[bool, str]:
        if self.created_at < timezone.now() - timedelta(minutes=10):
            return False, "OTP expired"
        if not self.is_active:
            return False, "OTP already used"
        if self.code != user_entered:
            return False, "Invalid OTP"
        # Only mark as used if not in check-only mode
        if not check_only:
            self.is_active = False
            self.save()
        return True, "OTP validated successfully"

    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    def existing_otp(email: str) -> "EmailOTP | None":
        return EmailOTP.objects.filter(
            email=email,
            is_active=True,
            created_at__gte=timezone.now() - timedelta(minutes=10),
        ).first()


class Notification(models.Model):
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.CASCADE,
        related_name="notifications"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_notifications"
    )
    target_grade = models.CharField(max_length=10, blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Notification to grade {self.target_grade} by {self.sender.email}"


class StudentNotification(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="recipients"
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("notification", "student")

    def __str__(self) -> str:
        return f"Notification {self.notification_id} -> {self.student.email}"


class Deadline(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="deadlines"
    )
    title = models.CharField(max_length=300)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    target_grade = models.CharField(max_length=10, blank=True, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_deadlines"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"


class SharedDocument(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="documents"
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_documents"
    )
    file_url = models.URLField(max_length=1000)
    file_name = models.CharField(max_length=300)
    category = models.CharField(max_length=100, blank=True, default="")
    note = models.TextField(blank=True, default="")
    students = models.ManyToManyField(
        User, related_name="shared_documents", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.file_name} ({self.school.name})"


class ModulePricing(models.Model):
    module_name = models.CharField(max_length=30, choices=ModuleName.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency_variants = models.JSONField(default=dict, blank=True)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, null=True, blank=True, related_name="module_pricing"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="module_pricing"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("module_name",),
                condition=Q(school__isnull=True, user__isnull=True),
                name="unique_global_module_pricing",
            ),
            models.UniqueConstraint(
                fields=("module_name", "school"),
                condition=Q(school__isnull=False, user__isnull=True),
                name="unique_school_module_pricing",
            ),
            models.UniqueConstraint(
                fields=("module_name", "user"),
                condition=Q(school__isnull=True, user__isnull=False),
                name="unique_user_module_pricing",
            ),
        ]

    def __str__(self) -> str:
        scope = "Global"
        if self.school_id:
            scope = f"School {self.school_id}"
        elif self.user_id:
            scope = f"User {self.user_id}"
        return f"{self.module_name} - {self.price} ({scope})"



class Coupon(models.Model):
    class Type(models.TextChoices):
        DISCOUNT = "discount", "Discount"
        ADDON = "addon", "Addon"

    class VoucherType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FLAT = "flat", "Flat"

    title = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    date_from = models.DateField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # in days
    is_limited = models.BooleanField(default=False)
    coupon_type = models.CharField(max_length=20, choices=Type.choices, default=Type.DISCOUNT)
    max_users = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)
    min_booking_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    voucher_type = models.CharField(max_length=20, choices=VoucherType.choices, default=VoucherType.PERCENTAGE)
    voucher_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_valid(self, amount: int | float = 0) -> tuple[bool, str]:
        from decimal import Decimal
        import logging
        logger = logging.getLogger("django.server")
        
        if not self.is_active:
            return False, "Coupon is inactive."
            
        now_date = timezone.now().date()
        if self.date_from and now_date < self.date_from:
            return False, "Coupon is not yet valid."
        if self.date_from and self.duration:
            if now_date > self.date_from + timedelta(days=self.duration):
                return False, "Coupon has expired."
        if self.is_limited and self.max_users is not None and self.used_count >= self.max_users:
            return False, "Coupon usage limit reached."
            
        # FORCE DECIMAL COMPARISON
        amt_decimal = Decimal(str(amount))
        min_amt = self.min_booking_amount
        
        logger.info(f"[DEBUG] Coupon {self.code}: Checking amount {amt_decimal} against min {min_amt}")
        
        if min_amt and amt_decimal < min_amt:
            logger.warning(f"[DEBUG] Coupon {self.code}: REJECTED. {amt_decimal} < {min_amt}")
            return False, f"Minimum booking amount is {min_amt}."
            
        return True, "Valid"

    def __str__(self) -> str:
        return self.code


class CustomModule(models.Model):
    value = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default="briefcase")
    color = models.CharField(max_length=100, default="bg-purple-100 text-purple-700")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.label


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activity_logs")
    event_type = models.CharField(max_length=50) # 'login', 'payment', 'module_start', 'llm_interaction', etc.
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.email} - {self.event_type} - {self.created_at}"

    @staticmethod
    def log(user, event_type, description, metadata=None, request=None):
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
        
        return ActivityLog.objects.create(
            user=user,
            event_type=event_type,
            description=description,
            metadata=metadata or {},
            ip_address=ip_address
        )

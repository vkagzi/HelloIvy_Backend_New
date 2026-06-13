import logging
from rest_framework import serializers
from .roles import UserRole
from .models import (
    School,
    SchoolModuleSubscription,
    User,
    UserModuleSubscription,
    UserPayment,
    SchoolPayment,
    ModulePricing,
    Notification,
    Deadline,
    SharedDocument,
    SUPPORTED_CURRENCIES,
    Coupon,
    CustomModule,
)

logger = logging.getLogger("django.server")


class SignupSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    code = serializers.CharField()


class LoginSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    password = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer[dict[str, str]]):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        import re
        if not re.search(r"[0-9]", attrs["new_password"]):
            raise serializers.ValidationError({"new_password": "Password must contain at least one number."})
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", attrs["new_password"]):
            raise serializers.ValidationError({"new_password": "Password must contain at least one special character."})
        return attrs


# --- School Serializers ---


class SchoolModuleSubscriptionSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    module_name = serializers.CharField(max_length=30)
    module_display = serializers.SerializerMethodField()

    def get_module_display(self, obj) -> str:
        from .models import CustomModule, ModuleName
        cm = CustomModule.objects.filter(value=obj.module_name).first()
        if cm:
            return cm.label
        for choice in ModuleName.choices:
            if choice[0] == obj.module_name:
                return choice[1]
        return obj.module_name

    class Meta:
        model = SchoolModuleSubscription
        fields = [
            "id",
            "module_name",
            "module_display",
            "max_students",
            "expiry_date",
            "is_active",
            "source",
            "payment",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class UserModuleSubscriptionSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    module_name = serializers.CharField(max_length=30)
    module_display = serializers.SerializerMethodField()
    assigned_by_email = serializers.CharField(
        source="assigned_by.email", read_only=True, default=None
    )

    def get_module_display(self, obj) -> str:
        from .models import CustomModule, ModuleName
        cm = CustomModule.objects.filter(value=obj.module_name).first()
        if cm:
            return cm.label
        for choice in ModuleName.choices:
            if choice[0] == obj.module_name:
                return choice[1]
        return obj.module_name

    class Meta:
        model = UserModuleSubscription
        fields = [
            "id",
            "module_name",
            "module_display",
            "expiry_date",
            "is_active",
            "source",
            "payment",
            "school_subscription",
            "assigned_by",
            "assigned_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "assigned_by_email"]


class UserPaymentSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = UserPayment
        fields = [
            "id",
            "user",
            "user_email",
            "user_first_name",
            "user_last_name",
            "modules_purchased",
            "amount",
            "currency",
            "status",
            "payment_gateway",
            "gateway_transaction_id",
            "order_id",
            "expiry_date",
            "quantity",
            "metadata",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_email", "user_first_name", "user_last_name"]


class SchoolPaymentSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta:
        model = SchoolPayment
        fields = [
            "id",
            "school",
            "school_name",
            "amount",
            "currency",
            "status",
            "payment_gateway",
            "gateway_transaction_id",
            "order_id",
            "modules_purchased",
            "expiry_date",
            "quantity",
            "metadata",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "school_name"]


class ModulePricingSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    module_name = serializers.CharField(max_length=30)
    school_name = serializers.CharField(source="school.name", read_only=True, default=None)
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = ModulePricing
        fields = [
            "id",
            "module_name",
            "price",
            "currency_variants",
            "school",
            "school_name",
            "user",
            "user_email",
            "label_override",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "school_name", "user_email", "created_at", "updated_at"]

    def validate_currency_variants(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError("currency_variants must be a dict")
        allowed = {c for c in SUPPORTED_CURRENCIES if c != "INR"}
        invalid_keys = set(value.keys()) - allowed
        if invalid_keys:
            raise serializers.ValidationError(f"Invalid currency keys: {invalid_keys}. Allowed: {allowed}")
        for k, v in value.items():
            if not isinstance(v, (int, float)) or v < 0:
                raise serializers.ValidationError(f"Price for {k} must be a non-negative number")
        return value


class SchoolSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    subscriptions = SchoolModuleSubscriptionSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "logo_url",
            "address",
            "city",
            "state",
            "country",
            "website",
            "contact_email",
            "contact_phone",
            "currency",
            "is_active",
            "subscriptions",
            "student_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_student_count(self, obj: School) -> int:
        return obj.users.filter(role=UserRole.STUDENT).count()


class SchoolCreateUpdateSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    # Use CharField to accept both full URLs (S3) and relative paths (local dev)
    logo_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = School
        fields = [
            "name",
            "logo_url",
            "address",
            "city",
            "state",
            "country",
            "website",
            "contact_email",
            "contact_phone",
            "currency",
        ]


# --- Admin User Create Serializer ---


class AdminUserCreateSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=UserRole.choices)
    school_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    send_password_email = serializers.BooleanField(default=True)
    academic_level = serializers.ChoiceField(
        choices=User.AcademicLevel.choices,
        required=False,
        allow_null=True,
    )
    grade_level = serializers.ChoiceField(
        choices=[
            (g, g)
            for grades in User.GRADE_LEVELS.values()
            for g in grades
        ],
        required=False,
        allow_null=True,
    )

    def validate(self, data: dict) -> dict:
        academic_level = data.get("academic_level")
        grade_level = data.get("grade_level")
        if grade_level and not academic_level:
            raise serializers.ValidationError(
                {"academic_level": "academic_level is required when grade_level is provided."}
            )
        if academic_level and grade_level:
            valid_grades = User.GRADE_LEVELS.get(academic_level, [])
            if grade_level not in valid_grades:
                raise serializers.ValidationError(
                    {"grade_level": f"Invalid grade_level for {academic_level}. Must be one of: {valid_grades}"}
                )
        return data


class BulkUserImportItemSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")


class BulkUserImportSerializer(serializers.Serializer[dict[str, str]]):
    users = serializers.ListField(child=BulkUserImportItemSerializer(), min_length=1, max_length=500)
    role = serializers.ChoiceField(choices=[
        (UserRole.STUDENT, UserRole.STUDENT.label),
        (UserRole.SCHOOLADMIN, UserRole.SCHOOLADMIN.label),
    ])
    school_id = serializers.IntegerField(required=False, allow_null=True)
    academic_level = serializers.ChoiceField(
        choices=User.AcademicLevel.choices,
        required=False,
        allow_null=True,
    )
    grade_level = serializers.ChoiceField(
        choices=[
            (g, g)
            for grades in User.GRADE_LEVELS.values()
            for g in grades
        ],
        required=False,
        allow_null=True,
    )
    send_password_email = serializers.BooleanField(default=True, required=False)

    def validate(self, data: dict) -> dict:
        academic_level = data.get("academic_level")
        grade_level = data.get("grade_level")
        if grade_level and not academic_level:
            raise serializers.ValidationError(
                {"academic_level": "academic_level is required when grade_level is provided."}
            )
        if academic_level and grade_level:
            valid_grades = User.GRADE_LEVELS.get(academic_level, [])
            if grade_level not in valid_grades:
                raise serializers.ValidationError(
                    {"grade_level": f"Invalid grade_level for {academic_level}. Must be one of: {valid_grades}"}
                )
        return data


class NotificationCreateSerializer(serializers.Serializer[dict[str, str]]):
    target_grade = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField()


class DeadlineSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True
    )

    class Meta:
        model = Deadline
        fields = [
            "id",
            "title",
            "date",
            "time",
            "target_grade",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "created_by_email", "created_at"]


class DeadlineCreateSerializer(serializers.Serializer[dict[str, str]]):
    title = serializers.CharField(max_length=300)
    date = serializers.DateField()
    time = serializers.TimeField(required=False, allow_null=True)
    target_grade = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class SharedDocumentSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    uploaded_by_email = serializers.EmailField(
        source="uploaded_by.email", read_only=True
    )

    class Meta:
        model = SharedDocument
        fields = [
            "id",
            "file_url",
            "file_name",
            "category",
            "note",
            "uploaded_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "uploaded_by_email", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "target_grade",
            "message",
            "sender_email",
            "created_at",
        ]
        read_only_fields = ["id", "sender_email", "created_at"]




class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = "__all__"


class CustomModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomModule
        fields = "__all__"

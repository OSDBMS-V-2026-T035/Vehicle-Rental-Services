from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r"^[6-9]\d{9}$",
    message="Enter exactly 10 digits and start the number with 6, 7, 8, or 9.",
)


class UserManager(BaseUserManager):
    """Create users without exposing the internal username field."""

    use_in_migrations = True

    def _create_user(self, email, phone_number, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        if not phone_number:
            raise ValueError("A phone number is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone_number, password, **extra_fields)

    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, phone_number, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "USER", "User"
        SHOPKEEPER = "SHOPKEEPER", "Shopkeeper"
        ADMIN = "ADMIN", "Administrator"

    username = None
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=10,
        unique=True,
        validators=[phone_validator],
        help_text="Indian mobile number without the +91 prefix.",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return self.get_full_name() or self.email


class ShopkeeperProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="shopkeeper_profile")
    shop_name = models.CharField(max_length=120)
    shop_address = models.CharField(max_length=255)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.shop_name


class OTPChallenge(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"

    class Purpose(models.TextChoices):
        SIGNUP = "SIGNUP", "Signup"
        LOGIN = "LOGIN", "Login"
        RESET = "RESET", "Password reset"

    contact = models.CharField(max_length=254)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.SIGNUP)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contact", "channel", "purpose", "created_at"]),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.channel} OTP for {self.contact}"

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"]), models.Index(fields=["actor", "created_at"])]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id or '-'}"


class CommissionConfiguration(models.Model):
    """One auditable platform-wide rate, applied only to newly captured payments."""

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="commission_configuration_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(commission_rate__gte=0, commission_rate__lte=100),
            name="commission_rate_between_zero_and_hundred",
        )]

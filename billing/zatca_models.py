"""
ZATCA E-Invoice Integration Models
Tracks invoice submissions to ZATCA
"""
from django.db import models
from django.conf import settings
from datetime import datetime
import uuid


class ZATCASubmission(models.Model):
    """
    Tracks ZATCA E-Invoice submissions
    """
    SUBMISSION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('rejected', 'Rejected'),
        ('error', 'Error'),
    ]
    
    # Reference
    invoice = models.OneToOneField('Invoice', on_delete=models.CASCADE, related_name='zatca_submission')
    submission_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Submission details
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS_CHOICES, default='pending')
    
    # XML and signatures
    xml_content = models.TextField(verbose_name="XML Content")
    xml_signature = models.TextField(blank=True, verbose_name="Digital Signature")
    
    # QR Code
    qr_code = models.ImageField(upload_to='zatca_qr_codes/', blank=True, null=True, verbose_name="QR Code")
    
    # ZATCA Response
    zatca_response = models.JSONField(blank=True, null=True, verbose_name="ZATCA API Response")
    zatca_uuid = models.CharField(max_length=100, blank=True, verbose_name="ZATCA UUID")
    zatca_status = models.CharField(max_length=50, blank=True, verbose_name="ZATCA Status")
    
    # Compliance Info
    compliance_invoice_number = models.CharField(max_length=100, blank=True, verbose_name="Compliance Invoice Number")
    is_compliant = models.BooleanField(default=False, verbose_name="Is Compliant")
    compliance_errors = models.JSONField(blank=True, null=True, verbose_name="Compliance Errors")
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Submitted At")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional info
    submission_method = models.CharField(
        max_length=20,
        choices=[('api', 'API'), ('portal', 'Portal'), ('manual', 'Manual')],
        default='api',
        verbose_name="Submission Method"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    class Meta:
        ordering = ['-submitted_at', '-created_at']
        verbose_name = 'ZATCA Submission'
        verbose_name_plural = 'ZATCA Submissions'
    
    def __str__(self):
        return f"ZATCA Submission - {self.invoice.invoice_number} - {self.status}"


class ZATCAConfiguration(models.Model):
    """
    ZATCA Configuration for the organization
    """
    # Organization Info
    organization_trn = models.CharField(max_length=20, unique=True, verbose_name="Tax Registration Number (TRN)")
    organization_name = models.CharField(max_length=255, verbose_name="Organization Name")
    organization_name_ar = models.CharField(max_length=255, blank=True, verbose_name="Organization Name (Arabic)")
    
    # Contact
    organization_email = models.EmailField(verbose_name="Organization Email")
    organization_phone = models.CharField(max_length=20, verbose_name="Organization Phone")
    organization_address = models.TextField(verbose_name="Organization Address")
    organization_city = models.CharField(max_length=100, default='Riyadh', verbose_name="City")
    
    # Credentials
    certificate_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to ZATCA certificate file",
        verbose_name="Certificate Path"
    )
    private_key_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to private key file",
        verbose_name="Private Key Path"
    )
    
    # API Settings
    use_sandbox = models.BooleanField(default=True, verbose_name="Use Sandbox Environment")
    api_username = models.CharField(max_length=255, blank=True, verbose_name="API Username")
    api_password = models.CharField(max_length=255, blank=True, verbose_name="API Password")
    
    # Features
    auto_submit = models.BooleanField(default=True, verbose_name="Auto Submit Invoices to ZATCA")
    auto_sign = models.BooleanField(default=True, verbose_name="Auto Sign Invoices")
    generate_qr = models.BooleanField(default=True, verbose_name="Generate QR Code")
    
    # Status
    is_configured = models.BooleanField(default=False, verbose_name="Configuration Complete")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name="Last Sync with ZATCA")
    
    class Meta:
        verbose_name = 'ZATCA Configuration'
        verbose_name_plural = 'ZATCA Configurations'
    
    def __str__(self):
        return f"ZATCA Config - {self.organization_name} ({self.organization_trn})"
    
    def save(self, *args, **kwargs):
        # Ensure only one active configuration
        if self.is_active:
            ZATCAConfiguration.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

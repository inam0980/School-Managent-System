from django.db import models
from django.conf import settings
from students.models import Student
from settings_app.models import VATConfig
from datetime import date, datetime
from decimal import Decimal

# Create your models here.

class FeeCategory(models.Model):
    """
    Fee categories like Tuition Fee, Transport Fee, Books Fee, etc. with Arabic support
    """
    category_name = models.CharField(max_length=100, unique=True, verbose_name="Fee Category Name")
    category_name_arabic = models.CharField(max_length=100, blank=True, verbose_name="Fee Category Name (Arabic)")
    description = models.TextField(blank=True, verbose_name="Description")
    description_arabic = models.TextField(blank=True, verbose_name="Description (Arabic)")
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Default Amount (SAR)")
    is_mandatory = models.BooleanField(default=True, verbose_name="Mandatory Fee")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    # Display order for receipts
    display_order = models.IntegerField(default=0, verbose_name="Display Order")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'category_name']
        verbose_name = 'Fee Category'
        verbose_name_plural = 'Fee Categories'
    
    def __str__(self):
        return f"{self.category_name} - {self.default_amount} SAR"


class Discount(models.Model):
    """
    Discount types and rules
    """
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    discount_name = models.CharField(max_length=100, unique=True, verbose_name="Discount Name")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Discount Value")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Validity period
    valid_from = models.DateField(verbose_name="Valid From")
    valid_to = models.DateField(verbose_name="Valid To")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Discount'
        verbose_name_plural = 'Discounts'
    
    def __str__(self):
        if self.discount_type == 'percentage':
            return f"{self.discount_name} - {self.discount_value}%"
        else:
            return f"{self.discount_name} - {self.discount_value} SAR"
    
    def calculate_discount(self, amount):
        """Calculate discount amount based on type using Decimal arithmetic"""
        from decimal import Decimal
        if self.discount_type == 'percentage':
            # ensure we perform decimal math to avoid float conversion
            pct = Decimal(self.discount_value) / Decimal('100')
            return amount * pct
        else:
            return Decimal(self.discount_value)
    
    def is_valid(self):
        """Check if discount is currently valid"""
        today = date.today()
        return self.is_active and self.valid_from <= today <= self.valid_to


class Invoice(models.Model):
    """
    Invoice/Bill for student fees
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Payment'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Invoice Details
    invoice_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Invoice Number")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='invoices')
    academic_year = models.CharField(max_length=20, verbose_name="Academic Year")
    
    # Dates
    invoice_date = models.DateField(default=date.today, verbose_name="Invoice Date")
    due_date = models.DateField(verbose_name="Due Date")
    
    # Financial Details
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Subtotal (SAR)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Discount Amount (SAR)")
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="VAT Amount (SAR)")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total Amount (SAR)")
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Paid Amount (SAR)")
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Balance Amount (SAR)")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Notes
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # Discount
    discount = models.ForeignKey(Discount, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    
    # ZATCA E-Invoice Integration
    zatca_submitted = models.BooleanField(default=False, verbose_name="Submitted to ZATCA")
    zatca_compliance_status = models.CharField(
        max_length=50, 
        blank=True,
        choices=[
            ('pending', 'Pending'),
            ('compliant', 'Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('rejected', 'Rejected'),
        ],
        verbose_name="ZATCA Compliance Status"
    )
    zatca_submission_uuid = models.CharField(max_length=100, blank=True, verbose_name="ZATCA Submission UUID")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='invoices_created')
    
    class Meta:
        ordering = ['-invoice_date', '-invoice_number']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
    
    def __str__(self):
        return f"{self.invoice_number} - {self.student.get_full_name()} - {self.total_amount} SAR"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Auto-generate invoice number: INV{YYYY}{MM}{COUNT}
            today = date.today()
            year_month = today.strftime('%Y%m')
            count = Invoice.objects.filter(invoice_number__startswith=f'INV{year_month}').count() + 1
            self.invoice_number = f'INV{year_month}{count:05d}'
        
        # Calculate amounts
        self.balance_amount = self.total_amount - self.paid_amount
        
        # Update status based on payment
        if self.balance_amount <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        elif date.today() > self.due_date and self.balance_amount > 0:
            self.status = 'overdue'
        elif self.status == 'draft':
            pass  # Keep draft status
        else:
            self.status = 'pending'
        
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate invoice totals from line items"""
        items = self.items.all()
        self.subtotal = sum(item.total_amount for item in items)
        
        # Apply discount only if valid; otherwise reset to zero
        if self.discount and self.discount.is_valid():
            self.discount_amount = self.discount.calculate_discount(self.subtotal)
        else:
            # ensure old discount amounts aren't carried over
            self.discount_amount = Decimal('0.00')
        
        # Calculate amount after discount
        amount_after_discount = self.subtotal - self.discount_amount
        
        # Calculate VAT
        try:
            vat_config = VATConfig.objects.filter(is_active=True).first()
            if vat_config:
                self.vat_amount = amount_after_discount * (vat_config.vat_percentage / 100)
        except:
            self.vat_amount = amount_after_discount * Decimal('0.15')  # Default 15% VAT
        
        # Calculate total
        self.total_amount = amount_after_discount + self.vat_amount
        self.balance_amount = self.total_amount - self.paid_amount
        
        self.save()


class InvoiceItem(models.Model):
    """
    Line items in an invoice
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    quantity = models.IntegerField(default=1, verbose_name="Quantity")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Unit Price (SAR)")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Amount (SAR)")
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Invoice Item'
        verbose_name_plural = 'Invoice Items'
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.fee_category.category_name}"
    
    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Update invoice totals
        self.invoice.calculate_totals()


class Payment(models.Model):
    """
    Payment records for invoices with transaction tracking
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Payment Details
    payment_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="Payment Number")
    transaction_number = models.CharField(max_length=100, unique=True, blank=True, verbose_name="Transaction Number")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    payment_date = models.DateField(default=date.today, verbose_name="Payment Date")
    payment_time = models.TimeField(auto_now_add=True, verbose_name="Payment Time")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount (SAR)")
    
    # Payment Method
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    
    # Payment Reference
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="Reference/Transaction Number")
    cheque_number = models.CharField(max_length=50, blank=True, verbose_name="Cheque Number")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="Bank Name")
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')
    
    # Notes
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # Receipt
    receipt_number = models.CharField(max_length=50, blank=True, verbose_name="Receipt Number")
    
    # Receipt printed tracking
    receipt_printed = models.BooleanField(default=False, verbose_name="Receipt Printed")
    receipt_printed_at = models.DateTimeField(null=True, blank=True, verbose_name="Receipt Printed At")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payments_received')
    
    class Meta:
        ordering = ['-payment_date', '-payment_time']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"{self.payment_number} - {self.invoice.invoice_number} - {self.amount} SAR"
    
    def save(self, *args, **kwargs):
        if not self.payment_number:
            # Auto-generate payment number: PAY{YYYY}{MM}{COUNT}
            today = date.today()
            year_month = today.strftime('%Y%m')
            count = Payment.objects.filter(payment_number__startswith=f'PAY{year_month}').count() + 1
            self.payment_number = f'PAY{year_month}{count:05d}'
        
        if not self.receipt_number:
            # Auto-generate receipt number
            self.receipt_number = f'REC{self.payment_number[3:]}'
        
        if not self.transaction_number:
            # Auto-generate transaction number: LIK{timestamp}{random}
            from datetime import datetime
            import random
            timestamp = datetime.now().strftime('%y%m%d%H%M%S')
            random_num = random.randint(100, 999)
            self.transaction_number = f'LIK{timestamp}{random_num}'
        
        super().save(*args, **kwargs)
        
        # Update invoice paid amount and status
        if self.status == 'completed':
            invoice = self.invoice
            total_paid = invoice.payments.filter(status='completed').aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            invoice.paid_amount = total_paid
            invoice.save()

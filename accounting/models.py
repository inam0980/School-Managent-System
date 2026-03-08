from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class FiscalYear(models.Model):
    """Financial Year for accounting periods"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='fiscal_years')
    name = models.CharField(max_length=100)  # e.g., "FY 2024-2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_closed = models.BooleanField(default=False)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_fiscal_years')
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        unique_together = ['school', 'name']
        indexes = [
            models.Index(fields=['school', 'is_active']),
            models.Index(fields=['school', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.school.school_name} - {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")


class AccountType(models.TextChoices):
    """Chart of Accounts Types following standard accounting classification"""
    ASSET = 'asset', _('Asset')
    LIABILITY = 'liability', _('Liability')
    EQUITY = 'equity', _('Equity')
    REVENUE = 'revenue', _('Revenue')
    EXPENSE = 'expense', _('Expense')


class Account(models.Model):
    """Chart of Accounts - General Ledger Accounts"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='accounts')
    code = models.CharField(max_length=20, help_text="Account code (e.g., 1000, 4100)")
    name = models.CharField(max_length=200)
    name_arabic = models.CharField(max_length=200, blank=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_accounts')
    
    # Account behavior
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="System accounts cannot be deleted")
    allow_manual_entries = models.BooleanField(default=True, help_text="Allow direct journal entries to this account")
    
    # Financial tracking
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    opening_balance_type = models.CharField(
        max_length=6,
        choices=[('debit', 'Debit'), ('credit', 'Credit')],
        default='debit'
    )
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Metadata
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_accounts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        unique_together = [['school', 'code'], ['school', 'name']]
        indexes = [
            models.Index(fields=['school', 'account_type']),
            models.Index(fields=['school', 'code']),
            models.Index(fields=['school', 'is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_balance(self, as_of_date=None):
        """Calculate account balance up to a specific date"""
        from django.db.models import Sum, Q
        
        journal_lines = self.journal_lines.filter(
            journal_entry__status='posted',
            journal_entry__fiscal_year__school=self.school
        )
        
        if as_of_date:
            journal_lines = journal_lines.filter(journal_entry__date__lte=as_of_date)
        
        debits = journal_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
        credits = journal_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
        
        # Apply opening balance
        if self.opening_balance_type == 'debit':
            debits += self.opening_balance
        else:
            credits += self.opening_balance
        
        # For asset and expense accounts, balance is debit - credit
        # For liability, equity, and revenue accounts, balance is credit - debit
        if self.account_type in [AccountType.ASSET, AccountType.EXPENSE]:
            return debits - credits
        else:
            return credits - debits

    def update_current_balance(self):
        """Update the cached current balance"""
        self.current_balance = self.get_balance()
        self.save(update_fields=['current_balance'])


class JournalEntry(models.Model):
    """Journal Entry - Double Entry Accounting Record"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('posted', _('Posted')),
        ('cancelled', _('Cancelled')),
    ]
    
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='journal_entries')
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name='journal_entries')
    entry_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    
    # Entry metadata
    reference = models.CharField(max_length=100, blank=True, help_text="External reference (e.g., Invoice #, Receipt #)")
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Linked transactions (Accountant mode - zatca removed)
    # invoice = models.ForeignKey('zatca.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries')
    billing_invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries')
    payment = models.ForeignKey('billing.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries')
    
    # Totals (must balance)
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Workflow
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_journal_entries')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journal_entries')
    posted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-entry_number']
        verbose_name_plural = "Journal Entries"
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'date']),
            models.Index(fields=['fiscal_year', 'status']),
            models.Index(fields=['entry_number']),
        ]

    def __str__(self):
        return f"JE-{self.entry_number} ({self.date})"

    def calculate_totals(self):
        """Calculate total debits and credits from lines"""
        from django.db.models import Sum
        
        totals = self.lines.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        
        self.total_debit = totals['total_debit'] or Decimal('0')
        self.total_credit = totals['total_credit'] or Decimal('0')

    def clean(self):
        """Validate journal entry"""
        self.calculate_totals()
        
        # Check if entry balances
        if abs(self.total_debit - self.total_credit) > Decimal('0.01'):
            raise ValidationError(
                f"Journal entry must balance. Debit: {self.total_debit}, Credit: {self.total_credit}"
            )
        
        # Check date is within fiscal year
        if self.fiscal_year_id:
            if self.date < self.fiscal_year.start_date or self.date > self.fiscal_year.end_date:
                raise ValidationError(
                    f"Entry date must be within fiscal year {self.fiscal_year.name}"
                )
        
        # Cannot modify posted entries
        if self.pk and self.status == 'posted':
            old_instance = JournalEntry.objects.get(pk=self.pk)
            if old_instance.status == 'posted':
                raise ValidationError("Cannot modify posted journal entries")

    def post(self, user):
        """Post the journal entry and update account balances"""
        if self.status == 'posted':
            raise ValidationError("Entry is already posted")
        
        self.clean()  # Validate before posting
        
        self.status = 'posted'
        self.posted_by = user
        from django.utils import timezone
        self.posted_at = timezone.now()
        self.save()
        
        # Update account balances
        for line in self.lines.all():
            line.account.update_current_balance()

    def generate_entry_number(self):
        """Auto-generate journal entry number"""
        if not self.entry_number:
            prefix = f"JE{self.fiscal_year.start_date.year}"
            last_entry = JournalEntry.objects.filter(
                entry_number__startswith=prefix
            ).order_by('-entry_number').first()
            
            if last_entry:
                last_num = int(last_entry.entry_number[len(prefix):])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.entry_number = f"{prefix}{new_num:06d}"


class JournalEntryLine(models.Model):
    """Journal Entry Line Item - Individual debit/credit to an account"""
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    
    description = models.CharField(max_length=500, blank=True)
    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    # Optional references (Accountant mode - teacher removed)
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True)
    # teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True)
    
    line_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['line_number']
        unique_together = ['journal_entry', 'line_number']

    def __str__(self):
        amount = self.debit_amount if self.debit_amount > 0 else self.credit_amount
        entry_type = "DR" if self.debit_amount > 0 else "CR"
        return f"{self.account.code} - {entry_type} {amount}"

    def clean(self):
        """Validate line item"""
        # Cannot have both debit and credit
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("Line cannot have both debit and credit amounts")
        
        # Must have either debit or credit
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("Line must have either debit or credit amount")
        
        # Check if account allows manual entries
        if self.account and not self.account.allow_manual_entries:
            raise ValidationError(f"Account {self.account.code} does not allow manual entries")


class AccountingPeriod(models.Model):
    """Monthly accounting periods within a fiscal year"""
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name='periods')
    name = models.CharField(max_length=50)  # e.g., "January 2024"
    period_number = models.PositiveIntegerField()  # 1-12
    start_date = models.DateField()
    end_date = models.DateField()
    
    is_closed = models.BooleanField(default=False)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fiscal_year', 'period_number']
        unique_together = ['fiscal_year', 'period_number']

    def __str__(self):
        return f"{self.fiscal_year.name} - {self.name}"


class BudgetLine(models.Model):
    """Budget allocation per account per fiscal year"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='budget_lines')
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name='budget_lines')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='budget_lines')
    
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['fiscal_year', 'account']
        indexes = [
            models.Index(fields=['school', 'fiscal_year']),
            models.Index(fields=['account']),
        ]

    def __str__(self):
        return f"{self.account.code} - {self.fiscal_year.name} Budget"

    def calculate_variance(self):
        """Calculate budget variance"""
        self.actual_amount = self.account.get_balance()
        self.variance = self.budgeted_amount - self.actual_amount
        self.save(update_fields=['actual_amount', 'variance'])

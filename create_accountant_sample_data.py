"""
Create Sample Financial Data for Accountant Testing
This script creates:
- Schools and organizations
- Sample students (for billing)
- Fee categories
- Sample invoices
- Sample payments
- Fiscal years and accounts
- Sample journal entries
- VAT configuration
Run this script after creating the accountant user with create_accountant_only.py
"""

import os
import django
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Database1.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

# Import models
from schools.models import Organization, School
from students.models import Student
from billing.models import FeeCategory, Invoice, InvoiceItem, Payment, Discount
from accounting.models import FiscalYear, Account, AccountType, JournalEntry, JournalEntryLine
from settings_app.models import VATConfig

User = get_user_model()


@transaction.atomic
def create_sample_data():
    """Create comprehensive sample data for accountant"""
    
    print("\n" + "="*60)
    print("  CREATING SAMPLE FINANCIAL DATA FOR ACCOUNTANT")
    print("="*60 + "\n")
    
    # Get or create accountant user
    accountant = User.objects.filter(username='accountant').first()
    if not accountant:
        print("❌ Accountant user not found. Please run create_accountant_only.py first.")
        return
    
    print(f"✅ Found accountant user: {accountant.username}\n")
    
    # 1. Create Organization and School
    print("📍 Step 1: Creating Organization and School...")
    org, created = Organization.objects.get_or_create(
        name="Al-Madinah Education Group",
        defaults={
            'organization_code': 'AMEG001',
            'registration_number': 'REG-2024-001',
            'email': 'info@almadina-edu.sa',
            'phone': '+966112345678',
            'address': '123 Education District, Riyadh',
            'city': 'Riyadh',
            'country': 'Saudi Arabia',
            'tax_number': 'TAX123456789',
            'vat_registration_number': 'SA123456789012345',
            'is_active': True
        }
    )
    print(f"   {'Created' if created else 'Found'} Organization: {org.name}")
    
    school, created = School.objects.get_or_create(
        school_name="International Academy",
        organization=org,
        defaults={
            'school_code': 'IA2024',
            'school_type': 'mixed',
            'shift': 'morning',
            'address': '123 Education Street, Al Olaya District, Riyadh',
            'city': 'Riyadh',
            'phone': '+966111234567',
            'email': 'info@intacademy.edu.sa',
            'principal_name': 'Dr. Khalid Al-Rahman',
            'principal_email': 'principal@intacademy.edu.sa',
            'principal_phone': '+966501234567',
            'total_capacity': 500,
            'is_active': True
        }
    )
    print(f"   {'Created' if created else 'Found'} School: {school.school_name}\n")
    
    # 2. Create VAT Configuration
    print("💰 Step 2: Setting up VAT Configuration...")
    today = date.today()
    vat_config, created = VATConfig.objects.get_or_create(
        is_active=True,
        defaults={
            'vat_percentage': Decimal('15.00'),
            'effective_from': today - timedelta(days=365),
            'description': 'Standard VAT rate for Saudi Arabia'
        }
    )
    if not created:
        # Update if exists
        vat_config = VATConfig.objects.filter(is_active=True).first()
        if not vat_config:
            vat_config = VATConfig.objects.create(
                vat_percentage=Decimal('15.00'),
                effective_from=today - timedelta(days=365),
                is_active=True,
                description='Standard VAT rate for Saudi Arabia'
            )
    print(f"   VAT Rate: {vat_config.vat_percentage}%\n")
    
    # 3. Create Students
    print("👨‍🎓 Step 3: Creating Sample Students...")
    student_names = [
        ('Ahmed', 'Al-Hassan'),
        ('Fatima', 'Al-Zahrani'),
        ('Mohammed', 'Al-Qahtani'),
        ('Sara', 'Al-Dosari'),
        ('Omar', 'Al-Maliki'),
        ('Layla', 'Al-Shammari'),
        ('Khalid', 'Al-Mutairi'),
        ('Noura', 'Al-Otaibi'),
        ('Abdullah', 'Al-Harbi'),
        ('Mariam', 'Al-Ghamdi'),
    ]
    
    students = []
    for i, (first_name, last_name) in enumerate(student_names, 1):
        student, created = Student.objects.get_or_create(
            student_id=f'STU202400{i:02d}',
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': f'{first_name.lower()}.{last_name.lower()}@student.edu.sa',
                'phone': f'+966-50-{random.randint(1000000, 9999999)}',
                'school': school,
                'is_active': True
            }
        )
        students.append(student)
        if created:
            print(f"   ✓ Created: {student.student_id} - {student.get_full_name()}")
    
    print(f"\n   Total Students: {len(students)}\n")
    
    # 4. Create Fee Categories
    print("📋 Step 4: Creating Fee Categories...")
    fee_categories_data = [
        ('Tuition Fee', 'Annual tuition fee', Decimal('25000.00'), True),
        ('Registration Fee', 'One-time registration', Decimal('2000.00'), True),
        ('Books & Materials', 'Textbooks and learning materials', Decimal('1500.00'), False),
        ('Transport Fee', 'School bus transportation', Decimal('3000.00'), False),
        ('Lab Fee', 'Science laboratory usage', Decimal('1000.00'), False),
        ('Sports Fee', 'Sports activities and equipment', Decimal('800.00'), False),
        ('Technology Fee', 'Computer and internet access', Decimal('1200.00'), True),
        ('Exam Fee', 'Examination charges', Decimal('500.00'), True),
    ]
    
    fee_categories = []
    for name, desc, amount, mandatory in fee_categories_data:
        cat, created = FeeCategory.objects.get_or_create(
            category_name=name,
            defaults={
                'description': desc,
                'default_amount': amount,
                'is_mandatory': mandatory,
                'is_active': True
            }
        )
        fee_categories.append(cat)
        if created:
            print(f"   ✓ {name}: {amount} SAR")
    
    print(f"\n   Total Fee Categories: {len(fee_categories)}\n")
    
    # 5. Create Discounts
    print("🎟️  Step 5: Creating Discount Schemes...")
    today = date.today()
    discounts_data = [
        ('Early Bird Discount', 'percentage', Decimal('10.00'), 'Register before deadline'),
        ('Sibling Discount', 'percentage', Decimal('15.00'), '2nd child discount'),
        ('Scholarship', 'percentage', Decimal('50.00'), 'Merit-based scholarship'),
        ('Staff Discount', 'percentage', Decimal('25.00'), 'Staff children discount'),
    ]
    
    discounts = []
    for name, disc_type, value, desc in discounts_data:
        disc, created = Discount.objects.get_or_create(
            discount_name=name,
            defaults={
                'discount_type': disc_type,
                'discount_value': value,
                'description': desc,
                'valid_from': today - timedelta(days=30),
                'valid_to': today + timedelta(days=365),
                'is_active': True
            }
        )
        discounts.append(disc)
        if created:
            print(f"   ✓ {name}: {value}% discount")
    
    print()
    
    # 6. Create Invoices
    print("🧾 Step 6: Creating Sample Invoices...")
    invoice_count = 0
    payment_count = 0
    
    for i, student in enumerate(students, 1):
        # Create invoice
        invoice = Invoice.objects.create(
            student=student,
            academic_year='2025-2026',
            invoice_date=today - timedelta(days=random.randint(0, 60)),
            due_date=today + timedelta(days=30),
            created_by=accountant,
            status='pending'
        )
        
        # Add invoice items
        subtotal = Decimal('0')
        
        # All students get tuition
        tuition = fee_categories[0]  # Tuition Fee
        item = InvoiceItem.objects.create(
            invoice=invoice,
            fee_category=tuition,
            description=tuition.category_name,
            quantity=1,
            unit_price=tuition.default_amount,
            total_amount=tuition.default_amount
        )
        subtotal += item.total_amount
        
        # Random additional fees
        for fee_cat in random.sample(fee_categories[2:], random.randint(2, 4)):
            item = InvoiceItem.objects.create(
                invoice=invoice,
                fee_category=fee_cat,
                description=fee_cat.category_name,
                quantity=1,
                unit_price=fee_cat.default_amount,
                total_amount=fee_cat.default_amount
            )
            subtotal += item.total_amount
        
        # Apply random discount for some students
        discount_amount = Decimal('0')
        if random.random() < 0.4:  # 40% get discount
            discount = random.choice(discounts)
            invoice.discount = discount
            discount_amount = subtotal * (discount.discount_value / 100)
        
        # Calculate totals
        invoice.subtotal = subtotal
        invoice.discount_amount = discount_amount
        invoice.vat_amount = (subtotal - discount_amount) * (vat_config.vat_percentage / 100)
        invoice.total_amount = subtotal - discount_amount + invoice.vat_amount
        invoice.balance_amount = invoice.total_amount
        
        # Generate invoice number
        invoice.invoice_number = f'INV-2025-{i:04d}'
        invoice.save()
        
        invoice_count += 1
        
        # Create payments for some invoices (60% paid/partial)
        if random.random() < 0.6:
            payment_methods = ['cash', 'bank_transfer', 'card', 'cheque']
            payment_statuses = ['completed', 'completed', 'completed', 'pending']
            
            # Full or partial payment
            if random.random() < 0.7:  # 70% full payment
                payment_amount = invoice.total_amount
                invoice.status = 'paid'
            else:  # 30% partial payment
                payment_amount = invoice.total_amount * Decimal(str(random.choice([0.3, 0.5, 0.7])))
                invoice.status = 'partial'
            
            payment = Payment.objects.create(
                invoice=invoice,
                payment_date=invoice.invoice_date + timedelta(days=random.randint(1, 20)),
                amount=payment_amount,
                payment_method=random.choice(payment_methods),
                status=random.choice(payment_statuses),
                received_by=accountant,
                reference_number=f'PAY-{random.randint(100000, 999999)}'
            )
            payment.payment_number = f'PAY-2025-{payment_count+1:04d}'
            payment.save()
            
            invoice.paid_amount = payment_amount
            invoice.balance_amount = invoice.total_amount - payment_amount
            invoice.save()
            
            payment_count += 1
    
    print(f"   ✓ Created {invoice_count} invoices")
    print(f"   ✓ Created {payment_count} payments\n")
    
    # 7. Create Fiscal Year
    print("📅 Step 7: Setting up Fiscal Year...")
    fiscal_year, created = FiscalYear.objects.get_or_create(
        school=school,
        name='FY 2025-2026',
        defaults={
            'start_date': date(2025, 9, 1),
            'end_date': date(2026, 8, 31),
            'is_active': True,
            'is_closed': False
        }
    )
    print(f"   ✓ {'Created' if created else 'Found'} Fiscal Year: {fiscal_year.name}\n")
    
    # 8. Create Chart of Accounts
    print("📊 Step 8: Creating Chart of Accounts...")
    accounts_data = [
        # Assets
        ('1000', 'Cash', AccountType.ASSET, None),
        ('1100', 'Bank - Al Rajhi', AccountType.ASSET, None),
        ('1200', 'Accounts Receivable', AccountType.ASSET, None),
        ('1300', 'Prepaid Expenses', AccountType.ASSET, None),
        
        # Liabilities
        ('2000', 'Accounts Payable', AccountType.LIABILITY, None),
        ('2100', 'VAT Payable', AccountType.LIABILITY, None),
        ('2200', 'Salaries Payable', AccountType.LIABILITY, None),
        
        # Equity
        ('3000', 'Capital', AccountType.EQUITY, None),
        ('3100', 'Retained Earnings', AccountType.EQUITY, None),
        
        # Revenue
        ('4000', 'Tuition Fee Revenue', AccountType.REVENUE, None),
        ('4100', 'Registration Fee Revenue', AccountType.REVENUE, None),
        ('4200', 'Other Fee Revenue', AccountType.REVENUE, None),
        
        # Expenses
        ('5000', 'Salary Expense', AccountType.EXPENSE, None),
        ('5100', 'Rent Expense', AccountType.EXPENSE, None),
        ('5200', 'Utilities Expense', AccountType.EXPENSE, None),
        ('5300', 'Office Supplies Expense', AccountType.EXPENSE, None),
    ]
    
    accounts = {}
    for code, name, acc_type, parent_code in accounts_data:
        parent = accounts.get(parent_code) if parent_code else None
        account, created = Account.objects.get_or_create(
            school=school,
            code=code,
            defaults={
                'name': name,
                'account_type': acc_type,
                'parent': parent,
                'is_active': True,
                'created_by': accountant
            }
        )
        accounts[code] = account
        if created:
            print(f"   ✓ {code} - {name}")
    
    print(f"\n   Total Accounts: {len(accounts)}\n")
    
    # 9. Create Sample Journal Entries
    print("📖 Step 9: Creating Sample Journal Entries...")
    
    # Get some paid invoices
    paid_invoices = Invoice.objects.filter(status='paid')[:3]
    
    for invoice in paid_invoices:
        # Create journal entry for invoice
        entry = JournalEntry.objects.create(
            school=school,
            fiscal_year=fiscal_year,
            date=invoice.invoice_date,
            description=f'Student fees invoice - {invoice.student.get_full_name()}',
            status='posted',
            created_by=accountant,
            posted_by=accountant,
            posted_at=timezone.now()
        )
        entry.entry_number = f'JE-{entry.id:05d}'
        entry.save()
        
        # Debit: Accounts Receivable
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=accounts['1200'],
            description='Student fees receivable',
            debit_amount=invoice.total_amount,
            credit_amount=Decimal('0'),
            student=invoice.student,
            line_number=1
        )
        
        # Credit: Revenue accounts
        revenue_amount = invoice.subtotal - invoice.discount_amount
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=accounts['4000'],
            description='Tuition fee revenue',
            debit_amount=Decimal('0'),
            credit_amount=revenue_amount,
            student=invoice.student,
            line_number=2
        )
        
        # Credit: VAT Payable
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=accounts['2100'],
            description='VAT on student fees',
            debit_amount=Decimal('0'),
            credit_amount=invoice.vat_amount,
            student=invoice.student,
            line_number=3
        )
        
        # Update entry totals
        entry.total_debit = invoice.total_amount
        entry.total_credit = invoice.total_amount
        entry.save()
        
        # Create journal entry for payment
        payment = invoice.payments.first()
        if payment:
            pay_entry = JournalEntry.objects.create(
                school=school,
                fiscal_year=fiscal_year,
                date=payment.payment_date,
                description=f'Payment received - {invoice.student.get_full_name()}',
                status='posted',
                billing_invoice=invoice,
                payment=payment,
                created_by=accountant,
                posted_by=accountant,
                posted_at=timezone.now()
            )
            pay_entry.entry_number = f'JE-{pay_entry.id:05d}'
            pay_entry.save()
            
            # Debit: Cash/Bank
            cash_account = accounts['1100'] if payment.payment_method == 'bank_transfer' else accounts['1000']
            JournalEntryLine.objects.create(
                journal_entry=pay_entry,
                account=cash_account,
                description='Payment received',
                debit_amount=payment.amount,
                credit_amount=Decimal('0'),
                student=invoice.student,
                line_number=1
            )
            
            # Credit: Accounts Receivable
            JournalEntryLine.objects.create(
                journal_entry=pay_entry,
                account=accounts['1200'],
                description='Payment against invoice',
                debit_amount=Decimal('0'),
                credit_amount=payment.amount,
                student=invoice.student,
                line_number=2
            )
            
            pay_entry.total_debit = payment.amount
            pay_entry.total_credit = payment.amount
            pay_entry.save()
    
    entries_count = JournalEntry.objects.filter(school=school).count()
    print(f"   ✓ Created {entries_count} journal entries\n")
    
    # Summary
    print("="*60)
    print("  📊 DATA CREATION SUMMARY")
    print("="*60)
    print(f"  Organizations:      1")
    print(f"  Schools:            1")
    print(f"  Students:           {len(students)}")
    print(f"  Fee Categories:     {len(fee_categories)}")
    print(f"  Discounts:          {len(discounts)}")
    print(f"  Invoices:           {invoice_count}")
    print(f"  Payments:           {payment_count}")
    print(f"  Fiscal Years:       1")
    print(f"  Chart of Accounts:  {len(accounts)}")
    print(f"  Journal Entries:    {entries_count}")
    print("="*60)
    
    # Calculate financial summary
    total_invoiced = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    total_pending = Invoice.objects.filter(status__in=['pending', 'partial']).aggregate(total=Sum('balance_amount'))['total'] or 0
    
    print("\n" + "="*60)
    print("  💰 FINANCIAL SUMMARY")
    print("="*60)
    print(f"  Total Invoiced:     {total_invoiced:,.2f} SAR")
    print(f"  Total Paid:         {total_paid:,.2f} SAR")
    print(f"  Total Outstanding:  {total_pending:,.2f} SAR")
    print("="*60)
    
    print("\n✅ Sample data created successfully!")
    print("\n🌐 Login at: http://127.0.0.1:8001/accounts/login/")
    print("👤 Username: accountant")
    print("🔑 Password: accountant123\n")


if __name__ == '__main__':
    from django.db.models import Sum
    create_sample_data()

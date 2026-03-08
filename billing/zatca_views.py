"""
ZATCA Invoice Views and Integration
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.utils import timezone
import json
import uuid

from .models import Invoice
from .zatca_models import ZATCASubmission, ZATCAConfiguration
from .zatca_service import ZATCAEInvoiceService
from accounts.decorators import module_required


def get_zatca_service():
    """Get configured ZATCA service instance"""
    try:
        config = ZATCAConfiguration.objects.filter(is_active=True, is_configured=True).first()
        if not config:
            return None
        
        return ZATCAEInvoiceService(
            organization_trn=config.organization_trn,
            organization_name=config.organization_name,
            certificate_path=config.certificate_path,
            private_key_path=config.private_key_path,
            use_sandbox=config.use_sandbox
        )
    except Exception as e:
        print(f"Error initializing ZATCA service: {str(e)}")
        return None


def prepare_invoice_data(invoice):
    """Prepare invoice object for ZATCA conversion"""
    return {
        'invoice_number': invoice.invoice_number,
        'invoice_date': invoice.invoice_date.isoformat(),
        'invoice_time': '00:00:00',
        'invoice_type': 'Standard Invoice',
        'uuid': str(uuid.uuid4()),
        
        # Supplier (Company) info
        'supplier_phone': '966500000000',
        'supplier_email': 'info@school.edu.sa',
        'supplier_address': 'Riyadh, Saudi Arabia',
        'supplier_city': 'Riyadh',
        
        # Customer (Student) info
        'customer_id': invoice.student.student_id,
        'customer_name': invoice.student.get_full_name(),
        'customer_email': invoice.student.email or 'student@example.com',
        
        # Financial details
        'subtotal': float(invoice.subtotal),
        'discount_amount': float(invoice.discount_amount),
        'vat_amount': float(invoice.vat_amount),
        'total_amount': float(invoice.total_amount),
        
        # Line items
        'items': [
            {
                'description': item.fee_category.category_name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_amount': float(item.total_amount),
            }
            for item in invoice.items.all()
        ]
    }


@login_required
@module_required('billing')
@require_http_methods(["POST"])
def submit_invoice_to_zatca(request, invoice_number):
    """Submit invoice to ZATCA for compliance"""
    invoice = get_object_or_404(Invoice, invoice_number=invoice_number)
    
    # Check if already submitted
    existing_submission = ZATCASubmission.objects.filter(invoice=invoice).first()
    if existing_submission and existing_submission.status in ['submitted', 'compliant']:
        messages.warning(request, "Invoice already submitted to ZATCA")
        return redirect('billing:detail', invoice_number=invoice_number)
    
    try:
        zatca_service = get_zatca_service()
        if not zatca_service:
            messages.error(request, "ZATCA configuration not found or incomplete")
            return redirect('billing:detail', invoice_number=invoice_number)
        
        # Prepare invoice data
        invoice_data = prepare_invoice_data(invoice)
        
        # Generate XML
        xml_content = zatca_service.invoice_to_xml(invoice_data)
        
        # Validate XML
        is_valid, error_msg = zatca_service.validate_invoice_format(xml_content)
        if not is_valid:
            messages.error(request, f"Invoice validation failed: {error_msg}")
            return redirect('billing:detail', invoice_number=invoice_number)
        
        # Sign invoice
        signature = zatca_service.sign_invoice_xml(xml_content)
        
        # Generate QR code
        qr_bytes = zatca_service.generate_qr_code(invoice_data, xml_content)
        
        # Create or update submission
        if existing_submission:
            submission = existing_submission
        else:
            submission = ZATCASubmission(invoice=invoice)
        
        submission.xml_content = xml_content
        submission.xml_signature = signature
        submission.status = 'pending'
        submission.save()
        
        # Save QR code
        qr_filename = f"zatca_qr_{invoice.invoice_number}_{uuid.uuid4().hex[:8]}.png"
        submission.qr_code.save(qr_filename, ContentFile(qr_bytes), save=True)
        
        # Submit to ZATCA
        api_response = zatca_service.submit_invoice_to_zatca(xml_content, submission.submission_uuid)
        
        submission.zatca_response = api_response
        submission.submitted_at = timezone.now()
        
        if api_response.get('success'):
            submission.status = 'submitted'
            submission.zatca_status = 'submitted'
            messages.success(request, "Invoice submitted to ZATCA successfully")
        else:
            submission.status = 'error'
            messages.error(request, f"ZATCA submission error: {api_response.get('error')}")
        
        submission.save()
        
    except Exception as e:
        messages.error(request, f"Error submitting invoice: {str(e)}")
    
    return redirect('billing:detail', invoice_number=invoice_number)


@login_required
@module_required('billing')
def zatca_submission_status(request, invoice_number):
    """Check ZATCA submission status"""
    invoice = get_object_or_404(Invoice, invoice_number=invoice_number)
    submission = ZATCASubmission.objects.filter(invoice=invoice).first()
    
    if not submission:
        return JsonResponse({
            'status': 'not_submitted',
            'message': 'Invoice not submitted to ZATCA yet'
        })
    
    return JsonResponse({
        'status': submission.status,
        'zatca_status': submission.zatca_status,
        'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
        'is_compliant': submission.is_compliant,
        'compliance_errors': submission.compliance_errors or [],
        'compliance_invoice_number': submission.compliance_invoice_number,
        'uuid': str(submission.submission_uuid),
    })


@login_required
@module_required('billing')
def download_zatca_xml(request, invoice_number):
    """Download ZATCA XML for invoice"""
    invoice = get_object_or_404(Invoice, invoice_number=invoice_number)
    submission = ZATCASubmission.objects.filter(invoice=invoice).first()
    
    if not submission:
        messages.error(request, "No ZATCA submission found for this invoice")
        return redirect('billing:detail', invoice_number=invoice_number)
    
    response = HttpResponse(submission.xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}_zatca.xml"'
    return response


@login_required
@module_required('billing')
def download_zatca_qr(request, invoice_number):
    """Download ZATCA QR code for invoice"""
    invoice = get_object_or_404(Invoice, invoice_number=invoice_number)
    submission = ZATCASubmission.objects.filter(invoice=invoice).first()
    
    if not submission or not submission.qr_code:
        messages.error(request, "No QR code found for this invoice")
        return redirect('billing:detail', invoice_number=invoice_number)
    
    response = HttpResponse(submission.qr_code.read(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}_qr.png"'
    return response


@login_required
@module_required('billing')
def zatca_configuration_view(request):
    """View and manage ZATCA configuration"""
    config = ZATCAConfiguration.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        try:
            config_data = json.loads(request.body)
            
            if config:
                config.organization_trn = config_data.get('organization_trn', config.organization_trn)
                config.organization_name = config_data.get('organization_name', config.organization_name)
                config.organization_email = config_data.get('organization_email', config.organization_email)
                config.organization_phone = config_data.get('organization_phone', config.organization_phone)
                config.use_sandbox = config_data.get('use_sandbox', config.use_sandbox)
                config.auto_submit = config_data.get('auto_submit', config.auto_submit)
                config.auto_sign = config_data.get('auto_sign', config.auto_sign)
                config.generate_qr = config_data.get('generate_qr', config.generate_qr)
            else:
                config = ZATCAConfiguration(
                    organization_trn=config_data.get('organization_trn'),
                    organization_name=config_data.get('organization_name'),
                    organization_email=config_data.get('organization_email'),
                    organization_phone=config_data.get('organization_phone'),
                    use_sandbox=config_data.get('use_sandbox', True),
                    is_active=True
                )
            
            config.save()
            return JsonResponse({'success': True, 'message': 'Configuration updated'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'billing/zatca_configuration.html', {
        'config': config
    })

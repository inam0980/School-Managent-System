# ZATCA E-Invoice Integration Guide

## Overview
This document provides complete instructions for implementing ZATCA E-Invoice (Fatoora) integration in the Django ERP system.

## What is ZATCA?
ZATCA is the **Zakat, Tax and Customs Authority** of Saudi Arabia. The E-Invoice (Fatoora) project requires all business organizations in Saudi Arabia to issue electronic invoices with:
- XML format compliant with UBL 2.1 standard
- Digital signatures
- QR codes
- Compliance with ZATCA regulations

## Features Implemented

✅ **E-Invoice Format Converter** - Converts invoices to ZATCA XML format (UBL 2.1)
✅ **Digital Signature** - Signs invoices with organization's digital certificate
✅ **QR Code Generation** - Generates Fatoora QR codes with invoice data
✅ **ZATCA API Integration** - Submits invoices to ZATCA for compliance check
✅ **Automatic Transmission** - Can automatically submit invoices on creation
✅ **Submission Tracking** - Tracks submission status and compliance

## Installation

### 1. Install Required Packages
```bash
cd "/Users/inamkhan/Desktop/MAIN/Django Drive/DB/Database1"
pip install -r requirements.txt
```

This installs:
- `cryptography` - For digital signatures
- `lxml` - For XML handling
- `zeep` - For SOAP/Web services (optional, for advanced integration)

### 2. Create Database Migrations
```bash
python manage.py makemigrations billing
python manage.py migrate
```

This creates the tables:
- `ZATCAConfiguration` - Stores ZATCA settings
- `ZATCASubmission` - Tracks invoice submissions

### 3. Collect Static Files (if needed)
```bash
python manage.py collectstatic
```

## Configuration

### Option A: Using the Web Interface
1. Navigate to: `http://localhost:8000/billing/zatca/configuration/`
2. Fill in:
   - **Tax Registration Number (TRN)** - Your 10-digit TRN
   - **Organization Name** - Your registered business name
   - **Email & Phone** - Contact information
   - **Certificate and Key Paths** - Paths to your ZATCA certificate files
3. Select your environment (Sandbox for testing, Production for live)
4. Save configuration

### Option B: Using Management Command
```bash
python manage.py zatca_setup setup \
    --trn 3104000151 \
    --name "Your School Name" \
    --email "billing@school.edu.sa" \
    --phone "+966500000000" \
    --cert "/path/to/certificate.pem" \
    --key "/path/to/private_key.pem" \
    --sandbox
```

### Option C: Manual Database Entry
```python
from billing.zatca_models import ZATCAConfiguration

config = ZATCAConfiguration.objects.create(
    organization_trn='3104000151',
    organization_name='Your School Name',
    organization_email='billing@school.edu.sa',
    organization_phone='+966500000000',
    certificate_path='/path/to/certificate.pem',
    private_key_path='/path/to/private_key.pem',
    use_sandbox=True,
    is_configured=True,
    is_active=True
)
```

## Getting ZATCA Credentials

### Prerequisites
- Business registration certificate
- Tax identification
- Valid email and phone number

### Steps to Get Certificate

1. **Register at ZATCA Portal**
   - Visit: https://zatca.gov.sa
   - Create account with your business details
   - Verify email and phone number

2. **Obtain Tax Registration Number (TRN)**
   - TRN Format: 10 digits
   - Example: `3104000151`
   - Available in your ZATCA portal

3. **Download Digital Certificate**
   - Go to ZATCA Portal → Certificates
   - Request new certificate
   - Download in PEM format (file extension: .pem)
   - Save securely

4. **Extract Private Key**
   - If certificate includes private key, extract separately
   - Save as `.pem` file
   - Keep private and never share

5. **Update Configuration**
   - Add certificate path: `/path/to/certificate.pem`
   - Add key path: `/path/to/private_key.pem`

## Usage

### Submitting an Invoice to ZATCA

#### Method 1: Web Interface
1. Create or view an invoice
2. Click button "Submit to ZATCA"
3. System will:
   - Generate XML in ZATCA format
   - Sign with digital certificate
   - Generate QR code
   - Submit to ZATCA
   - Display submission status

#### Method 2: Python API
```python
from billing.zatca_views import prepare_invoice_data, get_zatca_service
from billing.zatca_models import ZATCASubmission
from billing.models import Invoice

# Get invoice
invoice = Invoice.objects.get(invoice_number='INV202401001')

# Get ZATCA service
zatca_service = get_zatca_service()

# Prepare data
invoice_data = prepare_invoice_data(invoice)

# Generate XML
xml_content = zatca_service.invoice_to_xml(invoice_data)

# Sign
signature = zatca_service.sign_invoice_xml(xml_content)

# Generate QR
qr_bytes = zatca_service.generate_qr_code(invoice_data, xml_content)

# Submit (optional)
response = zatca_service.submit_invoice_to_zatca(xml_content, invoice.zatca_submission_uuid)
```

#### Method 3: API Endpoint
```bash
# Submit Invoice
POST /billing/invoice/INV202401001/zatca/submit/

# Check Status
GET /billing/invoice/INV202401001/zatca/status/

# Download XML
GET /billing/invoice/INV202401001/zatca/xml/

# Download QR Code
GET /billing/invoice/INV202401001/zatca/qr/
```

### Automatic Submission
Enable automatic submission in configuration:
1. Go to ZATCA Configuration page
2. Check "Auto Submit Invoices to ZATCA"
3. Save

Now all new invoices will be automatically submitted to ZATCA on creation.

## API Responses

### Successful Submission
```json
{
    "status": "submitted",
    "zatca_status": "submitted",
    "uuid": "12345678-1234-1234-1234-123456789012",
    "compliance_invoice_number": "INV202401001",
    "is_compliant": true
}
```

### Compliance Error
```json
{
    "status": "non_compliant",
    "compliance_errors": [
        "VAT amount mismatch",
        "Invalid TRN format"
    ]
}
```

### Network Error
```json
{
    "status": "error",
    "error": "Connection to ZATCA server failed"
}
```

## Troubleshooting

### Certificate Not Found
**Error:** `Error loading credentials: [Errno 2] No such file or directory`

**Solution:**
- Verify certificate path exists
- Check file permissions: `chmod 644 certificate.pem`
- Use absolute paths, not relative

### Invalid Signature
**Error:** `Error signing invoice: Invalid certificate`

**Solution:**
- Ensure certificate matches private key
- Verify certificate is in PEM format
- Check certificate hasn't expired
- Regenerate certificate from ZATCA portal

### ZATCA API Connection Failed
**Error:** `Connection to ZATCA server failed`

**Solution:**
- Check internet connection
- Verify firewall allows outbound HTTPS
- If using sandbox, ensure `use_sandbox=True`
- If using production, ensure `use_sandbox=False`
- Check ZATCA API status page

### QR Code Generation Failed
**Error:** `qrcode module not found`

**Solution:**
```bash
pip install qrcode
```

## XML Format Details

### UBL 2.1 Structure
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" ...>
    <UBLVersionID>2.1</UBLVersionID>
    <CustomizationID>urn:cefact:ubl:ph:core:ubltr:Invoice-1.0</CustomizationID>
    <ProfileID>urn:saudiarabia:ksa:profile:ubltr:invoice:v1.0</ProfileID>
    <ID>INV202401001</ID>
    <IssueDate>2024-01-10</IssueDate>
    <IssueTime>00:00:00</IssueTime>
    ...
</Invoice>
```

## QR Code Format

ZATCA Fatoora QR Code contains:
1. Seller Name
2. VAT Number (TRN)
3. Invoice Total Amount
4. VAT Amount
5. Invoice Date
6. Invoice Time
7. Invoice Hash
8. Signature Hash
9. Signing Certificate

## Database Models

### ZATCAConfiguration
Stores ZATCA integration settings
```python
{
    'organization_trn': '3104000151',
    'organization_name': 'School Name',
    'organization_email': 'billing@school.edu.sa',
    'certificate_path': '/path/to/cert.pem',
    'private_key_path': '/path/to/key.pem',
    'use_sandbox': True,
    'auto_submit': True,
    'auto_sign': True,
    'is_configured': True,
    'is_active': True
}
```

### ZATCASubmission
Tracks invoice submissions to ZATCA
```python
{
    'invoice': <Invoice object>,
    'status': 'submitted',  # pending, submitted, compliant, non_compliant, rejected, error
    'xml_content': '<xml>...</xml>',
    'xml_signature': 'base64_encoded_signature',
    'qr_code': <ImageField>,
    'zatca_response': {'compliance': 'true'},
    'zatca_uuid': '12345678...',
    'is_compliant': True
}
```

## Testing with Sandbox

1. **Setup Sandbox Environment**
   ```bash
   python manage.py zatca_setup setup --sandbox
   ```

2. **Create Test Invoice**
   - Navigate to `/billing/` 
   - Create sample invoice

3. **Submit to Sandbox**
   - Go to invoice detail page
   - Click "Submit to ZATCA"
   - Check sandbox portal for status

4. **Monitor Submissions**
   - Admin panel: Billing → ZATCA Submissions
   - View XML, signature, QR code, API response

## Production Deployment

1. **Obtain Production Certificate**
   - Request production certificate from ZATCA
   - Download PEM files

2. **Update Configuration**
   ```bash
   python manage.py zatca_setup setup --name "Your Company" --cert /prod/cert.pem --key /prod/key.pem
   ```

3. **Disable Sandbox**
   - ZATCA Configuration page
   - Uncheck "Use Sandbox Environment"
   - Save

4. **Test with Real Invoice**
   - Create invoices normally
   - Submit to ZATCA
   - Monitor compliance status

5. **Monitor**
   - Check ZATCA portal regularly
   - Monitor submission logs
   - Handle any compliance issues

## Advanced Features

### Custom Invoice Data Mapping
Edit `prepare_invoice_data()` in `zatca_views.py` to customize data sent to ZATCA

### Custom XML Generation
Override `invoice_to_xml()` in `zatca_service.py` for custom XML format

### Webhook Notifications
Add ZATCA response handlers in `zatca_views.py` for automatic status updates

## Support & Resources

- **ZATCA Official**: https://zatca.gov.sa
- **E-Invoice Documentation**: https://zatca.gov.sa/en/E-Invoicing
- **Technical Support**: support@zatca.gov.sa
- **Project Issues**: Create GitHub issue in this repository

## Changelog

### Version 1.0 (Current)
- ✅ XML generation (UBL 2.1)
- ✅ Digital signing with cryptography
- ✅ QR code generation (Fatoora)
- ✅ ZATCA API integration
- ✅ Web UI configuration
- ✅ Management command setup
- ✅ Sandbox/Production support
- ✅ Submission tracking

## License
This implementation follows ZATCA E-Invoice compliance requirements as of 2024.

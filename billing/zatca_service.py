"""
ZATCA E-Invoice Integration Service
Handles XML format conversion, digital signing, QR code generation, and API submission
"""
import hashlib
import base64
from datetime import datetime
from decimal import Decimal
from typing import Dict, Tuple, Optional
import io
import json

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509 import load_pem_x509_certificate
except ImportError:
    raise ImportError("cryptography package required. Install: pip install cryptography")

try:
    import qrcode
except ImportError:
    raise ImportError("qrcode package required. Install: pip install qrcode")

try:
    from lxml import etree
except ImportError:
    raise ImportError("lxml package required. Install: pip install lxml")

import requests


class ZATCAEInvoiceService:
    """Service for ZATCA E-Invoice (Fatoora) integration"""
    
    # ZATCA Endpoints
    ZATCA_SANDBOX_URL = "https://sandbox.zatca.gov.sa"
    ZATCA_PRODUCTION_URL = "https://api.zatca.gov.sa"
    
    # Namespaces
    UBL_NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
    }
    
    def __init__(self, organization_trn: str, organization_name: str, 
                 certificate_path: str = None, private_key_path: str = None,
                 use_sandbox: bool = True):
        """
        Initialize ZATCA service
        
        Args:
            organization_trn: Tax Registration Number (TRN)
            organization_name: Organization name
            certificate_path: Path to ZATCA certificate file
            private_key_path: Path to private key file
            use_sandbox: Whether to use sandbox environment
        """
        self.organization_trn = organization_trn
        self.organization_name = organization_name
        self.certificate_path = certificate_path
        self.private_key_path = private_key_path
        self.use_sandbox = use_sandbox
        self.base_url = self.ZATCA_SANDBOX_URL if use_sandbox else self.ZATCA_PRODUCTION_URL
        
        # Load certificate and key
        self.certificate = None
        self.private_key = None
        if certificate_path and private_key_path:
            self._load_credentials()
    
    def _load_credentials(self):
        """Load certificate and private key"""
        try:
            with open(self.certificate_path, 'rb') as f:
                cert_data = f.read()
                self.certificate = load_pem_x509_certificate(cert_data, default_backend())
            
            with open(self.private_key_path, 'rb') as f:
                key_data = f.read()
                self.private_key = serialization.load_pem_private_key(
                    key_data, password=None, backend=default_backend()
                )
        except Exception as e:
            raise Exception(f"Error loading credentials: {str(e)}")
    
    def invoice_to_xml(self, invoice_data: Dict) -> str:
        """
        Convert invoice to ZATCA XML format (UBL 2.1)
        
        Args:
            invoice_data: Invoice data dictionary
        
        Returns:
            XML string in ZATCA format
        """
        # Create root element
        invoice_elem = etree.Element(
            '{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice',
            nsmap={
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
                'ds': 'http://www.w3.org/2000/09/xmldsig#',
            }
        )
        
        # UBLVersionID
        ublversion = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}UBLVersionID')
        ublversion.text = '2.1'
        
        # CustomizationID
        customid = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID')
        customid.text = 'urn:cefact:ubl:ph:core:ubltr:Invoice-1.0'
        
        # ProfileID
        profileid = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ProfileID')
        profileid.text = 'urn:saudiarabia:ksa:profile:ubltr:invoice:v1.0'
        
        # ID (Invoice Number)
        inv_id = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        inv_id.text = invoice_data.get('invoice_number', '')
        
        # UUID
        inv_uuid = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}UUID')
        inv_uuid.text = invoice_data.get('uuid', '')
        
        # IssueDate
        issue_date = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueDate')
        issue_date.text = invoice_data.get('invoice_date', '')
        
        # IssueTime
        issue_time = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueTime')
        issue_time.text = invoice_data.get('invoice_time', '00:00:00')
        
        # InvoiceTypeCode
        invoice_type = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoiceTypeCode')
        invoice_type.set('name', invoice_data.get('invoice_type', 'Standard'))
        invoice_type.text = '388'  # Standard invoice
        
        # DocumentCurrencyCode
        currency = etree.SubElement(invoice_elem, '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}DocumentCurrencyCode')
        currency.text = 'SAR'
        
        # Add supplier (company) info
        self._add_supplier_info(invoice_elem, invoice_data)
        
        # Add customer (student) info
        self._add_customer_info(invoice_elem, invoice_data)
        
        # Add line items
        self._add_line_items(invoice_elem, invoice_data)
        
        # Add totals
        self._add_monetary_totals(invoice_elem, invoice_data)
        
        return etree.tostring(invoice_elem, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')
    
    def _add_supplier_info(self, parent_elem, invoice_data):
        """Add supplier (company) information to XML"""
        supplier_elem = etree.SubElement(
            parent_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingSupplierParty'
        )
        
        # Party info
        party_elem = etree.SubElement(
            supplier_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party'
        )
        
        # Party ID (TRN)
        party_id = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification'
        )
        party_id_value = etree.SubElement(
            party_id, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID'
        )
        party_id_value.set('schemeID', 'TRN')
        party_id_value.text = self.organization_trn
        
        # Party Name
        party_name = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName'
        )
        party_name_val = etree.SubElement(
            party_name, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name'
        )
        party_name_val.text = self.organization_name
        
        # Contact info
        contact_elem = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Contact'
        )
        
        telephone = etree.SubElement(
            contact_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Telephone'
        )
        telephone.text = invoice_data.get('supplier_phone', '')
        
        email = etree.SubElement(
            contact_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ElectronicMail'
        )
        email.text = invoice_data.get('supplier_email', '')
        
        # Address
        address_elem = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PostalAddress'
        )
        
        street = etree.SubElement(
            address_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}StreetName'
        )
        street.text = invoice_data.get('supplier_address', '')
        
        city = etree.SubElement(
            address_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CityName'
        )
        city.text = invoice_data.get('supplier_city', 'Riyadh')
    
    def _add_customer_info(self, parent_elem, invoice_data):
        """Add customer (student) information to XML"""
        customer_elem = etree.SubElement(
            parent_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingCustomerParty'
        )
        
        party_elem = etree.SubElement(
            customer_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party'
        )
        
        # Customer ID
        party_id = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification'
        )
        party_id_value = etree.SubElement(
            party_id, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID'
        )
        party_id_value.text = invoice_data.get('customer_id', '')
        
        # Customer Name
        party_name = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName'
        )
        party_name_val = etree.SubElement(
            party_name, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name'
        )
        party_name_val.text = invoice_data.get('customer_name', '')
        
        # Contact
        contact_elem = etree.SubElement(
            party_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Contact'
        )
        
        email = etree.SubElement(
            contact_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ElectronicMail'
        )
        email.text = invoice_data.get('customer_email', '')
    
    def _add_line_items(self, parent_elem, invoice_data):
        """Add invoice line items to XML"""
        items = invoice_data.get('items', [])
        
        for idx, item in enumerate(items, 1):
            line_elem = etree.SubElement(
                parent_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine'
            )
            
            # Line ID
            line_id = etree.SubElement(
                line_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID'
            )
            line_id.text = str(idx)
            
            # Invoiced Quantity
            quantity = etree.SubElement(
                line_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoicedQuantity'
            )
            quantity.set('unitCode', 'PCE')
            quantity.text = str(item.get('quantity', 1))
            
            # Line Extension Amount
            line_amount = etree.SubElement(
                line_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount'
            )
            line_amount.set('currencyID', 'SAR')
            line_amount.text = str(item.get('total_amount', 0))
            
            # Item details
            item_elem = etree.SubElement(
                line_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item'
            )
            
            item_name = etree.SubElement(
                item_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name'
            )
            item_name.text = item.get('description', '')
            
            # Price
            price_elem = etree.SubElement(
                line_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Price'
            )
            
            price_amount = etree.SubElement(
                price_elem, 
                '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PriceAmount'
            )
            price_amount.set('currencyID', 'SAR')
            price_amount.text = str(item.get('unit_price', 0))
    
    def _add_monetary_totals(self, parent_elem, invoice_data):
        """Add monetary totals to XML"""
        totals_elem = etree.SubElement(
            parent_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}LegalMonetaryTotal'
        )
        
        # Line Extension Total Amount
        line_total = etree.SubElement(
            totals_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionTotalAmount'
        )
        line_total.set('currencyID', 'SAR')
        line_total.text = str(invoice_data.get('subtotal', 0))
        
        # Tax Exclusive Amount
        tax_excl = etree.SubElement(
            totals_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxExclusiveAmount'
        )
        tax_excl.set('currencyID', 'SAR')
        tax_excl.text = str(invoice_data.get('subtotal', 0) - invoice_data.get('discount_amount', 0))
        
        # Tax Inclusive Amount
        tax_incl = etree.SubElement(
            totals_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxInclusiveAmount'
        )
        tax_incl.set('currencyID', 'SAR')
        tax_incl.text = str(invoice_data.get('total_amount', 0))
        
        # Payable Amount
        payable = etree.SubElement(
            totals_elem, 
            '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}DuePayableAmount'
        )
        payable.set('currencyID', 'SAR')
        payable.text = str(invoice_data.get('total_amount', 0))
    
    def generate_qr_code(self, invoice_data: Dict, xml_content: str = None) -> bytes:
        """
        Generate QR code with invoice data (ZATCA Fatoora format)
        
        Args:
            invoice_data: Invoice data dictionary
            xml_content: XML content for hashing
        
        Returns:
            QR code image bytes (PNG)
        """
        # ZATCA QR Code format: seller_name|vat_number|invoice_total|vat_amount|invoice_date|invoice_time|invoice_hash|signature_hash|signing_certificate
        
        qr_data_parts = [
            self.organization_name,  # Seller name
            self.organization_trn,  # VAT number (TRN)
            '{:.2f}'.format(invoice_data.get('total_amount', 0)),  # Invoice total
            '{:.2f}'.format(invoice_data.get('vat_amount', 0)),  # VAT amount
            invoice_data.get('invoice_date', ''),  # Invoice date
            invoice_data.get('invoice_time', '00:00:00'),  # Invoice time
            '',  # Invoice hash (to be replaced)
            '',  # Signature hash (to be replaced)
            '',  # Signing certificate (to be replaced)
        ]
        
        qr_data = '|'.join(qr_data_parts)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()
    
    def sign_invoice_xml(self, xml_content: str) -> str:
        """
        Sign invoice XML with digital signature
        
        Args:
            xml_content: XML content to sign
        
        Returns:
            Signed XML content
        """
        if not self.private_key or not self.certificate:
            raise Exception("Certificate and private key required for signing")
        
        # Calculate hash of XML
        xml_hash = hashlib.sha256(xml_content.encode()).digest()
        
        # Sign the hash
        signature = self.private_key.sign(
            xml_hash,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # Encode signature in base64
        signature_b64 = base64.b64encode(signature).decode('ascii')
        
        return signature_b64
    
    def submit_invoice_to_zatca(self, xml_content: str, invoice_uuid: str) -> Dict:
        """
        Submit invoice to ZATCA for compliance check and recording
        
        Args:
            xml_content: Signed XML content
            invoice_uuid: Invoice UUID
        
        Returns:
            API response dictionary
        """
        url = f"{self.base_url}/compliance/invoices"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        payload = {
            'invoiceHash': hashlib.sha256(xml_content.encode()).hexdigest(),
            'uuid': invoice_uuid,
            'invoice': base64.b64encode(xml_content.encode()).decode('ascii'),
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return {
                    'success': True,
                    'data': response.json(),
                    'status': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status': response.status_code
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status': None
            }
    
    def validate_invoice_format(self, xml_content: str) -> Tuple[bool, str]:
        """
        Validate invoice XML format against ZATCA requirements
        
        Args:
            xml_content: XML content to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            etree.fromstring(xml_content.encode())
            return True, ""
        except etree.XMLSyntaxError as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)

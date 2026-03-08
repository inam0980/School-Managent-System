from django.urls import path
from . import views
from . import zatca_views

app_name = 'billing'

urlpatterns = [
    path('', views.invoice_list, name='list'),
    path('invoice/create/', views.invoice_create, name='create'),
    path('invoice/create/simplified/', views.simplified_invoice_create, name='simplified_create'),
    path('invoice/create/vat/', views.vat_invoice_create, name='vat_create'),
    path('invoice/<str:invoice_number>/', views.invoice_detail, name='detail'),
    path('invoice/<str:invoice_number>/payment/', views.payment_create, name='payment'),
    path('invoice/<str:invoice_number>/pdf/', views.invoice_pdf, name='pdf'),
    path('invoice/<str:invoice_number>/print/', views.invoice_print, name='print'),
    path('payments/', views.payment_list, name='payments'),
    
    # ZATCA E-Invoice Integration
    path('zatca/configuration/', zatca_views.zatca_configuration_view, name='zatca_configuration'),
    path('invoice/<str:invoice_number>/zatca/submit/', zatca_views.submit_invoice_to_zatca, name='zatca_submit'),
    path('invoice/<str:invoice_number>/zatca/status/', zatca_views.zatca_submission_status, name='zatca_status'),
    path('invoice/<str:invoice_number>/zatca/xml/', zatca_views.download_zatca_xml, name='zatca_xml'),
    path('invoice/<str:invoice_number>/zatca/qr/', zatca_views.download_zatca_qr, name='zatca_qr'),
]

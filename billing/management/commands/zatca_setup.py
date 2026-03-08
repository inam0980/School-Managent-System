"""
Management command to setup and manage ZATCA configuration
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from billing.zatca_models import ZATCAConfiguration
import os


class Command(BaseCommand):
    help = 'Setup and manage ZATCA E-Invoice integration'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['setup', 'test', 'list', 'enable', 'disable'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--trn',
            type=str,
            help='Tax Registration Number'
        )
        
        parser.add_argument(
            '--name',
            type=str,
            help='Organization name'
        )
        
        parser.add_argument(
            '--email',
            type=str,
            help='Organization email'
        )
        
        parser.add_argument(
            '--phone',
            type=str,
            help='Organization phone'
        )
        
        parser.add_argument(
            '--cert',
            type=str,
            help='Path to certificate file'
        )
        
        parser.add_argument(
            '--key',
            type=str,
            help='Path to private key file'
        )
        
        parser.add_argument(
            '--sandbox',
            action='store_true',
            help='Use sandbox environment'
        )

    def handle(self, *args, **options):
        action = options['action']

        if action == 'setup':
            self.setup_zatca(options)
        elif action == 'test':
            self.test_zatca()
        elif action == 'list':
            self.list_zatca()
        elif action == 'enable':
            self.enable_zatca()
        elif action == 'disable':
            self.disable_zatca()

    def setup_zatca(self, options):
        """Setup ZATCA configuration"""
        self.stdout.write(self.style.SUCCESS('🔧 ZATCA Setup Wizard'))
        self.stdout.write('-' * 50)
        
        # Get existing config or create new
        config = ZATCAConfiguration.objects.filter(is_active=True).first()
        
        if config:
            self.stdout.write(self.style.WARNING(f'Found existing config: {config.organization_name}'))
            update = input('Update existing configuration? (y/n): ').lower() == 'y'
            if not update:
                return
        else:
            config = ZATCAConfiguration()
        
        # Get values from options or prompt
        config.organization_trn = options.get('trn') or input('Tax Registration Number (TRN): ')
        config.organization_name = options.get('name') or input('Organization Name: ')
        config.organization_email = options.get('email') or input('Organization Email: ')
        config.organization_phone = options.get('phone') or input('Organization Phone: ')
        config.certificate_path = options.get('cert') or input('Path to Certificate File: ')
        config.private_key_path = options.get('key') or input('Path to Private Key File: ')
        
        # Validate paths
        if config.certificate_path and not os.path.exists(config.certificate_path):
            raise CommandError(f'Certificate file not found: {config.certificate_path}')
        
        if config.private_key_path and not os.path.exists(config.private_key_path):
            raise CommandError(f'Private key file not found: {config.private_key_path}')
        
        config.use_sandbox = options.get('sandbox', True)
        config.is_configured = True
        config.is_active = True
        
        config.save()
        
        self.stdout.write(self.style.SUCCESS(f'✅ ZATCA configuration saved successfully!'))
        self.stdout.write(f'Organization: {config.organization_name}')
        self.stdout.write(f'TRN: {config.organization_trn}')
        self.stdout.write(f'Environment: {"Sandbox" if config.use_sandbox else "Production"}')

    def test_zatca(self):
        """Test ZATCA connection"""
        from billing.zatca_views import get_zatca_service
        
        self.stdout.write(self.style.SUCCESS('🧪 Testing ZATCA Connection'))
        self.stdout.write('-' * 50)
        
        zatca_service = get_zatca_service()
        
        if not zatca_service:
            raise CommandError('ZATCA service not properly configured')
        
        self.stdout.write(self.style.SUCCESS('✅ ZATCA service initialized successfully'))
        self.stdout.write(f'Organization: {zatca_service.organization_name}')
        self.stdout.write(f'TRN: {zatca_service.organization_trn}')
        self.stdout.write(f'Environment: {"Sandbox" if zatca_service.use_sandbox else "Production"}')

    def list_zatca(self):
        """List ZATCA configurations"""
        configs = ZATCAConfiguration.objects.all()
        
        if not configs.exists():
            self.stdout.write(self.style.WARNING('No ZATCA configurations found'))
            return
        
        self.stdout.write(self.style.SUCCESS('📋 ZATCA Configurations'))
        self.stdout.write('-' * 50)
        
        for config in configs:
            status = '✅ Active' if config.is_active else '⚪ Inactive'
            self.stdout.write(f'{status} | {config.organization_name} ({config.organization_trn})')
            self.stdout.write(f'   Email: {config.organization_email}')
            self.stdout.write(f'   Environment: {"Sandbox" if config.use_sandbox else "Production"}')
            self.stdout.write('')

    def enable_zatca(self):
        """Enable ZATCA configuration"""
        configs = ZATCAConfiguration.objects.filter(is_active=False)
        
        if not configs.exists():
            self.stdout.write(self.style.WARNING('No inactive ZATCA configurations found'))
            return
        
        for config in configs:
            config.is_active = True
            config.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Enabled: {config.organization_name}'))

    def disable_zatca(self):
        """Disable ZATCA configuration"""
        configs = ZATCAConfiguration.objects.filter(is_active=True)
        
        if not configs.exists():
            self.stdout.write(self.style.WARNING('No active ZATCA configurations found'))
            return
        
        for config in configs:
            config.is_active = False
            config.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Disabled: {config.organization_name}'))

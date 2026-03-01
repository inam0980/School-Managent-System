from django.test import TestCase, Client
from django.urls import reverse

from .models import Program


class ProgramViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create and login as superuser to access views
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_superuser('admin', 'a@b.com', 'pass')
        self.client.login(username='admin', password='pass')
        
    def test_program_list_empty(self):
        resp = self.client.get(reverse('settings_app:program_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No programs defined yet')

    def test_program_create_and_list(self):
        # create program via form POST
        resp = self.client.post(reverse('settings_app:program_create'), {
            'name': 'Elementary',
            'code': 'ELE',
            'is_active': True,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Program.objects.filter(code='ELE').exists())
        self.assertContains(resp, 'Elementary')
        # verify edit link present
        self.assertContains(resp, 'Edit')

    def test_program_edit(self):
        p = Program.objects.create(name='Middle', code='MID')
        url = reverse('settings_app:program_edit', args=[p.pk])
        resp = self.client.post(url, {
            'name': 'Middle School',
            'code': 'MID',
            'is_active': False,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.name, 'Middle School')
        self.assertFalse(p.is_active)

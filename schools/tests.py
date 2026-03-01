from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .models import School, Organization


@override_settings(FORCE_SCHOOL_IDENTIFIER='Alkawthar')
class SingleSchoolModeTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(
            name='Org1',
            registration_number='REG1',
            organization_code='OC1',
            email='a@b.com',
            phone='+123456789',
            address='addr',
            city='City',
        )
        self.school1 = School.objects.create(
            organization=org,
            school_name='Alkawthar International',
            school_code='ALKAWTHAR',
            email='x@x.com',
            phone='+111',
            address='addr',
            city='C',
            principal_name='P',
            principal_email='p@x.com',
            principal_phone='+222',
        )
        self.school2 = School.objects.create(
            organization=org,
            school_name='Other School',
            school_code='OTHER',
            email='y@y.com',
            phone='+333',
            address='addr',
            city='C',
            principal_name='Q',
            principal_email='q@y.com',
            principal_phone='+444',
        )
        self.client = Client()
        # create superuser to bypass permissions
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.client.login(username='admin', password='pass')

    def test_school_list_only_alka(self):
        resp = self.client.get(reverse('schools:school_list'))
        self.assertEqual(resp.status_code, 200)
        schools = resp.context['schools']
        self.assertEqual(len(schools), 1)
        self.assertEqual(schools[0].school_code, 'ALKAWTHAR')

    def test_switch_disabled(self):
        # attempt to switch to other school
        url = reverse('schools:school_switch', args=[self.school2.pk])
        resp = self.client.get(url, follow=True)
        # Redirect to dashboard regardless, session should still point to default
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.session.get('current_school_id'), self.school1.id)

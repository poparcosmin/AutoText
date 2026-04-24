"""End-to-end integration tests: full auth flow, sync workflow."""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..models import ExpiringToken, Shortcut, ShortcutSet


class IntegrationTests(APITestCase):
    """End-to-end integration tests."""

    def setUp(self):
        self.client = APIClient()

    def test_full_auth_flow(self):
        """Test complete authentication flow: register -> login -> use API -> logout."""
        # Create user (normally done via admin)
        User.objects.create_user(
            username='integration_user',
            password='secure_pass_123'
        )

        # Login
        login_response = self.client.post('/api/auth/login/', {
            'username': 'integration_user',
            'password': 'secure_pass_123'
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data['token']

        # Use API with token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        sets_response = self.client.get('/api/sets/')
        self.assertEqual(sets_response.status_code, status.HTTP_200_OK)

        # Verify token
        verify_response = self.client.get('/api/auth/verify/')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_response.data['valid'])

        # Logout
        logout_response = self.client.post('/api/auth/logout/')
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Token should no longer work
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        after_logout = self.client.get('/api/sets/')
        self.assertEqual(after_logout.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_shortcut_sync_workflow(self):
        """Test typical extension sync workflow."""
        # Setup
        user = User.objects.create_user(username='sync_user', password='pass')
        token = ExpiringToken.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create sets and shortcuts
        birou = ShortcutSet.objects.create(name='birou', set_type='general', owner=user)
        personal = ShortcutSet.objects.create(
            name='sync_user', set_type='personal', owner=user
        )

        shortcut1 = Shortcut.objects.create(key='hello', value='Hello!', owner=user)
        shortcut1.sets.add(birou)

        shortcut2 = Shortcut.objects.create(
            key='personal', value='My shortcut', owner=user
        )
        shortcut2.sets.add(personal)

        # Initial sync (no updated_after)
        response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou', 'sync_user']
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count']['shortcuts'], 2)

        # Record sync time
        sync_time = response.data['server_time']

        # Add new shortcut
        shortcut3 = Shortcut.objects.create(key='new', value='New!', owner=user)
        shortcut3.sets.add(birou)

        # Delta sync
        delta_response = self.client.post('/api/sync/bulk/', {
            'sets': ['birou', 'sync_user'],
            'updated_after': sync_time
        }, format='json')

        self.assertEqual(delta_response.status_code, status.HTTP_200_OK)
        # Should only return the new shortcut
        self.assertEqual(delta_response.data['count']['shortcuts'], 1)
        self.assertEqual(delta_response.data['shortcuts'][0]['key'], 'new')

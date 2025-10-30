from rest_framework import authentication, exceptions
from django.utils import timezone
from .models import ExpiringToken


class ExpiringTokenAuthentication(authentication.BaseAuthentication):
    """
    Custom token authentication with expiration.
    Tokens expire after 180 days.
    """

    keyword = 'Token'
    model = ExpiringToken

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = 'Invalid token header. No credentials provided.'
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, key):
        try:
            token = self.model.objects.select_related('user').get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        # Check if token is expired
        if token.is_expired():
            raise exceptions.AuthenticationFailed('Token has expired.')

        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword

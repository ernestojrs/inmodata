from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate an active account with either its username or email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        identifier = (username or kwargs.get(user_model.USERNAME_FIELD) or "").strip()

        if not identifier or password is None:
            return None

        try:
            user = user_model._default_manager.get(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            )
        except user_model.DoesNotExist:
            # Keep failed-login timing similar to a password check.
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

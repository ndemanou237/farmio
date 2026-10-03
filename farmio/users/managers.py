from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Manager custom : authentification par email, pas de username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            msg = _("L'adresse email est obligatoire.")
            raise ValueError(msg)
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("is_approved", True)
        extra_fields.setdefault("is_producer", False)
        extra_fields.setdefault("is_buyer", False)

        if extra_fields.get("is_staff") is not True:
            msg = _("Le superutilisateur doit avoir is_staff=True.")
            raise ValueError(msg)

        if extra_fields.get("is_superuser") is not True:
            msg = _("Le superutilisateur doit avoir is_superuser=True.")
            raise ValueError(msg)

        return self._create_user(email, password, **extra_fields)

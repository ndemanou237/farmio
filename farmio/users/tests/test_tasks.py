import pytest
from celery.result import EagerResult

from farmio.users.tasks import send_welcome_email_task
from farmio.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


from unittest.mock import patch

def test_send_welcome_email_task(settings):
    """A basic test to execute a Celery task."""
    user = UserFactory.create()
    settings.CELERY_TASK_ALWAYS_EAGER = True
    with patch("farmio.utils.email.EmailUtil.send_email_with_template", return_value=True):
        task_result = send_welcome_email_task.delay(user.pk, "http://localhost")
        assert isinstance(task_result, EagerResult)
        assert task_result.result is True

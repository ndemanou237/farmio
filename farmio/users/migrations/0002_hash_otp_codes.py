from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def hash_existing_otp_codes(apps, schema_editor):
    otp_model = apps.get_model("users", "OtpCode")
    for otp in otp_model.objects.iterator():
        if len(otp.code) < 20 or not otp.code.startswith("pbkdf2_"):
            otp.code = make_password(otp.code)
            otp.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="otpcode",
            name="code",
            field=models.CharField(max_length=128, verbose_name="code"),
        ),
        migrations.RunPython(hash_existing_otp_codes, migrations.RunPython.noop),
    ]
from django.db import migrations, models


def revoke_unverified(apps, schema_editor):
    """Every subscription before this migration was self-granted: the old
    verify endpoint trusted whatever token the client sent, so none of them
    were ever confirmed with Google Play. Revoke them; paying users re-verify
    through the real Play Billing flow (the app restores purchases on open)."""
    Subscription = apps.get_model("subscriptions", "Subscription")
    User = apps.get_model("users", "User")
    User.objects.filter(subscription__isnull=False).update(is_pro=False)
    Subscription.objects.update(
        play_purchase_token=None, status="expired", expires_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0002_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subscription",
            name="play_purchase_token",
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.RunPython(revoke_unverified, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="subscription",
            name="play_purchase_token",
            field=models.CharField(blank=True, max_length=512, null=True, unique=True),
        ),
    ]

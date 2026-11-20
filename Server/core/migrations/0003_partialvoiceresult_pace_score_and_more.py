from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_talkpause_alter_session_scheduled_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='partialvoiceresult',
            name='pace_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='partialvoiceresult',
            name='pitch_variation_score',
            field=models.FloatField(blank=True, null=True),
        ),
    ]

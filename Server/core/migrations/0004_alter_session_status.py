from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_partialvoiceresult_pace_score_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='status',
            field=models.CharField(choices=[('NOT_STARTED', 'Not started'), ('LIVE', 'Live'), ('FINISHED', 'Finished'), ('CANCELLED', 'Cancelled'), ('ABORTED', 'Aborted'), ('DELETED', 'Deleted')], default='NOT_STARTED', max_length=16),
        ),
    ]

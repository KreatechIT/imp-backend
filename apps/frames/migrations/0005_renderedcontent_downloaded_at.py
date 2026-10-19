from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('frames', '0004_alter_renderedcontent_crop_x_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='renderedcontent',
            name='downloaded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

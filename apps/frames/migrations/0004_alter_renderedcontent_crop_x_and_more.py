
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('frames', '0003_renderedcontent_crop_height_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='renderedcontent',
            name='crop_x',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='renderedcontent',
            name='crop_y',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]

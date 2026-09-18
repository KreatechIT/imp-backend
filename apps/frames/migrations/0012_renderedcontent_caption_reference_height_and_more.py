
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frames', '0011_renderedcontent_caption_background_color_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='renderedcontent',
            name='caption_reference_height',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='renderedcontent',
            name='caption_x',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='renderedcontent',
            name='caption_y',
            field=models.FloatField(blank=True, null=True),
        ),
    ]

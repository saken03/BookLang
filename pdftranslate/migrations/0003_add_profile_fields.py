# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdftranslate', '0002_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='social_media',
            field=models.CharField(blank=True, help_text='Social media handles or activity description', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='profile_photos/'),
        ),
    ] 
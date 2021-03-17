# Generated by Django 2.2.18 on 2021-03-17 11:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0053_osxapp_bundle_display_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Program',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mt_hash', models.CharField(max_length=40, unique=True)),
                ('mt_created_at', models.DateTimeField(auto_now_add=True)),
                ('name', models.TextField(blank=True, null=True)),
                ('version', models.TextField(blank=True, null=True)),
                ('language', models.TextField(blank=True, null=True)),
                ('publisher', models.TextField(blank=True, null=True)),
                ('identifying_number', models.TextField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProgramInstance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mt_hash', models.CharField(max_length=40, unique=True)),
                ('mt_created_at', models.DateTimeField(auto_now_add=True)),
                ('install_location', models.TextField(blank=True, null=True)),
                ('install_source', models.TextField(blank=True, null=True)),
                ('uninstall_string', models.TextField(blank=True, null=True)),
                ('install_date', models.DateTimeField(blank=True, null=True)),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.Program')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='machinesnapshot',
            name='program_instances',
            field=models.ManyToManyField(to='inventory.ProgramInstance'),
        ),
    ]

# Generated migration for Institution and InstitutionUser models (Phase 00)

from django.db import migrations, models
import django.db.models.deletion
import apps.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_outboxevent_aggregate_id_outboxevent_available_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Institution',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.CharField(default=apps.core.models.generate_ulid, editable=False, max_length=26, primary_key=True, serialize=False, help_text='Identifiant unique ULID de l\'institution (tenant_id).')),
                ('name', models.CharField(db_index=True, max_length=255, help_text='Nom légal de l\'institution SFD/IMF.')),
                ('slug', models.SlugField(max_length=100, unique=True, db_index=True, help_text='Identifiant lisible pour les URLs et sous-domaines (ex: \'coop-bamako\').')),
                ('status', models.CharField(choices=[('pending', 'En attente d\'onboarding'), ('active', 'Active et opérationnelle'), ('suspended', 'Suspendue (violation de conformité)'), ('archived', 'Archivée (fin de contrat)')], db_index=True, default='pending', max_length=20, help_text='Statut opérationnel de l\'institution.')),
                ('country_code', models.CharField(db_index=True, max_length=2, help_text='Code ISO 3166-1 alpha-2 (ex: \'ML\' pour Mali).')),
                ('registration_number', models.CharField(blank=True, db_index=True, max_length=100, help_text='Numéro d\'immatriculation auprès du régulateur (BCEAO).')),
                ('config', models.JSONField(blank=True, default=dict, help_text='Configuration JSON spécifique à l\'institution (paramètres métier, limites, etc.).')),
                ('onboarded_at', models.DateTimeField(blank=True, null=True, help_text='Timestamp du premier déploiement productif.')),
                ('suspended_at', models.DateTimeField(blank=True, null=True, help_text='Timestamp de la suspension (si applicable).')),
                ('suspended_reason', models.TextField(blank=True, help_text='Motif de la suspension (si applicable).')),
            ],
            options={
                'verbose_name': 'Institution (Tenant)',
                'verbose_name_plural': 'Institutions (Tenants)',
            },
        ),
        migrations.CreateModel(
            name='InstitutionUser',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.CharField(default=apps.core.models.generate_ulid, editable=False, max_length=26, primary_key=True, serialize=False)),
                ('user_id', models.CharField(db_index=True, max_length=26)),
                ('institution_role', models.CharField(choices=[('admin', 'Administrateur institution'), ('finance', 'Responsable finance'), ('compliance', 'Responsable conformité'), ('operator', 'Opérateur guichet'), ('field_agent', 'Agent terrain'), ('auditor', 'Auditeur')], max_length=50, help_text='Rôle de l\'utilisateur au sein de cette institution.')),
                ('is_primary_contact', models.BooleanField(default=False, help_text='Vrai si cet utilisateur est le contact principal de l\'institution.')),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='institution_users', to='core.institution')),
            ],
        ),
        migrations.AddIndex(
            model_name='institution',
            index=models.Index(fields=['status', 'created_at'], name='core_instit_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='institution',
            index=models.Index(fields=['country_code', 'status'], name='core_instit_country_status_idx'),
        ),
        migrations.AddIndex(
            model_name='institutionuser',
            index=models.Index(fields=['institution', 'user_id'], name='core_institu_instit_user_idx'),
        ),
        migrations.AddIndex(
            model_name='institutionuser',
            index=models.Index(fields=['user_id', 'institution'], name='core_institu_user_instit_idx'),
        ),
        migrations.AddConstraint(
            model_name='institutionuser',
            constraint=models.UniqueConstraint(fields=['institution', 'user_id'], name='uniq_institution_user'),
        ),
    ]

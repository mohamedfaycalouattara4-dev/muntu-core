# Generated migration: Add tenant_id to core models (Phase 00)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_institution_tenant_models'),
    ]

    operations = [
        # Add tenant_id to FinancialApproval
        migrations.AddField(
            model_name='financialapproval',
            name='tenant_id',
            field=models.CharField(
                max_length=26,
                db_index=True,
                default='',
                help_text='Identifiant du tenant (institution) — Phase 00.'
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='financialapproval',
            constraint=models.UniqueConstraint(
                fields=['tenant_id', 'operation_hash', 'approver_id'],
                name='uniq_approval_per_tenant_operation_approver'
            ),
        ),
        migrations.AddIndex(
            model_name='financialapproval',
            index=models.Index(fields=['tenant_id', 'operation_hash'], name='core_finapp_tenant_op_idx'),
        ),

        # Add tenant_id to OutboxEvent
        migrations.AddField(
            model_name='outboxevent',
            name='tenant_id',
            field=models.CharField(
                max_length=26,
                db_index=True,
                default='',
                help_text='Identifiant du tenant (institution) — Phase 00.'
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['tenant_id', 'status'], name='core_outbox_tenant_status_idx'),
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['tenant_id', 'aggregate'], name='core_outbox_tenant_agg_idx'),
        ),
    ]

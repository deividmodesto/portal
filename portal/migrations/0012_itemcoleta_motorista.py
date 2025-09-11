# portal/migrations/0012_itemcoleta_motorista.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0011_motorista'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcoleta',
            name='motorista',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coletas', to='portal.motorista', verbose_name='Motorista'),
        ),
    ]
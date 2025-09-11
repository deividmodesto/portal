# deividmodesto/logistica/logistica-e40c40324dc9e41cad3ed2ec8b1bc6bf7e34ac6d/portal/migrations/0010_itemcoletadetalhe_motivo_divergencia.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0009_sd1nfitem'), # Confirme que '0009_sd1nfitem' é sua última migração
    ]

    operations = [
        migrations.AddField(
            model_name='itemcoletadetalhe',
            name='motivo_divergencia',
            field=models.CharField(blank=True, choices=[('QUANTIDADE_A_MENOS', 'Divergência de quantidade (a menos)'), ('QUANTIDADE_A_MAIS', 'Divergência de quantidade (a mais)'), ('MERCADORIA_NAO_DISPONIBILIZADA', 'Mercadoria não disponibilizada'), ('NOTA_FISCAL_NAO_DISPONIBILIZADA', 'Nota fiscal não disponibilizada'), ('PRODUTO_AVARIADO', 'Produto avariado'), ('FALTA_DE_TEMPO', 'Não passou por falta de tempo'), ('INDISPONIBILIDADE_PRODUTO', 'Indisponibilidade do produto'), ('INDISPONIBILIDADE_VENDEDOR', 'Indisponibilidade do vendedor'), ('LOJA_FECHADA', 'Loja fechada'), ('MUDANCA_ROTA', 'Mudança de rota'), ('OUTRO', 'Outro (especificar na observação)')], max_length=50, null=True, verbose_name='Motivo da Divergência'),
        ),
    ]
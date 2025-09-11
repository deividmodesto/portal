# portal/models.py
from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User

# NOVA CLASSE MOTORISTA
class Motorista(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome do Motorista")
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Motorista"
        verbose_name_plural = "Motoristas"
        ordering = ['nome']

class SD1NFItem(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    d1_emissao = models.CharField(max_length=8, db_column='D1_EMISSAO')
    d1_cod = models.CharField(max_length=30, db_column='D1_COD') # O CAMPO DEVE SER d1_cod
    d1_vunit = models.DecimalField(max_digits=10, decimal_places=4, db_column='D1_VUNIT')

    class Meta:
        managed = False
        db_table = 'SD1010'


class FornecedorUsuario(models.Model):
    cnpj = models.CharField(max_length=20, unique=True)
    email = models.CharField(max_length=255)
    nome_fornecedor = models.CharField(max_length=255)
    password = models.CharField(max_length=128)
    codigo_externo = models.CharField(max_length=20, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_fornecedor} ({self.cnpj})"

    class Meta:
        db_table = 'FornecedorUsuario'


class PedidoLiberado(models.Model):
    STATUS_CHOICES = [
        ('LIBERADO', 'Não Respondido'),
        ('PARCIALMENTE_DISPONIVEL', 'Parcialmente Disponível'),
        ('TOTALMENTE_DISPONIVEL', 'Totalmente Disponível'),
        ('COLETADO', 'Coletado'),
    ]
    numero_pedido = models.CharField(max_length=50, unique=True)
    fornecedor_usuario = models.ForeignKey(FornecedorUsuario, on_delete=models.CASCADE)
    data_emissao = models.DateField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='LIBERADO')
    data_liberacao_portal = models.DateTimeField(auto_now_add=True)
    data_marcado_coleta = models.DateTimeField(blank=True, null=True)
    observacao_fornecedor = models.TextField(blank=True, null=True)
    data_visualizacao = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Pedido {self.numero_pedido} - {self.fornecedor_usuario.nome_fornecedor}"

    class Meta:
        db_table = 'PedidoLiberado'


class ItemColeta(models.Model):
    STATUS_COLETA_CHOICES = [
        ('PENDENTE', 'Pendente de Agendamento'),
        ('AGENDADA', 'Coleta Agendada'),
        ('REALIZADA_OK', 'Realizada com Sucesso'),
        ('REALIZADA_DIVERGENCIA', 'Realizada com Divergência'),
    ]

    PRIORIDADE_CHOICES = [
        ('NORMAL', 'Normal'),
        ('URGENTE', 'Urgente'),
    ]

    pedido_liberado = models.ForeignKey(PedidoLiberado, on_delete=models.CASCADE, related_name='coletas', null=True, blank=True)
    data_disponibilidade = models.DateField()
    data_agendada = models.DateField(blank=True, null=True)
    status_coleta = models.CharField(max_length=50, choices=STATUS_COLETA_CHOICES, default='PENDENTE')
    volumes = models.IntegerField(blank=True, null=True)
    peso_kg = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    numero_nota_fiscal = models.CharField(max_length=50, blank=True, null=True)
    chave_acesso_nfe = models.CharField(max_length=44, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)
    observacao_coleta = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    agendado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coletas_agendadas')
    conferido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coletas_conferidas')
    fornecedor_avulso = models.CharField(max_length=255, blank=True, null=True)
    descricao_avulsa = models.TextField(blank=True, null=True)
    ordem_visita = models.PositiveIntegerField(default=0, help_text="Ordem da visita na rota do dia")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    motorista = models.ForeignKey(Motorista, on_delete=models.SET_NULL, null=True, blank=True, related_name='coletas', verbose_name="Motorista")


    def __str__(self):
        if self.pedido_liberado:
            return f"Coleta para Pedido {self.pedido_liberado.numero_pedido} em {self.data_disponibilidade}"
        else:
            return f"Coleta Avulsa: {self.fornecedor_avulso} em {self.data_disponibilidade}"

    class Meta:
        db_table = 'ItemColeta'
        ordering = ['ordem_visita', 'prioridade']


class ItemColetaDetalhe(models.Model):
    MOTIVOS_DIVERGENCIA_CHOICES = [
        ('QUANTIDADE_A_MENOS', 'Divergência de quantidade (a menos)'),
        ('QUANTIDADE_A_MAIS', 'Divergência de quantidade (a mais)'),
        ('MERCADORIA_NAO_DISPONIBILIZADA', 'Mercadoria não disponibilizada'),
        ('NOTA_FISCAL_NAO_DISPONIBILIZADA', 'Nota fiscal não disponibilizada'),
        ('PRODUTO_AVARIADO', 'Produto avariado'),
        ('FALTA_DE_TEMPO', 'Não passou por falta de tempo'),
        ('INDISPONIBILIDADE_PRODUTO', 'Indisponibilidade do produto'),
        ('INDISPONIBILIDADE_VENDEDOR', 'Indisponibilidade do vendedor'),
        ('LOJA_FECHADA', 'Loja fechada'),
        ('MUDANCA_ROTA', 'Mudança de rota'),
        ('OUTRO', 'Outro (especificar na observação)'),
    ]

    item_coleta = models.ForeignKey(ItemColeta, on_delete=models.CASCADE, related_name='detalhes')
    item_erp_recno = models.IntegerField()
    quantidade_disponivel = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_coletada = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    motivo_divergencia = models.CharField(
        max_length=50,
        choices=MOTIVOS_DIVERGENCIA_CHOICES,
        blank=True,
        null=True,
        verbose_name="Motivo da Divergência"
    )
    observacao_divergencia = models.TextField(blank=True, null=True)

    # REMOVEMOS A PROPERTY DAQUI. A VIEW AGORA CUIDARÁ DE ASSOCIAR O OBJETO.

    class Meta:
        db_table = 'ItemColetaDetalhe'


# --- Modelos NÃO GERENCIADOS (Read-Only do ERP) ---

class SA2Fornecedor(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    a2_cod = models.CharField(max_length=20, db_column='A2_COD')
    a2_nome = models.CharField(max_length=255, db_column='A2_NOME')
    a2_cgc = models.CharField(max_length=20, db_column='A2_CGC')
    a2_email = models.CharField(max_length=255, db_column='A2_EMAIL')
    a2_end = models.CharField(max_length=255, db_column='A2_END')
    a2_mun = models.CharField(max_length=100, db_column='A2_MUN')
    a2_tel = models.CharField(max_length=20, db_column='A2_TEL')

    class Meta:
        managed = False
        db_table = 'SA2010'

    def __str__(self):
        return self.a2_nome


class SC7PedidoItem(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    c7_filial = models.CharField(max_length=10, db_column='C7_FILIAL')
    c7_num = models.CharField(max_length=20, db_column='C7_NUM')
    c7_item = models.CharField(max_length=4, db_column='C7_ITEM')
    c7_produto = models.CharField(max_length=30, db_column='C7_PRODUTO')
    c7_descri = models.CharField(max_length=255, db_column='C7_DESCRI')
    c7_quant = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_QUANT')
    c7_emissao = models.CharField(max_length=8, db_column='C7_EMISSAO')
    c7_fornece = models.CharField(max_length=20, db_column='C7_FORNECE')
    c7_encer = models.CharField(max_length=1, db_column='C7_ENCER', blank=True)
    c7_conapro = models.CharField(max_length=1, db_column='C7_CONAPRO', blank=True, null=True) # Campo adicionado
    c7_preco = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_PRECO')
    c7_total = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_TOTAL')
    c7_contato = models.CharField(max_length=50, db_column='C7_CONTATO', blank=True)
    c7_emitido = models.CharField(max_length=1, db_column='C7_EMITIDO', blank=True)
    c7_tpfrete = models.CharField(max_length=1, db_column='C7_TPFRETE', blank=True)
    c7_numsc = models.CharField(max_length=20, db_column='C7_NUMSC', blank=True)
    c7_numcot = models.CharField(max_length=20, db_column='C7_NUMCOT', blank=True)
    c7_compra = models.CharField(max_length=10, db_column='C7_COMPRA', blank=True)
    c7_quje = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_QUJE', default=0)
    c7_cond = models.CharField(max_length=20, db_column='C7_COND', blank=True, null=True)
    c7_contato = models.CharField(max_length=50, db_column='C7_CONTATO', blank=True, null=True)
    c7_datprf = models.CharField(max_length=8, db_column='C7_DATPRF', blank=True, null=True)
    c7_ipi = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_IPI', default=0)
    c7_frete = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_FRETE', default=0)
    c7_vldesc = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_VLDESC', default=0)
    c7_desc = models.DecimalField(max_digits=10, decimal_places=2, db_column='C7_DESC', default=0)
    c7_transp = models.CharField(max_length=20, db_column='C7_TRANSP', blank=True, null=True)
    c7_local = models.CharField(max_length=10, db_column='C7_LOCAL', blank=True, null=True)
    c7_um = models.CharField(max_length=4, db_column='C7_UM', blank=True, null=True)
    c7_obs = models.CharField(max_length=255, db_column='C7_OBS', blank=True, null=True)

    @property
    def data_emissao_formatada(self):
        if self.c7_emissao and len(self.c7_emissao) == 8:
            ano = self.c7_emissao[0:4]
            mes = self.c7_emissao[4:6]
            dia = self.c7_emissao[6:8]
            return f"{dia}/{mes}/{ano}"
        return self.c7_emissao

    @property
    def data_entrega_formatada(self):
        if self.c7_datprf and len(self.c7_datprf) == 8:
            ano = self.c7_datprf[0:4]
            mes = self.c7_datprf[4:6]
            dia = self.c7_datprf[6:8]
            return f"{dia}/{mes}/{ano}"
        return self.c7_datprf

    class Meta:
        managed = False
        db_table = 'SC7010'

    def __str__(self):
        return f"Pedido {self.c7_num} - Item {self.c7_item}"

# --- NOVO MODELO PARA GERENCIAR LOCAIS AVULSOS ---


class FornecedorAvulso(models.Model):
    nome = models.CharField(max_length=255, unique=True, verbose_name="Nome do Local/Fornecedor")
    cnpj = models.CharField(max_length=20, blank=True, null=True, verbose_name="CNPJ")
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço")
    municipio = models.CharField(max_length=100, blank=True, null=True, verbose_name="Município")
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Fornecedor Avulso"
        verbose_name_plural = "Fornecedores Avulsos"
        ordering = ['nome']


class SC8CotacaoItem(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    c8_filial = models.CharField(max_length=10, db_column='C8_FILIAL')
    c8_num = models.CharField(max_length=20, db_column='C8_NUM')
    c8_item = models.CharField(max_length=4, db_column='C8_ITEM')
    c8_produto = models.CharField(max_length=30, db_column='C8_PRODUTO')
    c8_quant = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_QUANT')
    c8_um = models.CharField(max_length=4, db_column='C8_UM')
    c8_preco = models.DecimalField(max_digits=10, decimal_places=4, db_column='C8_PRECO')
    c8_total = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_TOTAL')
    c8_fornece = models.CharField(max_length=20, db_column='C8_FORNECE')
    c8_loja = models.CharField(max_length=4, db_column='C8_LOJA')
    c8_contato = models.CharField(max_length=50, db_column='C8_CONTATO', blank=True, null=True)
    c8_cond = models.CharField(max_length=20, db_column='C8_COND', blank=True, null=True)
    c8_vldesc = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_VLDESC', default=0)
    c8_valfre = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_VALFRE', default=0)
    c8_seguro = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_SEGURO', default=0)
    c8_despesa = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_DESPESA', default=0)
    c8_valipi = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_VALIPI', default=0)
    c8_valicm = models.DecimalField(max_digits=10, decimal_places=2, db_column='C8_VALICM', default=0)
    c8_datprf = models.CharField(max_length=8, db_column='C8_DATPRF', blank=True, null=True)
    c8_prazo = models.DecimalField(max_digits=5, decimal_places=0, db_column='C8_PRAZO', default=0)
    c8_tpfrete = models.CharField(max_length=2, db_column='C8_TPFRETE', blank=True, null=True)
    c8_obs = models.CharField(max_length=255, db_column='C8_OBS', blank=True, null=True)
    c8_numsc = models.CharField(max_length=20, db_column='C8_NUMSC', blank=True, null=True)

    @property
    def data_entrega_formatada(self):
        if self.c8_datprf and len(self.c8_datprf) == 8:
            ano = self.c8_datprf[0:4]
            mes = self.c8_datprf[4:6]
            dia = self.c8_datprf[6:8]
            return f"{dia}/{mes}/{ano}"
        return self.c8_datprf

    class Meta:
        managed = False
        db_table = 'SC8010'

    def __str__(self):
        return f"Cotação {self.c8_num} - Item {self.c8_item} - Forn. {self.c8_fornece}"
class SYSCompany(models.Model):
    m0_codfil = models.CharField(max_length=10, db_column='M0_CODFIL', primary_key=True) # Código da Filial (Ex: "0101")
    m0_nome = models.CharField(max_length=255, db_column='M0_NOME') # Nome da Empresa/Grupo (Ex: "Grupo Reunidas")
    m0_filial = models.CharField(max_length=255, db_column='M0_FILIAL') # <-- CAMPO ADICIONADO: Nome da Filial (Ex: "REUNIDAS COMERCIO")
    m0_tel = models.CharField(max_length=20, db_column='M0_TEL', blank=True, null=True)
    m0_cgc = models.CharField(max_length=20, db_column='M0_CGC')
    m0_insc = models.CharField(max_length=20, db_column='M0_INSC', blank=True, null=True)
    m0_endent = models.CharField(max_length=255, db_column='M0_ENDENT', blank=True, null=True)
    m0_cident = models.CharField(max_length=100, db_column='M0_CIDENT', blank=True, null=True)
    m0_bairent = models.CharField(max_length=100, db_column='M0_BAIRENT', blank=True, null=True)
    m0_cepent = models.CharField(max_length=9, db_column='M0_CEPENT', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'SYS_COMPANY' 
        verbose_name = "Informações da Empresa"
        verbose_name_plural = "Informações da Empresa"
    
    def __str__(self):
        return self.m0_nome

class SC1(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    c1_filial = models.CharField(max_length=10, db_column='C1_FILIAL')
    c1_num = models.CharField(max_length=20, db_column='C1_NUM')
    c1_obs = models.CharField(max_length=255, db_column='C1_OBS', blank=True, null=True)
    c1_datprf = models.CharField(max_length=8, db_column='C1_DATPRF', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'SC1010'

    def __str__(self):
        return f"SC {self.c1_num} - {self.c1_obs}"


class SE4(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    e4_codigo = models.CharField(max_length=20, db_column='E4_CODIGO')
    e4_descri = models.CharField(max_length=255, db_column='E4_DESCRI')

    class Meta:
        managed = False
        db_table = 'SE4010'

    def __str__(self):
        return f"{self.e4_cod} - {self.e4_descri}"
    

class FornecedorEmailAdicional(models.Model):
    fornecedor = models.ForeignKey(
        'FornecedorUsuario',
        on_delete=models.CASCADE,
        related_name='emails_adicionais'
    )
    email = models.EmailField(
        max_length=255,
        verbose_name="E-mail Adicional"
    )
    observacao = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Observação (ex: e-mail de nota fiscal)"
    )

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "E-mail Adicional"
        verbose_name_plural = "E-mails Adicionais"
    
class SBM(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    bm_grupo = models.CharField(max_length=4, db_column='BM_GRUPO')
    bm_desc = models.CharField(max_length=100, db_column='BM_DESC')

    class Meta:
        managed = False
        db_table = 'SBM010'

    def __str__(self):
        return f"{self.bm_grupo.strip()} - {self.bm_desc.strip()}"
    
class SCR010Aprovacao(models.Model):
    recno = models.IntegerField(primary_key=True, db_column='R_E_C_N_O_')
    cr_filial = models.CharField(max_length=10, db_column='CR_FILIAL')
    cr_num = models.CharField(max_length=20, db_column='CR_NUM')
    cr_user = models.CharField(max_length=20, db_column='CR_USER')
    cr_status = models.CharField(max_length=2, db_column='CR_STATUS')

    class Meta:
        managed = False
        db_table = 'SCR010'
        
class SYSUSR(models.Model):
    usr_id = models.CharField(max_length=20, primary_key=True, db_column='USR_ID')
    usr_nome = models.CharField(max_length=255, db_column='USR_NOME')

    class Meta:
        managed = False
        db_table = 'SYS_USR'

    def __str__(self):
        return self.usr_nome
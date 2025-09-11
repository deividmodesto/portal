from django.contrib import admin
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.db.models import F, Window, Prefetch
from django.db.models.functions import RowNumber
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import Motorista 

# Importa todos os modelos necessários
from .models import FornecedorUsuario, PedidoLiberado, SA2Fornecedor, SC7PedidoItem, ItemColeta, ItemColetaDetalhe, FornecedorAvulso, FornecedorEmailAdicional


class FornecedorEmailAdicionalInline(admin.TabularInline):
    model = FornecedorEmailAdicional
    extra = 1

@admin.register(FornecedorUsuario)
class FornecedorUsuarioAdmin(admin.ModelAdmin):
    inlines = [FornecedorEmailAdicionalInline]
    list_display = ('nome_fornecedor', 'cnpj', 'email', 'data_criacao')
    search_fields = ('nome_fornecedor', 'cnpj')
    readonly_fields = ('password',)


class ItemColetaDetalheInline(admin.TabularInline):
    model = ItemColetaDetalhe
    extra = 0
    # AQUI ESTÁ A CORREÇÃO IMPORTANTE:
    # Usar 'item_erp_recno' diretamente, pois 'item_erp' é uma property e não um campo de BD.
    readonly_fields = ('item_erp_recno', 'quantidade_disponivel', 'quantidade_coletada', 'observacao_divergencia')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ItemColeta)
class ItemColetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_identificador_pedido', 'status_coleta', 'data_disponibilidade', 'data_agendada', 'agendado_por', 'conferido_por')
    list_filter = ('status_coleta', 'data_disponibilidade', 'data_agendada', ('pedido_liberado', admin.EmptyFieldListFilter))
    search_fields = ('pedido_liberado__numero_pedido', 'fornecedor_avulso')
    readonly_fields = ('agendado_por', 'conferido_por')
    list_display_links = ('id', 'get_identificador_pedido')
    inlines = [ItemColetaDetalheInline]

    @admin.display(description='Pedido / Coleta Avulsa')
    def get_identificador_pedido(self, obj):
        if obj.pedido_liberado:
            return f"Pedido: {obj.pedido_liberado.numero_pedido}"
        else:
            return f"Avulsa: {obj.fornecedor_avulso}"

class ItemColetaInline(admin.TabularInline):
    model = ItemColeta
    extra = 0
    fields = ('get_identificador_coleta', 'status_coleta', 'data_disponibilidade', 'data_agendada', 'conferido_por')
    readonly_fields = fields
    can_delete = False
    @admin.display(description='Coleta ID')
    def get_identificador_coleta(self, obj):
        return obj.id
    def has_add_permission(self, request, obj=None):
        return False
    
@admin.register(PedidoLiberado)
class PedidoLiberadoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'fornecedor_usuario', 'status', 'data_liberacao_portal')
    list_filter = ('status', 'fornecedor_usuario')
    search_fields = ('numero_pedido',)
    inlines = [ItemColetaInline]

@admin.register(SA2Fornecedor)
class SA2FornecedorAdmin(admin.ModelAdmin):
    list_display = ('a2_nome', 'a2_cgc', 'a2_email')
    search_fields = ('a2_nome', 'a2_cgc')
    actions = ['criar_acesso_portal']

    @admin.action(description='Criar acesso ao portal para selecionados')
    def criar_acesso_portal(self, request, queryset):
        # ... (código existente, sem alterações)
        pass # Mantenha seu código aqui

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SC7PedidoItem)
class SC7PedidoAdmin(admin.ModelAdmin):
    verbose_name = "Pedidos do ERP (para liberar)"
    verbose_name_plural = "Pedidos do ERP (para liberar)"
    list_display = ('c7_num', 'nome_do_fornecedor', 'c7_emissao')
    search_fields = ('c7_num', 'c7_fornece')
    actions = ['liberar_pedidos_para_fornecedor']

    def get_queryset(self, request):
        from django.db.models import F, Window
        from django.db.models.functions import RowNumber
        
        # 1. Busca os pedidos já liberados no banco 'logistica' e cria uma lista Python
        pedidos_ja_liberados = list(PedidoLiberado.objects.values_list('numero_pedido', flat=True))
        
        # 2. Inicia a consulta no banco do ERP, mas selecionando explicitamente todas as colunas com .only()
        # Esta é a base que sabemos que funciona no seu ambiente.
        qs = super().get_queryset(request).only(
            'recno', 'c7_filial', 'c7_num', 'c7_item', 'c7_produto', 'c7_descri',
            'c7_quant', 'c7_preco', 'c7_total', 'c7_emissao', 'c7_fornece',
            'c7_encer', 'c7_contato', 'c7_emitido', 'c7_tpfrete', 'c7_numsc',
            'c7_numcot', 'c7_compra'
        )
        
        # 3. Aplica os filtros necessários
        qs = qs.exclude(c7_encer='E').exclude(c7_num__in=pedidos_ja_liberados)
        
        # 4. Aplica o agrupamento para mostrar apenas uma linha por pedido
        qs = qs.annotate(
            row_number=Window(expression=RowNumber(), partition_by=[F('c7_num')], order_by=F('recno').asc())
        ).filter(row_number=1)
        
        return qs
    
    @admin.display(description='Fornecedor')
    def nome_do_fornecedor(self, obj):
        fornecedor = SA2Fornecedor.objects.filter(a2_cod=obj.c7_fornece.strip()).first()
        return fornecedor.a2_nome if fornecedor else "NÃO ENCONTRADO"

    @admin.action(description='Liberar pedido(s) para o fornecedor')
    def liberar_pedidos_para_fornecedor(self, request, queryset):
        messages.warning(request, "Esta ação foi movida para o 'Painel do Comprador' para um fluxo de trabalho mais rápido.")

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
   
@admin.register(FornecedorAvulso)
class FornecedorAvulsoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'municipio', 'telefone')
    search_fields = ('nome', 'cnpj')
    list_filter = ('municipio',)

@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone', 'ativo')
    search_fields = ('nome',)
    list_filter = ('ativo',)
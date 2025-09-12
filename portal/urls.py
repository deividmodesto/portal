from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    # Login / Logout e Dashboard do Fornecedor
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('redefinir-senha/', views.redefinir_senha_view, name='redefinir_senha'),
    path('', views.dashboard_view, name='dashboard'),
    path('pedido/<int:pedido_id>/', views.supplier_pedido_detalhes_view, name='supplier_pedido_detalhes'),

    # --- PAINEL INTERNO (COMPRADOR / LOGÍSTICA) ---

    # Dashboards
    path('interno/dashboard/', views.comprador_dashboard_view, name='comprador_dashboard'),
    path('interno/historico/', views.comprador_historico_view, name='comprador_historico'),
    path('interno/historico/enviar-lembrete/<int:pedido_id>/', views.enviar_lembrete_view, name='enviar_lembrete'), # Linha adicionada

    # Detalhes e Ações do Pedido (Ações do Comprador)
       path('interno/pedido/<str:pedido_num>/<str:filial>/detalhes/', views.comprador_pedido_detalhes_view, name='comprador_pedido_detalhes'),
    path('interno/pedido/<str:pedido_num>/<str:filial>/liberar/', views.liberar_pedido_view, name='liberar_pedido'),
    path('interno/pedido/<str:pedido_num>/<str:filial>/pdf/', views.gerar_pedido_pdf_view, name='gerar_pedido_pdf'),
    
    # Ações de Fornecedor
    path('interno/fornecedor/<str:fornecedor_cod>/criar-acesso/', views.criar_acesso_fornecedor_view, name='criar_acesso_fornecedor'),
    path('interno/fornecedor/<int:fornecedor_id>/adicionar-email/', views.adicionar_email_fornecedor_view, name='adicionar_email_fornecedor'),


    # Painel de Coletas (Ações da Logística)
    path('interno/coletas/', views.coleta_dashboard_view, name='coleta_dashboard'),
    path('interno/coletas/atualizar-ordem/', views.atualizar_ordem_coleta, name='atualizar_ordem_coleta'),

    
    # CORREÇÃO: Garanta que esta linha aponta para a view correta.
    path('interno/coletas/conferencia/<int:coleta_id>/', views.coleta_conferencia_view, name='coleta_conferencia'),
    
    path('interno/coletas/avulsa/adicionar/', views.adicionar_coleta_avulsa_view, name='adicionar_coleta_avulsa'),
    path('interno/coletas/avulsa/conferencia/<int:coleta_id>/', views.coleta_avulsa_conferencia_view, name='coleta_avulsa_conferencia'),


    # Gerenciar Locais Avulsos
    path('interno/locais/', views.gerenciar_locais_avulsos_view, name='gerenciar_locais'),
    path('interno/locais/adicionar/', views.adicionar_local_avulso_view, name='adicionar_local'),
    path('interno/locais/editar/<int:local_id>/', views.editar_local_avulso_view, name='editar_local'),
    path('interno/locais/excluir/<int:local_id>/', views.excluir_local_avulso_view, name='excluir_local'),

    # Relatórios
    path('interno/relatorios/', views.relatorios_view, name='relatorios'),
    path('interno/relatorios/romaneio/', views.gerar_romaneio_view, name='gerar_romaneio'),
    path('interno/relatorios/divergencias/', views.gerar_divergencias_view, name='gerar_divergencias'),
    path('interno/relatorios/desempenho/', views.gerar_desempenho_view, name='gerar_desempenho'),

    # Análise de Cotações
    path('interno/cotacoes/analise/', views.analise_cotacao_view, name='analise_cotacao'),
    path('interno/cotacoes/relatorio-condicao/', views.cotacoes_por_condicao_view, name='relatorio_cotacoes_condicao'),
    
]
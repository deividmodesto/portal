# Imports do Django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import F, Window, Subquery, OuterRef, Sum, Prefetch, Avg, Count, Q, Case, When, Value, CharField
from django.db.models.functions import Cast
from django.db import models
from django.db.models.functions import RowNumber, Concat
from django.shortcuts import render, redirect, Http404, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django import forms
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.core.mail import EmailMessage
from weasyprint import HTML, CSS
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Max, F, Value as V, Min 
from django.core.paginator import Paginator
from django.http import JsonResponse # Adicione este import
from django.views.decorators.http import require_POST # Adicione este import
import json # Adicione este import
import logging # Adicione este import
from django.db import transaction # Adicione este import

# Imports de bibliotecas nativas do Python
import re
import os
import base64

# Imports locais (do nosso projeto)
from .models import (FornecedorUsuario, PedidoLiberado, SA2Fornecedor, SC7PedidoItem, 
                     ItemColeta, ItemColetaDetalhe, FornecedorAvulso, SC8CotacaoItem, 
                     SYSCompany, SC1, SE4, FornecedorEmailAdicional, SD1NFItem, SBM,
                     SCR010Aprovacao, SYSUSR) 
from .models import Motorista, ItemColeta 
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
from .models import Rota, PontoGPS, EventoColeta # Adicionar ao topo
from django.db.models import F, Q

# Crie um logger para a view
logger = logging.getLogger(__name__)


class FornecedorEmailAdicionalForm(forms.ModelForm):
    class Meta:
        model = FornecedorEmailAdicional
        fields = ['email', 'observacao']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'observacao': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


@staff_member_required
def adicionar_email_fornecedor_view(request, fornecedor_id):
    fornecedor = get_object_or_404(FornecedorUsuario, id=fornecedor_id)
    if request.method == 'POST':
        form = FornecedorEmailAdicionalForm(request.POST)
        if form.is_valid():
            email_adicional = form.save(commit=False)
            email_adicional.fornecedor = fornecedor
            email_adicional.save()
            messages.success(request, f"E-mail adicional para {fornecedor.nome_fornecedor} salvo com sucesso.")
            return redirect('portal:comprador_dashboard')
    else:
        form = FornecedorEmailAdicionalForm()
    
    context = {
        'form': form,
        'fornecedor': fornecedor,
    }
    return render(request, 'portal/adicionar_email.html', context)

class FornecedorAvulsoForm(forms.ModelForm):
    class Meta:
        model = FornecedorAvulso
        fields = ['nome', 'cnpj', 'endereco', 'municipio', 'telefone']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-input'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-input'}),
            'endereco': forms.TextInput(attrs={'class': 'form-input'}),
            'municipio': forms.TextInput(attrs={'class': 'form-input'}),
            'telefone': forms.TextInput(attrs={'class': 'form-input'}),
        }


def autenticar_fornecedor(request, cnpj, password):
    try:
        fornecedor = FornecedorUsuario.objects.get(cnpj=cnpj)
        if fornecedor.password == password:
            user, created = User.objects.get_or_create(username=cnpj)
            if created:
                user.set_unusable_password()
                user.save()
            user.fornecedor = fornecedor
            return user
    except FornecedorUsuario.DoesNotExist:
        return None
    return None


def login_view(request):
    error = None
    if request.method == 'POST':
        cnpj_raw = request.POST.get('cnpj', '')
        cnpj = re.sub(r'[^0-9]', '', cnpj_raw)
        password = request.POST.get('password', '')
        user = autenticar_fornecedor(request, cnpj=cnpj, password=password)
        if user is not None:
            login(request, user)
            return redirect('portal:dashboard')
        else:
            error = "CNPJ ou senha inválidos."
    return render(request, 'portal/login.html', {'error': error})

def redefinir_senha_view(request):
    error = None
    if request.method == 'POST':
        cnpj_raw = request.POST.get('cnpj', '')
        cnpj = re.sub(r'[^0-9]', '', cnpj_raw)
        
        try:
            fornecedor = FornecedorUsuario.objects.get(cnpj=cnpj)
            nova_senha = get_random_string(10)
            
            # Atualiza a senha no banco de dados
            fornecedor.password = nova_senha
            fornecedor.save()
            
            # Envia e-mail com a nova senha
            contexto_email = {
                'nome_fornecedor': fornecedor.nome_fornecedor,
                'cnpj': fornecedor.cnpj,
                'nova_senha': nova_senha,
            }
            corpo_email = render_to_string('portal/email/redefinir_senha.txt', contexto_email)
            
            send_mail(
                subject='Redefinição de Senha do Portal de Coletas',
                message=corpo_email,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[fornecedor.email],
                fail_silently=False,
            )
            
            messages.success(request, "Uma nova senha foi enviada para o e-mail cadastrado.")
            return redirect('portal:redefinir_senha')
            
        except FornecedorUsuario.DoesNotExist:
            error = "CNPJ não encontrado em nossa base de dados."

    context = {'error': error}
    return render(request, 'portal/redefinir_senha.html', context)

def get_logo_base64():
    try:
        logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'img', 'logo_reunidas2.png')
        with open(logo_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"
    except (FileNotFoundError, IndexError):
        return None


@login_required(login_url='/login/')
def dashboard_view(request):
    if request.user.is_staff:
        return redirect('portal:comprador_dashboard')
    try:
        fornecedor = FornecedorUsuario.objects.get(cnpj=request.user.username)
        pedidos = PedidoLiberado.objects.filter(fornecedor_usuario=fornecedor).order_by('data_emissao')

        # Prepara os pedidos para exibição correta no template
        for pedido in pedidos:
            if not pedido.data_visualizacao:
                pedido.data_visualizacao = timezone.now()
                pedido.save(update_fields=['data_visualizacao'])
            
            try:
                pedido.numero_pedido_display = pedido.numero_pedido.split('-')[0]
            except:
                pedido.numero_pedido_display = pedido.numero_pedido

        context = {
            'nome_fornecedor': fornecedor.nome_fornecedor,
            'pedidos': pedidos
        }
        return render(request, 'portal/dashboard.html', context)
    except FornecedorUsuario.DoesNotExist:
        logout(request)
        return redirect('portal:login')


@login_required
def logout_view(request):
    logout(request)
    return redirect('portal:login')


@staff_member_required
def enviar_lembrete_view(request, pedido_id):
    try:
        pedido = get_object_or_404(PedidoLiberado, id=pedido_id)

        # Apenas envie o e-mail se o status for 'LIBERADO' e não tiver sido visualizado
        if pedido.status == 'LIBERADO' and not pedido.data_visualizacao:
            fornecedor_portal = pedido.fornecedor_usuario
            emails_to_send = [
                email for email in [fornecedor_portal.email] + list(fornecedor_portal.emails_adicionais.values_list('email', flat=True))
                if email and '@' in email and '.' in email
            ]

            if not emails_to_send:
                messages.error(request, f"Nenhum e-mail de fornecedor válido encontrado para o pedido {pedido.numero_pedido}.")
            else:
                contexto_email = {
                    'nome_fornecedor': fornecedor_portal.nome_fornecedor,
                    'numero_pedido': pedido.numero_pedido,
                }
                corpo_email = render_to_string('portal/email/lembrete_coleta.txt', contexto_email)

                email = EmailMessage(
                    subject=f'Lembrete: Pedido de Compra Nº {pedido.numero_pedido} Pendente de Resposta',
                    body=corpo_email,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=emails_to_send,
                )
                email.send(fail_silently=False)
                messages.success(request, f"E-mail de lembrete enviado com sucesso para {fornecedor_portal.nome_fornecedor} (Pedido Nº {pedido.numero_pedido}).")
        else:
            messages.warning(request, f"Não foi possível enviar o lembrete. O pedido {pedido.numero_pedido} já foi visualizado ou não está com o status 'Não Respondido'.")

    except Exception as e:
        logger.error(f"Erro ao enviar lembrete para o pedido {pedido_id}: {e}")
        messages.error(request, f"Ocorreu um erro inesperado ao tentar enviar o e-mail de lembrete: {e}")
    
    return redirect('portal:comprador_historico')


@login_required
def supplier_pedido_detalhes_view(request, pedido_id):
    try:
        fornecedor = FornecedorUsuario.objects.get(cnpj=request.user.username)
        pedido_liberado = PedidoLiberado.objects.get(id=pedido_id, fornecedor_usuario=fornecedor)
    except (FornecedorUsuario.DoesNotExist, PedidoLiberado.DoesNotExist):
        raise Http404("Pedido não encontrado")

    try:
        num_pedido_original, filial_pedido = pedido_liberado.numero_pedido.split('-')
    except ValueError:
        num_pedido_original = pedido_liberado.numero_pedido
        filial_pedido = '01' 

    itens_erp = SC7PedidoItem.objects.filter(
        c7_num=num_pedido_original, 
        c7_filial=filial_pedido
    ).exclude(d_e_l_e_t='*').order_by('c7_item')
    
    itens_ja_disponiveis = ItemColetaDetalhe.objects.filter(
        item_coleta__pedido_liberado=pedido_liberado
    ).values('item_erp_recno').annotate(total_disponivel=Sum('quantidade_disponivel'))
    mapa_disponiveis = {item['item_erp_recno']: item['total_disponivel'] for item in itens_ja_disponiveis}

    itens_para_template = []
    total_pendente_geral = Decimal('0.0')
    for item_erp in itens_erp:
        disponivel = mapa_disponiveis.get(item_erp.recno, 0)
        pendente = Decimal(str(item_erp.c7_quant)) - Decimal(str(disponivel))
        total_pendente_geral += pendente
        itens_para_template.append({
            'erp': item_erp,
            'disponivel': disponivel,
            'pendente': pendente
        })

    if request.method == 'POST':
        data_disp = request.POST.get('data_disponibilidade')
        if not data_disp:
            messages.error(request, "A 'Data para Retirada' é um campo obrigatório.")
            return redirect('portal:supplier_pedido_detalhes', pedido_id=pedido_id)

        nova_coleta = ItemColeta.objects.create(
            pedido_liberado=pedido_liberado,
            data_disponibilidade=data_disp,
            volumes=request.POST.get('volumes') or None,
            peso_kg=request.POST.get('peso_kg') or None,
            numero_nota_fiscal=request.POST.get('numero_nota_fiscal'),
            chave_acesso_nfe=request.POST.get('chave_acesso_nfe')
        )

        itens_a_disponibilizar = []
        soma_qtd_disponibilizada = Decimal('0.0')
        for item in itens_para_template:
            recno = item['erp'].recno
            qtd_str = request.POST.get(f'quantidade_item_{recno}')
            if qtd_str:
                try:
                    qtd_a_disponibilizar = Decimal(qtd_str.replace(',', '.'))
                    if qtd_a_disponibilizar > 0:
                        itens_a_disponibilizar.append(
                            ItemColetaDetalhe(
                                item_coleta=nova_coleta,
                                item_erp_recno=recno,
                                quantidade_disponivel=qtd_a_disponibilizar
                            )
                        )
                        soma_qtd_disponibilizada += qtd_a_disponibilizar
                except:
                    pass
        
        if itens_a_disponibilizar:
            ItemColetaDetalhe.objects.bulk_create(itens_a_disponibilizar)
            if total_pendente_geral - soma_qtd_disponibilizada <= 0:
                pedido_liberado.status = 'TOTALMENTE_DISPONIVEL'
            else:
                pedido_liberado.status = 'PARCIALMENTE_DISPONIVEL'
            pedido_liberado.save()
            messages.success(request, "Itens disponibilizados para coleta com sucesso!")
        else:
            nova_coleta.delete()
            messages.warning(request, "Nenhuma quantidade foi informada.")
        return redirect('portal:supplier_pedido_detalhes', pedido_id=pedido_id)

    coletas_anteriores = ItemColeta.objects.filter(pedido_liberado=pedido_liberado).order_by('-data_criacao')
    context = {
        'pedido': pedido_liberado,
        'itens': itens_para_template,
        'coletas_anteriores': coletas_anteriores
    }
    return render(request, 'portal/supplier_pedido_detalhes.html', context)

@staff_member_required
def comprador_dashboard_view(request):
    # Lógica de filtros (sem alteração)
    filtro_fornecedor_cod = request.GET.get('fornecedor', '')
    filtro_pedido_num = request.GET.get('pedido', '')
    filtro_data_inicio = request.GET.get('data_inicio', '')
    filtro_data_fim = request.GET.get('data_fim', '')
    filtro_filial = request.GET.get('filial', '')
    filtro_status = request.GET.get('status', '')
    filtro_grupo_produto = request.GET.get('grupo_produto', '')
    filtro_municipio = request.GET.get('municipio', '')
    filtro_classe_superior = request.GET.get('classe_superior', '')

    status_choices = { 'L': 'Liberado', 'B': 'Bloqueado', 'R': 'Reprovado' }

    pedidos_ja_liberados = list(PedidoLiberado.objects.values_list('numero_pedido', flat=True))

    base_pedidos_pendentes_qs = SC7PedidoItem.objects.annotate(
        composite_key=Concat('c7_num', V('-'), 'c7_filial')
    ).exclude(
        c7_encer='E'
    ).exclude(
        composite_key__in=pedidos_ja_liberados
    )

    # Lógica para obter filtros (sem alteração)
    todos_grupos = SBM.objects.all().order_by('bm_grupo')
    classes_superiores = []
    codigos_classes_adicionadas = set()
    for grupo in todos_grupos:
        if len(grupo.bm_grupo.strip()) == 1:
            codigo_classe = grupo.bm_grupo.strip()
            if codigo_classe not in codigos_classes_adicionadas:
                classes_superiores.append({
                    'cod': codigo_classe,
                    'desc': f"{codigo_classe} - {grupo.bm_desc.strip()}"
                })
                codigos_classes_adicionadas.add(codigo_classe)

    grupos_de_produto = todos_grupos.exclude(bm_grupo__in=[c['cod'] for c in classes_superiores])

    filiais_para_filtro = base_pedidos_pendentes_qs.values_list('c7_filial', flat=True).distinct().order_by('c7_filial')
    codigos_fornecedores_para_filtro = base_pedidos_pendentes_qs.values_list('c7_fornece', flat=True).distinct()
    fornecedores_para_filtro = SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores_para_filtro).order_by('a2_nome')
    municipios_pendentes = SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores_para_filtro).values_list('a2_mun', flat=True).distinct().order_by('a2_mun')

    pedidos_filtrados_qs = base_pedidos_pendentes_qs
    if filtro_fornecedor_cod:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_fornece=filtro_fornecedor_cod)
    if filtro_pedido_num:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_num__icontains=filtro_pedido_num)
    if filtro_data_inicio and filtro_data_fim:
        data_inicio_protheus = filtro_data_inicio.replace('-', '')
        data_fim_protheus = filtro_data_fim.replace('-', '')
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_emissao__range=[data_inicio_protheus, data_fim_protheus])
    elif filtro_data_inicio:
        data_inicio_protheus = filtro_data_inicio.replace('-', '')
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_emissao__gte=data_inicio_protheus)
    elif filtro_data_fim:
        data_fim_protheus = filtro_data_fim.replace('-', '')
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_emissao__lte=data_fim_protheus)
    if filtro_filial:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_filial=filtro_filial)
    if filtro_status:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_conapro=filtro_status)

    if filtro_classe_superior:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_produto__startswith=filtro_classe_superior)
    elif filtro_grupo_produto:
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_produto__startswith=filtro_grupo_produto)

    if filtro_municipio:
        codigos_fornecedores_municipio = SA2Fornecedor.objects.filter(a2_mun=filtro_municipio).values_list('a2_cod', flat=True)
        pedidos_filtrados_qs = pedidos_filtrados_qs.filter(c7_fornece__in=codigos_fornecedores_municipio)

    pedidos_unicos_filtrados = pedidos_filtrados_qs.annotate(
        row_number=Window(expression=RowNumber(), partition_by=[F('c7_num'), F('c7_filial')], order_by=F('recno').asc())
    ).filter(row_number=1)

    resultado_final = pedidos_unicos_filtrados.annotate(
        nome_fornecedor=Subquery(
            SA2Fornecedor.objects.filter(a2_cod=OuterRef('c7_fornece')).values('a2_nome')[:1]
        ),
        status_pedido_display=Case(
            When(c7_conapro='B', then=Value('Bloqueado')),
            When(c7_conapro='L', then=Value('Liberado')),
            When(c7_conapro='R', then=Value('Reprovado')),
            default=Value('Não Definido'),
            output_field=CharField()
        )
    ).order_by('-c7_emissao')

    # --- LÓGICA DE PAGINAÇÃO CORRIGIDA ---
    per_page = request.GET.get('per_page', 25)
    try:
        per_page = int(per_page)
    except (ValueError, TypeError):
        per_page = 25
    
    # =====> ALTERAÇÃO ESTÁ AQUI <=====
    # Convertendo para lista para garantir que a paginação funcione com a query complexa
    paginator = Paginator(list(resultado_final), per_page)
    
    page_number = request.GET.get('page')
    pedidos_page_obj = paginator.get_page(page_number)

    cnpjs_com_acesso = {user.cnpj.strip(): user for user in FornecedorUsuario.objects.all()}

    for pedido in pedidos_page_obj:
        codigo_fornecedor = pedido.c7_fornece.strip()
        possible_suppliers = SA2Fornecedor.objects.filter(a2_cod=codigo_fornecedor)

        pedido.fornecedor_tem_acesso = False
        pedido.fornecedor_usuario = None

        if possible_suppliers.count() > 1:
            pedido.multiple_suppliers = True
            pedido.supplier_options = possible_suppliers
            if any(sup.a2_cgc.strip() in cnpjs_com_acesso for sup in possible_suppliers):
                pedido.fornecedor_tem_acesso = True
                for sup in possible_suppliers:
                    if sup.a2_cgc.strip() in cnpjs_com_acesso:
                        pedido.fornecedor_usuario = cnpjs_com_acesso[sup.a2_cgc.strip()]
                        break
        else:
            pedido.multiple_suppliers = False
            supplier = possible_suppliers.first()
            if supplier and supplier.a2_cgc.strip() in cnpjs_com_acesso:
                pedido.fornecedor_tem_acesso = True
                pedido.fornecedor_usuario = cnpjs_com_acesso[supplier.a2_cgc.strip()]

    # --- LÓGICA DE ESTATÍSTICAS (SOBRE O TOTAL FILTRADO) ---
    contagem_status = resultado_final.aggregate(
        total_aprovados=Count('c7_num', filter=Q(c7_conapro='L')),
        total_bloqueados=Count('c7_num', filter=Q(c7_conapro='B')),
        total_reprovados=Count('c7_num', filter=Q(c7_conapro='R')),
        total_nao_definido=Count('c7_num', filter=Q(c7_conapro=''))
    )

    codigos_fornecedores_filtrados = set(resultado_final.values_list('c7_fornece', flat=True))
    fornecedores_com_acesso_set = set()
    fornecedores_sem_acesso_set = set()

    for fornecedor_cod in codigos_fornecedores_filtrados:
        suppliers = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod.strip())
        if any(sup.a2_cgc.strip() in cnpjs_com_acesso for sup in suppliers):
            fornecedores_com_acesso_set.add(fornecedor_cod)
        else:
            fornecedores_sem_acesso_set.add(fornecedor_cod)

    stats = {
        'total_pedidos': paginator.count,
        'fornecedores_com_acesso': len(fornecedores_com_acesso_set),
        'fornecedores_sem_acesso': len(fornecedores_sem_acesso_set),
        'pedidos_aprovados': contagem_status['total_aprovados'],
        'pedidos_bloqueados': contagem_status['total_bloqueados'],
        'pedidos_reprovados': contagem_status['total_reprovados'],
        'pedidos_nao_definido': contagem_status['total_nao_definido'],
    }

    context = {
        'pedidos_page_obj': pedidos_page_obj,
        'per_page': per_page,
        'todos_fornecedores': fornecedores_para_filtro,
        'filiais_pendentes': filiais_para_filtro,
        'municipios_pendentes': municipios_pendentes,
        'classes_superiores': classes_superiores,
        'grupos_de_produto': grupos_de_produto,
        'status_choices': status_choices,
        'filtros': {
            'fornecedor': filtro_fornecedor_cod,
            'pedido': filtro_pedido_num,
            'data_inicio': filtro_data_inicio,
            'data_fim': filtro_data_fim,
            'filial': filtro_filial,
            'status': filtro_status,
            'grupo_produto': filtro_grupo_produto,
            'municipio': filtro_municipio,
            'classe_superior': filtro_classe_superior,
        },
        'stats': stats,
    }
    return render(request, 'portal/comprador_dashboard.html', context)


def preparar_contexto_pdf(pedido_num, filial, fornecedor_erp=None):
    itens_pedido_erp = SC7PedidoItem.objects.filter(
        c7_num=pedido_num, c7_filial=filial
    ).exclude(d_e_l_e_t='*').order_by('c7_item') # <-- Filtro adicionado aqui
    if not itens_pedido_erp.exists():
        raise Http404("Pedido não encontrado no ERP para esta filial")

    pedido_erp = itens_pedido_erp.first()
    
    try:
        # CORREÇÃO: Altera .get() para .filter().first() para evitar erro de múltiplos resultados.
        empresa_emitente = SYSCompany.objects.filter(m0_codfil=pedido_erp.c7_filial.strip()).first()
    except SYSCompany.DoesNotExist:
        empresa_emitente = None

    if not fornecedor_erp:
        fornecedor_cod = pedido_erp.c7_fornece.strip()
        try:
            fornecedor_erp = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod.strip()).first()

        except SA2Fornecedor.DoesNotExist:
            fornecedor_erp = None
    
    try:
        condicao_pagamento = SE4.objects.get(e4_codigo=pedido_erp.c7_cond.strip())
        desc_cond_pagamento = condicao_pagamento.e4_descri
    except SE4.DoesNotExist:
        desc_cond_pagamento = pedido_erp.c7_cond or "Não especificada"

    # Lógica para obter a aprovação do pedido
    aprovacoes_pedido = SCR010Aprovacao.objects.filter(
        cr_filial=filial, 
        cr_num=pedido_num
    ).order_by('cr_user') # CORRIGIDO: de 'cr_aprov' para 'cr_user'

    # Busca os nomes dos aprovadores em uma única consulta
    # AQUI ESTÁ A MUDANÇA: GARANTINDO QUE OS IDS ESTÃO SEM ESPAÇOS
    aprovador_ids = [aprovacao.cr_user.strip() for aprovacao in aprovacoes_pedido] # CORRIGIDO: de 'aprovacao.cr_aprov' para 'aprovacao.cr_user'
    aprovadores_map = {u.usr_id.strip(): u.usr_nome.strip() for u in SYSUSR.objects.filter(usr_id__in=aprovador_ids)}

    status_aprovacao_map = {
        '01': 'Aguardando nível anterior',
        '02': 'Pendente',
        '03': 'Liberado',
        '04': 'Bloqueado',
        '05': 'Liberado por outro aprovador',
        '06': 'Rejeitado',
        '07': 'Rejeitado/Bloqueado por outro aprovador'
    }

    aprovacoes_para_template = []
    for aprovacao in aprovacoes_pedido:
        aprovacoes_para_template.append({
            'aprovador': aprovadores_map.get(aprovacao.cr_user.strip(), "Aprovador não encontrado"),
            'status': status_aprovacao_map.get(aprovacao.cr_status.strip(), "Status desconhecido")
        })

    num_sc = pedido_erp.c7_numsc.strip()
    obs_sc = "N/A"
    data_necessidade = "N/A"
    try:
        # CORREÇÃO: Altera .get() para .filter().first() para evitar erro de múltiplos resultados.
        solicitacao_compra = SC1.objects.filter(c1_filial=pedido_erp.c7_filial, c1_num=num_sc).first()
        if solicitacao_compra:
            obs_sc = solicitacao_compra.c1_obs
            if solicitacao_compra.c1_datprf and len(solicitacao_compra.c1_datprf) == 8:
                ano = solicitacao_compra.c1_datprf[0:4]
                mes = solicitacao_compra.c1_datprf[4:6]
                dia = solicitacao_compra.c1_datprf[6:8]
                data_necessidade = f"{dia}/{mes}/{ano}"
    except SC1.DoesNotExist:
        pass

    status_map = {'B': 'Bloqueado', 'L': 'Liberado', 'R': 'Reprovado'}
    status_pedido = status_map.get(pedido_erp.c7_conapro.strip(), 'Não Definido')
    status_class = status_pedido.replace(' ', '-')

    total_produtos = sum(item.c7_total for item in itens_pedido_erp)
    total_ipi = sum(item.c7_ipi for item in itens_pedido_erp)
    total_frete = sum(item.c7_frete for item in itens_pedido_erp)
    total_desconto = sum(item.c7_vldesc for item in itens_pedido_erp)
    total_geral = (total_produtos + total_ipi + total_frete) - total_desconto

    logo_base64 = get_logo_base64()

    contexto = {
        'itens_pedido': itens_pedido_erp,
        'info_geral': pedido_erp,
        'empresa_emitente': empresa_emitente,
        'fornecedor': fornecedor_erp,
        'desc_cond_pagamento': desc_cond_pagamento,
        'obs_solicitacao_compra': obs_sc,
        'data_necessidade': data_necessidade,
        'status_pedido': status_pedido,
        'status_class': status_class,
        'logo_base64': logo_base64,
        'totais': {
            'produtos': total_produtos,
            'ipi': total_ipi,
            'frete': total_frete,
            'desconto': total_desconto,
            'geral': total_geral,
        },
        # Adicione a lista de aprovações ao contexto
        'aprovacoes': aprovacoes_para_template,
    }
    return contexto


@staff_member_required
def liberar_pedido_view(request, pedido_num, filial):
    if request.method == 'POST':
        fornecedor_recno = request.POST.get('fornecedor_recno')

        try:
            fornecedor_erp = None
            if fornecedor_recno:
                fornecedor_erp = SA2Fornecedor.objects.get(recno=fornecedor_recno)
            else:
                itens_pedido = SC7PedidoItem.objects.filter(c7_num=pedido_num, c7_filial=filial)
                if not itens_pedido.exists():
                    raise Http404("Pedido não encontrado")
                fornecedor_cod = itens_pedido.first().c7_fornece.strip()
                fornecedores = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod)
                if fornecedores.count() > 1:
                    messages.error(request, "Este fornecedor possui múltiplas filiais. Selecione uma filial para liberar o pedido.")
                    return redirect('portal:comprador_dashboard')
                fornecedor_erp = fornecedores.first()

            if not fornecedor_erp:
                messages.error(request, "Fornecedor não encontrado no ERP.")
                return redirect('portal:comprador_dashboard')

            fornecedor_portal, created = FornecedorUsuario.objects.get_or_create(
                cnpj=fornecedor_erp.a2_cgc.strip(),
                defaults={
                    'email': fornecedor_erp.a2_email.strip(),
                    'nome_fornecedor': fornecedor_erp.a2_nome.strip(),
                    'codigo_externo': fornecedor_erp.a2_cod.strip(),
                    'password': get_random_string(10)
                }
            )

            if created:
                contexto_email = {
                    'nome_fornecedor': fornecedor_erp.a2_nome.strip(),
                    'cnpj': fornecedor_erp.a2_cgc.strip(),
                    'senha': fornecedor_portal.password,
                }
                corpo_email = render_to_string('portal/email/novo_acesso.txt', contexto_email)
                send_mail(
                    subject='Seu Acesso ao Portal de Coletas',
                    message=corpo_email,
                    from_email=None,
                    recipient_list=[fornecedor_erp.a2_email.strip()],
                    fail_silently=False,
                )
                messages.success(request, f"Novo acesso criado para {fornecedor_erp.a2_nome.strip()} (CNPJ: {fornecedor_erp.a2_cgc.strip()}).")

            composite_key = f"{pedido_num}-{filial}"
            if PedidoLiberado.objects.filter(numero_pedido=composite_key).exists():
                 messages.warning(request, f"O Pedido Nº {pedido_num} ({filial}) já foi liberado.")
                 return redirect('portal:comprador_dashboard')

            contexto_pdf = preparar_contexto_pdf(pedido_num, filial, fornecedor_erp=fornecedor_erp)
            
            emails_to_send = [
                email for email in [fornecedor_portal.email] + list(fornecedor_portal.emails_adicionais.values_list('email', flat=True))
                if email and '@' in email and '.' in email
            ]

            if not emails_to_send:
                raise ValueError("Nenhum e-mail de fornecedor válido encontrado para enviar a notificação.")

            html_string = render_to_string('portal/pedido_compra_pdf.html', contexto_pdf)
            pdf_file = HTML(string=html_string).write_pdf()
            
            PedidoLiberado.objects.create(
                numero_pedido=composite_key,
                fornecedor_usuario=fornecedor_portal,
                data_emissao=contexto_pdf['info_geral'].c7_emissao,
                status='LIBERADO'
            )

            corpo_email_texto = render_to_string('portal/email/pedido_liberado.txt', {
                'nome_fornecedor': fornecedor_portal.nome_fornecedor,
                'numero_pedido': contexto_pdf['info_geral'].c7_num,
            })
            
            email = EmailMessage(
                subject=f'Pedido de Compra Nº {contexto_pdf["info_geral"].c7_num} Liberado',
                body=corpo_email_texto,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=emails_to_send,
            )
            email.attach(f'Pedido_de_Compra_{contexto_pdf["info_geral"].c7_num}.pdf', pdf_file, 'application/pdf')
            email.send(fail_silently=False)
            
            messages.success(request, f"Pedido Nº {pedido_num} ({filial}) liberado com sucesso para {fornecedor_portal.nome_fornecedor}.")

        except Exception as e:
            messages.error(request, f"Ocorreu um erro inesperado: {e}")
            
    return redirect('portal:comprador_dashboard')


@staff_member_required
def gerar_pedido_pdf_view(request, pedido_num, filial):
    try:
        fornecedor_erp = None
        composite_key = f"{pedido_num}-{filial}"
        
        # Verifica se o pedido já foi liberado (está no histórico)
        pedido_liberado = PedidoLiberado.objects.select_related('fornecedor_usuario').filter(numero_pedido=composite_key).first()

        if pedido_liberado:
            # Se foi liberado, usa o CNPJ salvo para encontrar o fornecedor exato e gerar o PDF
            fornecedor_cnpj = pedido_liberado.fornecedor_usuario.cnpj
            fornecedor_erp = get_object_or_404(SA2Fornecedor, a2_cgc=fornecedor_cnpj)
        else:
            # Se não foi liberado (veio do dashboard), aplica a validação de múltiplas filiais
            itens_pedido = SC7PedidoItem.objects.filter(c7_num=pedido_num, c7_filial=filial)
            if not itens_pedido.exists():
                raise Http404("Pedido não encontrado no ERP para esta filial")
            
            fornecedor_cod = itens_pedido.first().c7_fornece.strip()
            possible_suppliers = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod)
            
            if possible_suppliers.count() > 1:
                messages.warning(request, f"O fornecedor do Pedido {pedido_num} possui múltiplas filiais. O PDF não pode ser gerado diretamente. Utilize a ação 'Liberar para Filial' e o PDF será anexado ao e-mail.")
                return redirect('portal:comprador_dashboard')
            
            fornecedor_erp = possible_suppliers.first()

        # Com o fornecedor_erp correto em mãos, preparamos o contexto para o PDF
        contexto_pdf = preparar_contexto_pdf(pedido_num, filial, fornecedor_erp=fornecedor_erp)
        html_string = render_to_string('portal/pedido_compra_pdf.html', contexto_pdf)
        pdf_file = HTML(string=html_string).write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Pedido_de_Compra_{pedido_num}.pdf"'
        return response
    
    except Http404 as e:
        messages.error(request, f"Não foi possível gerar o PDF. Detalhes: {e}")
    except Exception as e:
        print(f"Erro ao gerar PDF para {pedido_num}-{filial}: {e}") 
        messages.error(request, f"Ocorreu um erro inesperado ao gerar o PDF.")
    
    # Em caso de erro, tenta retornar o usuário para a página de onde ele veio
    referer = request.META.get('HTTP_REFERER')
    if referer and 'historico' in referer:
        return redirect('portal:comprador_historico')
    return redirect('portal:comprador_dashboard')


@staff_member_required
def criar_acesso_fornecedor_view(request, fornecedor_cod):
    if request.method == 'POST':
        fornecedores_erp = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod.strip())
        
        if fornecedores_erp.count() > 1:
            messages.warning(request, "Este fornecedor possui múltiplas filiais. Para criar o acesso, por favor, utilize a opção 'Liberar' no pedido desejado e selecione a filial correta.")
            return redirect('portal:comprador_dashboard')

        fornecedor_erp = fornecedores_erp.first()
        if not fornecedor_erp:
            messages.error(request, f"Erro: Fornecedor com código {fornecedor_cod} não encontrado no ERP.")
            return redirect('portal:comprador_dashboard')

        if FornecedorUsuario.objects.filter(cnpj=fornecedor_erp.a2_cgc.strip()).exists():
            messages.warning(request, "Este fornecedor (baseado no CNPJ) já possui um acesso.")
            return redirect('portal:comprador_dashboard')
        
        try:
            senha_provisoria = get_random_string(10)
            FornecedorUsuario.objects.create(
                cnpj=fornecedor_erp.a2_cgc.strip(),
                email=fornecedor_erp.a2_email.strip(),
                nome_fornecedor=fornecedor_erp.a2_nome.strip(),
                codigo_externo=fornecedor_erp.a2_cod.strip(),
                password=senha_provisoria
            )
            contexto_email = {
                'nome_fornecedor': fornecedor_erp.a2_nome.strip(),
                'cnpj': fornecedor_erp.a2_cgc.strip(),
                'senha': senha_provisoria,
            }
            corpo_email = render_to_string('portal/email/novo_acesso.txt', contexto_email)
            send_mail(
                subject='Seu Acesso ao Portal de Coletas',
                message=corpo_email,
                from_email=None,
                recipient_list=[fornecedor_erp.a2_email.strip()],
                fail_silently=False,
            )
            messages.success(request, f"Acesso criado com sucesso para {fornecedor_erp.a2_nome.strip()}. Um e-mail foi enviado.")
        except Exception as e:
            messages.error(request, f"Ocorreu um erro inesperado: {e}")

    return redirect('portal:comprador_dashboard')


@staff_member_required
def comprador_pedido_detalhes_view(request, pedido_num, filial):
    itens_pedido = SC7PedidoItem.objects.filter(
        c7_num=pedido_num, c7_filial=filial
    ).exclude(d_e_l_e_t='*').order_by('c7_item') # <-- Filtro adicionado aqui
    if not itens_pedido.exists():
        raise Http404("Pedido não encontrado")

    info_geral = itens_pedido.first()
    try:
        fornecedor = SA2Fornecedor.objects.filter(a2_cod=info_geral.c7_fornece.strip()).first()
        nome_fornecedor = fornecedor.a2_nome if fornecedor else "Não encontrado"
    except SA2Fornecedor.DoesNotExist:
        nome_fornecedor = "Não encontrado"

    # Lógica para obter a aprovação do pedido
    aprovacoes_pedido = SCR010Aprovacao.objects.filter(
        cr_filial=filial, 
        cr_num=pedido_num
    ).order_by('cr_user') # CORRIGIDO: de 'cr_aprov' para 'cr_user'

    # Busca os nomes dos aprovadores em uma única consulta
    # AQUI ESTÁ A MUDANÇA: GARANTINDO QUE OS IDS ESTÃO SEM ESPAÇOS
    aprovador_ids = [aprovacao.cr_user.strip() for aprovacao in aprovacoes_pedido] # CORRIGIDO: de 'aprovacao.cr_aprov' para 'aprovacao.cr_user'
    aprovadores_map = {u.usr_id.strip(): u.usr_nome.strip() for u in SYSUSR.objects.filter(usr_id__in=aprovador_ids)}

    status_aprovacao_map = {
        '01': 'Aguardando nível anterior',
        '02': 'Pendente',
        '03': 'Liberado',
        '04': 'Bloqueado',
        '05': 'Liberado por outro aprovador',
        '06': 'Rejeitado',
        '07': 'Rejeitado/Bloqueado por outro aprovador'
    }

    aprovacoes_para_template = []
    for aprovacao in aprovacoes_pedido:
        aprovacoes_para_template.append({
            'aprovador': aprovadores_map.get(aprovacao.cr_user.strip(), "Aprovador não encontrado"),
            'status': status_aprovacao_map.get(aprovacao.cr_status.strip(), "Status desconhecido")
        })

    total_pedido_qtd = Decimal('0.0')
    total_entregue_qtd = Decimal('0.0')

    for item in itens_pedido:
        quant_decimal = Decimal(str(item.c7_quant or 0))
        quje_decimal = Decimal(str(item.c7_quje or 0))

        item.saldo_pendente = quant_decimal - quje_decimal
        total_pedido_qtd += quant_decimal
        total_entregue_qtd += quje_decimal

    if total_pedido_qtd > 0:
        percentual_conclusao = round((total_entregue_qtd / total_pedido_qtd) * 100)
    else:
        percentual_conclusao = 0
    
    saldo_total_pendente = total_pedido_qtd - total_entregue_qtd

    if info_geral.c7_tpfrete == 'C':
        tipo_frete = 'CIF (Custo, Seguro e Frete pagos pelo fornecedor)'
    elif info_geral.c7_tpfrete == 'F':
        tipo_frete = 'FOB (Frete pago pelo comprador/cliente)'
    else:
        tipo_frete = 'Não especificado'

    context = {
        'pedido_num': pedido_num,
        'itens_pedido': itens_pedido,
        'nome_fornecedor': nome_fornecedor,
        'info_geral': info_geral,
        'tipo_frete': tipo_frete,
        'status_entrega': {
            'total_pedido': total_pedido_qtd,
            'total_entregue': total_entregue_qtd,
            'saldo_pendente': saldo_total_pendente,
            'percentual': percentual_conclusao,
        },
        'aprovacoes': aprovacoes_para_template,
    }
    return render(request, 'portal/comprador_pedido_detalhes.html', context)


@staff_member_required
def comprador_historico_view(request):
    # Lógica de filtros atualizada
    filtro_fornecedor_id = request.GET.get('fornecedor', '')
    filtro_pedido_num = request.GET.get('pedido', '')
    filtro_data_liberacao = request.GET.get('data_liberacao', '')
    filtro_status = request.GET.get('status', '') # Filtro de status existente

    # NOVOS FILTROS ADICIONADOS
    filtro_data_disponibilidade = request.GET.get('data_disponibilidade_coleta', '')
    filtro_status_coleta = request.GET.get('status_coleta', '')

    historico_qs = PedidoLiberado.objects.select_related(
        'fornecedor_usuario'
    ).prefetch_related(
        'coletas'
    ).all()

    if filtro_fornecedor_id:
        historico_qs = historico_qs.filter(fornecedor_usuario__id=filtro_fornecedor_id)
    if filtro_pedido_num:
        historico_qs = historico_qs.filter(numero_pedido__icontains=filtro_pedido_num)
    if filtro_data_liberacao:
        historico_qs = historico_qs.filter(data_liberacao_portal__date=filtro_data_liberacao)
    if filtro_status: # Aplicando o filtro de status
        historico_qs = historico_qs.filter(status=filtro_status)

    # LÓGICA PARA NOVOS FILTROS
    if filtro_data_disponibilidade:
        historico_qs = historico_qs.filter(coletas__data_disponibilidade=filtro_data_disponibilidade)
        
    if filtro_status_coleta:
        historico_qs = historico_qs.filter(coletas__status_coleta=filtro_status_coleta)

    # Adicionando anotações para a data de coleta e o status mais recente
    historico_qs = historico_qs.annotate(
        data_disponibilidade_coleta=Min('coletas__data_disponibilidade'),
        status_coleta_display_key=Max('coletas__status_coleta')
    ).order_by('-data_liberacao_portal')

    # Lógica de paginação
    per_page = request.GET.get('per_page', 25)
    try:
        per_page = int(per_page)
    except (ValueError, TypeError):
        per_page = 25
    
    paginator = Paginator(historico_qs, per_page)
    page_number = request.GET.get('page')
    pedidos_historico_page_obj = paginator.get_page(page_number)
    
    status_map = dict(ItemColeta.STATUS_COLETA_CHOICES)
    for pedido in pedidos_historico_page_obj:
        try:
            pedido.num_original, pedido.filial = pedido.numero_pedido.split('-')
        except ValueError:
            pedido.num_original = pedido.numero_pedido
            pedido.filial = '01'
        
        if pedido.status_coleta_display_key:
            pedido.status_coleta_display = status_map.get(pedido.status_coleta_display_key, pedido.status_coleta_display_key)
        else:
             pedido.status_coleta_display = 'N/A'

    stats_historico = {
        'total_pedidos': paginator.count,
        'aguardando_fornecedor': historico_qs.filter(status='LIBERADO').count(),
        'prontos_para_coleta': historico_qs.filter(status__in=['PARCIALMENTE_DISPONIVEL', 'TOTALMENTE_DISPONIVEL']).count(),
        'concluidos': historico_qs.filter(status='COLETADO').count(),
    }

    fornecedores_com_pedidos = FornecedorUsuario.objects.filter(
        pedidoliberado__isnull=False
    ).distinct().order_by('nome_fornecedor')

    context = {
        'pedidos_historico_page_obj': pedidos_historico_page_obj,
        'per_page': per_page,
        'fornecedores': fornecedores_com_pedidos,
        'status_choices': PedidoLiberado.STATUS_CHOICES,
        'status_coleta_choices': ItemColeta.STATUS_COLETA_CHOICES, # ENVIANDO OPÇÕES PARA O TEMPLATE
        'filtros': {
            'fornecedor': filtro_fornecedor_id,
            'pedido': filtro_pedido_num,
            'data_liberacao': filtro_data_liberacao,
            'status': filtro_status,
            'data_disponibilidade_coleta': filtro_data_disponibilidade, # ENVIANDO VALOR ATUAL
            'status_coleta': filtro_status_coleta, # ENVIANDO VALOR ATUAL
        },
        'stats_historico': stats_historico,
    }
    return render(request, 'portal/comprador_historico.html', context)


@staff_member_required
def coleta_dashboard_view(request):
    if request.method == 'POST':
        coleta_id = request.POST.get('coleta_id')
        if not coleta_id:
            messages.error(request, "Erro: Ação inválida. O ID da coleta não foi encontrado no formulário.")
            return redirect('portal:coleta_dashboard')
        
        try:
            coleta_para_atualizar = ItemColeta.objects.get(id=coleta_id)

            if 'agendar_coleta' in request.POST:
                data_agendada_str = request.POST.get('data_agendada')
                if data_agendada_str:
                    data_obj = datetime.strptime(data_agendada_str, '%Y-%m-%d').date()
                    coleta_para_atualizar.data_agendada = data_obj
                    coleta_para_atualizar.status_coleta = 'AGENDADA'
                    coleta_para_atualizar.agendado_por = request.user
                    coleta_para_atualizar.save()
                    messages.success(request, f"Coleta agendada por {request.user.username} para {data_obj.strftime('%d/%m/%Y')}.")
                else: 
                    coleta_para_atualizar.data_agendada = None
                    coleta_para_atualizar.status_coleta = 'PENDENTE'
                    coleta_para_atualizar.agendado_por = request.user
                    coleta_para_atualizar.save()
                    messages.warning(request, f"Agendamento removido por {request.user.username}.")
            
            elif 'salvar_planejamento' in request.POST:
                ordem_str = request.POST.get('ordem_visita', '0')
                prioridade = request.POST.get('prioridade', 'NORMAL')
                observacao = request.POST.get('observacao_coleta', '')
                motorista_id = request.POST.get('motorista', None)
                
                coleta_para_atualizar.ordem_visita = int(ordem_str) if ordem_str.isdigit() else 0
                coleta_para_atualizar.prioridade = prioridade
                coleta_para_atualizar.observacao_coleta = observacao
                coleta_para_atualizar.motorista_id = motorista_id if motorista_id else None
                coleta_para_atualizar.save()
                messages.success(request, f"Planejamento da coleta atualizado com sucesso.")

        except ItemColeta.DoesNotExist:
            messages.error(request, "Erro: a coleta não foi encontrada.")
        
        query_string = request.GET.urlencode()
        return redirect(f"{reverse('portal:coleta_dashboard')}?{query_string}")

    filtro_fornecedor_id = request.GET.get('fornecedor', '')
    filtro_data_disp = request.GET.get('data_disponibilidade', '')
    filtro_status = request.GET.get('status', '')
    filtro_municipio = request.GET.get('municipio', '')

    base_coletas_qs = ItemColeta.objects.select_related(
        'pedido_liberado__fornecedor_usuario', 'motorista', 'agendado_por', 'conferido_por'
    ).prefetch_related('detalhes')

    if filtro_fornecedor_id:
        base_coletas_qs = base_coletas_qs.filter(pedido_liberado__fornecedor_usuario__id=filtro_fornecedor_id)
    if filtro_data_disp:
        base_coletas_qs = base_coletas_qs.filter(data_agendada=filtro_data_disp)
    if filtro_status:
        base_coletas_qs = base_coletas_qs.filter(status_coleta=filtro_status)
    if filtro_municipio:
        codigos_fornecedores_municipio = SA2Fornecedor.objects.filter(a2_mun=filtro_municipio).values_list('a2_cod', flat=True)
        fornecedor_usuario_ids = FornecedorUsuario.objects.filter(codigo_externo__in=codigos_fornecedores_municipio).values_list('id', flat=True)
        nomes_fornecedores_avulsos_municipio = FornecedorAvulso.objects.filter(municipio=filtro_municipio).values_list('nome', flat=True)
        base_coletas_qs = base_coletas_qs.filter(
            Q(pedido_liberado__fornecedor_usuario_id__in=fornecedor_usuario_ids) |
            Q(fornecedor_avulso__in=nomes_fornecedores_avulsos_municipio)
        )

    todas_as_coletas = list(base_coletas_qs)
    
    codigos_fornecedores_necessarios = {
        c.pedido_liberado.fornecedor_usuario.codigo_externo.strip()
        for c in todas_as_coletas if c.pedido_liberado and c.pedido_liberado.fornecedor_usuario.codigo_externo
    }
    mapa_fornecedores_erp = {f.a2_cod.strip(): f for f in SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores_necessarios)}

    recnos_itens_necessarios = {det.item_erp_recno for col in todas_as_coletas for det in col.detalhes.all()}
    mapa_itens_erp = {item.recno: item for item in SC7PedidoItem.objects.filter(recno__in=recnos_itens_necessarios)}

    for coleta in todas_as_coletas:
        coleta.display_nome_fornecedor = "N/A"
        coleta.display_municipio = "N/A"
        
        if coleta.pedido_liberado and coleta.pedido_liberado.fornecedor_usuario:
            coleta.display_nome_fornecedor = coleta.pedido_liberado.fornecedor_usuario.nome_fornecedor
            if coleta.pedido_liberado.fornecedor_usuario.codigo_externo:
                codigo = coleta.pedido_liberado.fornecedor_usuario.codigo_externo.strip()
                fornecedor_erp = mapa_fornecedores_erp.get(codigo)
                if fornecedor_erp:
                    coleta.display_municipio = fornecedor_erp.a2_mun
        
        elif coleta.fornecedor_avulso:
            coleta.display_nome_fornecedor = coleta.fornecedor_avulso
            try:
                local = FornecedorAvulso.objects.get(nome=coleta.fornecedor_avulso)
                coleta.display_municipio = local.municipio
            except FornecedorAvulso.DoesNotExist:
                pass
        
        for detalhe in coleta.detalhes.all():
            detalhe.item_erp = mapa_itens_erp.get(detalhe.item_erp_recno)

    coletas_por_dia = defaultdict(list)
    coletas_por_semana = defaultdict(list)
    coletas_por_mes = defaultdict(list)
    
    today = date.today()

    for coleta in sorted(todas_as_coletas, key=lambda c: (c.data_agendada is not None, -c.data_agendada.toordinal() if c.data_agendada else 0, c.ordem_visita)):
        if coleta.data_agendada:
            if coleta.data_agendada == today:
                coletas_por_dia['Hoje'].append(coleta)
            else:
                coletas_por_dia[coleta.data_agendada].append(coleta)

            year, week_num, _ = coleta.data_agendada.isocalendar()
            start_of_week = date.fromisocalendar(year, week_num, 1)
            end_of_week = start_of_week + timedelta(days=6)
            week_key = f"Semana {week_num} ({start_of_week.strftime('%d/%m')} - {end_of_week.strftime('%d/%m')})"
            coletas_por_semana[week_key].append(coleta)

            month_key = coleta.data_agendada.strftime('%B de %Y').capitalize()
            coletas_por_mes[month_key].append(coleta)
        else:
            coletas_por_dia['Sem Data'].append(coleta)


    fornecedores_para_filtro = FornecedorUsuario.objects.filter(pedidoliberado__coletas__isnull=False).distinct().order_by('nome_fornecedor')
    motoristas = Motorista.objects.filter(ativo=True).order_by('nome')
    municipios_erp = SA2Fornecedor.objects.values_list('a2_mun', flat=True).distinct()
    municipios_avulsos = FornecedorAvulso.objects.values_list('municipio', flat=True).distinct()
    todos_municipios = sorted(list(set([m.strip() for m in municipios_erp if m] + [m.strip() for m in municipios_avulsos if m])))

    context = {
        'coletas_por_dia': dict(coletas_por_dia),
        'coletas_por_semana': dict(coletas_por_semana),
        'coletas_por_mes': dict(coletas_por_mes),
        'fornecedores': fornecedores_para_filtro,
        'status_choices': ItemColeta.STATUS_COLETA_CHOICES,
        'prioridade_choices': ItemColeta.PRIORIDADE_CHOICES,
        'municipios': todos_municipios,
        'motoristas': motoristas,
        'filtros': {
            'fornecedor': filtro_fornecedor_id,
            'data_disponibilidade': filtro_data_disp, 
            'status': filtro_status,
            'municipio': filtro_municipio,
        }
    }
    return render(request, 'portal/coleta_dashboard.html', context)

@staff_member_required
def coleta_conferencia_view(request, coleta_id):
    coleta = get_object_or_404(ItemColeta, id=coleta_id)
    detalhes_coleta = coleta.detalhes.all()

    # --- INÍCIO DA CORREÇÃO ---
    # Adicione este bloco para carregar as informações dos produtos
    recnos_itens = [det.item_erp_recno for det in detalhes_coleta]
    itens_erp_map = {
        item.recno: item for item in SC7PedidoItem.objects.filter(recno__in=recnos_itens)
    }

    for detalhe in detalhes_coleta:
        detalhe.item_erp = itens_erp_map.get(detalhe.item_erp_recno)
    # --- FIM DA CORREÇÃO ---

    if request.method == 'POST':
        houve_divergencia = False
        detalhes_para_atualizar = []
        for detalhe in detalhes_coleta:
            qtd_coletada_str = request.POST.get(f'qtd_coletada_{detalhe.id}')
            motivo_divergencia = request.POST.get(f'motivo_divergencia_{detalhe.id}')
            obs_divergencia = request.POST.get(f'obs_divergencia_{detalhe.id}')

            try:
                qtd_coletada = Decimal(qtd_coletada_str.replace(',', '.')) if qtd_coletada_str else detalhe.quantidade_disponivel
                detalhe.quantidade_coletada = qtd_coletada
                detalhe.motivo_divergencia = motivo_divergencia
                detalhe.observacao_divergencia = obs_divergencia
                detalhes_para_atualizar.append(detalhe)
                if qtd_coletada != detalhe.quantidade_disponivel:
                    houve_divergencia = True
            except (ValueError, TypeError):
                messages.error(request, f"Valor inválido para quantidade do item {detalhe.item_erp.c7_produto}.")
                continue
        
        ItemColetaDetalhe.objects.bulk_update(detalhes_para_atualizar, ['quantidade_coletada', 'motivo_divergencia', 'observacao_divergencia'])

        if houve_divergencia:
            coleta.status_coleta = 'REALIZADA_DIVERGENCIA'
            messages.warning(request, "Coleta confirmada com divergências.")
        else:
            coleta.status_coleta = 'REALIZADA_OK'
            messages.success(request, "Coleta confirmada com sucesso.")
        
        coleta.conferido_por = request.user
        coleta.save()
        
        pedido_principal = coleta.pedido_liberado
        if pedido_principal:
            todas_as_coletas_do_pedido = pedido_principal.coletas.all()
            todas_conferidas = all(c.status_coleta.startswith('REALIZADA') for c in todas_as_coletas_do_pedido)

            if todas_conferidas:
                pedido_principal.status = 'COLETADO'
                pedido_principal.save()
                messages.info(request, f"Todas as coletas do Pedido Nº {pedido_principal.numero_pedido} foram concluídas.")
        
        return redirect('portal:coleta_dashboard')

    context = {
        'coleta': coleta,
        'detalhes_coleta': detalhes_coleta,
        'motivos_divergencia': ItemColetaDetalhe.MOTIVOS_DIVERGENCIA_CHOICES,
    }
    return render(request, 'portal/coleta_conferencia.html', context)

@staff_member_required
def adicionar_coleta_avulsa_view(request):
    if request.method == 'POST':
        fornecedor_nome = request.POST.get('fornecedor_avulso')
        descricao = request.POST.get('descricao_avulsa')
        data_agendada = request.POST.get('data_agendada')
        volumes = request.POST.get('volumes')
        peso = request.POST.get('peso_kg')
        obs = request.POST.get('observacao_coleta')

        if not fornecedor_nome or not data_agendada:
            messages.error(request, "O nome do Fornecedor e a Data Agendada são obrigatórios.")
        else:
            if not SA2Fornecedor.objects.filter(a2_nome=fornecedor_nome).exists() and \
               not FornecedorUsuario.objects.filter(nome_fornecedor=fornecedor_nome).exists():
                FornecedorAvulso.objects.get_or_create(nome=fornecedor_nome)

            ItemColeta.objects.create(
                fornecedor_avulso=fornecedor_nome,
                descricao_avulsa=descricao,
                data_disponibilidade=data_agendada,
                data_agendada=data_agendada,
                volumes=volumes if volumes else None,
                peso_kg=peso if peso else None,
                observacao_coleta=obs,
                status_coleta='AGENDADA',
                agendado_por=request.user
            )
            messages.success(request, f"Coleta avulsa para '{fornecedor_nome}' agendada com sucesso.")
            return redirect('portal:coleta_dashboard')

    fornecedores_erp = list(SA2Fornecedor.objects.values_list('a2_nome', flat=True))
    fornecedores_portal = list(FornecedorUsuario.objects.values_list('nome_fornecedor', flat=True))
    fornecedores_avulsos_gerenciados = list(FornecedorAvulso.objects.values_list('nome', flat=True))

    sugestoes_fornecedores = sorted(list(set(
        fornecedores_erp + fornecedores_portal + fornecedores_avulsos_gerenciados
    )))

    context = {
        'sugestoes_fornecedores': sugestoes_fornecedores
    }
    return render(request, 'portal/adicionar_coleta_avulsa.html', context)

@staff_member_required
def coleta_avulsa_conferencia_view(request, coleta_id):
    coleta = get_object_or_404(ItemColeta, id=coleta_id, pedido_liberado__isnull=True)

    if request.method == 'POST':
        coleta.fornecedor_avulso = request.POST.get('fornecedor_avulso')
        coleta.descricao_avulsa = request.POST.get('descricao_avulsa')
        coleta.data_agendada = request.POST.get('data_agendada')
        coleta.volumes = request.POST.get('volumes') or None
        coleta.peso_kg = request.POST.get('peso_kg') or None
        coleta.observacao_coleta = request.POST.get('observacao_coleta')

        coleta.status_coleta = 'REALIZADA_OK'
        coleta.conferido_por = request.user
        
        coleta.save()
        
        messages.success(request, f"Coleta avulsa para '{coleta.fornecedor_avulso}' foi confirmada com sucesso.")
        return redirect('portal:coleta_dashboard')

    context = {
        'coleta': coleta
    }
    return render(request, 'portal/coleta_avulsa_conferencia.html', context)

@staff_member_required
def relatorios_view(request):
    # Busca dados para popular os filtros
    motoristas = Motorista.objects.filter(ativo=True).order_by('nome')
    fornecedores = FornecedorUsuario.objects.all().order_by('nome_fornecedor')

    # Lógica para obter todos os municípios únicos
    municipios_erp = SA2Fornecedor.objects.values_list('a2_mun', flat=True).distinct()
    municipios_avulsos = FornecedorAvulso.objects.values_list('municipio', flat=True).distinct()
    todos_municipios = sorted(list(set(
        [m.strip() for m in municipios_erp if m] +
        [m.strip() for m in municipios_avulsos if m]
    )))

    context = {
        'motoristas': motoristas,
        'fornecedores': fornecedores,
        'municipios': todos_municipios,
    }

    # Mantém a lógica para redirecionar para a view correta do relatório
    if 'tipo_relatorio' in request.GET:
        tipo = request.GET.get('tipo_relatorio')
        params = request.GET.urlencode()
        if tipo == 'romaneio_coleta':
            return redirect(f"{reverse('portal:gerar_romaneio')}?{params}")
        elif tipo == 'divergencias':
            return redirect(f"{reverse('portal:gerar_divergencias')}?{params}")
        elif tipo == 'desempenho':
            return redirect(f"{reverse('portal:gerar_desempenho')}?{params}")
        # LINHA CORRIGIDA/ADICIONADA:
        elif tipo == 'pendencias_embarque':
            return redirect(f"{reverse('portal:gerar_pendencias_embarque')}?{params}")
        else:
            messages.error(request, "Tipo de relatório inválido.")
    
    return render(request, 'portal/relatorios.html', context)


@staff_member_required
def gerar_romaneio_view(request):
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    motorista_id = request.GET.get('motorista')
    fornecedor_id = request.GET.get('fornecedor')
    municipio = request.GET.get('municipio')

    if not data_inicio_str or not data_fim_str:
        messages.error(request, "As datas de início e fim são obrigatórias.")
        return redirect('portal:relatorios')

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    coletas_agendadas = ItemColeta.objects.filter(
        status_coleta='AGENDADA',
        data_agendada__range=[data_inicio, data_fim]
    ).prefetch_related(
        'detalhes'
    ).select_related('pedido_liberado__fornecedor_usuario', 'motorista').order_by('ordem_visita', '-prioridade')

    if motorista_id:
        coletas_agendadas = coletas_agendadas.filter(motorista_id=motorista_id)
    
    if fornecedor_id:
        fornecedor = FornecedorUsuario.objects.get(id=fornecedor_id)
        coletas_agendadas = coletas_agendadas.filter(
            Q(pedido_liberado__fornecedor_usuario_id=fornecedor_id) | 
            Q(fornecedor_avulso=fornecedor.nome_fornecedor)
        )

    if municipio:
        codigos_fornecedores_erp = list(SA2Fornecedor.objects.filter(a2_mun=municipio).values_list('a2_cod', flat=True))
        fornecedor_usuario_ids = list(FornecedorUsuario.objects.filter(codigo_externo__in=codigos_fornecedores_erp).values_list('id', flat=True))
        nomes_fornecedores_avulsos = list(FornecedorAvulso.objects.filter(municipio=municipio).values_list('nome', flat=True))

        coletas_agendadas = coletas_agendadas.filter(
            Q(pedido_liberado__fornecedor_usuario_id__in=fornecedor_usuario_ids) |
            Q(fornecedor_avulso__in=nomes_fornecedores_avulsos)
        )

    coletas_por_fornecedor = {}

    recnos_necessarios = {det.item_erp_recno for coleta in coletas_agendadas for det in coleta.detalhes.all()}
    mapa_itens_erp = {item.recno: item for item in SC7PedidoItem.objects.filter(recno__in=recnos_necessarios)}

    filiais_necessarias = {
        coleta.pedido_liberado.numero_pedido.split('-')[1].strip()
        for coleta in coletas_agendadas if coleta.pedido_liberado and '-' in coleta.pedido_liberado.numero_pedido
    }
    mapa_empresas = {
        empresa.m0_codfil.strip(): empresa 
        for empresa in SYSCompany.objects.filter(m0_codfil__in=filiais_necessarias)
    }


    for coleta in coletas_agendadas:
        for detalhe in coleta.detalhes.all():
            detalhe.item_erp_info = mapa_itens_erp.get(detalhe.item_erp_recno)

        fornecedor_info = { 'nome': 'N/A', 'endereco': 'N/A', 'municipio': 'N/A', 'telefone': 'N/A' }
        fornecedor_key = None
        empresa_faturamento = None

        if coleta.pedido_liberado:
            fornecedor_portal = coleta.pedido_liberado.fornecedor_usuario
            fornecedor_key = f"portal_{fornecedor_portal.id}"
            try:
                fornecedor_erp = SA2Fornecedor.objects.filter(a2_cod=fornecedor_portal.codigo_externo.strip()).first()
                if fornecedor_erp:
                    fornecedor_info['nome'] = fornecedor_erp.a2_nome
                    fornecedor_info['endereco'] = fornecedor_erp.a2_end
                    fornecedor_info['municipio'] = fornecedor_erp.a2_mun
                    fornecedor_info['telefone'] = fornecedor_erp.a2_tel
                
                if '-' in coleta.pedido_liberado.numero_pedido:
                    filial_pedido = coleta.pedido_liberado.numero_pedido.split('-')[1]
                    empresa_faturamento = mapa_empresas.get(filial_pedido.strip())

            except SA2Fornecedor.DoesNotExist:
                fornecedor_info['nome'] = fornecedor_portal.nome_fornecedor
        else:
            fornecedor_key = f"avulso_{coleta.fornecedor_avulso}"
            fornecedor_info['nome'] = coleta.fornecedor_avulso
            try:
                local_avulso = FornecedorAvulso.objects.get(nome=coleta.fornecedor_avulso)
                fornecedor_info['endereco'] = local_avulso.endereco or "Verificar observações"
                fornecedor_info['municipio'] = local_avulso.municipio or ""
                fornecedor_info['telefone'] = local_avulso.telefone or ""
            except FornecedorAvulso.DoesNotExist:
                fornecedor_info['endereco'] = "Verificar observações"

        if fornecedor_key not in coletas_por_fornecedor:
            coletas_por_fornecedor[fornecedor_key] = {
                'fornecedor': fornecedor_info,
                'coletas': [],
                'empresa_faturamento': empresa_faturamento
            }

        coletas_por_fornecedor[fornecedor_key]['coletas'].append(coleta)

    coletas_ordenadas_final = sorted(
        coletas_por_fornecedor.values(), 
        key=lambda item: item['coletas'][0].ordem_visita
    )
    
    context = {
        'coletas_por_fornecedor': coletas_ordenadas_final,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }

    return render(request, 'portal/romaneio_coleta.html', context)


@staff_member_required
def gerar_divergencias_view(request):
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    motorista_id = request.GET.get('motorista')
    fornecedor_id = request.GET.get('fornecedor')
    municipio = request.GET.get('municipio')

    if not data_inicio_str or not data_fim_str:
        messages.error(request, "As datas de início e fim são obrigatórias.")
        return redirect('portal:relatorios')

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    detalhes_com_divergencia = ItemColetaDetalhe.objects.filter(
        item_coleta__status_coleta='REALIZADA_DIVERGENCIA',
        item_coleta__data_agendada__range=[data_inicio, data_fim],
        quantidade_coletada__isnull=False
    ).exclude(
        quantidade_coletada=models.F('quantidade_disponivel')
    ).select_related(
        'item_coleta__pedido_liberado__fornecedor_usuario', 
        'item_coleta__conferido_por',
        'item_coleta__motorista'
    ).order_by('item_coleta__data_agendada')
    
    if motorista_id:
        detalhes_com_divergencia = detalhes_com_divergencia.filter(item_coleta__motorista_id=motorista_id)
    
    if fornecedor_id:
        detalhes_com_divergencia = detalhes_com_divergencia.filter(item_coleta__pedido_liberado__fornecedor_usuario_id=fornecedor_id)

    if municipio:
        codigos_fornecedores_erp = list(SA2Fornecedor.objects.filter(a2_mun=municipio).values_list('a2_cod', flat=True))
        fornecedor_usuario_ids = list(FornecedorUsuario.objects.filter(codigo_externo__in=codigos_fornecedores_erp).values_list('id', flat=True))
        
        detalhes_com_divergencia = detalhes_com_divergencia.filter(
            item_coleta__pedido_liberado__fornecedor_usuario_id__in=fornecedor_usuario_ids
        )

    for detalhe in detalhes_com_divergencia:
        diferenca_valor = detalhe.quantidade_disponivel - detalhe.quantidade_coletada
        detalhe.diferenca = diferenca_valor
        detalhe.diferenca_abs = abs(diferenca_valor)

    context = {
        'detalhes': detalhes_com_divergencia,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    return render(request, 'portal/relatorio_divergencias.html', context)

@staff_member_required
def gerar_desempenho_view(request):
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    fornecedor_id = request.GET.get('fornecedor')
    municipio = request.GET.get('municipio')

    if not data_inicio_str or not data_fim_str:
        messages.error(request, "As datas de início e fim são obrigatórias.")
        return redirect('portal:relatorios')

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    pedidos_finalizados = PedidoLiberado.objects.filter(
        coletas__status_coleta__startswith='REALIZADA',
        coletas__data_agendada__range=[data_inicio, data_fim]
    ).distinct().prefetch_related('coletas', 'fornecedor_usuario')

    if fornecedor_id:
        pedidos_finalizados = pedidos_finalizados.filter(fornecedor_usuario_id=fornecedor_id)
        
    if municipio:
        codigos_fornecedores_erp = list(SA2Fornecedor.objects.filter(a2_mun=municipio).values_list('a2_cod', flat=True))
        pedidos_finalizados = pedidos_finalizados.filter(fornecedor_usuario__codigo_externo__in=codigos_fornecedores_erp)

    desempenho_final = []
    fornecedores_processados = set()

    for pedido in pedidos_finalizados:
        fornecedor = pedido.fornecedor_usuario
        if fornecedor.id in fornecedores_processados:
            continue
        
        fornecedores_processados.add(fornecedor.id)

        pedidos_do_fornecedor_no_periodo = [
            p for p in pedidos_finalizados if p.fornecedor_usuario_id == fornecedor.id
        ]
        
        total_pedidos = len(pedidos_do_fornecedor_no_periodo)
        coletas_com_divergencia = 0
        volume_total = 0
        peso_total = 0
        soma_dias_preparo = 0
        coletas_contadas_para_media = 0

        for p in pedidos_do_fornecedor_no_periodo:
            for coleta in p.coletas.all():
                if data_inicio <= coleta.data_agendada <= data_fim and coleta.status_coleta.startswith('REALIZADA'):
                    if coleta.status_coleta == 'REALIZADA_DIVERGENCIA':
                        coletas_com_divergencia += 1
                    
                    volume_total += coleta.volumes or 0
                    peso_total += coleta.peso_kg or 0

                    tempo_preparo = (coleta.data_disponibilidade - p.data_liberacao_portal.date()).days
                    if tempo_preparo >= 0:
                        soma_dias_preparo += tempo_preparo
                        coletas_contadas_para_media += 1

        tempo_medio = soma_dias_preparo / coletas_contadas_para_media if coletas_contadas_para_media > 0 else 0

        desempenho_final.append({
            'nome_fornecedor': fornecedor.nome_fornecedor,
            'total_pedidos_coletados': total_pedidos,
            'coletas_com_divergencia': coletas_com_divergencia,
            'tempo_medio_preparo_dias': round(tempo_medio),
            'volume_total': volume_total,
            'peso_total': peso_total,
        })

    context = {
        'desempenho_fornecedores': sorted(desempenho_final, key=lambda f: f['nome_fornecedor']),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    return render(request, 'portal/relatorio_desempenho_py.html', context)


@staff_member_required
def gerar_pendencias_embarque_view(request):
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    fornecedor_id = request.GET.get('fornecedor')
    municipio = request.GET.get('municipio')

    coletas_pendentes = ItemColeta.objects.filter(
        status_coleta='PENDENTE'
    ).select_related('pedido_liberado__fornecedor_usuario').order_by('data_disponibilidade')

    if data_inicio_str and data_fim_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        coletas_pendentes = coletas_pendentes.filter(data_disponibilidade__range=[data_inicio, data_fim])
    
    if fornecedor_id:
        coletas_pendentes = coletas_pendentes.filter(
            Q(pedido_liberado__fornecedor_usuario_id=fornecedor_id) | 
            Q(fornecedor_avulso=FornecedorUsuario.objects.get(id=fornecedor_id).nome_fornecedor)
        )

    if municipio:
        codigos_fornecedores_erp = list(SA2Fornecedor.objects.filter(a2_mun=municipio).values_list('a2_cod', flat=True))
        fornecedor_usuario_ids = list(FornecedorUsuario.objects.filter(codigo_externo__in=codigos_fornecedores_erp).values_list('id', flat=True))
        nomes_fornecedores_avulsos = list(FornecedorAvulso.objects.filter(municipio=municipio).values_list('nome', flat=True))

        coletas_pendentes = coletas_pendentes.filter(
            Q(pedido_liberado__fornecedor_usuario_id__in=fornecedor_usuario_ids) |
            Q(fornecedor_avulso__in=nomes_fornecedores_avulsos)
        )

    context = {
        'coletas_pendentes': coletas_pendentes,
        'data_inicio': data_inicio_str,
        'data_fim': data_fim_str,
    }
    return render(request, 'portal/relatorio_pendencias_embarque.html', context)

@staff_member_required
def gerenciar_locais_avulsos_view(request):
    locais = FornecedorAvulso.objects.all()
    context = {
        'locais_avulsos': locais
    }
    return render(request, 'portal/gerenciar_locais_avulsos.html', context)

@staff_member_required
def adicionar_local_avulso_view(request):
    if request.method == 'POST':
        form = FornecedorAvulsoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Novo local de coleta salvo com sucesso.")
            return redirect('portal:gerenciar_locais')
    else:
        form = FornecedorAvulsoForm()
    
    return render(request, 'portal/local_avulso_form.html', {'form': form})

@staff_member_required
def editar_local_avulso_view(request, local_id):
    local = get_object_or_404(FornecedorAvulso, id=local_id)
    if request.method == 'POST':
        form = FornecedorAvulsoForm(request.POST, instance=local)
        if form.is_valid():
            form.save()
            messages.success(request, f"Os dados de '{local.nome}' foram atualizados.")
            return redirect('portal:gerenciar_locais')
    else:
        form = FornecedorAvulsoForm(instance=local)

    return render(request, 'portal/local_avulso_form.html', {'form': form})

@staff_member_required
def excluir_local_avulso_view(request, local_id):
    local = get_object_or_404(FornecedorAvulso, id=local_id)
    if request.method == 'POST':
        nome_local = local.nome
        local.delete()
        messages.warning(request, f"O local '{nome_local}' foi excluído.")
    return redirect('portal:gerenciar_locais')

@staff_member_required
def analise_cotacao_view(request):
    sc_buscada = request.GET.get('sc_num', None)
    filial_buscada = request.GET.get('filial', None)
    produtos_analisados = []
    
    filiais = SC8CotacaoItem.objects.values_list('c8_filial', flat=True).distinct().order_by('c8_filial')

    if sc_buscada:
        cotacoes_qs = SC8CotacaoItem.objects.filter(c8_numsc=sc_buscada)
        if filial_buscada:
            cotacoes_qs = cotacoes_qs.filter(c8_filial=filial_buscada)

        cotacoes = cotacoes_qs.order_by('c8_produto', 'c8_preco')
        
        codigos_fornecedores = cotacoes.values_list('c8_fornece', flat=True).distinct()
        fornecedores_map = {
            f.a2_cod.strip(): f.a2_nome for f in SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores)
        }
        
        codigos_condicoes = cotacoes.values_list('c8_cond', flat=True).distinct()
        condicoes_map = {
            c.e4_codigo.strip(): c.e4_descri for c in SE4.objects.filter(e4_codigo__in=codigos_condicoes)
        }

        produtos_agrupados = defaultdict(list)
        for cot in cotacoes:
            if cot.c8_preco > 0:
                produtos_agrupados[(cot.c8_filial, cot.c8_produto)].append(cot)

        codigos_produtos = list(set([p[1] for p in produtos_agrupados.keys()]))
        descricoes_map = {
            item.c7_produto: item.c7_descri
            for item in SC7PedidoItem.objects.filter(c7_produto__in=codigos_produtos)
        }
        
        ultimo_precos_map = {}
        for produto_cod in codigos_produtos:
            ultimo_preco = SD1NFItem.objects.filter(
                d1_cod=produto_cod
            ).order_by(
                F('d1_emissao').desc()
            ).values('d1_vunit').first()
            if ultimo_preco:
                ultimo_precos_map[produto_cod] = ultimo_preco['d1_vunit']
            else:
                ultimo_precos_map[produto_cod] = None

        for produto_key, cotacoes_do_produto in produtos_agrupados.items():
            filial_item, produto_cod = produto_key
            
            precos_validos = [c.c8_preco for c in cotacoes_do_produto if c.c8_preco > 0]
            menor_preco = min(precos_validos) if precos_validos else None

            produto_info = {
                'filial': filial_item,
                'codigo': produto_cod,
                'descricao': descricoes_map.get(produto_cod, "Descrição não encontrada"),
                'quantidade': cotacoes_do_produto[0].c8_quant,
                'um': cotacoes_do_produto[0].c8_um,
                'ultimo_preco': ultimo_precos_map.get(produto_cod),
                'cotacoes': []
            }

            for cot in cotacoes_do_produto:
                is_best = (menor_preco is not None) and (cot.c8_preco == menor_preco)
                produto_info['cotacoes'].append({
                    'fornecedor_nome': fornecedores_map.get(cot.c8_fornece.strip(), cot.c8_fornece),
                    'preco': cot.c8_preco,
                    'total': cot.c8_total,
                    'cond_pgto': condicoes_map.get(cot.c8_cond.strip(), cot.c8_cond),
                    'data_entrega': cot.data_entrega_formatada,
                    'frete': cot.c8_valfre,
                    'tipo_frete': cot.c8_tpfrete,
                    'ipi': cot.c8_valipi,
                    'icms': cot.c8_valicm,
                    'desconto': cot.c8_vldesc,
                    'is_best_price': is_best
                })
            
            produtos_analisados.append(produto_info)
    
    context = {
        'sc_buscada': sc_buscada,
        'filial_buscada': filial_buscada,
        'filiais': filiais,
        'produtos_analisados': produtos_analisados,
    }
    return render(request, 'portal/analise_cotacao.html', context)


@staff_member_required
def cotacoes_por_condicao_view(request):
    sc_buscada = request.GET.get('sc_num', None)
    filial_buscada = request.GET.get('filial', None)
    cotacoes_agrupadas = []

    filiais = SC8CotacaoItem.objects.values_list('c8_filial', flat=True).distinct().order_by('c8_filial')

    if sc_buscada:
        cotacoes_qs = SC8CotacaoItem.objects.filter(
            c8_numsc=sc_buscada, c8_preco__gt=0
        )
        if filial_buscada:
            cotacoes_qs = cotacoes_qs.filter(c8_filial=filial_buscada)

        cotacoes = cotacoes_qs.order_by('c8_produto', 'c8_cond', 'c8_preco')
        
        codigos_fornecedores = cotacoes.values_list('c8_fornece', flat=True).distinct()
        fornecedores_map = {
            f.a2_cod.strip(): f.a2_nome for f in SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores)
        }
        
        codigos_produtos = cotacoes.values_list('c8_produto', flat=True).distinct()
        descricoes_map = {
            item.c7_produto: item.c7_descri
            for item in SC7PedidoItem.objects.filter(c7_produto__in=codigos_produtos)
        }
        
        produtos_por_condicao = defaultdict(lambda: defaultdict(list))
        for cot in cotacoes:
            produtos_por_condicao[(cot.c8_filial, cot.c8_produto)][cot.c8_cond].append(cot)

        for produto_key, condicoes in produtos_por_condicao.items():
            filial_item, produto_cod = produto_key
            produto_info = {
                'filial': filial_item,
                'codigo': produto_cod,
                'descricao': descricoes_map.get(produto_cod, "Descrição não encontrada"),
                'condicoes': []
            }
            for cond_pgto, lista_cotacoes in condicoes.items():
                menor_preco = min(c.c8_preco for c in lista_cotacoes)
                cotacoes_formatadas = []
                for cot in lista_cotacoes:
                    cotacoes_formatadas.append({
                        'fornecedor_nome': fornecedores_map.get(cot.c8_fornece.strip(), cot.c8_fornece),
                        'preco': cot.c8_preco,
                        'is_best_price': cot.c8_preco == menor_preco,
                    })
                produto_info['condicoes'].append({
                    'condicao': cond_pgto,
                    'cotacoes': cotacoes_formatadas,
                })
            cotacoes_agrupadas.append(produto_info)
    
    context = {
        'sc_buscada': sc_buscada,
        'filial_buscada': filial_buscada,
        'filiais': filiais,
        'cotacoes_agrupadas': cotacoes_agrupadas,
    }

@require_POST
@staff_member_required
def atualizar_ordem_coleta(request):
    try:
        data = json.loads(request.body)
        coleta_ids_ordenados = data.get('ordem', [])
        
        with models.transaction.atomic():
            for index, coleta_id in enumerate(coleta_ids_ordenados):
                ItemColeta.objects.filter(id=coleta_id).update(ordem_visita=index)
        
        return JsonResponse({'status': 'success', 'message': 'Ordem das coletas atualizada.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    

    return render(request, 'portal/relatorio_cotacoes_condicao.html', context)

@staff_member_required
def rota_mapa_view(request, rota_id):
    rota = get_object_or_404(Rota.objects.prefetch_related('pontos_gps', 'eventos_coleta__item_coleta__pedido_liberado__fornecedor_usuario'), id=rota_id)

    # --- CORREÇÃO APLICADA AQUI ---
    # Convertemos os Decimals para floats para garantir o ponto decimal.
    pontos_gps = [
        {
            "latitude": float(p.latitude),
            "longitude": float(p.longitude),
            "timestamp": p.timestamp
        }
        for p in rota.pontos_gps.all()
    ]

    eventos = []
    # Só processa eventos se houver pontos de GPS para lhes dar uma localização
    if pontos_gps:
        # Usamos um loop para construir os dados dos eventos de forma segura
        for evento in rota.eventos_coleta.all():
            fornecedor_nome = "Coleta Avulsa" # Valor padrão
            if evento.item_coleta.pedido_liberado:
                fornecedor_nome = evento.item_coleta.pedido_liberado.fornecedor_usuario.nome_fornecedor
            elif evento.item_coleta.fornecedor_avulso:
                fornecedor_nome = evento.item_coleta.fornecedor_avulso
            
            # Encontra o ponto de GPS mais próximo do evento no tempo
            ponto_mais_proximo = min(
                pontos_gps,
                key=lambda ponto: abs(ponto['timestamp'] - evento.timestamp)
            )

            eventos.append({
                "fornecedor_nome": fornecedor_nome,
                "evento": evento.evento,
                "timestamp": evento.timestamp,
                "latitude": float(ponto_mais_proximo['latitude']),
                "longitude": float(ponto_mais_proximo['longitude'])
            })

    context = {
        'rota': rota,
        'pontos_gps_json': json.dumps(pontos_gps, default=str),
        'eventos_json': json.dumps(eventos, default=str)
    }
    return render(request, 'portal/rota_mapa.html', context)

@staff_member_required
def acompanhamento_rotas_view(request):
    # Busca todas as rotas para a data de hoje
    hoje = date.today()
    rotas_do_dia = Rota.objects.filter(data=hoje).select_related('motorista').order_by('-hora_inicio')

    context = {
        'rotas': rotas_do_dia,
        'active_menu': 'acompanhamento' # Para destacar o menu
    }
    return render(request, 'portal/acompanhamento_rotas.html', context)
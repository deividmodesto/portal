# portal/utils.py

import base64
import os
from django.conf import settings
from django.template.loader import render_to_string
from .models import SC7PedidoItem, SYSCompany, SA2Fornecedor, SE4, SCR010Aprovacao, SYSUSR, SC1

def get_logo_base64():
    try:
        logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'img', 'logo_reunidas2.png')
        with open(logo_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"
    except (FileNotFoundError, IndexError):
        return None

def preparar_contexto_pdf(pedido_num, filial, fornecedor_erp=None):
    itens_pedido_erp = SC7PedidoItem.objects.filter(
        c7_num=pedido_num, c7_filial=filial
    ).exclude(d_e_l_e_t='*').order_by('c7_item')
    if not itens_pedido_erp.exists():
        return None # Retorna None se o pedido não for encontrado

    pedido_erp = itens_pedido_erp.first()
    
    empresa_emitente = SYSCompany.objects.filter(m0_codfil=pedido_erp.c7_filial.strip()).first()

    if not fornecedor_erp:
        fornecedor_cod = pedido_erp.c7_fornece.strip()
        fornecedor_erp = SA2Fornecedor.objects.filter(a2_cod=fornecedor_cod.strip()).first()
    
    try:
        condicao_pagamento = SE4.objects.get(e4_codigo=pedido_erp.c7_cond.strip())
        desc_cond_pagamento = condicao_pagamento.e4_descri
    except SE4.DoesNotExist:
        desc_cond_pagamento = pedido_erp.c7_cond or "Não especificada"

    aprovacoes_pedido = SCR010Aprovacao.objects.filter(cr_filial=filial, cr_num=pedido_num).order_by('cr_user')
    aprovador_ids = [aprovacao.cr_user.strip() for aprovacao in aprovacoes_pedido]
    aprovadores_map = {u.usr_id.strip(): u.usr_nome.strip() for u in SYSUSR.objects.filter(usr_id__in=aprovador_ids)}
    status_aprovacao_map = {
        '01': 'Aguardando', '02': 'Pendente', '03': 'Liberado', '04': 'Bloqueado',
        '05': 'Liberado por outro', '06': 'Rejeitado', '07': 'Rejeitado/Bloqueado'
    }
    aprovacoes_para_template = [{'aprovador': aprovadores_map.get(a.cr_user.strip(), "N/A"), 'status': status_aprovacao_map.get(a.cr_status.strip(), "N/A")} for a in aprovacoes_pedido]

    num_sc = pedido_erp.c7_numsc.strip()
    obs_sc, data_necessidade = "N/A", "N/A"
    solicitacao_compra = SC1.objects.filter(c1_filial=pedido_erp.c7_filial, c1_num=num_sc).first()
    if solicitacao_compra:
        obs_sc = solicitacao_compra.c1_obs
        if solicitacao_compra.c1_datprf and len(solicitacao_compra.c1_datprf) == 8:
            data_necessidade = f"{solicitacao_compra.c1_datprf[6:8]}/{solicitacao_compra.c1_datprf[4:6]}/{solicitacao_compra.c1_datprf[0:4]}"

    status_map = {'B': 'Bloqueado', 'L': 'Liberado', 'R': 'Reprovado'}
    status_pedido = status_map.get(pedido_erp.c7_conapro.strip(), 'Não Definido')

    total_produtos = sum(item.c7_total for item in itens_pedido_erp)
    total_ipi = sum(item.c7_ipi for item in itens_pedido_erp)
    total_frete = sum(item.c7_frete for item in itens_pedido_erp)
    total_desconto = sum(item.c7_vldesc for item in itens_pedido_erp)
    total_geral = (total_produtos + total_ipi + total_frete) - total_desconto

    return {
        'itens_pedido': itens_pedido_erp, 'info_geral': pedido_erp,
        'empresa_emitente': empresa_emitente, 'fornecedor': fornecedor_erp,
        'desc_cond_pagamento': desc_cond_pagamento, 'obs_solicitacao_compra': obs_sc,
        'data_necessidade': data_necessidade, 'status_pedido': status_pedido,
        'status_class': status_pedido.replace(' ', '-'), 'logo_base64': get_logo_base64(),
        'totais': {'produtos': total_produtos, 'ipi': total_ipi, 'frete': total_frete, 'desconto': total_desconto, 'geral': total_geral},
        'aprovacoes': aprovacoes_para_template,
    }
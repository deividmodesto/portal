# portal/tasks.py
from celery import shared_task
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML

from .models import FornecedorUsuario, PedidoLiberado, SA2Fornecedor
from .utils import preparar_contexto_pdf # IMPORTAÇÃO CORRIGIDA

@shared_task
def enviar_email_novo_acesso_task(fornecedor_id, senha_provisoria):
    """ Envia o e-mail de boas-vindas com a senha provisória. """
    try:
        fornecedor = FornecedorUsuario.objects.get(id=fornecedor_id)
        contexto_email = {
            'nome_fornecedor': fornecedor.nome_fornecedor,
            'cnpj': fornecedor.cnpj,
            'senha': senha_provisoria,
        }
        corpo_email = render_to_string('portal/email/novo_acesso.txt', contexto_email)
        send_mail(
            subject='Seu Acesso ao Portal de Coletas',
            message=corpo_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[fornecedor.email],
            fail_silently=False,
        )
    except FornecedorUsuario.DoesNotExist:
        print(f"Erro na task: Fornecedor com ID {fornecedor_id} não encontrado.")

@shared_task
def enviar_email_liberacao_pedido_task(fornecedor_id, pedido_id, pedido_num, filial):
    """ Gera o PDF e envia o e-mail de liberação de pedido. """
    try:
        fornecedor_portal = FornecedorUsuario.objects.get(id=fornecedor_id)
        fornecedor_erp = SA2Fornecedor.objects.filter(a2_cgc=fornecedor_portal.cnpj.strip()).first()
        
        contexto_pdf = preparar_contexto_pdf(pedido_num, filial, fornecedor_erp=fornecedor_erp)
        if not contexto_pdf:
            print(f"Não foi possível gerar o contexto do PDF para o pedido {pedido_num}-{filial}")
            return

        html_string = render_to_string('portal/pedido_compra_pdf.html', contexto_pdf)
        pdf_file = HTML(string=html_string).write_pdf()

        emails_to_send = [email for email in [fornecedor_portal.email] + list(fornecedor_portal.emails_adicionais.values_list('email', flat=True)) if email]

        if not emails_to_send:
            print(f"Nenhum e-mail válido para o fornecedor ID {fornecedor_id}")
            return

        corpo_email_texto = render_to_string('portal/email/pedido_liberado.txt', {
            'nome_fornecedor': fornecedor_portal.nome_fornecedor,
            'numero_pedido': pedido_num,
        })

        email = EmailMessage(
            subject=f'Pedido de Compra Nº {pedido_num} Liberado',
            body=corpo_email_texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails_to_send,
        )
        email.attach(f'Pedido_de_Compra_{pedido_num}.pdf', pdf_file, 'application/pdf')
        email.send(fail_silently=False)

    except Exception as e:
        print(f"Erro na task de envio de liberação para o pedido ID {pedido_id}: {e}")
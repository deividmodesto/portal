# api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from portal.models import Rota # Adicione a Rota aos imports
from .serializers import PontoGPSSerializer # Adicione o novo serializer
from datetime import date
from portal.models import EventoColeta
from django.utils import timezone

# Imports adicionados para a lógica de busca de dados
from portal.models import (
    ItemColeta, MotoristaToken, SA2Fornecedor, FornecedorAvulso,
    FornecedorUsuario
)
from .serializers import ItemColetaSerializer
from .authentication import MotoristaTokenAuthentication

class LoginMotoristaView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if user is not None and hasattr(user, 'motorista'):
            token, created = MotoristaToken.objects.get_or_create(user=user)
            return Response({"token": token.key, "nome_motorista": user.motorista.nome})

        return Response({"error": "Credenciais inválidas"}, status=400)


class ColetasMotoristaView(APIView):
    authentication_classes = [MotoristaTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        motorista = request.user.motorista
        coletas = ItemColeta.objects.filter(
            motorista=motorista, status_coleta='AGENDADA'
        ).select_related('pedido_liberado__fornecedor_usuario').order_by('ordem_visita')

        # --- LÓGICA DE BUSCA DE DADOS (A CORREÇÃO ESTÁ AQUI) ---
        # 1. Pega os códigos de fornecedores necessários das coletas
        codigos_fornecedores_necessarios = {
            c.pedido_liberado.fornecedor_usuario.codigo_externo.strip()
            for c in coletas if c.pedido_liberado and c.pedido_liberado.fornecedor_usuario.codigo_externo
        }
        # 2. Busca os fornecedores do ERP numa única consulta
        mapa_fornecedores_erp = {
            f.a2_cod.strip(): f for f in SA2Fornecedor.objects.filter(a2_cod__in=codigos_fornecedores_necessarios)
        }
        # 3. Pega os nomes dos locais avulsos
        nomes_avulsos = {c.fornecedor_avulso for c in coletas if c.fornecedor_avulso}
        mapa_locais_avulsos = {
            l.nome: l for l in FornecedorAvulso.objects.filter(nome__in=nomes_avulsos)
        }

        # 4. Anexa os nomes e municípios a cada coleta
        for coleta in coletas:
            if coleta.pedido_liberado and coleta.pedido_liberado.fornecedor_usuario:
                coleta.display_nome_fornecedor = coleta.pedido_liberado.fornecedor_usuario.nome_fornecedor
                codigo_erp = coleta.pedido_liberado.fornecedor_usuario.codigo_externo
                if codigo_erp:
                    fornecedor_erp = mapa_fornecedores_erp.get(codigo_erp.strip())
                    coleta.display_municipio = fornecedor_erp.a2_mun if fornecedor_erp else "N/A"
            elif coleta.fornecedor_avulso:
                coleta.display_nome_fornecedor = coleta.fornecedor_avulso
                local = mapa_locais_avulsos.get(coleta.fornecedor_avulso)
                coleta.display_municipio = local.municipio if local else "N/A"
            else:
                coleta.display_nome_fornecedor = "Indefinido"
                coleta.display_municipio = "N/A"
        # --- FIM DA CORREÇÃO ---

        serializer = ItemColetaSerializer(coletas, many=True)
        return Response(serializer.data)
    
class RotaView(APIView):
    authentication_classes = [MotoristaTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Cria uma nova rota ou obtém a existente para o dia de hoje.
        """
        motorista = request.user.motorista
        rota, created = Rota.objects.get_or_create(motorista=motorista, data=date.today())
        
        # --- LÓGICA ADICIONADA AQUI ---
        # Se a rota foi criada agora, define a hora de início.
        if created:
            rota.hora_inicio = timezone.now()
            rota.save()
        # --- FIM DA LÓGICA ---
        
        return Response({'rota_id': rota.id, 'created': created})


class PontoGPSView(APIView):
    authentication_classes = [MotoristaTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PontoGPSSerializer(data=request.data)
        if serializer.is_valid():
            rota = Rota.objects.get(id=serializer.validated_data['rota_id'])
            if rota.motorista != request.user.motorista:
                return Response(
                    {"error": "Não autorizado a adicionar pontos a esta rota."},
                    status=403
                )

            serializer.save()
            return Response({"status": "Ponto GPS recebido"}, status=201)

        # --- LINHA DE DEPURAÇÃO ADICIONADA ---
        print("Erro de validação do Serializer:", serializer.errors)

        return Response(serializer.errors, status=400)
    
class EventoColetaView(APIView):
    authentication_classes = [MotoristaTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        coleta_id = request.data.get('item_coleta')
        rota_id = request.data.get('rota')
        evento = request.data.get('evento') # Ex: 'INICIO_COLETA' ou 'FIM_COLETA'

        # Validação simples dos dados recebidos
        if not all([coleta_id, rota_id, evento]):
            return Response({"error": "Dados em falta."}, status=400)
        
        if evento not in ['INICIO_COLETA', 'FIM_COLETA']:
            return Response({"error": "Tipo de evento inválido."}, status=400)

        try:
            # Cria o registo do evento na base de dados
            EventoColeta.objects.create(
                item_coleta_id=coleta_id,
                rota_id=rota_id,
                evento=evento
            )
            return Response({"status": f"Evento '{evento}' registado com sucesso."}, status=201)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class FinalizarRotaView(APIView):
    authentication_classes = [MotoristaTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        rota_id = request.data.get('rota_id')
        if not rota_id:
            return Response({"error": "ID da Rota em falta."}, status=400)

        try:
            # Procura a rota e verifica se pertence ao motorista logado
            rota = Rota.objects.get(id=rota_id, motorista=request.user.motorista)

            # Define a hora de fim e salva
            rota.hora_fim = timezone.now()
            rota.save()

            return Response({"status": f"Rota {rota_id} finalizada com sucesso."})
        except Rota.DoesNotExist:
            return Response({"error": "Rota não encontrada ou não pertence a este motorista."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
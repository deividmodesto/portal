# api/urls.py

from django.urls import path
# Adicione as novas views ao import
from .views import LoginMotoristaView, ColetasMotoristaView, RotaView, PontoGPSView, EventoColetaView, FinalizarRotaView

urlpatterns = [
    path('login/', LoginMotoristaView.as_view(), name='api_login_motorista'),
    path('coletas/', ColetasMotoristaView.as_view(), name='api_coletas_motorista'),
    
    # --- NOVOS URLS ADICIONADOS ---
    path('rotas/iniciar/', RotaView.as_view(), name='api_iniciar_rota'),
    path('rotas/ponto-gps/', PontoGPSView.as_view(), name='api_ponto_gps'),
    path('coletas/evento/', EventoColetaView.as_view(), name='api_coleta_evento'),
    path('rotas/finalizar/', FinalizarRotaView.as_view(), name='api_finalizar_rota'),


]
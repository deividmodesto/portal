# api/serializers.py

from rest_framework import serializers
from portal.models import Motorista, ItemColeta, PontoGPS, Rota

class MotoristaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Motorista
        fields = ['id', 'nome']

class ItemColetaSerializer(serializers.ModelSerializer):
    # Vamos criar campos personalizados para mostrar nomes em vez de IDs
    fornecedor = serializers.SerializerMethodField()
    municipio = serializers.SerializerMethodField()
    
    class Meta:
        model = ItemColeta
        fields = [
            'id', 'fornecedor', 'municipio', 'data_agendada', 
            'volumes', 'peso_kg', 'status_coleta'
        ]

    def get_fornecedor(self, obj):
        return obj.display_nome_fornecedor

    def get_municipio(self, obj):
        return obj.display_municipio
    

class PontoGPSSerializer(serializers.ModelSerializer):
    # Digo ao serializer que a rota será apenas um número inteiro.
    rota_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = PontoGPS
        # Os campos que esperamos receber do aplicativo
        fields = ['rota_id', 'latitude', 'longitude']
        
    def create(self, validated_data):
        # Pega no rota_id e transforma-o no objeto Rota completo antes de salvar.
        rota = Rota.objects.get(id=validated_data.pop('rota_id'))
        ponto = PontoGPS.objects.create(rota=rota, **validated_data)
        return ponto
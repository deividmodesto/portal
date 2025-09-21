# api/authentication.py

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from portal.models import MotoristaToken

class MotoristaTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Procura pelo cabeçalho 'Authorization'
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Token '):
            return None  # Nenhuma tentativa de autenticação

        try:
            # Pega a chave (token) do cabeçalho
            token_key = auth_header.split(' ')[1]
            # Procura o nosso token personalizado na base de dados
            token = MotoristaToken.objects.select_related('user').get(key=token_key)
        except (MotoristaToken.DoesNotExist, IndexError):
            raise AuthenticationFailed('Token inválido.')

        # Se o token for válido, retorna o utilizador e o token
        # Isto fará com que o request.user fique disponível na nossa view
        return (token.user, token)
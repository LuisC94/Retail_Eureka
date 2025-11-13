from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect

def role_required(role_names):
    """
    Decorator que verifica se o utilizador logado pertence a UM dos grupos fornecidos.
    role_names deve ser uma lista ou tuplo (ex: ['Admin', 'Produtor']).
    """
    def check_user_role(user):
        if user.is_superuser:
            return True # Superuser passa sempre
        
        # Verifica se o utilizador está em algum dos grupos exigidos
        return user.groups.filter(name__in=role_names).exists()
    
    # Se o teste falhar, redireciona para a página principal (ou para uma página de acesso negado)
    return user_passes_test(check_user_role, login_url='/')
from django.urls import path
from . import views 
from . import api_views
from django.contrib.auth import views as auth_views
from .views import ProducerDashboardView # ProducerDataSubmitView removida

urlpatterns = [
    # 1. Rota Principal (REDIRECIONADOR INTELIGENTE)
    path('', views.AdminDashboardView.as_view(), name='admin_dashboard'), 
    
    # 2. Dashboards Principais
    path('producer/', views.ProducerDashboardView.as_view(), name='producer_dashboard'),
    
    # NOVAS ROTAS DE SUBMISSÃO
    path('submit-product/', views.producer_submit_product, name='producer_submit_product'),
    path('submit-plantation/', views.producer_submit_plantation, name='producer_submit_plantation'),
    path('submit-harvest/', views.producer_submit_harvest, name='producer_submit_harvest'),

    path('transporter/', views.TransporterDashboardView.as_view(), name='transporter_dashboard'),
    
    # 3. ROTAS DE DASHBOARD PARA OUTROS PERFIS
    path('consumer/', views.ConsumerDashboardView.as_view(), name='consumer_dashboard'),
    path('processor/', views.ProcessorDashboardView.as_view(), name='processor_dashboard'),
    path('retailer/', views.RetailerDashboardView.as_view(), name='retailer_dashboard'),

    # 4. APIs e Autenticação
    path('api/kpis/', api_views.get_kpis_data, name='api_kpis'), 
    path('accounts/register/', views.RegisterView.as_view(), name='register'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
]
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
    path('submit-warehouse/', views.producer_submit_warehouse, name='producer_submit_warehouse'),
    path('submit-sensor/', views.producer_submit_sensor, name='producer_submit_sensor'),
    
    # NOVAS ROTAS DE SUBMISSÃO

    path('submit-plantation/', views.producer_submit_plantation, name='producer_submit_plantation'),
    path('submit-plantation-crop/', views.producer_submit_plantation_crop, name='producer_submit_plantation_crop'),
    path('submit-soil-characteristic/', views.producer_submit_soil_characteristic, name='producer_submit_soil_characteristic'),
    path('submit-harvest/', views.producer_submit_harvest, name='producer_submit_harvest'),
    path('submit-event/', views.producer_submit_event, name='producer_submit_event'),
    path('submit-event/fertilizer-synth/', views.producer_submit_fertilizer_synth, name='producer_submit_fertilizer_synth'),
    path('submit-event/fertilizer-org/', views.producer_submit_fertilizer_org, name='producer_submit_fertilizer_org'),
    path('submit-event/soil-corrective/', views.producer_submit_soil_corrective, name='producer_submit_soil_corrective'),
    path('submit-event/pest-control/', views.producer_submit_pest_control, name='producer_submit_pest_control'),
    path('submit-event/machinery/', views.producer_submit_machinery, name='producer_submit_machinery'),
    path('submit-event/fuel/', views.producer_submit_fuel, name='producer_submit_fuel'),
    path('submit-event/electric/', views.producer_submit_electric, name='producer_submit_electric'),
    path('submit-event/water/', views.producer_submit_water, name='producer_submit_water'),
    path('submit-delivery/', views.producer_submit_delivery, name='producer_submit_delivery'),

    # MARKETPLACE URLS
    path('market/submit-order/', views.market_submit_order, name='market_submit_order'),
    path('market/accept-order/', views.market_accept_order, name='market_accept_order'),

    path('transporter/', views.TransporterDashboardView.as_view(), name='transporter_dashboard'),
    path('transporter/accept-job/', views.transporter_accept_job, name='transporter_accept_job'),
    path('transporter/submit-plan/', views.transporter_submit_plan, name='transporter_submit_plan'),
    path('transporter/validate-pickup/', views.transporter_validate_pickup, name='transporter_validate_pickup'),
    path('transporter/submit-delivery/', views.transporter_submit_delivery, name='transporter_submit_delivery'),
    
    # 3. ROTAS DE DASHBOARD PARA OUTROS PERFIS
    path('consumer/', views.ConsumerDashboardView.as_view(), name='consumer_dashboard'),
    path('processor/', views.ProcessorDashboardView.as_view(), name='processor_dashboard'),
    path('processor/submit-warehouse/', views.processor_submit_warehouse, name='processor_submit_warehouse'),
    path('processor/submit-sensor/', views.processor_submit_sensor, name='processor_submit_sensor'),
    path('processor/accept-order/', views.processor_accept_order, name='processor_accept_order'),
    path('retailer/', views.RetailerDashboardView.as_view(), name='retailer_dashboard'),
    path('retailer/submit-warehouse/', views.retailer_submit_warehouse, name='retailer_submit_warehouse'),
    path('retailer/submit-sensor/', views.retailer_submit_sensor, name='retailer_submit_sensor'),
    path('retailer/accept-order/', views.retailer_accept_order, name='retailer_accept_order'),

    # 4. APIs e Autenticação
    path('api/soil-characteristics/', api_views.get_soil_characteristics, name='api_soil_characteristics'),
    path('accounts/register/', views.RegisterView.as_view(), name='register'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
]
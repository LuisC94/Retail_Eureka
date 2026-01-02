from django.urls import path
from . import views

urlpatterns = [
    path('generate_genesis/<int:harvest_id>/', views.generate_genesis_block, name='generate_genesis_block'),
    path('chain/<str:batch_id>/', views.view_batch_chain, name='view_batch_chain'),
]

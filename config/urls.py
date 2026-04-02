from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from gestao import views, api_views

urlpatterns = [ # type: ignore
    path('api/login/',    api_views.api_login,    name='api_login'),
    path('api/analisar/', api_views.api_analisar,  name='api_analisar'),       
    path('api/historico/',api_views.api_historico, name='api_historico'),
    path('api/config/',   api_views.api_config,    name='api_config'),
    path('admin/', admin.site.urls),
    path('analisar/mascara/', views.analisar_com_mascara, name='analisar_com_mascara'),

    # Autenticação
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil,      name='perfil'),

    # Sistema
    path('',               views.home,           name='home'),
    path('analisar/',      views.analisar_logo,   name='analisar'),
    path('vendas/',        views.vendas,          name='vendas'),
    path('clientes/',      views.clientes,        name='clientes'),
    path('clientes/<int:cliente_id>/', views.cliente_detalhe, name='cliente_detalhe'),
    path('financeiro/',    views.financeiro,      name='financeiro'),
    path('ajustes/',       views.ajustes,         name='ajustes'),
    path('adicionar-item/', views.adicionar_item, name='adicionar_item'),
    path('pedido/<int:pedido_id>/', views.pedido_detalhe, name='pedido_detalhe'),
    path('producao/', views.producao, name='producao'),
    path('caixa/',    views.caixa,    name='caixa'),
    path('download-dst/<int:matriz_id>/', views.download_dst, name='download_dst'),
    path('download-pdf/<int:matriz_id>/', views.download_pdf, name='download_pdf'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

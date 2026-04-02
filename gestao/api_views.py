"""
API REST para o app Flutter PONTO.

Instalar dependências:
    pip install djangorestframework --break-system-packages

Adicionar em settings.py:
    INSTALLED_APPS = [
        ...
        'rest_framework',
        'rest_framework.authtoken',
    ]
    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.TokenAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
    }

Adicionar em config/urls.py:
    from gestao import api_views
    urlpatterns += [
        path('api/login/',    api_views.api_login,    name='api_login'),
        path('api/analisar/', api_views.api_analisar,  name='api_analisar'),
        path('api/historico/',api_views.api_historico, name='api_historico'),
        path('api/config/',   api_views.api_config,    name='api_config'),
    ]

Depois rodar:
    python manage.py migrate          (cria tabela de tokens)
    python manage.py createcachetable (opcional)
"""

import os
import sys
import json
import base64
import io
from PIL import Image as PILImage

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import MatrizBordado, ConfiguracaoBordado, Cliente


# =============================================================================
# LOGIN — retorna token de autenticação
# =============================================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    POST /api/login/
    Body: { "username": "...", "password": "..." }
    Response: { "token": "...", "nome": "...", "is_admin": bool }
    """
    try:
        data     = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({'error': 'Usuário ou senha incorretos'}, status=401)

    token, _ = Token.objects.get_or_create(user=user)

    # Nome de exibição
    try:
        nome = user.perfil.nome_exibicao or user.username
    except Exception:
        nome = user.username

    return JsonResponse({
        'token':    token.key,
        'nome':     nome,
        'username': user.username,
        'is_admin': user.is_superuser,
    })


# =============================================================================
# ANALISAR — recebe imagem + dimensões, retorna análise completa
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_analisar(request):
    """
    POST /api/analisar/
    Headers: Authorization: Token <token>
    Body (multipart/form-data):
        imagem:     arquivo de imagem (JPEG/PNG)
        largura_mm: float
        altura_mm:  float
        descricao:  string (opcional)
        cliente_id: int (opcional)
        ppm:        int (opcional, padrão 850)

    OU Body (JSON com imagem em base64):
        {
            "imagem_b64": "data:image/jpeg;base64,...",
            "largura_mm": 80,
            "altura_mm": 60,
            "descricao": "Logo cliente"
        }

    Response: {
        "ok": true,
        "matriz_id": 42,
        "total_pontos": 11290,
        "cores": [...],
        "bastidor": "10x10",
        "tempo_min": 18,
        "tipo_elemento": "logo",
        "cobertura": 64.0,
        "custo_bordado": 12.42,
        "sequencia_cores": "Verde → Preto",
        "largura_mm": 80.5,
        "altura_mm": 67.6,
        "imagem_url": "/media/logos_originais/..."
    }
    """
    # --- Pega parâmetros ---
    largura_mm = float(request.data.get('largura_mm', 0) or request.POST.get('largura_mm', 0))
    altura_mm  = float(request.data.get('altura_mm',  0) or request.POST.get('altura_mm',  0))
    descricao  = str(request.data.get('descricao', 'Análise App') or 'Análise App').strip()
    cliente_id = request.data.get('cliente_id') or None
    ppm        = int(request.data.get('ppm', 850) or 850)

    if largura_mm <= 0 or altura_mm <= 0:
        return JsonResponse({'error': 'Informe largura_mm e altura_mm válidos'}, status=400)

    # --- Pega imagem ---
    imagem_file = request.FILES.get('imagem')

    if not imagem_file:
        # Tenta receber imagem em base64
        imagem_b64 = request.data.get('imagem_b64', '')
        if imagem_b64:
            try:
                if ',' in imagem_b64:
                    imagem_b64 = imagem_b64.split(',')[1]
                img_bytes  = base64.b64decode(imagem_b64)
                imagem_file = _bytes_to_uploadedfile(img_bytes, f"{descricao[:10]}.jpg")
            except Exception as e:
                return JsonResponse({'error': f'Erro ao decodificar imagem base64: {e}'}, status=400)
        else:
            return JsonResponse({'error': 'Envie o campo "imagem" ou "imagem_b64"'}, status=400)

    # --- Cria e salva a MatrizBordado ---
    try:
        m = MatrizBordado(
            descricao=descricao,
            cliente_id=cliente_id,
            largura_desejada_mm=largura_mm,
            altura_desejada_mm=altura_mm,
            pontos_por_minuto=ppm,
            densidade_escolhida=5.5,
            imagem_original=imagem_file,
            cor_tecido_fundo='AUTO',
        )
        m.save()
    except Exception as e:
        return JsonResponse({'error': f'Erro ao salvar matriz: {e}'}, status=500)

    # --- Análise avançada ---
    analise = None
    try:
        gestao_dir = os.path.join(_base_dir(), 'gestao')
        if gestao_dir not in sys.path:
            sys.path.insert(0, gestao_dir)
        from analise_avancada import analisar_imagem
        img = PILImage.open(m.imagem_original.path)
        analise = analisar_imagem(
            img_pil=img,
            largura_mm=float(m.largura_mm),
            altura_mm=float(m.altura_mm),
            pontos_por_min=ppm,
        )
    except Exception as e:
        print(f"[API] Erro análise avançada: {e}")

    # --- Monta resposta ---
    config        = ConfiguracaoBordado.objects.first()
    valor_por_mil = float(config.valor_mil_pontos) if config else 5.0

    if analise:
        total_pontos = analise['total_pontos']
        cores = [
            {
                'nome':    d['nome'],
                'hex':     '#{:02X}{:02X}{:02X}'.format(*d['rgb'][:3]),
                'pontos':  d['pontos'],
                'pct':     round(d['pontos'] / total_pontos * 100, 1) if total_pontos else 0,
                'tipo':    d['tipo_ponto'],
                'area':    d['area_mm2'],
            }
            for d in analise['detalhes_cores']
        ]
        resp = {
            'ok':              True,
            'matriz_id':       m.id,
            'total_pontos':    total_pontos,
            'cores':           cores,
            'bastidor':        analise['bastidor'],
            'tempo_min':       analise['tempo_min'],
            'tipo_elemento':   analise['tipo_elemento'],
            'cobertura':       analise['fator_cobertura'],
            'n_cores':         analise['n_cores'],
            'trocas_linha':    analise['trocas_linha'],
            'sequencia_cores': analise['sequencia_nomes'],
            'largura_mm':      float(m.largura_mm),
            'altura_mm':       float(m.altura_mm),
            'custo_bordado':   round(total_pontos / 1000 * valor_por_mil, 2),
            'valor_por_mil':   valor_por_mil,
            'imagem_url':      m.imagem_original.url if m.imagem_original else None,
        }
    else:
        # Fallback: usa dados do models.py
        total_pontos = m.quantidade_pontos
        resp = {
            'ok':              True,
            'matriz_id':       m.id,
            'total_pontos':    total_pontos,
            'cores':           [],
            'bastidor':        m.bastidor_recomendado,
            'tempo_min':       int(m.tempo_estimado.replace(' min', '')),
            'tipo_elemento':   'logo',
            'cobertura':       50.0,
            'n_cores':         m.mudancas_cores + 1,
            'trocas_linha':    m.mudancas_cores,
            'sequencia_cores': m.sequencia_cores,
            'largura_mm':      float(m.largura_mm),
            'altura_mm':       float(m.altura_mm),
            'custo_bordado':   round(total_pontos / 1000 * valor_por_mil, 2),
            'valor_por_mil':   valor_por_mil,
            'imagem_url':      m.imagem_original.url if m.imagem_original else None,
        }

    return JsonResponse(resp)


# =============================================================================
# HISTÓRICO — últimas análises do usuário
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_historico(request):
    """
    GET /api/historico/?limit=20
    Response: { "historico": [...] }
    """
    limit   = int(request.GET.get('limit', 20))
    matrizes = MatrizBordado.objects.order_by('-criado_em')[:limit]

    config        = ConfiguracaoBordado.objects.first()
    valor_por_mil = float(config.valor_mil_pontos) if config else 5.0

    historico = []
    for m in matrizes:
        historico.append({
            'id':           m.id,
            'descricao':    m.descricao,
            'cliente':      m.cliente.nome if m.cliente else None,
            'largura_mm':   float(m.largura_mm),
            'altura_mm':    float(m.altura_mm),
            'pontos':       m.quantidade_pontos,
            'bastidor':     m.bastidor_recomendado,
            'tempo':        m.tempo_estimado,
            'cores':        m.sequencia_cores,
            'custo':        round(m.quantidade_pontos / 1000 * valor_por_mil, 2),
            'imagem_url':   m.imagem_original.url if m.imagem_original else None,
            'criado_em':    m.criado_em.strftime('%d/%m/%Y %H:%M') if m.criado_em else None,
        })

    return JsonResponse({'historico': historico})


# =============================================================================
# CONFIG — retorna configurações do sistema
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_config(request):
    """
    GET /api/config/
    Response: { "valor_por_mil": 1.10, "dias_aviso": 3 }
    """
    config = ConfiguracaoBordado.objects.first()
    if not config:
        return JsonResponse({'valor_por_mil': 5.0})

    return JsonResponse({
        'valor_por_mil': float(config.valor_mil_pontos),
        'dias_aviso':    config.dias_aviso_conta,
    })


# =============================================================================
# HELPERS
# =============================================================================

def _base_dir():
    from django.conf import settings
    return settings.BASE_DIR


def _bytes_to_uploadedfile(img_bytes, filename):
    """Converte bytes de imagem em InMemoryUploadedFile."""
    from django.core.files.uploadedfile import InMemoryUploadedFile
    buf = io.BytesIO(img_bytes)
    return InMemoryUploadedFile(
        file=buf,
        field_name='imagem',
        name=filename,
        content_type='image/jpeg',
        size=len(img_bytes),
        charset=None,
    )

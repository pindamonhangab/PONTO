"""
Módulo de visualização da análise de bordado.
Gera imagens de diagnóstico como base64 para embed direto no HTML.

Imagens geradas:
1. Imagem processada — o que vai ser bordado (fundo removido)
2. Camadas por cor — cada cor isolada
3. Mapa de calor — densidade de pontos por região
4. Comparação com/sem fundo
"""

import io
import math
import base64
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# =============================================================================
# UTILITÁRIOS
# =============================================================================

def _to_base64(img_pil, fmt='PNG'):
    buf = io.BytesIO()
    img_pil.save(buf, format=fmt, optimize=True)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def _dist(a, b):
    return math.sqrt(
        ((a[0]-b[0])*0.299)**2 +
        ((a[1]-b[1])*0.587)**2 +
        ((a[2]-b[2])*0.114)**2
    )


# =============================================================================
# 1. IMAGEM PROCESSADA (o que vai ser bordado)
# =============================================================================

def gerar_imagem_processada(img_pil, rgb_fundo=None, tamanho=(400, 400)):
    """
    Retorna base64 da imagem com fundo removido,
    mostrando exatamente o que vai ser bordado sobre
    fundo xadrez (transparência visual).
    """
    img_rgba = img_pil.convert('RGBA')
    w, h     = img_rgba.size
    arr      = np.array(img_rgba)

    # Máscara do que vai ser bordado
    if rgb_fundo:
        dist_map = (
            abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
        )
        mascara = (dist_map > 28) & (arr[:,:,3] > 128)
    else:
        mascara = arr[:,:,3] > 128

    # Cria imagem com canal alpha correto
    saida = arr.copy()
    saida[:,:,3] = np.where(mascara, 255, 0)
    img_sem_fundo = Image.fromarray(saida.astype(np.uint8), 'RGBA')

    # Fundo xadrez cinza (indica transparência/fundo ignorado)
    tam_quad = 20
    xadrez = Image.new('RGBA', (w, h), (240, 240, 240, 255))
    draw   = ImageDraw.Draw(xadrez)
    for y in range(0, h, tam_quad):
        for x in range(0, w, tam_quad):
            if (x // tam_quad + y // tam_quad) % 2 == 0:
                draw.rectangle([x, y, x+tam_quad, y+tam_quad], fill=(200, 200, 200, 255))

    xadrez.paste(img_sem_fundo, mask=img_sem_fundo.split()[3])
    xadrez = xadrez.convert('RGB')
    xadrez.thumbnail(tamanho, Image.LANCZOS)
    return _to_base64(xadrez)


# =============================================================================
# 2. CAMADAS POR COR
# =============================================================================

def gerar_camadas_cores(img_pil, detalhes_cores, rgb_fundo=None, tamanho_camada=(200, 200)):
    """
    Retorna lista de dicts com:
      - nome: nome da cor
      - hex: cor em hex
      - b64: base64 da imagem desta camada
      - pontos: qtd de pontos desta cor
      - pct: porcentagem
    """
    img_rgba = img_pil.convert('RGBA')
    arr      = np.array(img_rgba)
    total_pontos = sum(d['pontos'] for d in detalhes_cores)
    camadas = []

    for d in detalhes_cores:
        rgb  = d['rgb']
        nome = d['nome']

        # Máscara desta cor
        dist_map = (
            abs(arr[:,:,0].astype(int) - rgb[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb[2]) * 0.114
        )
        if rgb_fundo:
            dist_fundo = (
                abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
                abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
                abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
            )
            mascara = (dist_map < 40) & (dist_fundo > 25) & (arr[:,:,3] > 128)
        else:
            mascara = (dist_map < 40) & (arr[:,:,3] > 128)

        # Imagem da camada: cor real em fundo branco
        h, w = arr.shape[:2]
        camada = np.ones((h, w, 3), dtype=np.uint8) * 255  # fundo branco
        camada[mascara] = rgb[:3]
        img_camada = Image.fromarray(camada, 'RGB')
        img_camada.thumbnail(tamanho_camada, Image.LANCZOS)

        hex_cor = '#{:02X}{:02X}{:02X}'.format(*rgb[:3])
        pct = (d['pontos'] / total_pontos * 100) if total_pontos else 0

        camadas.append({
            'nome':   nome,
            'hex':    hex_cor,
            'b64':    _to_base64(img_camada),
            'pontos': d['pontos'],
            'pct':    round(pct, 1),
            'tipo':   d.get('tipo_ponto', '—'),
            'area':   d.get('area_mm2', 0),
        })

    return camadas


# =============================================================================
# 3. MAPA DE CALOR
# =============================================================================

def gerar_mapa_calor(img_pil, rgb_fundo=None, tamanho=(400, 400)):
    """
    Mapa de calor mostrando densidade de pixels por região.
    Vermelho = alta densidade de pontos, azul = baixa.
    """
    img_rgba = img_pil.convert('RGBA')
    arr      = np.array(img_rgba)

    # Máscara do que será bordado
    if rgb_fundo:
        dist_map = (
            abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
        )
        mascara = (dist_map > 28) & (arr[:,:,3] > 128)
    else:
        mascara = arr[:,:,3] > 128

    # Calcula densidade local com blur gaussiano
    mascara_f = mascara.astype(np.float32)
    img_mask  = Image.fromarray((mascara_f * 255).astype(np.uint8), 'L')

    # Aplica blur para criar gradiente de densidade
    raio = max(3, min(img_pil.width, img_pil.height) // 20)
    for _ in range(3):
        img_mask = img_mask.filter(ImageFilter.GaussianBlur(raio))

    densidade = np.array(img_mask).astype(np.float32)
    if densidade.max() > 0:
        densidade = densidade / densidade.max()

    # Colormap: azul → verde → amarelo → vermelho
    h, w = densidade.shape
    calor_rgb = np.zeros((h, w, 3), dtype=np.uint8)

    # Fundo branco onde não há bordado
    calor_rgb[:,:] = [245, 245, 245]

    # Aplica gradiente de cor nas regiões com bordado
    for threshold, (r1,g1,b1), (r2,g2,b2) in [
        (0.25, (0,0,200),   (0,180,255)),   # azul → ciano
        (0.50, (0,180,255), (50,220,50)),   # ciano → verde
        (0.75, (50,220,50), (255,220,0)),   # verde → amarelo
        (1.00, (255,220,0), (220,0,0)),     # amarelo → vermelho
    ]:
        low = threshold - 0.25
        idx = (densidade >= low) & (densidade < threshold)
        t   = np.clip((densidade[idx] - low) / 0.25, 0, 1)
        calor_rgb[:,:,0][idx] = np.clip(r1 + (r2-r1)*t, 0, 255).astype(np.uint8)
        calor_rgb[:,:,1][idx] = np.clip(g1 + (g2-g1)*t, 0, 255).astype(np.uint8)
        calor_rgb[:,:,2][idx] = np.clip(b1 + (b2-b1)*t, 0, 255).astype(np.uint8)

    img_calor = Image.fromarray(calor_rgb, 'RGB')

    # Adiciona contorno da logo por cima
    contorno = np.array(img_mask.filter(ImageFilter.FIND_EDGES))
    overlay  = img_calor.convert('RGBA')
    ov_arr   = np.array(overlay)
    borda    = contorno > 30
    ov_arr[borda] = [0, 0, 0, 200]
    img_calor = Image.fromarray(ov_arr, 'RGBA').convert('RGB')

    img_calor.thumbnail(tamanho, Image.LANCZOS)
    return _to_base64(img_calor)


# =============================================================================
# 4. COMPARAÇÃO COM / SEM FUNDO
# =============================================================================

def gerar_comparacao(img_pil, rgb_fundo=None, tamanho=(600, 300)):
    """
    Retorna base64 de imagem side-by-side:
    Esquerda = original | Direita = o que vai ser bordado
    """
    img_rgb  = img_pil.convert('RGB')
    img_rgba = img_pil.convert('RGBA')
    arr      = np.array(img_rgba)

    # Versão com fundo removido
    if rgb_fundo:
        dist_map = (
            abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
        )
        mascara = (dist_map > 28) & (arr[:,:,3] > 128)
    else:
        mascara = arr[:,:,3] > 128

    # Imagem processada com fundo cinza
    processada = arr.copy()
    # Fundo ignorado → cinza claro
    nao_bordado = ~mascara
    processada[nao_bordado, 0] = 230
    processada[nao_bordado, 1] = 230
    processada[nao_bordado, 2] = 230
    processada[:,:,3] = 255
    img_proc = Image.fromarray(processada.astype(np.uint8), 'RGBA').convert('RGB')

    # Resize ambas para o mesmo tamanho
    w_metade = tamanho[0] // 2
    h_total  = tamanho[1]

    img_esq = img_rgb.copy()
    img_esq.thumbnail((w_metade - 5, h_total - 40), Image.LANCZOS)
    img_dir = img_proc.copy()
    img_dir.thumbnail((w_metade - 5, h_total - 40), Image.LANCZOS)

    # Cria canvas de comparação
    canvas = Image.new('RGB', tamanho, (255, 255, 255))
    draw   = ImageDraw.Draw(canvas)

    # Labels
    draw.rectangle([0, 0, w_metade, 22], fill=(80, 80, 80))
    draw.rectangle([w_metade, 0, tamanho[0], 22], fill=(220, 53, 69))
    draw.text((10, 4), "ORIGINAL", fill=(255,255,255))
    draw.text((w_metade+10, 4), "O QUE SERÁ BORDADO", fill=(255,255,255))

    # Linha divisória
    draw.line([(w_metade, 0), (w_metade, h_total)], fill=(200,200,200), width=2)

    # Cola as imagens centralizadas
    def colar_centralizado(canvas, img, x_offset, y_offset=24):
        max_w = w_metade - 10
        max_h = h_total - 30
        img_c = img.copy()
        img_c.thumbnail((max_w, max_h), Image.LANCZOS)
        px = x_offset + (max_w - img_c.width) // 2
        py = y_offset + (max_h - img_c.height) // 2
        canvas.paste(img_c, (px, py))

    colar_centralizado(canvas, img_esq, 0)
    colar_centralizado(canvas, img_dir, w_metade)

    return _to_base64(canvas)


# =============================================================================
# FUNÇÃO PRINCIPAL — gera tudo de uma vez
# =============================================================================

def gerar_visualizacoes(img_pil, analise):
    """
    Gera todas as visualizações e retorna dict com base64 strings.

    Args:
        img_pil:  Imagem PIL original
        analise:  dict retornado por analise_avancada.analisar_imagem()

    Returns:
        dict com chaves:
          - img_processada: base64
          - img_calor: base64
          - img_comparacao: base64
          - camadas: lista de dicts por cor
    """
    rgb_fundo      = analise.get('rgb_fundo')
    detalhes_cores = analise.get('detalhes_cores', [])

    resultado = {}

    try:
        resultado['img_processada'] = gerar_imagem_processada(img_pil, rgb_fundo)
    except Exception as e:
        resultado['img_processada'] = None
        print(f"Erro img_processada: {e}")

    try:
        resultado['img_calor'] = gerar_mapa_calor(img_pil, rgb_fundo)
    except Exception as e:
        resultado['img_calor'] = None
        print(f"Erro img_calor: {e}")

    try:
        resultado['img_comparacao'] = gerar_comparacao(img_pil, rgb_fundo)
    except Exception as e:
        resultado['img_comparacao'] = None
        print(f"Erro img_comparacao: {e}")

    try:
        resultado['camadas'] = gerar_camadas_cores(img_pil, detalhes_cores, rgb_fundo)
    except Exception as e:
        resultado['camadas'] = []
        print(f"Erro camadas: {e}")

    return resultado

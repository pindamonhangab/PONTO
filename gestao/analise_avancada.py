"""
analise_avancada.py — Cálculo de pontos de bordado (v2)

Fórmula:
    pontos = área_total_mm² × cobertura × densidade_efetiva × fator_geometria

Densidades efetivas POR TIPO (calibradas com Wilcom real, modo Médio 5.5):
    icone_simples : 2.50 pts/mm²
    logo          : 2.59 pts/mm²  ← Bandeiras Brasil/Paraguai reais
    brasao        : 3.24 pts/mm²  ← Medicina Unila real
    texto         : 3.50 pts/mm²

Slider de densidade multiplica a base:
    4.0  Leve   → 0.65×
    5.5  Médio  → 1.00×  (base, calibrado)
    7.5  Denso  → 1.45×
    9.0  Pesado → 1.90×

IMPORTANTE: fator_cobertura é sempre FRAÇÃO 0.0–1.0 (ex: 0.64 = 64%).
Nunca armazenar como percentagem (64.0) — sempre multiplicar por 100 na exibição.

MUDANÇAS v2:
    - Detecção de fundo melhorada: branco/cinza claro detectado mesmo sem flood fill
    - Flood fill com tolerância adaptativa por luminosidade
    - Filtro de cor de fundo na quantização (não conta como cor de bordado)
    - Classificador de tipo com métricas mais robustas
    - Fator de geometria: regiões estreitas (satin) vs largas (tatami)
    - Estimativa de underlay automática
"""

import math
import numpy as np
from PIL import Image, ImageFilter, ImageMorph
from collections import Counter


# =============================================================================
# DENSIDADES BASE CALIBRADAS (pts/mm²) — modo Médio (5.5)
# =============================================================================

DENS_POR_TIPO = {
    'icone_simples': 2.50,
    'logo':          2.59,
    'brasao':        3.24,
    'texto':         3.50,
}

SLIDER_MULT = {
    4.0: 0.65,
    5.5: 1.00,
    7.5: 1.45,
    9.0: 1.90,
}

# Fator de underlay por tipo — underlay adiciona pontos extras de base
# Wilcom aplica underlay automaticamente; nosso cálculo precisa compensar
UNDERLAY_FATOR = {
    'icone_simples': 1.00,   # simples, quase sem underlay
    'logo':          1.00,   # calibração já inclui underlay típico
    'brasao':        1.00,   # idem
    'texto':         1.00,   # idem
}


# =============================================================================
# PALETA COMERCIAL
# =============================================================================

PALETA_BORDADO = {
    "Preto":            (0,   0,   0),   "Branco":           (255, 255, 255),
    "Cinza Claro":      (200, 200, 200), "Cinza Médio":      (140, 140, 140),
    "Cinza Escuro":     (70,  70,  70),  "Vermelho":         (200, 0,   0),
    "Vermelho Escuro":  (140, 0,   0),   "Bordô":            (100, 0,   30),
    "Rosa Claro":       (255, 180, 193), "Rosa":             (230, 100, 140),
    "Magenta":          (200, 0,   120), "Coral":            (255, 110, 80),
    "Laranja":          (255, 120, 0),   "Laranja Escuro":   (210, 80,  0),
    "Amarelo":          (255, 220, 0),   "Amarelo Escuro":   (210, 170, 0),
    "Dourado":          (200, 150, 20),  "Ouro":             (180, 130, 0),
    "Verde Limão":      (130, 200, 0),   "Verde Claro":      (80,  200, 80),
    "Verde":            (0,   150, 0),   "Verde Escuro":     (0,   100, 0),
    "Verde Militar":    (60,  100, 40),  "Verde Menta":      (60,  180, 140),
    "Verde Floresta":   (30,  80,  40),  "Azul Céu":         (100, 180, 255),
    "Azul Claro":       (60,  130, 220), "Azul":             (0,   80,  200),
    "Azul Royal":       (0,   50,  170), "Azul Marinho":     (0,   30,  100),
    "Azul Petróleo":    (0,   80,  110), "Turquesa":         (0,   160, 180),
    "Lilás":            (180, 130, 220), "Roxo":             (130, 0,   170),
    "Violeta":          (80,  0,   130), "Vinho":            (110, 0,   60),
    "Bege":             (220, 190, 150), "Creme":            (245, 225, 185),
    "Marrom Claro":     (180, 120, 60),  "Marrom":           (120, 70,  30),
    "Marrom Escuro":    (70,  40,  15),  "Caramelo":         (200, 130, 50),
    "Chocolate":        (90,  40,  10),  "Prata":            (190, 190, 200),
    "Bronze":           (160, 110, 50),
}


def dist_perceptual(a, b):
    return math.sqrt(
        ((a[0]-b[0])*0.299)**2 +
        ((a[1]-b[1])*0.587)**2 +
        ((a[2]-b[2])*0.114)**2
    )


def _luminosidade(rgb):
    """Luminosidade perceptual 0–255."""
    return rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114


def nome_cor(rgb):
    return min(PALETA_BORDADO, key=lambda n: dist_perceptual(rgb, PALETA_BORDADO[n]))


# =============================================================================
# DETECÇÃO DE FUNDO — v2: múltiplas estratégias combinadas
# =============================================================================

def _eh_cor_neutra(rgb, limiar_saturacao=30, limiar_lum_alta=210):
    """
    Retorna True se a cor é 'neutra' o suficiente pra ser fundo.
    Cores neutras: branco, cinza claro, preto, bege muito claro.
    Critério: baixa saturação E alta luminosidade.
    """
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    saturacao = max_c - min_c
    lum = _luminosidade(rgb)
    # Branco / cinza claro: alta luminosidade + baixa saturação
    if lum > limiar_lum_alta and saturacao < limiar_saturacao:
        return True
    # Preto / cinza escuro como fundo
    if lum < 30 and saturacao < limiar_saturacao:
        return True
    return False


def _tolerancia_adaptativa(cor_fundo, base=28):
    """
    Ajusta tolerância do flood fill baseado na luminosidade do fundo.
    Fundos claros (branco, bege) precisam de tolerância maior porque
    artefatos de compressão JPEG criam variação em torno do branco.
    """
    lum = _luminosidade(cor_fundo)
    if lum > 220:
        return base + 15   # branco/quase branco: mais tolerante
    elif lum > 180:
        return base + 8    # cinza claro
    elif lum < 40:
        return base + 10   # preto/quase preto
    return base


def _mascara_fundo_flood(arr_rgba, tolerancia_base=28):
    """
    Remove fundo por flood fill conectado às bordas.
    
    v2 melhorias:
    - Tolerância adaptativa por luminosidade da cor de fundo
    - Detecção de múltiplas cores de borda (cantos podem ter cores diferentes)
    - Guarda de segurança mais inteligente: verifica se a cor é neutra
    - Se a cor da borda é neutra (branco/cinza) E cobre >60% → ainda remove
      (o critério antigo de 40% impedia remoção de fundo branco)
    
    Retorna array booleano: True = pixel de fundo a remover.
    """
    h, w = arr_rgba.shape[:2]

    # ---- Cor dominante nas bordas ----
    borda_pixels = np.concatenate([
        arr_rgba[0, :, :3],  arr_rgba[-1, :, :3],
        arr_rgba[:, 0, :3],  arr_rgba[:, -1, :3],
    ])
    borda_alpha = np.concatenate([
        arr_rgba[0, :, 3],  arr_rgba[-1, :, 3],
        arr_rgba[:, 0, 3],  arr_rgba[:, -1, 3],
    ])
    validos = borda_pixels[borda_alpha > 128]
    if len(validos) == 0:
        return np.zeros((h, w), dtype=bool)

    # Quantizar bordas pra achar cor dominante
    q = (validos // 12 * 12)   # quantização mais fina que v1 (era 15)
    uniq, counts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    cor_fundo = tuple(int(v) for v in uniq[counts.argmax()])

    # ---- Tolerância adaptativa ----
    tolerancia = _tolerancia_adaptativa(cor_fundo, tolerancia_base)

    # ---- Guarda de segurança: cor da borda cobre muita área? ----
    dist_global = np.sqrt(
        ((arr_rgba[:,:,0].astype(int) - cor_fundo[0]) * 0.299)**2 +
        ((arr_rgba[:,:,1].astype(int) - cor_fundo[1]) * 0.587)**2 +
        ((arr_rgba[:,:,2].astype(int) - cor_fundo[2]) * 0.114)**2
    )
    cobertura_fundo = float((dist_global < tolerancia).mean())

    # v2: se a cor é neutra (branco/cinza), sempre tenta remover —
    # só bloqueia se for cor saturada cobrindo >40% (ex: bandeira verde)
    cor_neutra = _eh_cor_neutra(cor_fundo)
    if not cor_neutra and cobertura_fundo > 0.40:
        return np.zeros((h, w), dtype=bool)
    # Se a cor é neutra mas cobre >92% → imagem toda é essa cor, não faz sentido
    if cor_neutra and cobertura_fundo > 0.92:
        return np.zeros((h, w), dtype=bool)

    # ---- Flood fill BFS das 4 bordas ----
    visitado = np.zeros((h, w), dtype=bool)
    fila = []

    def try_add(x, y):
        if 0 <= x < w and 0 <= y < h and not visitado[y, x]:
            if arr_rgba[y, x, 3] < 128:
                # Pixel transparente = fundo
                visitado[y, x] = True
                fila.append((x, y))
                return
            pixel = arr_rgba[y, x, :3]
            d = math.sqrt(
                ((int(pixel[0]) - cor_fundo[0]) * 0.299)**2 +
                ((int(pixel[1]) - cor_fundo[1]) * 0.587)**2 +
                ((int(pixel[2]) - cor_fundo[2]) * 0.114)**2
            )
            if d <= tolerancia:
                visitado[y, x] = True
                fila.append((x, y))

    for x in range(w):
        try_add(x, 0); try_add(x, h - 1)
    for y in range(h):
        try_add(0, y); try_add(w - 1, y)

    while fila:
        cx, cy = fila.pop()
        for nx, ny in [(cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)]:
            try_add(nx, ny)

    return visitado


def _segunda_passada_fundo(arr_rgba, mascara_bool):
    """
    Segunda passada: após a remoção de fundo inicial, verifica se sobrou
    alguma região interna grande que é da mesma cor do fundo detectado
    e que provavelmente não é bordado (ex: espaços internos de letras,
    buracos em logos).
    
    Não remove — apenas sinaliza para a quantização não contar como cor.
    Retorna a cor RGB do fundo detectado (ou None).
    """
    if not mascara_bool.any():
        return None

    # Pixels que foram removidos como fundo
    fundo_pixels = arr_rgba[~mascara_bool][:, :3]
    if len(fundo_pixels) == 0:
        return None

    # Cor média do fundo removido
    cor_media = tuple(int(v) for v in fundo_pixels.mean(axis=0))
    return cor_media


# =============================================================================
# TIPO DE ELEMENTO — v2: mais robusto
# =============================================================================

def _detectar_tipo(img_rgba, mascara_bool):
    """
    Classifica: icone_simples, logo, brasao ou texto.
    
    v2: usa métricas mais robustas e não depende tanto de n_reg
    que pode inflar com ruído de quantização.
    """
    arr   = np.array(img_rgba)
    h, w  = arr.shape[:2]

    total_px   = h * w
    px_validos = int(np.count_nonzero(mascara_bool))
    if px_validos == 0:
        return 'logo'

    cobertura = px_validos / total_px

    # ---- Razão de borda (edge density) ----
    gray = np.array(img_rgba.convert('L'))
    edges = np.array(Image.fromarray(gray, 'L').filter(ImageFilter.FIND_EDGES))
    # Só contar edges dentro da máscara
    edges_mascara = edges.copy()
    edges_mascara[~mascara_bool] = 0
    razao_borda = int(np.count_nonzero(edges_mascara > 25)) / max(1, px_validos)

    # ---- Variação de cor ----
    cores_validas = arr[:,:,:3][mascara_bool]
    var_cor = float(cores_validas.std()) / 255.0 if len(cores_validas) > 0 else 0

    # ---- Número de cores reais (quantização mais limpa) ----
    try:
        # Criar imagem só com pixels válidos pra quantizar
        img_masked = img_rgba.copy()
        arr_m = np.array(img_masked)
        arr_m[~mascara_bool] = [255, 255, 255, 0]
        img_m = Image.fromarray(arr_m, 'RGBA')
        base = Image.new("RGB", img_m.size, (255, 255, 255))
        base.paste(img_m.convert("RGB"), mask=img_m.split()[3])
        arr_q = np.array(base.quantize(colors=12, method=Image.Quantize.MEDIANCUT))
        n_reg = len(np.unique(arr_q[mascara_bool.reshape(arr_q.shape)]))
    except Exception:
        n_reg = 4

    # ---- Classificação ----
    # Texto: muitas bordas, pouca variação de cor, geralmente poucas cores
    if razao_borda > 0.10 and var_cor < 0.28 and n_reg <= 4:
        return 'texto'

    # Ícone simples: poucas cores, baixa complexidade, cobertura moderada
    if n_reg <= 3 and var_cor < 0.20 and razao_borda < 0.08:
        return 'icone_simples'

    # Brasão: muitas cores OU muita variação OU alta complexidade
    if n_reg > 6 or (var_cor > 0.35 and n_reg > 4):
        return 'brasao'

    # Default: logo
    return 'logo'


# =============================================================================
# QUANTIZAÇÃO DE CORES — v2: filtra cor de fundo
# =============================================================================

def _quantizar_cores(img_rgba, mascara_bool, cor_fundo_rgb=None,
                     n_max=12, min_cob=0.015):
    """
    Extrai cores dominantes apenas da área bordada.
    
    v2: recebe cor_fundo_rgb e filtra qualquer cor muito próxima do fundo.
    Isso evita que branco/cinza de fundo entre como cor de bordado.
    """
    arr = np.array(img_rgba)

    arr_m = arr.copy()
    arr_m[~mascara_bool] = [255, 255, 255, 0]
    img_m = Image.fromarray(arr_m.astype(np.uint8), 'RGBA')

    base  = Image.new("RGB", img_m.size, (255, 255, 255))
    base.paste(img_m.convert("RGB"), mask=img_m.split()[3])
    img_q     = base.quantize(colors=n_max, method=Image.Quantize.MEDIANCUT).convert("RGB")
    cores_raw = img_q.getcolors(maxcolors=n_max * 4) or []
    total     = sum(c[0] for c in cores_raw)
    if not total:
        return []

    px_validos = int(np.count_nonzero(mascara_bool))
    nomes = []

    for count, rgb in sorted(cores_raw, reverse=True):
        fracao = count / px_validos
        if fracao < min_cob:
            continue

        # v2: filtrar cor muito próxima do fundo
        if cor_fundo_rgb is not None:
            d_fundo = dist_perceptual(rgb, cor_fundo_rgb)
            # Se a cor é muito próxima do fundo E é neutra, pular
            if d_fundo < 25 and _eh_cor_neutra(rgb):
                continue

        n = nome_cor(rgb)
        if n not in nomes:
            nomes.append(n)

    return nomes


# =============================================================================
# FATOR DE GEOMETRIA — v2 novo
# =============================================================================

def _fator_geometria(mascara_bool, largura_mm, altura_mm):
    """
    Analisa a geometria das regiões bordadas pra ajustar a densidade.
    
    Regiões estreitas (tipo contornos, letras finas) usam satin stitch
    que tem mais pontos/mm² do que tatami em áreas grandes.
    
    Regiões largas usam tatami que é mais eficiente.
    
    Retorna fator multiplicador: 1.0 = normal, >1.0 = muitos detalhes finos.
    """
    if not mascara_bool.any():
        return 1.0

    h_px, w_px = mascara_bool.shape

    # Escala px → mm
    scale_x = largura_mm / max(1, w_px)
    scale_y = altura_mm / max(1, h_px)

    # Calcular "espessura" média das regiões usando distance transform
    # (distância de cada pixel bordado até a borda mais próxima)
    from scipy import ndimage
    try:
        dist = ndimage.distance_transform_edt(mascara_bool)
    except ImportError:
        # Se não tem scipy, retorna neutro
        return 1.0

    # Só pixels dentro da máscara
    dist_validos = dist[mascara_bool]
    if len(dist_validos) == 0:
        return 1.0

    # Espessura média em mm (distância média × 2 ≈ largura média da região)
    espessura_media_px = float(dist_validos.mean()) * 2
    espessura_mm = espessura_media_px * (scale_x + scale_y) / 2

    # Classificar:
    # < 2mm → muito fino (satin puro) → mais pontos
    # 2-5mm → médio (satin + tatami)
    # > 5mm → largo (tatami puro) → densidade normal
    if espessura_mm < 1.5:
        return 1.25   # regiões muito finas: +25% pontos
    elif espessura_mm < 3.0:
        return 1.12   # regiões médias: +12%
    elif espessura_mm < 5.0:
        return 1.05   # levemente acima do normal
    return 1.0


# =============================================================================
# CÁLCULO DE PONTOS — atribuição exclusiva (sem double counting)
# =============================================================================

def _pontos_por_cor(arr, mascara_bool, nomes_cores, area_mm2, dens_efetiva):
    """
    Cada pixel é atribuído à cor mais próxima.
    Garante: soma dos pontos por cor == total de pontos.
    """
    if not nomes_cores:
        return []

    dist_maps = []
    for nome in nomes_cores:
        rgb = PALETA_BORDADO[nome]
        dm  = (
            abs(arr[:,:,0].astype(int) - rgb[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb[2]) * 0.114
        )
        dist_maps.append(dm)

    idx   = np.argmin(np.stack(dist_maps, axis=0), axis=0)
    gray  = (arr[:,:,0]*0.299 + arr[:,:,1]*0.587 + arr[:,:,2]*0.114).astype(np.uint8)
    edges = np.array(Image.fromarray(gray, 'L').filter(ImageFilter.FIND_EDGES)) > 30

    total_valido = int(np.count_nonzero(mascara_bool))
    if total_valido == 0:
        return []

    detalhes = []

    for i, nome in enumerate(nomes_cores):
        mask_cor = (idx == i) & mascara_bool
        px       = int(np.count_nonzero(mask_cor))
        if px == 0:
            continue

        # v2: fração relativa à área bordada, não à imagem inteira
        fracao   = px / total_valido
        area_cor = area_mm2 * fracao
        pontos   = int(area_cor * dens_efetiva)

        r_borda = int(np.count_nonzero(mask_cor & edges)) / px
        tipo_st = (
            'Satin / Contorno'      if r_borda > 0.50 else
            'Satin + Tatami'        if r_borda > 0.25 else
            'Tatami / Preenchimento'
        )

        detalhes.append({
            'nome':       nome,
            'rgb':        PALETA_BORDADO[nome],
            'pontos':     pontos,
            'area_mm2':   round(area_cor, 1),
            'r_borda':    round(r_borda, 3),
            'tipo_ponto': tipo_st,
            'fracao':     fracao,
        })

    return detalhes


# =============================================================================
# HELPERS
# =============================================================================

def _slider_mult(densidade):
    k = min(SLIDER_MULT.keys(), key=lambda x: abs(x - float(densidade)))
    return SLIDER_MULT[k]


def _bastidor(lw, lh):
    return (
        '6x6'   if lw <= 60  and lh <= 60  else
        '10x10' if lw <= 100 and lh <= 100 else
        '13x18' if lw <= 130 and lh <= 180 else
        '20x26' if lw <= 200 and lh <= 260 else '30x40'
    )


def _montar_resultado(tipo, cobertura, dens_ef, densidade, detalhes,
                       largura_mm, altura_mm, pontos_por_min, mascara_aplicada,
                       cor_fundo_rgb=None, fator_geo=1.0):
    total  = sum(d['pontos'] for d in detalhes)
    trocas = max(0, len(detalhes) - 1)
    tempo  = math.ceil(total / max(1, pontos_por_min) + trocas * 2.0)
    return {
        'tipo_elemento':      tipo,
        'fator_cobertura':    round(cobertura, 4),   # SEMPRE fração 0.0–1.0
        'densidade_escolhida': float(densidade),
        'densidade_efetiva':  round(dens_ef, 3),
        'total_pontos':       total,
        'detalhes_cores':     detalhes,
        'sequencia_nomes':    ' → '.join(d['nome'] for d in detalhes),
        'n_cores':            len(detalhes),
        'trocas_linha':       trocas,
        'tempo_min':          tempo,
        'bastidor':           _bastidor(largura_mm, altura_mm),
        'largura_mm':         largura_mm,
        'altura_mm':          altura_mm,
        'rgb_fundo':          cor_fundo_rgb,
        'mascara_aplicada':   mascara_aplicada,
        'fator_geometria':    round(fator_geo, 3),
    }


# =============================================================================
# ANÁLISE AUTOMÁTICA (sem máscara) — v2
# =============================================================================

def analisar_imagem(img_pil, largura_mm, altura_mm,
                    densidade=5.5, pontos_por_min=850):
    """
    Análise automática com remoção inteligente de fundo.

    Args:
        densidade: 4.0=Leve, 5.5=Médio, 7.5=Denso, 9.0=Pesado

    Returns:
        dict com fator_cobertura como FRAÇÃO 0.0–1.0
    """
    img_rgba = img_pil.convert('RGBA')
    w, h     = img_rgba.size
    arr      = np.array(img_rgba)
    area_mm2 = largura_mm * altura_mm

    # ---- Máscara de fundo ----
    tem_alpha = bool((arr[:,:,3] < 128).any())
    if tem_alpha:
        mascara_bool = arr[:,:,3] >= 128
    else:
        fundo_mask   = _mascara_fundo_flood(arr)
        mascara_bool = ~fundo_mask & (arr[:,:,3] >= 128)

    px_sel = int(np.count_nonzero(mascara_bool))
    if px_sel == 0:
        return None

    # v2: detectar cor do fundo pra filtrar na quantização
    cor_fundo_rgb = _segunda_passada_fundo(arr, mascara_bool)

    cobertura = px_sel / (w * h)
    tipo      = _detectar_tipo(img_rgba, mascara_bool)
    dens_base = DENS_POR_TIPO[tipo] * _slider_mult(densidade)

    # v2: fator de geometria
    fator_geo = _fator_geometria(mascara_bool, largura_mm, altura_mm)
    dens_ef   = dens_base * fator_geo

    # v2: underlay
    dens_ef *= UNDERLAY_FATOR.get(tipo, 1.0)

    # v2: quantização com filtro de fundo
    nomes = _quantizar_cores(img_rgba, mascara_bool, cor_fundo_rgb=cor_fundo_rgb)
    if not nomes:
        return None

    # v2: pontos calculados sobre área bordada (cobertura × area_total)
    area_bordada = area_mm2 * cobertura
    detalhes = _pontos_por_cor(arr, mascara_bool, nomes, area_bordada, dens_ef)
    if not detalhes:
        return None

    return _montar_resultado(tipo, cobertura, dens_ef, densidade,
                              detalhes, largura_mm, altura_mm,
                              pontos_por_min, False,
                              cor_fundo_rgb=cor_fundo_rgb,
                              fator_geo=fator_geo)


# =============================================================================
# ANÁLISE COM MÁSCARA (seleção manual do canvas) — v2
# =============================================================================

def analisar_imagem_com_mascara(img_pil, mascara_pil, largura_mm, altura_mm,
                                  densidade=5.5, pontos_por_min=850):
    """
    Análise com máscara manual — mais precisa que a automática.

    Args:
        mascara_pil: imagem PIL modo 'L' — branco=bordar, preto=ignorar
        densidade:   4.0=Leve, 5.5=Médio, 7.5=Denso, 9.0=Pesado

    Returns:
        dict com fator_cobertura como FRAÇÃO 0.0–1.0
    """
    img_rgba = img_pil.convert('RGBA')
    w, h     = img_rgba.size
    arr      = np.array(img_rgba)
    area_mm2 = largura_mm * altura_mm

    mascara_resize = mascara_pil.resize((w, h), Image.NEAREST)
    mascara_bool   = np.array(mascara_resize) > 128

    px_sel = int(np.count_nonzero(mascara_bool))
    if px_sel < 10:
        return None

    # v2: detectar cor do fundo pra filtrar
    cor_fundo_rgb = _segunda_passada_fundo(arr, mascara_bool)

    cobertura = px_sel / (w * h)
    tipo      = _detectar_tipo(img_rgba, mascara_bool)
    dens_base = DENS_POR_TIPO[tipo] * _slider_mult(densidade)

    # v2: fator de geometria
    fator_geo = _fator_geometria(mascara_bool, largura_mm, altura_mm)
    dens_ef   = dens_base * fator_geo

    # v2: underlay
    dens_ef *= UNDERLAY_FATOR.get(tipo, 1.0)

    # v2: quantização com filtro de fundo
    nomes = _quantizar_cores(img_rgba, mascara_bool, cor_fundo_rgb=cor_fundo_rgb)
    if not nomes:
        return None

    # v2: pontos calculados sobre área bordada
    area_bordada = area_mm2 * cobertura
    detalhes = _pontos_por_cor(arr, mascara_bool, nomes, area_bordada, dens_ef)
    if not detalhes:
        return None

    return _montar_resultado(tipo, cobertura, dens_ef, densidade,
                              detalhes, largura_mm, altura_mm,
                              pontos_por_min, True,
                              cor_fundo_rgb=cor_fundo_rgb,
                              fator_geo=fator_geo)

"""
analise_avancada.py — Cálculo de pontos de bordado

Fórmula:
    pontos = área_total_mm² × cobertura × densidade_efetiva

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
"""

import math
import numpy as np
from PIL import Image, ImageFilter
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


def nome_cor(rgb):
    return min(PALETA_BORDADO, key=lambda n: dist_perceptual(rgb, PALETA_BORDADO[n]))


# =============================================================================
# DETECÇÃO DE FUNDO — flood fill das bordas (não remove interior)
# =============================================================================

def _mascara_fundo_flood(arr_rgba, tolerancia=28):
    """
    Remove fundo por flood fill conectado às bordas.
    Se a cor da borda cobre >40% da imagem → não é fundo (ex: bandeira verde).
    Retorna array booleano: True = pixel de fundo a remover.
    """
    h, w = arr_rgba.shape[:2]

    # Cor dominante nas bordas
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

    q = (validos // 15 * 15)
    uniq, counts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    cor_fundo = tuple(int(v) for v in uniq[counts.argmax()])

    # Guarda de segurança: cor da borda cobre >40% da imagem = conteúdo, não fundo
    dist_global = np.sqrt(
        ((arr_rgba[:,:,0].astype(int) - cor_fundo[0]) * 0.299)**2 +
        ((arr_rgba[:,:,1].astype(int) - cor_fundo[1]) * 0.587)**2 +
        ((arr_rgba[:,:,2].astype(int) - cor_fundo[2]) * 0.114)**2
    )
    if float((dist_global < tolerancia).mean()) > 0.40:
        return np.zeros((h, w), dtype=bool)

    # Flood fill BFS das 4 bordas
    visitado = np.zeros((h, w), dtype=bool)
    fila = []

    def try_add(x, y):
        if 0 <= x < w and 0 <= y < h and not visitado[y, x]:
            pixel = arr_rgba[y, x, :3]
            d = math.sqrt(
                ((int(pixel[0]) - cor_fundo[0]) * 0.299)**2 +
                ((int(pixel[1]) - cor_fundo[1]) * 0.587)**2 +
                ((int(pixel[2]) - cor_fundo[2]) * 0.114)**2
            )
            if d <= tolerancia and arr_rgba[y, x, 3] > 128:
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


# =============================================================================
# TIPO DE ELEMENTO
# =============================================================================

def _detectar_tipo(img_rgba, mascara_bool):
    """Classifica: icone_simples, logo, brasao ou texto."""
    arr   = np.array(img_rgba)
    edges = np.array(img_rgba.convert('L').filter(ImageFilter.FIND_EDGES))

    total_px   = arr.shape[0] * arr.shape[1]
    px_validos = int(np.count_nonzero(mascara_bool))
    if px_validos == 0:
        return 'logo'

    razao_borda   = int(np.count_nonzero(edges > 25)) / total_px
    cores_validas = arr[:,:,:3][mascara_bool]
    var_cor       = float(cores_validas.std()) / 255.0 if len(cores_validas) > 0 else 0

    base  = Image.new("RGB", img_rgba.size, (255, 255, 255))
    base.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])
    arr_q = np.array(base.quantize(colors=16, method=Image.Quantize.MEDIANCUT))
    n_reg = len(np.unique(arr_q[mascara_bool.reshape(arr_q.shape)]))

    complexidade = min(1.0, (razao_borda * 2 + var_cor + n_reg / 16) / 3)

    if razao_borda > 0.12 and var_cor < 0.25:
        return 'texto'
    elif n_reg <= 2 and complexidade < 0.25:
        return 'icone_simples'
    elif complexidade > 0.60 or n_reg > 8:
        return 'brasao'
    return 'logo'


# =============================================================================
# QUANTIZAÇÃO DE CORES
# =============================================================================

def _quantizar_cores(img_rgba, mascara_bool, n_max=12, min_cob=0.015):
    """Extrai cores dominantes apenas da área bordada."""
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
        if count / px_validos < min_cob:
            continue
        n = nome_cor(rgb)
        if n not in nomes:
            nomes.append(n)
    return nomes


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

    total_px = arr.shape[0] * arr.shape[1]
    detalhes = []

    for i, nome in enumerate(nomes_cores):
        mask_cor = (idx == i) & mascara_bool
        px       = int(np.count_nonzero(mask_cor))
        if px == 0:
            continue

        fracao   = px / total_px
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
                       largura_mm, altura_mm, pontos_por_min, mascara_aplicada):
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
        'rgb_fundo':          None,
        'mascara_aplicada':   mascara_aplicada,
    }


# =============================================================================
# ANÁLISE AUTOMÁTICA (sem máscara)
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

    # Máscara
    tem_alpha    = bool((arr[:,:,3] < 128).any())
    if tem_alpha:
        mascara_bool = arr[:,:,3] >= 128
    else:
        fundo_mask   = _mascara_fundo_flood(arr)
        mascara_bool = ~fundo_mask & (arr[:,:,3] >= 128)

    px_sel = int(np.count_nonzero(mascara_bool))
    if px_sel == 0:
        return None

    cobertura = px_sel / (w * h)
    tipo      = _detectar_tipo(img_rgba, mascara_bool)
    dens_ef   = DENS_POR_TIPO[tipo] * _slider_mult(densidade)

    nomes    = _quantizar_cores(img_rgba, mascara_bool)
    if not nomes:
        return None
    detalhes = _pontos_por_cor(arr, mascara_bool, nomes, area_mm2, dens_ef)
    if not detalhes:
        return None

    return _montar_resultado(tipo, cobertura, dens_ef, densidade,
                              detalhes, largura_mm, altura_mm,
                              pontos_por_min, False)


# =============================================================================
# ANÁLISE COM MÁSCARA (seleção manual do canvas)
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

    cobertura = px_sel / (w * h)
    tipo      = _detectar_tipo(img_rgba, mascara_bool)
    dens_ef   = DENS_POR_TIPO[tipo] * _slider_mult(densidade)

    nomes    = _quantizar_cores(img_rgba, mascara_bool)
    if not nomes:
        return None
    detalhes = _pontos_por_cor(arr, mascara_bool, nomes, area_mm2, dens_ef)
    if not detalhes:
        return None

    return _montar_resultado(tipo, cobertura, dens_ef, densidade,
                              detalhes, largura_mm, altura_mm,
                              pontos_por_min, True)

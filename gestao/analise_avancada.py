"""
Análise avançada de imagem para bordado — calibrada com dados reais do Wilcom.

Calibração baseada em comparação direta:
  Logo Medicina Unila 80.5×67.6mm:
    PONTO antigo:  49.615 pts (5.5 pts/mm² base) → ERRADO
    Wilcom real:   11.290 pts                     → CORRETO
    Densidade real efetiva: ~2.5 pts/mm²

Problema do algoritmo anterior:
  - Usava 5.5 pts/mm² (densidade de impressão, não de bordado)
  - Bordado profissional usa 1.5–3.5 pts/mm² dependendo do tipo
  - Wilcom aplica densidades diferentes por tipo de stitch:
      Tatami fill:   2.0–2.8 pts/mm²
      Satin stitch:  3.0–4.5 pts/mm² (mas só nas bordas, área pequena)
      Running stitch: 0.5–1.0 pts/mm²
      Underlay:      +15–25% sobre o fill

Novos parâmetros calibrados:
  - Densidade base tatami:  2.4 pts/mm²  (corrigido de 5.5)
  - Densidade satin borda:  3.5 pts/mm²  (só para regiões de contorno)
  - Underlay conservador:   1.15–1.20×   (não 1.25×)
  - Cobertura real:         só pixels efetivamente stitchados
"""

import math
import numpy as np
from PIL import Image, ImageFilter
from collections import Counter


# =============================================================================
# DENSIDADES CALIBRADAS (pts/mm²) — baseadas em Wilcom real
# =============================================================================

DENSIDADE_TATAMI_LEVE   = 2.2   # logos simples, ícones
DENSIDADE_TATAMI_MEDIO  = 2.8   # logos padrão (brasões, lettering)
DENSIDADE_TATAMI_DENSO  = 3.4   # detalhes finos, textos pequenos
DENSIDADE_SATIN         = 3.2   # contornos/bordas (satin stitch)
DENSIDADE_RUNNING       = 0.8   # underlay running stitch

FATOR_UNDERLAY_SIMPLES  = 1.10  # logos simples
FATOR_UNDERLAY_MEDIO    = 1.15  # logos padrão
FATOR_UNDERLAY_COMPLEXO = 1.18  # brasões, muitos detalhes


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


def detectar_fundo(img_rgba, margem=0.05):
    w, h   = img_rgba.size
    pixels = list(img_rgba.getdata())
    m      = max(2, int(min(w, h) * margem))
    amostras = [
        (r//15*15, g//15*15, b//15*15)
        for y in range(h) for x in range(w)
        if (x < m or x >= w-m or y < m or y >= h-m)
        for r, g, b, a in [pixels[y*w+x]] if a > 128
    ]
    return Counter(amostras).most_common(1)[0][0] if amostras else None


# =============================================================================
# DETECÇÃO DE TIPO DE ELEMENTO (calibrada)
# =============================================================================

def detectar_tipo_elemento(img_rgba, rgb_fundo=None):
    """
    Classifica o tipo dominante do design.
    Retorna (tipo, razao_borda, complexidade)
    
    tipos: 'texto', 'icone_simples', 'logo', 'brasao'
    complexidade: 0.0 (simples) a 1.0 (complexo)
    """
    arr   = np.array(img_rgba)
    gray  = np.array(img_rgba.convert('L'))
    edges = np.array(img_rgba.convert('L').filter(ImageFilter.FIND_EDGES))

    total_px = arr.shape[0] * arr.shape[1]

    # Pixels válidos (não fundo, não transparente)
    if rgb_fundo:
        dist_map = (
            abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
        )
        mascara_valida = (dist_map > 25) & (arr[:,:,3] > 128)
    else:
        mascara_valida = arr[:,:,3] > 128

    px_validos = int(np.count_nonzero(mascara_valida))
    if px_validos == 0:
        return 'logo', 0.2, 0.5

    px_bordas  = int(np.count_nonzero(edges > 25))
    razao_borda = px_bordas / total_px

    # Variância de cores (maior = mais complexo)
    cores_validas = arr[:,:,:3][mascara_valida]
    variancia_cor = float(cores_validas.std()) / 255.0 if len(cores_validas) > 0 else 0

    # Número estimado de regiões distintas (via quantização)
    base = Image.new("RGB", img_rgba.size, (255,255,255))
    base.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])
    img_q = base.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    arr_q = np.array(img_q)
    n_regioes = len(np.unique(arr_q[mascara_valida.reshape(arr_q.shape)]))

    # Complexidade 0–1
    complexidade = min(1.0, (razao_borda * 2 + variancia_cor + n_regioes/16) / 3)

    # Classificação
    if razao_borda > 0.12 and variancia_cor < 0.25:
        tipo = 'texto'
    elif n_regioes <= 3 and complexidade < 0.3:
        tipo = 'icone_simples'
    elif complexidade > 0.6 or n_regioes > 8:
        tipo = 'brasao'
    else:
        tipo = 'logo'

    return tipo, razao_borda, complexidade


# =============================================================================
# CÁLCULO DE PONTOS POR COR (calibrado)
# =============================================================================

def calcular_pontos_por_cor(img_rgba, nomes_cores, largura_mm, altura_mm,
                             tipo_elemento, razao_borda, complexidade,
                             rgb_fundo=None):
    """
    Calcula pontos por cor com atribuição EXCLUSIVA de pixels.

    Cada pixel é atribuído à cor comercial mais próxima — sem double counting.
    Isso é o que garante que a soma dos pontos por cor == total de pontos.

    Calibração baseada em dados reais do Wilcom:
      - Logo 80.5×67.6mm, 64% cobertura → 11.290 pts efetivos
      - Densidade efetiva: ~3.24 pts/mm² (fill + satin + underlay)
    """
    arr  = np.array(img_rgba)
    w, h = img_rgba.size
    area_total_mm2 = largura_mm * altura_mm

    # Mapa de bordas
    edges         = np.array(img_rgba.convert('L').filter(ImageFilter.FIND_EDGES))
    mascara_borda = edges > 30

    # Densidade base por tipo
    densidade_fill = {
        'texto':         DENSIDADE_TATAMI_DENSO,
        'icone_simples': DENSIDADE_TATAMI_LEVE,
        'logo':          DENSIDADE_TATAMI_MEDIO,
        'brasao':        DENSIDADE_TATAMI_MEDIO,
    }.get(tipo_elemento, DENSIDADE_TATAMI_MEDIO)

    # Underlay por complexidade
    if complexidade < 0.3:
        fator_ul = FATOR_UNDERLAY_SIMPLES
    elif complexidade < 0.6:
        fator_ul = FATOR_UNDERLAY_MEDIO
    else:
        fator_ul = FATOR_UNDERLAY_COMPLEXO

    # ------------------------------------------------------------------
    # ATRIBUIÇÃO EXCLUSIVA: cada pixel → cor mais próxima
    # ------------------------------------------------------------------
    # Máscara global de pixels bordados (não fundo, não transparente)
    if rgb_fundo:
        dist_fundo_global = (
            abs(arr[:,:,0].astype(int) - rgb_fundo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_fundo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_fundo[2]) * 0.114
        )
        mascara_global = (dist_fundo_global > 22) & (arr[:,:,3] > 128)
    else:
        mascara_global = arr[:,:,3] > 128

    # Para cada pixel bordado, calcula distância a cada cor comercial
    # e atribui ao mais próximo
    if len(nomes_cores) == 0:
        return [], fator_ul

    # Mapa de distâncias para cada cor candidata
    dist_maps = []
    for nome in nomes_cores:
        rgb_alvo = PALETA_BORDADO[nome]
        dm = (
            abs(arr[:,:,0].astype(int) - rgb_alvo[0]) * 0.299 +
            abs(arr[:,:,1].astype(int) - rgb_alvo[1]) * 0.587 +
            abs(arr[:,:,2].astype(int) - rgb_alvo[2]) * 0.114
        )
        dist_maps.append(dm)

    # Índice da cor mais próxima para cada pixel
    dist_stack  = np.stack(dist_maps, axis=0)  # (n_cores, h, w)
    idx_mais_prox = np.argmin(dist_stack, axis=0)  # (h, w)

    resultado = []

    for i, nome in enumerate(nomes_cores):
        # Pixels exclusivamente desta cor E dentro da máscara global
        mascara_cor = (idx_mais_prox == i) & mascara_global

        px_cor = int(np.count_nonzero(mascara_cor))
        if px_cor == 0:
            continue

        fracao   = px_cor / (w * h)
        area_cor = area_total_mm2 * fracao

        # Proporção de borda
        px_borda_cor = int(np.count_nonzero(mascara_cor & mascara_borda))
        r_borda = px_borda_cor / px_cor if px_cor > 0 else 0

        # Densidade efetiva
        densidade_eff = (
            densidade_fill * (1 - r_borda) +
            DENSIDADE_SATIN * r_borda
        )

        pontos = int(area_cor * densidade_eff * fator_ul)

        if r_borda > 0.5:
            tipo_stitch = 'Satin / Contorno'
        elif r_borda > 0.25:
            tipo_stitch = 'Satin + Tatami'
        else:
            tipo_stitch = 'Tatami / Preenchimento'

        resultado.append({
            'nome':       nome,
            'rgb':        PALETA_BORDADO[nome],
            'pontos':     pontos,
            'area_mm2':   round(area_cor, 1),
            'r_borda':    round(r_borda, 3),
            'tipo_ponto': tipo_stitch,
            'fracao':     fracao,
        })

    return resultado, fator_ul


# =============================================================================
# QUANTIZAÇÃO DE CORES (melhorada)
# =============================================================================

def quantizar_cores(img_rgba, rgb_fundo=None, n_max=12, min_cobertura=0.015):
    """
    Extrai as cores dominantes do design, ignorando o fundo.
    Retorna lista de nomes de cores comerciais.
    """
    base = Image.new("RGB", img_rgba.size, (255, 255, 255))
    base.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])

    img_q     = base.quantize(colors=n_max, method=Image.Quantize.MEDIANCUT).convert("RGB")
    cores_raw = img_q.getcolors(maxcolors=n_max * 4) or []
    total     = sum(c[0] for c in cores_raw)

    if not total:
        return []

    nomes = []
    for count, rgb in sorted(cores_raw, reverse=True):
        if count / total < min_cobertura:
            continue
        if rgb_fundo and dist_perceptual(rgb, rgb_fundo) < 28:
            continue
        n = nome_cor(rgb)
        if n not in nomes:
            nomes.append(n)

    return nomes


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def analisar_imagem(img_pil, largura_mm, altura_mm,
                    densidade=None, pontos_por_min=850):
    """
    Análise completa de imagem para bordado, calibrada com dados Wilcom.

    O parâmetro 'densidade' agora é usado apenas como multiplicador fino
    (escala de 0.5 a 2.0×) sobre a densidade base calibrada.
    Valor padrão = 1.0 (sem ajuste).

    Args:
        img_pil:       Imagem PIL
        largura_mm:    Largura do bordado
        altura_mm:     Altura do bordado
        densidade:     Ajuste fino (0.5–2.0). None ou 1.0 = sem ajuste.
        pontos_por_min: Velocidade da máquina

    Returns:
        dict com todos os dados da análise
    """
    img_rgba = img_pil.convert('RGBA')
    w, h     = img_rgba.size
    pixels   = list(img_rgba.getdata())

    # Detecção de fundo
    tem_alpha = any(a < 128 for *_, a in pixels)
    if tem_alpha:
        rgb_fundo    = None
        px_validos   = [(r,g,b) for r,g,b,a in pixels if a >= 128]
    else:
        rgb_fundo    = detectar_fundo(img_rgba)
        px_validos   = [
            (r,g,b) for r,g,b,a in pixels
            if not (rgb_fundo and dist_perceptual((r,g,b), rgb_fundo) < 28)
        ]

    if not px_validos:
        return None

    total_px         = w * h
    fator_cobertura  = len(px_validos) / total_px
    area_mm2         = largura_mm * altura_mm

    # Tipo e complexidade
    tipo_elem, razao_borda, complexidade = detectar_tipo_elemento(img_rgba, rgb_fundo)

    # Cores
    nomes_cores = quantizar_cores(img_rgba, rgb_fundo)

    # Pontos por cor
    detalhes_cores, fator_ul = calcular_pontos_por_cor(
        img_rgba, nomes_cores, largura_mm, altura_mm,
        tipo_elem, razao_borda, complexidade, rgb_fundo
    )

    # Ajuste fino pelo parâmetro densidade (mapeado de [3,12] → [0.6,1.5])
    if densidade is not None and densidade != 5.5:
        # 5.5 é o "neutro" do slider antigo
        # Novo: mapeia [3,12] para [0.75, 1.30]
        fator_ajuste = 0.75 + (float(densidade) - 3) / (12 - 3) * 0.55
        for d in detalhes_cores:
            d['pontos'] = int(d['pontos'] * fator_ajuste)

    total_pontos = sum(d['pontos'] for d in detalhes_cores)

    # Bastidor
    lw, lh = largura_mm, altura_mm
    bastidor = (
        '6x6'   if lw <= 60  and lh <= 60  else
        '10x10' if lw <= 100 and lh <= 100 else
        '13x18' if lw <= 130 and lh <= 180 else
        '20x26' if lw <= 200 and lh <= 260 else '30x40'
    )

    # Tempo
    trocas    = max(0, len(detalhes_cores) - 1)
    tempo_min = math.ceil(total_pontos / pontos_por_min + trocas * 2.0)

    return {
        'tipo_elemento':   tipo_elem,
        'razao_borda':     round(razao_borda, 3),
        'complexidade':    round(complexidade, 3),
        'fator_cobertura': round(fator_cobertura * 100, 1),  # em %
        'fator_underlay':  round(fator_ul, 2),
        'total_pontos':    total_pontos,
        'detalhes_cores':  detalhes_cores,
        'sequencia_nomes': ' → '.join(d['nome'] for d in detalhes_cores),
        'n_cores':         len(detalhes_cores),
        'trocas_linha':    trocas,
        'tempo_min':       tempo_min,
        'bastidor':        bastidor,
        'largura_mm':      largura_mm,
        'altura_mm':       altura_mm,
        'rgb_fundo':       rgb_fundo,
    }

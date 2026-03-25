"""
Gerador de arquivo DST (Tajima) corrigido para máquinas RICOMA.

Encoding correto (Tajima spec):

Byte 0:
  0x80: y+1   0x40: y-1
  0x20: x+1   0x10: x-1
  0x08: y+9   0x04: y-9
  0x02: x+9   0x01: x-9

Byte 1:
  0x80: y+27  0x40: y-27
  0x20: x+27  0x10: x-27

Byte 2 (comando):
  0x03 = stitch  0x83 = jump  0xC3 = troca cor  0xF3 = fim

Máximo por stitch = ±(1+9+27) = ±37 unidades = ±3.7mm
Para movimentos maiores: encadeia múltiplos jumps.
"""

import math
import numpy as np
from PIL import Image, ImageFilter


UNIT_MM   = 0.1   # 1 unidade DST = 0.1mm
MAX_DELTA = 37    # máx por stitch: 1+9+27=37

DST_STITCH = 0x03
DST_JUMP   = 0x83
DST_COLOR  = 0xC3
DST_END    = 0xF3


# =============================================================================
# ENCODER CORRETO
# =============================================================================

def encode_stitch(dx, dy, cmd):
    """Codifica um stitch DST com dx, dy em [-37, +37]."""
    b0 = 0
    b1 = 0

    # Eixo Y
    vy = abs(dy)
    if vy >= 27: b1 |= (0x80 if dy > 0 else 0x40); vy -= 27
    if vy >= 9:  b0 |= (0x08 if dy > 0 else 0x04); vy -= 9
    if vy >= 1:  b0 |= (0x80 if dy > 0 else 0x40); vy -= 1

    # Eixo X
    vx = abs(dx)
    if vx >= 27: b1 |= (0x20 if dx > 0 else 0x10); vx -= 27
    if vx >= 9:  b0 |= (0x02 if dx > 0 else 0x01); vx -= 9
    if vx >= 1:  b0 |= (0x20 if dx > 0 else 0x10); vx -= 1

    return bytes([b0, b1, cmd])


def mover_para(x_cur, y_cur, x_dst, y_dst, cmd):
    """Gera stitches para mover de (x_cur,y_cur) a (x_dst,y_dst) em passos de MAX_DELTA."""
    steps = []
    while x_cur != x_dst or y_cur != y_dst:
        dx = max(-MAX_DELTA, min(MAX_DELTA, x_dst - x_cur))
        dy = max(-MAX_DELTA, min(MAX_DELTA, y_dst - y_cur))
        steps.append(encode_stitch(dx, dy, cmd))
        x_cur += dx
        y_cur += dy
    return steps, x_cur, y_cur


# =============================================================================
# PALETA E DETECÇÃO DE COR
# =============================================================================

PALETA = {
    "Preto":        (0,0,0),       "Branco":       (255,255,255),
    "Vermelho":     (200,0,0),     "Azul":         (0,80,200),
    "Verde":        (0,150,0),     "Amarelo":      (255,220,0),
    "Laranja":      (255,120,0),   "Rosa":         (230,100,140),
    "Cinza":        (140,140,140), "Marrom":       (120,70,30),
    "Roxo":         (130,0,170),   "Turquesa":     (0,160,180),
    "Bege":         (220,190,150), "Dourado":      (200,150,20),
    "Cinza Escuro": (70,70,70),    "Cinza Claro":  (200,200,200),
}


def _dist(a, b):
    return math.sqrt(((a[0]-b[0])*.299)**2 + ((a[1]-b[1])*.587)**2 + ((a[2]-b[2])*.114)**2)


def _nome_cor(rgb):
    return min(PALETA, key=lambda n: _dist(rgb, PALETA[n]))


def _detectar_fundo(arr_rgba, margem=0.05):
    h, w = arr_rgba.shape[:2]
    m    = max(2, int(min(w, h) * margem))
    borda_pixels = np.concatenate([
        arr_rgba[:m, :, :3].reshape(-1, 3),
        arr_rgba[-m:, :, :3].reshape(-1, 3),
        arr_rgba[:, :m, :3].reshape(-1, 3),
        arr_rgba[:, -m:, :3].reshape(-1, 3),
    ])
    borda_alpha = np.concatenate([
        arr_rgba[:m, :, 3].flatten(), arr_rgba[-m:, :, 3].flatten(),
        arr_rgba[:, :m, 3].flatten(), arr_rgba[:, -m:, 3].flatten(),
    ])
    validos = borda_pixels[borda_alpha > 128]
    if len(validos) == 0:
        return (255, 255, 255)
    q = (validos // 15 * 15)
    uniq, counts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in uniq[counts.argmax()])


# =============================================================================
# FILL TATAMI
# =============================================================================

def _gerar_fill(mask, esc_x_mm, esc_y_mm, esp_mm=0.45, stitch_mm=0.35):
    """
    Gera pontos de fill em ziguezague.
    Retorna lista de (x, y) em unidades DST absolutas.
    """
    h, w      = mask.shape
    esp_px    = max(1, int(esp_mm    / esc_y_mm))
    stitch_px = max(1, int(stitch_mm / esc_x_mm))
    pontos    = []
    direcao   = 1

    for row in range(0, h, esp_px):
        cols = np.where(mask[row, :])[0]
        if len(cols) == 0:
            continue

        grupos = []
        ini, prev = int(cols[0]), int(cols[0])
        for c in cols[1:]:
            c = int(c)
            if c - prev > 4:
                grupos.append((ini, prev))
                ini = c
            prev = c
        grupos.append((ini, prev))

        seq = grupos if direcao == 1 else list(reversed(grupos))
        y_u = int(round(row * esc_y_mm / UNIT_MM))

        for (c_ini, c_fim) in seq:
            rng = range(c_ini, c_fim + 1, stitch_px) if direcao == 1 \
                  else range(c_fim, c_ini - 1, -stitch_px)
            for c in rng:
                x_u = int(round(c * esc_x_mm / UNIT_MM))
                pontos.append((x_u, y_u))

        direcao *= -1

    return pontos


# =============================================================================
# GERADOR PRINCIPAL
# =============================================================================

def imagem_para_dst(img_pil, largura_mm, altura_mm, descricao="PONTO", rgb_fundo=None):
    """
    Converte imagem PIL em bytes DST para RICOMA/Tajima.
    Retorna bytes ou None se falhar.
    """
    img_rgba = img_pil.convert('RGBA')
    w, h     = img_rgba.size
    if w == 0 or h == 0 or largura_mm <= 0 or altura_mm <= 0:
        return None

    esc_x = largura_mm / w   # mm por pixel em X
    esc_y = altura_mm  / h   # mm por pixel em Y

    arr = np.array(img_rgba)

    # Detectar fundo
    tem_alpha = (arr[:, :, 3] < 128).any()
    if rgb_fundo is None and not tem_alpha:
        rgb_fundo = _detectar_fundo(arr)

    # Quantizar para separar cores
    base = Image.new("RGB", img_rgba.size, (255, 255, 255))
    base.paste(img_rgba.convert("RGB"), mask=img_rgba.split()[3])
    n_max = 8
    img_q  = base.quantize(colors=n_max, method=Image.Quantize.MEDIANCUT)
    arr_q  = np.array(img_q)

    regioes = []
    for idx in np.unique(arr_q):
        mask = (arr_q == idx)
        if not np.any(mask):
            continue
        pixels_rgb = arr[:, :, :3][mask]
        media_rgb  = tuple(int(v) for v in pixels_rgb.mean(axis=0))

        if rgb_fundo and _dist(media_rgb, rgb_fundo) < 35:
            continue
        if arr[:, :, 3][mask].mean() < 64:
            continue
        if mask.sum() / (w * h) < 0.005:
            continue

        regioes.append((mask, _nome_cor(media_rgb)))

    if not regioes:
        return None

    # Gera bytes de stitches
    all_bytes = bytearray()
    x_cur = y_cur = 0
    x_min = x_max = y_min = y_max = 0
    n_stitches = n_colors = 0

    for i, (mask, _nome) in enumerate(regioes):
        pontos = _gerar_fill(mask, esc_x, esc_y)
        if not pontos:
            continue

        # Jump até o primeiro ponto
        steps, x_cur, y_cur = mover_para(x_cur, y_cur, *pontos[0], DST_JUMP)
        for s in steps:
            all_bytes += s

        # Stitches de fill
        for xp, yp in pontos[1:]:
            dist_mm = math.sqrt(((xp - x_cur) * UNIT_MM)**2 + ((yp - y_cur) * UNIT_MM)**2)
            cmd     = DST_STITCH if dist_mm <= 12.0 else DST_JUMP
            steps, x_cur, y_cur = mover_para(x_cur, y_cur, xp, yp, cmd)
            for s in steps:
                all_bytes += s
            if cmd == DST_STITCH:
                n_stitches += 1
            x_min = min(x_min, x_cur); x_max = max(x_max, x_cur)
            y_min = min(y_min, y_cur); y_max = max(y_max, y_cur)

        # Troca de cor (não na última)
        if i < len(regioes) - 1:
            all_bytes += encode_stitch(0, 0, DST_COLOR)
            n_colors += 1

    # Fim
    all_bytes += encode_stitch(0, 0, DST_END)

    # ===========================================================================
    # Header DST — 512 bytes
    # Campos de dimensão são em unidades DST (0.1mm)
    # ===========================================================================
    nome_h = (descricao[:16] + ' ' * 16)[:16]

    header = (
        f"LA:{nome_h}    "
        f"ST:{n_stitches:<7d}"
        f"CO:{n_colors:<3d}"
        f"+X:{x_max:<6d}"
        f"-X:{abs(x_min):<6d}"
        f"+Y:{y_max:<6d}"
        f"-Y:{abs(y_min):<6d}"
        f"AX:{0:<6d}"
        f"AY:{0:<6d}"
        f"MX:{0:<6d}"
        f"MY:{0:<6d}"
        f"PD:******"
    )
    hb = header.encode('ascii', errors='replace')
    # Header deve ter exatamente 512 bytes, terminado com 0x1a
    hb = (hb + b' ' * 512)[:511] + b'\x1a'

    return bytes(hb) + bytes(all_bytes)


# =============================================================================
# INTERFACE COM DJANGO
# =============================================================================

def gerar_dst_da_matriz(matriz_obj):
    """Gera DST de um MatrizBordado Django. Retorna (bytes, nome) ou (None, None)."""
    if not matriz_obj.imagem_original:
        return None, None
    try:
        img = Image.open(matriz_obj.imagem_original.path)
        lw  = float(matriz_obj.largura_mm)
        lh  = float(matriz_obj.altura_mm)
        if lw <= 0 or lh <= 0:
            return None, None

        dst = imagem_para_dst(img, lw, lh, descricao=matriz_obj.descricao[:16])
        if not dst:
            return None, None

        nome = (matriz_obj.descricao[:20]
                .replace(' ', '_').replace('/', '_').replace('\\', '_')) + '.dst'
        return dst, nome
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None

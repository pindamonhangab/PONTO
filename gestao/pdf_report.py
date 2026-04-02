"""
Gerador de relatório PDF profissional de bordado, estilo Wilcom EmbroideryStudio.

Requer: pip install reportlab pillow
"""

import io
import math

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.platypus import Image as RLImage


# =============================================================================
# CORES
# =============================================================================

COR_PRIMARIA = HexColor('#DC3545')
COR_ESCURA   = HexColor('#212529')
COR_MEDIA    = HexColor('#6C757D')
COR_CLARA    = HexColor('#F8F9FA')
COR_BORDA    = HexColor('#DEE2E6')


def rgb_to_hex(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


# =============================================================================
# CABEÇALHO / RODAPÉ
# =============================================================================

def _desenhar_pagina(canvas_obj, doc, titulo='Relatório de Bordado', subtitulo=''):
    w, h = A4

    canvas_obj.setFillColor(COR_PRIMARIA)
    canvas_obj.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)

    canvas_obj.setFillColor(white)
    canvas_obj.setFont('Helvetica-Bold', 14)
    canvas_obj.drawString(15*mm, h - 12*mm, 'PONTO')
    canvas_obj.setFont('Helvetica', 10)
    canvas_obj.drawRightString(w - 15*mm, h - 12*mm, 'Sistema de Gestão de Bordados')

    canvas_obj.setFillColor(COR_ESCURA)
    canvas_obj.setFont('Helvetica-Bold', 10)
    canvas_obj.drawString(15*mm, h - 24*mm, titulo)
    if subtitulo:
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(COR_MEDIA)
        canvas_obj.drawString(15*mm, h - 30*mm, subtitulo)

    canvas_obj.setStrokeColor(COR_BORDA)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(15*mm, h - 33*mm, w - 15*mm, h - 33*mm)

    canvas_obj.setFillColor(COR_MEDIA)
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.drawString(15*mm, 10*mm, 'Gerado pelo sistema PONTO — Gestão de Bordados')
    canvas_obj.drawRightString(w - 15*mm, 10*mm, f'Pág. {canvas_obj.getPageNumber()}')
    canvas_obj.setStrokeColor(COR_BORDA)
    canvas_obj.line(15*mm, 14*mm, w - 15*mm, 14*mm)


# =============================================================================
# GERADOR PRINCIPAL
# =============================================================================

def gerar_pdf_bordado(analise, config=None, imagem_path=None, nome_design='Design'):
    """
    Gera relatório PDF completo.

    Args:
        analise:      dict de analisar_imagem() — fator_cobertura é FRAÇÃO 0.0-1.0
        config:       objeto ConfiguracaoBordado
        imagem_path:  caminho da imagem original
        nome_design:  nome do bordado

    Returns:
        bytes do PDF
    """
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=38*mm, bottomMargin=20*mm,
    )

    styles      = getSampleStyleSheet()
    estilo_tit  = ParagraphStyle('Tit',  fontSize=13, fontName='Helvetica-Bold',
                                  textColor=COR_ESCURA, spaceBefore=6*mm, spaceAfter=3*mm)
    estilo_sub  = ParagraphStyle('Sub',  fontSize=10, fontName='Helvetica-Bold',
                                  textColor=COR_MEDIA, spaceAfter=2*mm)
    estilo_norm = ParagraphStyle('Norm', fontSize=9,  fontName='Helvetica',
                                  textColor=COR_ESCURA, leading=14)

    story = []

    # ── Dados básicos ────────────────────────────────────────────────────────
    total_pontos = analise.get('total_pontos', 0)
    lw           = analise.get('largura_mm', 0)
    lh           = analise.get('altura_mm',  0)
    bastidor     = analise.get('bastidor',   '—')
    tempo_min    = analise.get('tempo_min',  0)
    n_cores      = analise.get('n_cores',    0)
    trocas       = analise.get('trocas_linha', 0)
    detalhes     = analise.get('detalhes_cores', [])

    # fator_cobertura é FRAÇÃO 0.0-1.0 → multiplica por 100 para exibir
    cob_frac = analise.get('fator_cobertura', 0)
    cob_pct  = cob_frac * 100   # ex: 0.64 → 64.0

    dens_ef  = analise.get('densidade_efetiva', 0)
    tipo_elem = analise.get('tipo_elemento', 'logo')

    valor_bordado = 0.0
    if config:
        try:
            valor_bordado = (total_pontos / 1000) * float(config.valor_mil_pontos)
        except Exception:
            pass

    tipo_label = {
        'texto':         'Bordado de Texto / Lettering',
        'icone_simples': 'Ícone / Símbolo',
        'logo':          'Logo / Composição',
        'brasao':        'Brasão / Composição Complexa',
    }.get(tipo_elem, 'Logo / Composição')

    # ── Cabeçalho do design ──────────────────────────────────────────────────
    story.append(Paragraph(nome_design, ParagraphStyle(
        'Nome', fontSize=18, fontName='Helvetica-Bold',
        textColor=COR_PRIMARIA, spaceAfter=1*mm,
    )))
    story.append(Paragraph(tipo_label, estilo_sub))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA, spaceAfter=4*mm))

    # ── Imagem + Resumo ──────────────────────────────────────────────────────
    resumo_data = [
        ['Campo', 'Valor'],
        ['Tamanho',             f'{lw:.1f} × {lh:.1f} mm'],
        ['Bastidor',            bastidor],
        ['Total de Pontos',     f'{total_pontos:,}'.replace(',', '.')],
        ['Número de Cores',     str(n_cores)],
        ['Trocas de Linha',     str(trocas)],
        ['Tempo Estimado',      f'{tempo_min} min'],
        ['Tipo de Elemento',    tipo_label],
        ['Cobertura da Imagem', f'{cob_pct:.0f}%'],        # fração × 100
        ['Densidade Efetiva',   f'{dens_ef:.2f} pts/mm²'],
        ['Custo do Bordado',    f'R$ {valor_bordado:.2f}'],
    ]

    resumo_table = Table(resumo_data, colWidths=[55*mm, 55*mm])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND',     (0,0), (-1,0), COR_PRIMARIA),
        ('TEXTCOLOR',      (0,0), (-1,0), white),
        ('FONTNAME',       (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',       (0,0), (-1,-1), 8),
        ('FONTNAME',       (0,1), (0,-1), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, COR_CLARA]),
        ('GRID',           (0,0), (-1,-1), 0.3, COR_BORDA),
        ('TOPPADDING',     (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 4),
        ('LEFTPADDING',    (0,0), (-1,-1), 6),
        ('ALIGN',          (1,0), (1,-1), 'RIGHT'),
    ]))

    esq = []
    if imagem_path:
        try:
            esq.append(RLImage(imagem_path, width=60*mm, height=60*mm, kind='proportional'))
        except Exception:
            pass

    if esq:
        layout = Table([[esq[0], resumo_table]], colWidths=[70*mm, 110*mm])
        layout.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 5*mm),
        ]))
        story.append(layout)
    else:
        story.append(resumo_table)

    story.append(Spacer(1, 6*mm))

    # ── Paleta de cores ──────────────────────────────────────────────────────
    story.append(Paragraph('Paleta de Cores', estilo_tit))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    if detalhes:
        header = [
            Paragraph('<b>Ord.</b>', estilo_norm),
            Paragraph('<b>Cor</b>',  estilo_norm),
            Paragraph('<b>Nome</b>', estilo_norm),
            Paragraph('<b>Tipo Ponto</b>', estilo_norm),
            Paragraph('<b>Pontos</b>', estilo_norm),
            Paragraph('<b>%</b>',    estilo_norm),
            Paragraph('<b>Área mm²</b>', estilo_norm),
            Paragraph('<b>Tempo</b>', estilo_norm),
        ]
        rows = [header]

        for i, d in enumerate(detalhes, 1):
            rgb     = d.get('rgb', (0, 0, 0))
            hex_cor = rgb_to_hex(rgb)
            pts_d   = d.get('pontos', 0)
            pct     = pts_d / total_pontos * 100 if total_pontos else 0
            area    = d.get('area_mm2', 0)
            t_d     = math.ceil(pts_d / total_pontos * tempo_min) if total_pontos else 0

            swatch = Paragraph(
                f'<font color="{hex_cor}">████</font>',
                ParagraphStyle('Sw', fontSize=12, leading=14)
            )
            rows.append([
                Paragraph(str(i), estilo_norm),
                swatch,
                Paragraph(d.get('nome', '—'), estilo_norm),
                Paragraph(d.get('tipo_ponto', '—'), estilo_norm),
                Paragraph(f"{pts_d:,}".replace(',', '.'), estilo_norm),
                Paragraph(f'{pct:.1f}%', estilo_norm),
                Paragraph(f'{area:.1f}', estilo_norm),
                Paragraph(f'~{t_d} min', estilo_norm),
            ])

        tab_cores = Table(rows, colWidths=[12*mm, 12*mm, 38*mm, 42*mm, 24*mm, 12*mm, 18*mm, 20*mm])
        tab_cores.setStyle(TableStyle([
            ('BACKGROUND',     (0,0), (-1,0), COR_ESCURA),
            ('TEXTCOLOR',      (0,0), (-1,0), white),
            ('FONTSIZE',       (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, COR_CLARA]),
            ('GRID',           (0,0), (-1,-1), 0.3, COR_BORDA),
            ('TOPPADDING',     (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',  (0,0), (-1,-1), 4),
            ('LEFTPADDING',    (0,0), (-1,-1), 5),
            ('ALIGN',          (4,0), (7,-1), 'RIGHT'),
        ]))
        story.append(tab_cores)
    else:
        story.append(Paragraph('Nenhuma cor detectada.', estilo_norm))

    story.append(Spacer(1, 6*mm))

    # ── Sequência de operação ────────────────────────────────────────────────
    story.append(Paragraph('Sequência de Operação', estilo_tit))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    seq = [['Passo', 'Operação', 'Cor', 'Detalhe']]
    passo = 1
    for i, d in enumerate(detalhes):
        if i == 0:
            seq.append([str(passo), 'Início / Posicionar', d['nome'], 'Levar ao ponto inicial'])
            passo += 1
        seq.append([str(passo), 'Bordar', d['nome'],
                    f"{d['pontos']:,} pts · {d['tipo_ponto']}".replace(',', '.')])
        passo += 1
        if i < len(detalhes) - 1:
            prox = detalhes[i+1]
            seq.append([str(passo), 'Troca de Linha', prox['nome'],
                        f"Retirar {d['nome']} → colocar {prox['nome']}"])
            passo += 1
    seq.append([str(passo), 'Finalizar', '—', 'Cortar linhas e remover do bastidor'])

    tab_seq = Table(seq, colWidths=[14*mm, 36*mm, 40*mm, 92*mm])
    tab_seq.setStyle(TableStyle([
        ('BACKGROUND',     (0,0), (-1,0), COR_ESCURA),
        ('TEXTCOLOR',      (0,0), (-1,0), white),
        ('FONTNAME',       (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',       (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, COR_CLARA]),
        ('GRID',           (0,0), (-1,-1), 0.3, COR_BORDA),
        ('TOPPADDING',     (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 4),
        ('LEFTPADDING',    (0,0), (-1,-1), 5),
        ('ALIGN',          (0,0), (0,-1), 'CENTER'),
    ]))
    story.append(tab_seq)
    story.append(Spacer(1, 6*mm))

    # ── Instruções técnicas ──────────────────────────────────────────────────
    story.append(Paragraph('Instruções e Recomendações Técnicas', estilo_tit))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    recs = [f'• Bastidor recomendado: <b>{bastidor}</b>. Centralizar com tensão uniforme.']

    if tipo_elem == 'texto':
        recs += [
            '• Texto detectado. Agulha 75/11 ou 80/12 para melhor definição.',
            '• Estabilizador médio gramatura (70–90 g/m²).',
            '• Para letras menores que 5mm, reduza a velocidade.',
        ]
    elif tipo_elem == 'icone_simples':
        recs += [
            '• Ícone simples. Agulha 75/11 é suficiente.',
            '• Estabilizador leve (50–70 g/m²) para tecidos finos.',
        ]
    elif tipo_elem == 'brasao':
        recs += [
            '• Brasão complexo. Agulha 80/12 para equilíbrio de velocidade e qualidade.',
            '• Estabilizador médio (70–90 g/m²). Em elásticos, prefira estabilizador de corte.',
        ]
    else:
        recs += [
            '• Logo padrão. Agulha 80/12 recomendada.',
            '• Estabilizador médio (70–90 g/m²).',
        ]

    recs.append('• Tensão do fio: ajustar para médio. Verifique a bobina antes de iniciar.')
    recs.append('• Velocidade sugerida: 700–900 ppm para melhor acabamento.')

    if total_pontos > 30000:
        recs.append('• Design complexo (+30k pts). Monitore o aquecimento da cabeça.')
    if lw > 200 or lh > 200:
        recs.append('• Design grande. Verifique a fixação do bastidor durante a execução.')

    for rec in recs:
        story.append(Paragraph(rec, estilo_norm))
        story.append(Spacer(1, 1*mm))

    story.append(Spacer(1, 4*mm))

    # ── Orçamento ────────────────────────────────────────────────────────────
    if config and valor_bordado > 0:
        story.append(Paragraph('Orçamento', estilo_tit))
        story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

        orc = Table(
            [
                ['Item', 'Detalhe', 'Valor'],
                ['Bordado',
                 f"{total_pontos:,} pts × R$ {config.valor_mil_pontos}/1.000 pts".replace(',', '.'),
                 f'R$ {valor_bordado:.2f}'],
            ],
            colWidths=[40*mm, 110*mm, 32*mm],
        )
        orc.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), COR_PRIMARIA),
            ('TEXTCOLOR',     (0,0), (-1,0), white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('GRID',          (0,0), (-1,-1), 0.3, COR_BORDA),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
            ('ALIGN',         (2,0), (2,-1), 'RIGHT'),
        ]))
        story.append(orc)

    # ── Build ────────────────────────────────────────────────────────────────
    def _primeira(c, d):
        _desenhar_pagina(c, d,
            titulo=f'Relatório de Bordado — {nome_design}',
            subtitulo=f'{lw:.0f}×{lh:.0f}mm · {total_pontos:,} pontos · {n_cores} cores'.replace(',', '.'),
        )

    def _seguintes(c, d):
        _desenhar_pagina(c, d, titulo=f'Relatório — {nome_design} (cont.)')

    doc.build(story, onFirstPage=_primeira, onLaterPages=_seguintes)
    buffer.seek(0)
    return buffer.read()


# =============================================================================
# INTERFACE COM DJANGO
# =============================================================================

def gerar_pdf_da_matriz(matriz_obj, config=None):
    """
    Gera PDF a partir de um objeto MatrizBordado do Django.
    Retorna (bytes, nome_arquivo) ou (None, None).
    """
    try:
        import os, sys
        from django.conf import settings as dj_settings
        gestao_dir = os.path.join(dj_settings.BASE_DIR, 'gestao')
        if gestao_dir not in sys.path:
            sys.path.insert(0, gestao_dir)

        from analise_avancada import analisar_imagem
        from PIL import Image as PILImage

        img_path = None
        analise  = None

        if matriz_obj.imagem_original:
            img_path = matriz_obj.imagem_original.path
            img      = PILImage.open(img_path)
            analise  = analisar_imagem(
                img_pil=img,
                largura_mm=float(matriz_obj.largura_mm),
                altura_mm=float(matriz_obj.altura_mm),
                densidade=float(matriz_obj.densidade_escolhida),
                pontos_por_min=matriz_obj.pontos_por_minuto,
            )

        if not analise:
            # Fallback com dados do model — fator_cobertura como fração
            n_cores_fb = max(1, matriz_obj.mudancas_cores + 1)
            pts_fb     = matriz_obj.quantidade_pontos
            analise = {
                'tipo_elemento':     'logo',
                'fator_cobertura':   0.5,          # fração
                'densidade_escolhida': 5.5,
                'densidade_efetiva': 2.59,
                'total_pontos':      pts_fb,
                'detalhes_cores': [
                    {
                        'nome':       c.strip() or '—',
                        'rgb':        (100, 100, 100),
                        'pontos':     pts_fb // n_cores_fb,
                        'area_mm2':   0,
                        'r_borda':    0.2,
                        'tipo_ponto': 'Tatami / Preenchimento',
                    }
                    for c in (matriz_obj.sequencia_cores or '—').split('→')[:n_cores_fb]
                ],
                'sequencia_nomes': matriz_obj.sequencia_cores or '—',
                'n_cores':         n_cores_fb,
                'trocas_linha':    matriz_obj.mudancas_cores,
                'tempo_min':       int((matriz_obj.tempo_estimado or '0 min').replace(' min', '') or 0),
                'bastidor':        matriz_obj.bastidor_recomendado or '—',
                'largura_mm':      float(matriz_obj.largura_mm),
                'altura_mm':       float(matriz_obj.altura_mm),
                'rgb_fundo':       None,
                'mascara_aplicada': False,
            }

        pdf_bytes = gerar_pdf_bordado(
            analise=analise,
            config=config,
            imagem_path=img_path,
            nome_design=matriz_obj.descricao,
        )

        nome = f"{matriz_obj.descricao[:30].replace(' ', '_')}_relatorio.pdf"
        return pdf_bytes, nome

    except Exception as e:
        import traceback
        print(f'[pdf_report] Erro: {e}')
        traceback.print_exc()
        return None, None

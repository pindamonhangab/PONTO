"""
Gerador de relatório PDF profissional de bordado, estilo Wilcom EmbroideryStudio.

Requer: pip install reportlab pillow
"""

import io
import math
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import (
    HexColor, white, black, Color,
    red, green, gray, lightgrey
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import Image as RLImage
from reportlab.pdfgen import canvas


# =============================================================================
# CORES DO SISTEMA
# =============================================================================

COR_PRIMARIA  = HexColor('#DC3545')
COR_ESCURA    = HexColor('#212529')
COR_MEDIA     = HexColor('#6C757D')
COR_CLARA     = HexColor('#F8F9FA')
COR_BORDA     = HexColor('#DEE2E6')
COR_SUCESSO   = HexColor('#198754')
COR_AVISO     = HexColor('#FFC107')


def rgb_to_hex(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


def _cor_texto_sobre(rgb):
    """Determina se texto deve ser branco ou preto sobre a cor de fundo."""
    r, g, b = rgb
    luminancia = 0.299*r + 0.587*g + 0.114*b
    return white if luminancia < 128 else black


# =============================================================================
# PÁGINA COM CABEÇALHO/RODAPÉ
# =============================================================================

def _desenhar_pagina(canvas_obj, doc, titulo="Relatório de Bordado", subtitulo=""):
    """Desenha cabeçalho e rodapé em cada página."""
    w, h = A4

    # Faixa vermelha no topo
    canvas_obj.setFillColor(COR_PRIMARIA)
    canvas_obj.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)

    # Logo PONTO (texto)
    canvas_obj.setFillColor(white)
    canvas_obj.setFont("Helvetica-Bold", 14)
    canvas_obj.drawString(15*mm, h - 12*mm, "🧵 PONTO")

    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawRightString(w - 15*mm, h - 12*mm, "Sistema de Gestão de Bordados")

    # Título da seção
    canvas_obj.setFillColor(COR_ESCURA)
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(15*mm, h - 24*mm, titulo)
    if subtitulo:
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.setFillColor(COR_MEDIA)
        canvas_obj.drawString(15*mm, h - 30*mm, subtitulo)

    # Linha divisória
    canvas_obj.setStrokeColor(COR_BORDA)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(15*mm, h - 33*mm, w - 15*mm, h - 33*mm)

    # Rodapé
    canvas_obj.setFillColor(COR_MEDIA)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(15*mm, 10*mm, "Gerado pelo sistema PONTO — Gestão de Bordados")
    canvas_obj.drawRightString(w - 15*mm, 10*mm, f"Pág. {canvas_obj.getPageNumber()}")
    canvas_obj.setStrokeColor(COR_BORDA)
    canvas_obj.line(15*mm, 14*mm, w - 15*mm, 14*mm)


# =============================================================================
# GERADOR PRINCIPAL
# =============================================================================

def gerar_pdf_bordado(analise, config=None, imagem_path=None, nome_design="Design"):
    """
    Gera relatório PDF completo.

    Args:
        analise:      dict retornado por analise_avancada.analisar_imagem()
        config:       objeto ConfiguracaoBordado (para valor/1k pontos)
        imagem_path:  caminho para a imagem original
        nome_design:  nome do bordado

    Returns:
        bytes: conteúdo do arquivo PDF
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=38*mm, bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()

    # Estilos personalizados
    titulo_estilo = ParagraphStyle('TituloSec',
        fontSize=13, fontName='Helvetica-Bold',
        textColor=COR_ESCURA, spaceBefore=6*mm, spaceAfter=3*mm)

    subtit_estilo = ParagraphStyle('SubTit',
        fontSize=10, fontName='Helvetica-Bold',
        textColor=COR_MEDIA, spaceAfter=2*mm)

    normal_estilo = ParagraphStyle('NormalPonto',
        fontSize=9, fontName='Helvetica',
        textColor=COR_ESCURA, leading=14)

    story = []

    # ------------------------------------------------------------------
    # SEÇÃO 1 — CABEÇALHO DO DESIGN
    # ------------------------------------------------------------------
    story.append(Paragraph(nome_design, ParagraphStyle(
        'NomeDesign', fontSize=18, fontName='Helvetica-Bold',
        textColor=COR_PRIMARIA, spaceAfter=1*mm
    )))

    tipo_label = {
        'texto': 'Bordado de Texto / Lettering',
        'icone': 'Ícone / Símbolo',
        'logo':  'Logo / Composição',
    }.get(analise.get('tipo_elemento','logo'), 'Logo / Composição')

    story.append(Paragraph(tipo_label, subtit_estilo))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=4*mm))

    # ------------------------------------------------------------------
    # SEÇÃO 2 — IMAGEM + RESUMO LADO A LADO
    # ------------------------------------------------------------------
    esq_items = []

    if imagem_path:
        try:
            img_rl = RLImage(imagem_path, width=60*mm, height=60*mm, kind='proportional')
            esq_items.append(img_rl)
        except Exception:
            pass

    # Resumo rápido
    total_pontos = analise.get('total_pontos', 0)
    lw           = analise.get('largura_mm', 0)
    lh           = analise.get('altura_mm',  0)
    bastidor     = analise.get('bastidor',   '—')
    tempo_min    = analise.get('tempo_min',  0)
    n_cores      = analise.get('n_cores',    0)
    trocas       = analise.get('trocas_linha', 0)

    valor_bordado = 0.0
    if config:
        try:
            valor_bordado = (total_pontos / 1000) * float(config.valor_mil_pontos)
        except Exception:
            pass

    resumo_data = [
        ['Campo',                'Valor'],
        ['Tamanho',              f'{lw:.1f} × {lh:.1f} mm'],
        ['Bastidor',             bastidor],
        ['Total de Pontos',      f'{total_pontos:,}'.replace(',', '.')],
        ['Número de Cores',      str(n_cores)],
        ['Trocas de Linha',      str(trocas)],
        ['Tempo Estimado',       f'{tempo_min} min'],
        ['Tipo de Elemento',     tipo_label],
        ['Cobertura da Imagem',  f"{analise.get('fator_cobertura',0)*100:.0f}%"],
        ['Fator Underlay',       f"{analise.get('fator_underlay',1.20):.2f}×"],
        ['Custo do Bordado',     f'R$ {valor_bordado:.2f}'],
    ]

    resumo_table = Table(resumo_data, colWidths=[55*mm, 55*mm])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), COR_PRIMARIA),
        ('TEXTCOLOR',   (0,0), (-1,0), white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,-1), 8),
        ('FONTNAME',    (0,1), (0,-1), 'Helvetica-Bold'),
        ('BACKGROUND',  (0,1), (-1,-1), white),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, COR_CLARA]),
        ('GRID',        (0,0), (-1,-1), 0.3, COR_BORDA),
        ('TOPPADDING',  (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('ALIGN',       (1,0), (1,-1), 'RIGHT'),
    ]))

    # Layout 2 colunas: imagem | resumo
    if imagem_path and esq_items:
        layout = Table(
            [[esq_items[0], resumo_table]],
            colWidths=[70*mm, 110*mm]
        )
        layout.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 5*mm),
        ]))
        story.append(layout)
    else:
        story.append(resumo_table)

    story.append(Spacer(1, 6*mm))

    # ------------------------------------------------------------------
    # SEÇÃO 3 — PALETA DE CORES COM SWATCHES
    # ------------------------------------------------------------------
    story.append(Paragraph("Paleta de Cores", titulo_estilo))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    detalhes = analise.get('detalhes_cores', [])

    if detalhes:
        # Cabeçalho
        cores_header = [
            Paragraph('<b>Ordem</b>', normal_estilo),
            Paragraph('<b>Cor</b>', normal_estilo),
            Paragraph('<b>Nome</b>', normal_estilo),
            Paragraph('<b>Tipo Ponto</b>', normal_estilo),
            Paragraph('<b>Pontos</b>', normal_estilo),
            Paragraph('<b>%</b>', normal_estilo),
            Paragraph('<b>Área (mm²)</b>', normal_estilo),
            Paragraph('<b>Tempo (min)</b>', normal_estilo),
        ]
        cores_rows = [cores_header]

        for i, d in enumerate(detalhes, 1):
            rgb       = d.get('rgb', (0,0,0))
            hex_cor   = rgb_to_hex(rgb)
            pontos_d  = d.get('pontos', 0)
            pct       = (pontos_d / total_pontos * 100) if total_pontos else 0
            area      = d.get('area_mm2', 0)
            tempo_d   = math.ceil(pontos_d / max(1, analise.get('total_pontos',1)) *
                                  analise.get('tempo_min', 1))

            # Swatch de cor (parágrafo com fundo colorido)
            swatch = Paragraph(
                f'<font color="{hex_cor}">████</font>',
                ParagraphStyle('Sw', fontSize=12, leading=14)
            )

            cores_rows.append([
                Paragraph(str(i), normal_estilo),
                swatch,
                Paragraph(d.get('nome','—'), normal_estilo),
                Paragraph(d.get('tipo_ponto','—'), normal_estilo),
                Paragraph(f"{pontos_d:,}".replace(',','.'), normal_estilo),
                Paragraph(f"{pct:.1f}%", normal_estilo),
                Paragraph(f"{area:.1f}", normal_estilo),
                Paragraph(f"~{tempo_d}", normal_estilo),
            ])

        tabela_cores = Table(
            cores_rows,
            colWidths=[12*mm, 12*mm, 38*mm, 42*mm, 24*mm, 14*mm, 20*mm, 20*mm]
        )
        tabela_cores.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), COR_ESCURA),
            ('TEXTCOLOR',     (0,0), (-1,0), white),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [white, COR_CLARA]),
            ('GRID',          (0,0), (-1,-1), 0.3, COR_BORDA),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 5),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('ALIGN',         (4,0), (7,-1), 'RIGHT'),
        ]))
        story.append(tabela_cores)
    else:
        story.append(Paragraph("Nenhuma cor detectada.", normal_estilo))

    story.append(Spacer(1, 6*mm))

    # ------------------------------------------------------------------
    # SEÇÃO 4 — SEQUÊNCIA DE OPERAÇÃO
    # ------------------------------------------------------------------
    story.append(Paragraph("Sequência de Operação", titulo_estilo))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    seq_data = [['Passo', 'Operação', 'Cor', 'Detalhe']]
    passo = 1

    for i, d in enumerate(detalhes):
        if i == 0:
            seq_data.append([str(passo), 'Início / Posicionar', d['nome'], 'Levar a máquina ao ponto inicial'])
            passo += 1

        seq_data.append([str(passo), 'Bordar', d['nome'],
                         f"{d['pontos']:,} pts · {d['tipo_ponto']}".replace(',','.')])
        passo += 1

        if i < len(detalhes) - 1:
            prox = detalhes[i+1]
            seq_data.append([str(passo), 'Troca de Linha', prox['nome'],
                             f"Retirar {d['nome']} → colocar {prox['nome']}"])
            passo += 1

    seq_data.append([str(passo), 'Finalizar', '—', 'Cortar linhas e remover do bastidor'])

    tabela_seq = Table(seq_data, colWidths=[14*mm, 36*mm, 40*mm, 92*mm])
    tabela_seq.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), COR_ESCURA),
        ('TEXTCOLOR',     (0,0), (-1,0), white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [white, COR_CLARA]),
        ('GRID',          (0,0), (-1,-1), 0.3, COR_BORDA),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 5),
        ('ALIGN',         (0,0), (0,-1), 'CENTER'),
    ]))
    story.append(tabela_seq)
    story.append(Spacer(1, 6*mm))

    # ------------------------------------------------------------------
    # SEÇÃO 5 — INSTRUÇÕES TÉCNICAS
    # ------------------------------------------------------------------
    story.append(Paragraph("Instruções e Recomendações Técnicas", titulo_estilo))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

    # Recomendações baseadas no tipo e tamanho
    recomendacoes = []

    recomendacoes.append(f"• Bastidor recomendado: <b>{bastidor}</b>. Centralizar o tecido com tensão uniforme.")

    if analise.get('tipo_elemento') == 'texto':
        recomendacoes.append("• Elemento de texto detectado. Use agulha tamanho 75/11 ou 80/12 para melhor definição.")
        recomendacoes.append("• Recomendado estabilizador de médio gramatura (70–90 g/m²) por baixo do tecido.")
        recomendacoes.append("• Para letras menores que 5mm de altura, reduza a velocidade da máquina.")
    elif analise.get('tipo_elemento') == 'icone':
        recomendacoes.append("• Ícone simples. Agulha 75/11 é suficiente.")
        recomendacoes.append("• Estabilizador leve (50–70 g/m²) para malhas e tecidos finos.")
    else:
        recomendacoes.append("• Logo com múltiplos elementos. Agulha 80/12 para equilíbrio entre velocidade e qualidade.")
        recomendacoes.append("• Use estabilizador de médio gramatura (70–90 g/m²). Em tecidos elásticos, prefira estabilizador de corte.")

    recomendacoes.append(f"• Tensão do fio: ajustar para tensão média. Verificar a tensão da bobina antes de iniciar.")
    recomendacoes.append(f"• Velocidade sugerida: 700–900 ppm para máxima qualidade de acabamento.")

    if total_pontos > 30000:
        recomendacoes.append("• Design de alta complexidade (+30.000 pts). Monitore o aquecimento da cabeça da máquina.")

    if lw > 200 or lh > 200:
        recomendacoes.append("• Design grande. Verifique se o bastidor está bem fixo ao longo da execução.")

    for rec in recomendacoes:
        story.append(Paragraph(rec, normal_estilo))
        story.append(Spacer(1, 1*mm))

    story.append(Spacer(1, 4*mm))

    # ------------------------------------------------------------------
    # SEÇÃO 6 — ORÇAMENTO
    # ------------------------------------------------------------------
    if config and valor_bordado > 0:
        story.append(Paragraph("Orçamento", titulo_estilo))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=3*mm))

        orc_data = [
            ['Item', 'Detalhe', 'Valor'],
            ['Bordado', f'{total_pontos:,} pts × R$ {config.valor_mil_pontos}/1000 pts'.replace(',','.'),
             f'R$ {valor_bordado:.2f}'],
        ]

        orc_table = Table(orc_data, colWidths=[40*mm, 110*mm, 32*mm])
        orc_table.setStyle(TableStyle([
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
        story.append(orc_table)

    # ------------------------------------------------------------------
    # GERAR PDF
    # ------------------------------------------------------------------
    def _primeira_pagina(c, doc):
        _desenhar_pagina(c, doc,
                         titulo=f"Relatório de Bordado — {nome_design}",
                         subtitulo=f"{lw:.0f}×{lh:.0f}mm · {total_pontos:,} pontos · {n_cores} cores".replace(',','.'))

    def _paginas_seguintes(c, doc):
        _desenhar_pagina(c, doc, titulo=f"Relatório — {nome_design} (cont.)")

    doc.build(story,
              onFirstPage=_primeira_pagina,
              onLaterPages=_paginas_seguintes)

    buffer.seek(0)
    return buffer.read()


def gerar_pdf_da_matriz(matriz_obj, config=None):
    """
    Gera PDF a partir de um objeto MatrizBordado do Django.
    Retorna (bytes, nome_arquivo) ou (None, None).
    """
    try:
        from analise_avancada import analisar_imagem

        img_path = None
        analise  = None

        if matriz_obj.imagem_original:
            img_path = matriz_obj.imagem_original.path
            from PIL import Image as PILImage2
            img = PILImage2.open(img_path)
            analise  = analisar_imagem(
                img_pil=img,
                largura_mm=float(matriz_obj.largura_mm),
                altura_mm=float(matriz_obj.altura_mm),
                densidade=float(matriz_obj.densidade_escolhida),
                pontos_por_min=matriz_obj.pontos_por_minuto,
            )

        if not analise:
            # Fallback: usa dados já calculados no modelo
            analise = {
                'tipo_elemento':   'logo',
                'razao_borda':     0.2,
                'fator_cobertura': 0.5,
                'fator_underlay':  1.20,
                'total_pontos':    matriz_obj.quantidade_pontos,
                'detalhes_cores':  [
                    {'nome': c.strip(), 'rgb': (100,100,100),
                     'pontos': matriz_obj.quantidade_pontos // max(1, len(matriz_obj.sequencia_cores.split('→'))),
                     'area_mm2': 0, 'r_borda': 0.3, 'tipo_ponto': 'Tatami / Preenchimento'}
                    for c in matriz_obj.sequencia_cores.split('→')
                ],
                'sequencia_nomes': matriz_obj.sequencia_cores,
                'n_cores':         matriz_obj.mudancas_cores + 1,
                'trocas_linha':    matriz_obj.mudancas_cores,
                'tempo_min':       int(matriz_obj.tempo_estimado.replace(' min', '')),
                'bastidor':        matriz_obj.bastidor_recomendado,
                'largura_mm':      float(matriz_obj.largura_mm),
                'altura_mm':       float(matriz_obj.altura_mm),
                'rgb_fundo':       None,
            }

        pdf_bytes = gerar_pdf_bordado(
            analise=analise,
            config=config,
            imagem_path=img_path,
            nome_design=matriz_obj.descricao,
        )

        nome = f"{matriz_obj.descricao[:30].replace(' ','_')}_relatorio.pdf"
        return pdf_bytes, nome

    except Exception as e:
        import traceback
        print(f"Erro ao gerar PDF: {e}")
        traceback.print_exc()
        return None, None

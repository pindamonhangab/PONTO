from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
import json
import os
import sys
sys.path.insert(0, os.path.join(settings.BASE_DIR, 'gestao'))

from .models import (
    ContaReceber, MatrizBordado, Pedido, ItemPedido,
    Cliente, ConfiguracaoBordado, Produto, ContaPagar,
    PerfilUsuario, HistoricoLogin, LancamentoCaixa, FechamentoCaixa,
)


# =============================================================================
# AUTENTICAÇÃO
# =============================================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember')
        ip       = _get_ip(request)
        ua       = request.META.get('HTTP_USER_AGENT', '')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            # Lembrar de mim: mantém sessão por 30 dias
            if not remember:
                request.session.set_expiry(0)  # fecha ao fechar o browser
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)

            # Registra no histórico
            HistoricoLogin.objects.create(user=user, ip=ip, navegador=ua, sucesso=True)

            next_url = request.POST.get('next') or request.GET.get('next') or 'home'
            return redirect(next_url)
        else:
            # Tenta encontrar o usuário para registrar tentativa falha
            from django.contrib.auth.models import User
            try:
                u = User.objects.get(username=username)
                HistoricoLogin.objects.create(user=u, ip=ip, navegador=ua, sucesso=False)
            except User.DoesNotExist:
                pass

            return render(request, 'gestao/login.html', {
                'form': type('F', (), {'errors': True})(),
                'next': request.POST.get('next', ''),
            })

    return render(request, 'gestao/login.html', {
        'next': request.GET.get('next', ''),
    })


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('login')


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# =============================================================================
# PERFIL DO USUÁRIO
# =============================================================================

@login_required
def perfil(request):
    perfil_obj, _ = PerfilUsuario.objects.get_or_create(user=request.user)
    historico     = HistoricoLogin.objects.filter(user=request.user)[:20]

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'trocar_nome':
            nome = request.POST.get('nome_exibicao', '').strip()
            perfil_obj.nome_exibicao = nome
            perfil_obj.save()
            messages.success(request, "Nome atualizado com sucesso!")

        elif acao == 'trocar_foto':
            foto = request.FILES.get('foto')
            if foto:
                # Remove foto antiga se existir
                if perfil_obj.foto:
                    perfil_obj.delete_foto()
                perfil_obj.foto = foto
                perfil_obj.save()
                messages.success(request, "Foto atualizada!")
            else:
                messages.error(request, "Selecione uma imagem.")

        elif acao == 'remover_foto':
            perfil_obj.delete_foto()
            messages.success(request, "Foto removida.")

        elif acao == 'trocar_senha':
            senha_atual    = request.POST.get('senha_atual', '')
            nova_senha     = request.POST.get('nova_senha', '')
            confirmar      = request.POST.get('confirmar_senha', '')

            if not request.user.check_password(senha_atual):
                messages.error(request, "❌ Senha atual incorreta.")
            elif nova_senha != confirmar:
                messages.error(request, "❌ As novas senhas não coincidem.")
            elif len(nova_senha) < 6:
                messages.error(request, "❌ A senha deve ter pelo menos 6 caracteres.")
            else:
                request.user.set_password(nova_senha)
                request.user.save()
                update_session_auth_hash(request, request.user)  # mantém logado
                messages.success(request, "✅ Senha alterada com sucesso!")

        return redirect('perfil')

    return render(request, 'gestao/perfil.html', {
        'perfil':    perfil_obj,
        'historico': historico,
    })


# =============================================================================
# FINANCEIRO
# =============================================================================


# Adicione esta import no topo do views.py (junto com os outros imports de models):
# from .models import (..., ContaReceber)

# ============================================================
# Substitua a função financeiro() no views.py por esta:
# ============================================================

@login_required
def financeiro(request):
    aba     = request.GET.get('aba', 'geral')
    pedidos = Pedido.objects.all()

    total_bruto = float(pedidos.aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    total_pago  = float(pedidos.filter(pago=True).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    lucro_estimado = total_pago * 0.60

    # Dados para gráficos
    hoje = timezone.now()
    meses_labels, meses_valores, meses_pagos = [], [], []
    MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    for i in range(5, -1, -1):
        alvo = (hoje.replace(day=1) - timedelta(days=i*28)).replace(day=1)
        fim  = alvo.replace(month=alvo.month%12+1, day=1) if alvo.month < 12 \
               else alvo.replace(year=alvo.year+1, month=1, day=1)
        qs = pedidos.filter(data_pedido__gte=alvo, data_pedido__lt=fim)
        meses_labels.append(f"{MESES[alvo.month-1]}/{str(alvo.year)[2:]}")
        meses_valores.append(float(qs.aggregate(Sum('valor_total'))['valor_total__sum'] or 0))
        meses_pagos.append(float(qs.filter(pago=True).aggregate(Sum('valor_total'))['valor_total__sum'] or 0))

    # Contas a pagar
    contas = ContaPagar.objects.all()
    total_contas_pendentes = float(
        contas.filter(status='pendente').aggregate(Sum('valor'))['valor__sum'] or 0
    )
    config_obj = ConfiguracaoBordado.objects.first()
    dias_aviso = config_obj.dias_aviso_conta if config_obj else 3
    contas_alerta = contas.filter(
        status='pendente',
        vencimento__lte=timezone.localdate() + timedelta(days=dias_aviso)
    ).count()
    contas_proximas = contas.filter(
        status='pendente',
        vencimento__lte=timezone.localdate() + timedelta(days=7)
    ).order_by('vencimento')

    # Contas a receber — pedidos pendentes + lançamentos manuais
    pedidos_pendentes_lista = pedidos.filter(pago=False).order_by('data_pedido')
    contas_receber          = ContaReceber.objects.all().order_by('vencimento')

    valor_pedidos_pendentes = float(
        pedidos_pendentes_lista.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    )
    valor_lancamentos_pendentes = float(
        contas_receber.filter(status='pendente').aggregate(Sum('valor'))['valor__sum'] or 0
    )
    total_a_receber  = valor_pedidos_pendentes + valor_lancamentos_pendentes
    total_pendente_count = pedidos_pendentes_lista.count() + \
                           contas_receber.filter(status='pendente').count()

    # POST
    if request.method == 'POST':
        acao = request.POST.get('acao')

        # --- Contas a Receber: marcar pedido como pago ---
        if acao == 'marcar_pago':
            pedido = get_object_or_404(Pedido, id=request.POST.get('pedido_id'))
            pedido.pago = True
            pedido.save(update_fields=['pago'])
            messages.success(request, f"Pedido #{pedido.id} marcado como pago! ✅")
            return redirect('/financeiro/?aba=receber')

        # --- Contas a Receber: criar lançamento manual ---
        elif acao == 'criar_receber':
            cliente_id = request.POST.get('cliente_id') or None
            try:
                ContaReceber.objects.create(
                    descricao=request.POST.get('descricao','').strip(),
                    cliente_id=cliente_id,
                    valor=float(request.POST.get('valor', 0)),
                    vencimento=request.POST.get('vencimento'),
                    categoria=request.POST.get('categoria','outro'),
                    observacoes=request.POST.get('observacoes','').strip(),
                )
                messages.success(request, "Lançamento criado!")
            except Exception as e:
                messages.error(request, f"Erro: {e}")
            return redirect('/financeiro/?aba=receber')

        # --- Contas a Receber: marcar lançamento como recebido ---
        elif acao == 'receber_conta':
            cr = get_object_or_404(ContaReceber, id=request.POST.get('receber_id'))
            cr.status = 'recebido'; cr.save(update_fields=['status'])
            messages.success(request, f"'{cr.descricao}' marcado como recebido! ✅")
            return redirect('/financeiro/?aba=receber')

        # --- Contas a Receber: excluir lançamento ---
        elif acao == 'excluir_receber':
            cr = get_object_or_404(ContaReceber, id=request.POST.get('receber_id'))
            nome = cr.descricao; cr.delete()
            messages.success(request, f"Lançamento '{nome}' excluído.")
            return redirect('/financeiro/?aba=receber')

        # --- Contas a Pagar ---
        elif acao == 'criar_conta':
            try:
                ContaPagar.objects.create(
                    descricao=request.POST.get('descricao','').strip(),
                    fornecedor=request.POST.get('fornecedor','').strip(),
                    valor=float(request.POST.get('valor', 0)),
                    vencimento=request.POST.get('vencimento'),
                    categoria=request.POST.get('categoria','outro'),
                    observacoes=request.POST.get('observacoes','').strip(),
                    nota_fiscal=request.FILES.get('nota_fiscal'),
                )
                messages.success(request, "Conta cadastrada!")
            except Exception as e:
                messages.error(request, f"Erro: {e}")

        elif acao == 'pagar_conta':
            conta = get_object_or_404(ContaPagar, id=request.POST.get('conta_id'))
            conta.status = 'pago'; conta.save(update_fields=['status'])
            messages.success(request, f"'{conta.descricao}' marcada como paga! ✅")

        elif acao == 'excluir_conta':
            conta = get_object_or_404(ContaPagar, id=request.POST.get('conta_id'))
            nome = conta.descricao; conta.delete()
            messages.success(request, f"Conta '{nome}' excluída.")

        elif acao == 'enviar_alerta':
            from .email_alertas import enviar_alerta_conta, EmailAlertaError
            conta = get_object_or_404(ContaPagar, id=request.POST.get('conta_id'))
            try:
                enviar_alerta_conta(conta)
                messages.success(request, f"✅ Email enviado! ({conta.descricao})")
            except EmailAlertaError as e:
                messages.error(request, f"❌ {e}")

        return redirect(f'/financeiro/?aba={aba}')

    return render(request, 'gestao/financeiro.html', {
        'aba':                    aba,
        'pedidos':                pedidos.order_by('-data_pedido'),
        'pedidos_pendentes_lista': pedidos_pendentes_lista,
        'total_pendente_count':   total_pendente_count,
        'contas_receber':         contas_receber,
        'categorias_receber':     ContaReceber.CATEGORIAS,
        'clientes':               Cliente.objects.all().order_by('nome'),
        'total_bruto':            total_bruto,
        'total_pago':             total_pago,
        'total_a_receber':        total_a_receber,
        'lucro_estimado':         lucro_estimado,
        'total_pago_js':          total_pago,
        'a_receber_js':           total_a_receber,
        'meses_labels':           json.dumps(meses_labels),
        'meses_valores':          json.dumps(meses_valores),
        'meses_pagos':            json.dumps(meses_pagos),
        'contas':                 contas.order_by('vencimento'),
        'contas_proximas':        contas_proximas,
        'total_contas_pendentes': total_contas_pendentes,
        'contas_alerta':          contas_alerta,
        'categorias_conta':       ContaPagar.CATEGORIAS,
    })


# ============================================================
# Adicione esta função nova no views.py:
# ============================================================

@login_required
def pedido_detalhe(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    itens  = pedido.itens.select_related('produto', 'matriz_bordado').all()

    if request.method == 'POST' and request.POST.get('acao') == 'marcar_pago':
        pedido.pago = True
        pedido.save(update_fields=['pago'])
        messages.success(request, f"Pedido #{pedido.id} marcado como pago! ✅")
        return redirect('pedido_detalhe', pedido_id=pedido_id)

    return render(request, 'gestao/pedido_detalhe.html', {
        'pedido': pedido,
        'itens':  itens,
    })



# =============================================================================
# HOME
# =============================================================================

@login_required
def home(request):
    matrizes = MatrizBordado.objects.all().order_by('-id')
    pedidos  = Pedido.objects.all()
    return render(request, 'gestao/index.html', {
        'matrizes':          matrizes,
        'vendas_hoje':        pedidos.filter(pago=True).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'total_matrizes':     matrizes.count(),
        'pedidos_pendentes':  pedidos.filter(pago=False).count(),
    })


# =============================================================================
# VENDAS
# =============================================================================


@login_required
def vendas(request):
    aba = request.GET.get('aba', 'pedidos')

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'criar':
            nome = request.POST.get('nome', '').strip()
            try:
                custo = float(request.POST.get('custo', '0').replace(',', '.'))
            except ValueError:
                custo = 0.0
            if nome and custo > 0:
                Produto.objects.create(
                    nome=nome,
                    categoria=request.POST.get('categoria', 'outro'),
                    custo=custo,
                    descricao_produto=request.POST.get('descricao_produto', '').strip(),
                )
                messages.success(request, f"Produto '{nome}' criado!")
            else:
                messages.error(request, "Preencha nome e custo.")

        elif acao == 'editar':
            p = get_object_or_404(Produto, id=request.POST.get('produto_id'))
            p.nome      = request.POST.get('nome', p.nome).strip()
            p.categoria = request.POST.get('categoria', p.categoria)
            p.descricao_produto = request.POST.get('descricao_produto', '').strip()
            try:
                p.custo = float(request.POST.get('custo', str(p.custo)).replace(',', '.'))
            except ValueError:
                pass
            p.save()
            messages.success(request, f"Produto '{p.nome}' atualizado!")

        elif acao == 'excluir':
            p = get_object_or_404(Produto, id=request.POST.get('produto_id'))
            nome = p.nome
            p.delete()
            messages.success(request, f"Produto '{nome}' excluído.")

        return redirect(f'/vendas/?aba={aba}')

    return render(request, 'gestao/vendas.html', {
        'pedidos':    Pedido.objects.all().order_by('-data_pedido'),
        'produtos':   Produto.objects.all(),
        'categorias': Produto.CATEGORIAS,
        'aba':        aba,
    })



# =============================================================================
# CLIENTES
# =============================================================================

@login_required
def clientes(request):
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'criar':
            nome = request.POST.get('nome', '').strip()
            if nome:
                Cliente.objects.create(
                    nome=nome,
                    telefone=request.POST.get('telefone', '').strip(),
                    email=request.POST.get('email', '').strip(),
                )
                messages.success(request, f"Cliente '{nome}' cadastrado!")
            else:
                messages.error(request, "Nome obrigatório.")
        elif acao == 'editar':
            c = get_object_or_404(Cliente, id=request.POST.get('cliente_id'))
            nome = request.POST.get('nome', '').strip()
            if nome:
                c.nome     = nome
                c.telefone = request.POST.get('telefone', '').strip()
                c.email    = request.POST.get('email', '').strip()
                c.save()
                messages.success(request, f"Cliente '{nome}' atualizado!")
        elif acao == 'excluir':
            c = get_object_or_404(Cliente, id=request.POST.get('cliente_id'))
            nome = c.nome; c.delete()
            messages.success(request, f"Cliente '{nome}' excluído.")
        return redirect('clientes')
    return render(request, 'gestao/clientes.html', {
        'clientes': Cliente.objects.all().order_by('nome')
    })

# =============================================================================
# CLIENTE DETALHE
# =============================================================================

@login_required
def cliente_detalhe(request, cliente_id):
    cliente  = get_object_or_404(Cliente, id=cliente_id)
    matrizes = cliente.matrizes.all().order_by('-id')
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'adicionar_matriz':
            descricao = request.POST.get('descricao', '').strip()
            if not descricao:
                messages.error(request, "Descrição obrigatória.")
                return redirect('cliente_detalhe', cliente_id=cliente_id)
            m = MatrizBordado(
                cliente=cliente, descricao=descricao,
                largura_desejada_mm=float(request.POST.get('largura') or 0),
                altura_desejada_mm=float(request.POST.get('altura') or 0),
                pontos_por_minuto=int(request.POST.get('ppm') or 850),
                densidade_escolhida=float(request.POST.get('densidade') or 5.5),
                imagem_original=request.FILES.get('imagem'),
                arquivo_matriz=request.FILES.get('arquivo_matriz'),
                cor_tecido_fundo='AUTO',
            )
            m.save(); messages.success(request, f"Matriz '{descricao}' salva!")
        elif acao == 'anexar_arquivo':
            m = get_object_or_404(MatrizBordado, id=request.POST.get('matriz_id'), cliente=cliente)
            arq = request.FILES.get('arquivo_matriz')
            if arq: m.arquivo_matriz = arq; m.save(); messages.success(request, "Arquivo anexado!")
            else: messages.error(request, "Selecione um arquivo.")
        elif acao == 'excluir_matriz':
            m = get_object_or_404(MatrizBordado, id=request.POST.get('matriz_id'), cliente=cliente)
            nome = m.descricao; m.delete(); messages.success(request, f"Matriz '{nome}' excluída.")
        return redirect('cliente_detalhe', cliente_id=cliente_id)
    return render(request, 'gestao/cliente_detalhe.html', {'cliente': cliente, 'matrizes': matrizes})


# =============================================================================
# AJUSTES
# =============================================================================

@login_required
def ajustes(request):
    config, _ = ConfiguracaoBordado.objects.get_or_create(id=1)
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'salvar_precos':
            config.valor_mil_pontos = request.POST.get('valor_mil_pontos')
            config.save(); messages.success(request, "Preços atualizados! 💰")
        elif acao in ('salvar_email', 'testar_email'):
            config.email_remetente    = request.POST.get('email_remetente', '').strip()
            config.email_senha_app    = request.POST.get('email_senha_app', '').strip()
            config.email_destinatario = request.POST.get('email_destinatario', '').strip()
            try: config.dias_aviso_conta = int(request.POST.get('dias_aviso_conta', 3))
            except ValueError: config.dias_aviso_conta = 3
            config.save()
            if acao == 'testar_email':
                from .email_alertas import testar_conexao
                sucesso, msg = testar_conexao()
                messages.success(request, msg) if sucesso else messages.error(request, f"❌ {msg}")
            else:
                messages.success(request, "Configuração de email salva!")
        return redirect('ajustes')
    return render(request, 'gestao/ajustes.html', {'config': config})


# =============================================================================
# ANALISAR LOGO
# =============================================================================

@login_required
def download_dst(request, matriz_id):
    """Gera e faz download do arquivo DST para máquinas RICOMA."""
    from django.conf import settings
    from django.http import HttpResponse

    # Garante que o diretório da gestao está no path
    gestao_dir = os.path.join(settings.BASE_DIR, 'gestao')
    if gestao_dir not in sys.path:
        sys.path.insert(0, gestao_dir)

    try:
        from dst_generator import gerar_dst_da_matriz
    except ImportError as e:
        messages.error(request, f"Módulo DST não encontrado. Copie dst_generator.py para gestao/. Erro: {e}")
        return redirect('cliente_detalhe', cliente_id=request.GET.get('cliente_id', 1))

    matriz = get_object_or_404(MatrizBordado, id=matriz_id)

    if not matriz.imagem_original:
        messages.error(request, "Esta matriz não tem imagem — necessária para gerar o DST.")
        return redirect('cliente_detalhe', cliente_id=matriz.cliente_id or 1)

    dst_bytes, nome_arq = gerar_dst_da_matriz(matriz)

    if not dst_bytes:
        messages.error(request, "Não foi possível gerar o arquivo DST desta imagem.")
        return redirect('cliente_detalhe', cliente_id=matriz.cliente_id or 1)

    response = HttpResponse(dst_bytes, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{nome_arq}"'
    return response


@login_required
def download_pdf(request, matriz_id):
    from django.conf import settings
    from django.http import HttpResponse
    import traceback

    gestao_dir = os.path.join(settings.BASE_DIR, 'gestao')
    if gestao_dir not in sys.path:
        sys.path.insert(0, gestao_dir)

    matriz = get_object_or_404(MatrizBordado, id=matriz_id)
    config = ConfiguracaoBordado.objects.first()

    try:
        from pdf_report import gerar_pdf_da_matriz
        pdf_bytes, nome_arq = gerar_pdf_da_matriz(matriz, config=config)

        if not pdf_bytes:
            messages.error(request, "Não foi possível gerar o PDF desta matriz.")
            return redirect('cliente_detalhe', cliente_id=matriz.cliente_id or 1)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nome_arq}"'
        return response

    except Exception as e:
        traceback.print_exc()
        messages.error(request, f"Erro ao gerar PDF: {e}")
        return redirect('cliente_detalhe', cliente_id=matriz.cliente_id or 1)

# ============================================================
# Substitua também a função analisar_logo() por esta versão
# melhorada que usa analise_avancada.py:
# ============================================================

@login_required
def analisar_logo(request):
    if request.method == 'POST':
        produto_id = request.POST.get('produto') or None
        produto    = Produto.objects.filter(id=produto_id).first() if produto_id else None

        m = MatrizBordado(
            descricao=request.POST.get('descricao') or 'Sem nome',
            cliente_id=request.POST.get('cliente') or None,
            largura_desejada_mm=float(request.POST.get('largura') or 0),
            altura_desejada_mm=float(request.POST.get('altura')   or 0),
            pontos_por_minuto=int(request.POST.get('ppm')          or 850),
            densidade_escolhida=float(request.POST.get('densidade') or 5.5),
            imagem_original=request.FILES.get('imagem'),
            cor_tecido_fundo='AUTO',
        )
        m.save()

        config = ConfiguracaoBordado.objects.first()
        valor_por_mil = float(config.valor_mil_pontos) if config else 5.0

        # -----------------------------------------------------------------------
        # Análise avançada + visualizações
        # -----------------------------------------------------------------------
        analise_extra = None
        vis           = {}

        if m.imagem_original:
            try:
                gestao_dir = os.path.join(settings.BASE_DIR, 'gestao')
                if gestao_dir not in sys.path:
                    sys.path.insert(0, gestao_dir)

                from analise_avancada import analisar_imagem
                from visualizacao import gerar_visualizacoes
                from PIL import Image as PILImage

                img = PILImage.open(m.imagem_original.path)
                analise_extra = analisar_imagem(
                    img_pil=img,
                    largura_mm=float(m.largura_mm),
                    altura_mm=float(m.altura_mm),
                    densidade=float(m.densidade_escolhida),
                    pontos_por_min=m.pontos_por_minuto,
                )

                if analise_extra:
                    vis = gerar_visualizacoes(img, analise_extra)

            except Exception as e:
                import traceback
                traceback.print_exc()

        # -----------------------------------------------------------------------
        # Dados de orçamento
        # -----------------------------------------------------------------------
        total_pontos    = analise_extra['total_pontos'] if analise_extra else m.quantidade_pontos
        fator_underlay  = analise_extra['fator_underlay'] if analise_extra else 1.20
        area_mm2        = float(m.largura_mm) * float(m.altura_mm)
        fator_cob       = analise_extra['fator_cobertura'] if analise_extra else 0.5
        densidade       = float(m.densidade_escolhida)

        # Pontos sem underlay (base pura)
        pontos_sem_ul   = int(area_mm2 * fator_cob * densidade)

        custo_com_ul    = round(total_pontos    / 1000 * valor_por_mil, 2)
        custo_sem_ul    = round(pontos_sem_ul   / 1000 * valor_por_mil, 2)
        custo_produto   = float(produto.custo) if produto else 0.0
        valor_total     = custo_com_ul + custo_produto

        # Custo por cor
        custo_por_cor = []
        if analise_extra and analise_extra.get('detalhes_cores'):
            for d in analise_extra['detalhes_cores']:
                custo_cor = round(d['pontos'] / 1000 * valor_por_mil, 2)
                custo_por_cor.append({
                    'nome':  d['nome'],
                    'hex':   '#{:02X}{:02X}{:02X}'.format(*d['rgb'][:3]),
                    'pontos': d['pontos'],
                    'pct':   round(d['pontos'] / total_pontos * 100, 1) if total_pontos else 0,
                    'custo': f"{custo_cor:.2f}",
                })

        # Resumo técnico
        resumo_tecnico = [
            ('Tamanho',          f"{m.largura_mm}×{m.altura_mm}mm"),
            ('Área total',       f"{area_mm2:.0f}mm²"),
            ('Bastidor',         m.bastidor_recomendado or '—'),
            ('Total de pontos',  f"{total_pontos:,}".replace(',','.')),
            ('Trocas de linha',  str(analise_extra['trocas_linha'] if analise_extra else m.mudancas_cores)),
            ('Tempo estimado',   m.tempo_estimado),
            ('Cobertura',        f"{fator_cob*100:.0f}%"),
            ('Tipo detectado',   (analise_extra['tipo_elemento'].capitalize() if analise_extra else '—')),
        ]

        # Sugestão de densidade
        sugestao = None
        if analise_extra:
            tipo = analise_extra.get('tipo_elemento', 'logo')
            rb   = analise_extra.get('razao_borda', 0.2)
            if tipo == 'texto':
                sugestao = ("Elemento de texto detectado. Recomendamos densidade "
                            "3.5–4.5 pts/mm² para melhor definição das letras.")
            elif rb > 0.15:
                sugestao = ("Alta proporção de contornos detectada. Recomendamos "
                            "densidade 4.0–5.0 pts/mm² com underlay 1.25× para satin stitches.")
            else:
                sugestao = ("Logo com preenchimento sólido. Densidade 5.0–6.5 pts/mm² "
                            "com underlay 1.20× para tatami fill uniforme.")

        return render(request, 'gestao/resultado.html', {
            'matriz':             m,
            'produto':            produto,
            'valor_total':        valor_total,
            'custo_com_underlay': f"{custo_com_ul:.2f}",
            'custo_sem_underlay': f"{custo_sem_ul:.2f}",
            'pontos_sem_underlay': pontos_sem_ul,
            'custo_por_cor':      custo_por_cor,
            'resumo_tecnico':     resumo_tecnico,
            'analise_extra':      analise_extra,
            'vis':                vis,
            'sugestao_densidade': sugestao,
            'config_valor':       f"{valor_por_mil:.2f}",
            'config_valor_float': valor_por_mil,
            'area_total_mm2':     area_mm2,
        })

    return render(request, 'gestao/analisar.html', {
        'clientes': Cliente.objects.all(),
        'produtos': Produto.objects.filter(ativo=True),
    })



# =============================================================================
# ADICIONAR ITEM
# =============================================================================

@login_required
def adicionar_item(request):
    if request.method == 'POST':
        cliente   = get_object_or_404(Cliente, id=request.POST.get('cliente'))
        produto   = Produto.objects.filter(id=request.POST.get('produto') or 0).first()
        matriz    = MatrizBordado.objects.filter(id=request.POST.get('matriz') or 0).first()
        quantidade = int(request.POST.get('quantidade') or 1)
        if not produto and not matriz:
            messages.error(request, "Selecione pelo menos um produto ou uma matriz.")
            return redirect('adicionar_item')
        pedido_id = request.POST.get('pedido') or None
        pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente) if pedido_id \
                 else (Pedido.objects.filter(cliente=cliente, pago=False).order_by('-data_pedido').first()
                       or Pedido.objects.create(cliente=cliente))
        ItemPedido(pedido=pedido, produto=produto, matriz_bordado=matriz, quantidade=quantidade).save()
        messages.success(request, f"Item adicionado! Total: R$ {pedido.valor_total:.2f}")
        return redirect('vendas')
    return render(request, 'gestao/adicionar_item.html', {
        'clientes':        Cliente.objects.all().order_by('nome'),
        'produtos':        Produto.objects.filter(ativo=True),
        'matrizes':        MatrizBordado.objects.all().order_by('-id'),
        'pedidos_abertos': Pedido.objects.filter(pago=False).select_related('cliente').order_by('-data_pedido'),
    })

@login_required
def producao(request):
    import json as _json

    if request.method == 'POST':
        pedido = get_object_or_404(Pedido, id=request.POST.get('pedido_id'))
        pedido.status_producao     = request.POST.get('status_producao', pedido.status_producao)
        pedido.observacao_producao = request.POST.get('observacao_producao', '').strip()
        data_prev = request.POST.get('data_prevista', '')
        pedido.data_prevista = data_prev if data_prev else None
        pedido.save(update_fields=['status_producao', 'observacao_producao', 'data_prevista'])

        if request.POST.get('notificar_cliente'):
            cliente_email = pedido.cliente.email
            if cliente_email:
                try:
                    from .email_alertas import enviar_email
                    enviar_email(
                        assunto=f"🧵 PONTO — Seu pedido #{pedido.id} está pronto!",
                        corpo_html=f"""
                        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
                          <div style="background:#dc3545;padding:16px 24px;border-radius:10px 10px 0 0;">
                            <h2 style="color:white;margin:0;">🧵 PONTO — Pedido Pronto!</h2>
                          </div>
                          <div style="background:#f8f9fa;padding:24px;border-radius:0 0 10px 10px;">
                            <p>Olá, <strong>{pedido.cliente.nome}</strong>!</p>
                            <p>Seu pedido <strong>#{pedido.id}</strong> está
                               <strong style="color:#198754;">pronto para retirada</strong>.</p>
                            <p style="color:#666;font-size:13px;">Valor: R$ {pedido.valor_total:.2f}</p>
                            {"<p style='color:#666;font-size:13px;'>Obs: " + pedido.observacao_producao + "</p>" if pedido.observacao_producao else ""}
                          </div>
                        </div>""",
                    )
                    pedido.notificado = True
                    pedido.save(update_fields=['notificado'])
                    messages.success(request, f"✅ Pedido #{pedido.id} atualizado e email enviado para {cliente_email}!")
                except Exception as e:
                    messages.warning(request, f"Pedido atualizado, mas erro ao notificar: {e}")
            else:
                messages.warning(request, f"Pedido #{pedido.id} atualizado. Cliente sem email cadastrado — notificação não enviada.")
        else:
            messages.success(request, f"Pedido #{pedido.id} atualizado!")

        return redirect('producao')

    # Kanban
    todos = Pedido.objects.select_related('cliente').prefetch_related('itens')
    col_aguardando = todos.filter(status_producao='aguardando')
    col_producao   = todos.filter(status_producao='producao')
    col_pronto     = todos.filter(status_producao='pronto')
    col_entregue   = todos.filter(status_producao='entregue').order_by('-data_pedido')[:10]

    colunas = [
        (col_aguardando, 'Aguardando',  '#6c757d'),
        (col_producao,   'Em Produção', '#0d6efd'),
        (col_pronto,     'Pronto',      '#198754'),
        (col_entregue,   'Entregue',    '#212529'),
    ]

    # JSON para o modal JS — inclui email do cliente
    pedidos_json = {}
    for p in todos:
        pedidos_json[p.id] = {
            'cliente':         p.cliente.nome,
            'email':           p.cliente.email or '',
            'status_producao': p.status_producao,
            'data_prevista':   p.data_prevista.strftime('%Y-%m-%d') if p.data_prevista else '',
            'observacao':      p.observacao_producao,
        }

    return render(request, 'gestao/producao.html', {
        'colunas':        colunas,
        'col_aguardando': col_aguardando,
        'col_producao':   col_producao,
        'col_pronto':     col_pronto,
        'col_entregue':   col_entregue,
        'pedidos_json':   _json.dumps(pedidos_json),
    })

# ============================================================
# VIEW: caixa
# ============================================================

@login_required
def caixa(request):
    from django.utils.timezone import localdate
    import json as _json

    aba   = request.GET.get('aba', 'hoje')
    hoje  = localdate()
    config = ConfiguracaoBordado.objects.first()
    taxa_credito = float(getattr(config, 'taxa_credito', 3))
    taxa_debito  = float(getattr(config, 'taxa_debito',  1.5))

    # Lançamentos de hoje
    lancamentos_hoje = LancamentoCaixa.objects.filter(data__date=hoje)
    total_entrada_hoje = float(lancamentos_hoje.filter(tipo='entrada').aggregate(Sum('valor'))['valor__sum'] or 0)
    total_saida_hoje   = float(lancamentos_hoje.filter(tipo='saida').aggregate(Sum('valor'))['valor__sum'] or 0)
    saldo_hoje         = total_entrada_hoje - total_saida_hoje

    # Taxas descontadas hoje
    total_taxas = 0.0
    for l in lancamentos_hoje.filter(tipo='entrada'):
        if l.metodo == 'credito':
            total_taxas += float(l.valor) * taxa_credito / 100
        elif l.metodo == 'debito':
            total_taxas += float(l.valor) * taxa_debito / 100

    # Histórico de fechamentos
    fechamentos = FechamentoCaixa.objects.all()

    # Relatório por método
    relatorio_metodo = []
    for val, label in LancamentoCaixa.METODOS:
        qs     = LancamentoCaixa.objects.filter(metodo=val, tipo='entrada')
        total  = float(qs.aggregate(Sum('valor'))['valor__sum'] or 0)
        count  = qs.count()
        taxa   = taxa_credito if val == 'credito' else (taxa_debito if val == 'debito' else 0)
        relatorio_metodo.append({
            'label': label, 'total': total, 'count': count,
            'taxa': taxa, 'total_taxa': total * taxa / 100, 'tipo': 'entrada',
        })

    relatorio_chart = _json.dumps({
        'labels': [r['label'] for r in relatorio_metodo if r['total'] > 0],
        'values': [r['total'] for r in relatorio_metodo if r['total'] > 0],
    })

    pedidos_abertos = Pedido.objects.filter(pago=False).order_by('-data_pedido')

    # POST
    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'criar_lancamento':
            pedido_id = request.POST.get('pedido_id') or None
            try:
                LancamentoCaixa.objects.create(
                    descricao=request.POST.get('descricao','').strip(),
                    valor=float(request.POST.get('valor', 0)),
                    metodo=request.POST.get('metodo','dinheiro'),
                    tipo=request.POST.get('tipo','entrada'),
                    pedido_id=pedido_id,
                    observacao=request.POST.get('observacao','').strip(),
                )
                messages.success(request, "Lançamento registrado!")
            except Exception as e:
                messages.error(request, f"Erro: {e}")

        elif acao == 'excluir_lancamento':
            l = get_object_or_404(LancamentoCaixa, id=request.POST.get('lancamento_id'))
            l.delete()
            messages.success(request, "Lançamento excluído.")

        elif acao == 'fechar_caixa':
            if FechamentoCaixa.objects.filter(data=hoje).exists():
                messages.warning(request, "O caixa de hoje já foi fechado.")
            else:
                FechamentoCaixa.objects.create(
                    data=hoje,
                    total_entrada=total_entrada_hoje,
                    total_saida=total_saida_hoje,
                    saldo=saldo_hoje,
                )
                messages.success(request, f"Caixa fechado! Saldo do dia: R$ {saldo_hoje:.2f}")

        return redirect(f'/caixa/?aba={aba}')

    return render(request, 'gestao/caixa.html', {
        'aba':                aba,
        'lancamentos_hoje':   lancamentos_hoje,
        'total_entrada_hoje': total_entrada_hoje,
        'total_saida_hoje':   total_saida_hoje,
        'saldo_hoje':         saldo_hoje,
        'total_taxas':        total_taxas,
        'fechamentos':        fechamentos,
        'relatorio_metodo':   relatorio_metodo,
        'relatorio_chart':    relatorio_chart,
        'metodos':            LancamentoCaixa.METODOS,
        'pedidos_abertos':    pedidos_abertos,
        'taxa_credito':       taxa_credito,
        'taxa_debito':        taxa_debito,
    })

   

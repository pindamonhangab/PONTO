from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from PIL import Image
import math
from collections import Counter
from django.db.models import Sum
from django.utils import timezone


# =============================================================================
# PERFIL DE USUÁRIO
# =============================================================================

class PerfilUsuario(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    nome_exibicao = models.CharField(max_length=100, blank=True)
    foto          = models.ImageField(upload_to='fotos_perfil/', null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"

    def delete_foto(self):
        if self.foto:
            import os
            if os.path.isfile(self.foto.path):
                os.remove(self.foto.path)
            self.foto = None
            self.save()


class HistoricoLogin(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historico_login')
    data      = models.DateTimeField(auto_now_add=True)
    ip        = models.GenericIPAddressField(null=True, blank=True)
    navegador = models.TextField(blank=True)
    sucesso   = models.BooleanField(default=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        status = "✅" if self.sucesso else "❌"
        return f"{status} {self.user.username} — {self.data.strftime('%d/%m/%Y %H:%M')}"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.get_or_create(user=instance)


# =============================================================================
# PALETA DE CORES
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


def _distancia_perceptual(rgb1, rgb2):
    return math.sqrt(
        ((rgb1[0]-rgb2[0])*0.299)**2 +
        ((rgb1[1]-rgb2[1])*0.587)**2 +
        ((rgb1[2]-rgb2[2])*0.114)**2
    )

def _buscar_nome_cor(rgb):
    return min(PALETA_BORDADO, key=lambda n: _distancia_perceptual(rgb, PALETA_BORDADO[n]))

def _detectar_cor_fundo(img_rgba, margem_pct=0.05):
    w, h = img_rgba.size
    pixels = list(img_rgba.getdata())
    m = max(2, int(min(w, h) * margem_pct))
    amostras = [
        (r//15*15, g//15*15, b//15*15)
        for y in range(h) for x in range(w)
        if x < m or x >= w-m or y < m or y >= h-m
        for r, g, b, a in [pixels[y*w+x]] if a > 128
    ]
    return Counter(amostras).most_common(1)[0][0] if amostras else None


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

class ConfiguracaoBordado(models.Model):
    valor_mil_pontos   = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    valor_camisa_lisa  = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    email_remetente    = models.EmailField(blank=True)
    email_senha_app    = models.CharField(max_length=50, blank=True)
    email_destinatario = models.EmailField(blank=True)
    dias_aviso_conta   = models.PositiveIntegerField(default=3)
    taxa_credito       = models.DecimalField(max_digits=5, decimal_places=2, default=3.00)
    taxa_debito        = models.DecimalField(max_digits=5, decimal_places=2, default=1.50)
    meta_mensal        = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = "Configuração de Preços do Bordado"

    def __str__(self):
        return f"Regra: R$ {self.valor_mil_pontos} / 1k pontos"


# =============================================================================
# CLIENTE
# =============================================================================

class Cliente(models.Model):
    nome     = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True)
    email    = models.EmailField(blank=True)

    def __str__(self):
        return self.nome


# =============================================================================
# PRODUTO
# =============================================================================

class Produto(models.Model):
    CATEGORIAS = [
        ('camiseta', 'Camiseta'), ('camisa', 'Camisa'), ('bone', 'Boné'),
        ('calca', 'Calça'), ('jaqueta', 'Jaqueta'), ('toalha', 'Toalha'),
        ('outro', 'Outro'),
    ]
    nome              = models.CharField(max_length=100)
    categoria         = models.CharField(max_length=20, choices=CATEGORIAS, default='camiseta')
    custo             = models.DecimalField(max_digits=10, decimal_places=2)
    descricao_produto = models.CharField(max_length=300, blank=True)
    ativo             = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} — R$ {self.custo}"

    class Meta:
        ordering = ['categoria', 'nome']


# =============================================================================
# MATRIZ DE BORDADO
# =============================================================================

class MatrizBordado(models.Model):
    cliente             = models.ForeignKey(Cliente, on_delete=models.CASCADE,
                                            related_name='matrizes', null=True, blank=True)
    descricao           = models.CharField(max_length=200)
    imagem_original     = models.ImageField(upload_to='logos_originais/', null=True, blank=True)
    arquivo_matriz      = models.FileField(upload_to='arquivos_matrizes/', null=True, blank=True)
    largura_desejada_mm = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    altura_desejada_mm  = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    pontos_por_minuto   = models.PositiveIntegerField(default=850)
    densidade_escolhida = models.DecimalField(max_digits=3, decimal_places=1, default=5.5)
    OPCOES_CORES = [
        ('TRANSPARENTE', 'Ignorar Fundo Transparente (PNG)'),
        ('Branco',       'Tecido Branco'),
        ('Preto',        'Tecido Preto'),
        ('NENHUMA',      'Bordar TUDO'),
        ('AUTO',         'Detecção Automática'),
    ]
    cor_tecido_fundo     = models.CharField(max_length=20, choices=OPCOES_CORES, default='AUTO')
    quantidade_pontos    = models.PositiveIntegerField(default=0)
    largura_mm           = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    altura_mm            = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    sequencia_cores      = models.TextField(blank=True)
    mudancas_cores       = models.PositiveIntegerField(default=0)
    bastidor_recomendado = models.CharField(max_length=20, blank=True)
    criado_em            = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.descricao} ({self.cliente})"

    @property
    def nome_arquivo(self):
        return self.arquivo_matriz.name.split('/')[-1] if self.arquivo_matriz else None

    @property
    def extensao_arquivo(self):
        return self.arquivo_matriz.name.split('.')[-1].upper() if self.arquivo_matriz else None

    @property
    def tempo_estimado(self):
        if self.quantidade_pontos > 0:
            return f"{math.ceil(self.quantidade_pontos / max(1, self.pontos_por_minuto) + self.mudancas_cores * 2.0)} min"
        return "0 min"

    def gerar_orcamento_texto(self, produto=None):
        config        = ConfiguracaoBordado.objects.first()
        custo_bordado = (self.quantidade_pontos / 1000) * float(config.valor_mil_pontos) if config else 0
        custo_produto = float(produto.custo) if produto else 0
        linha_produto = f" Produto: {produto.nome} — R$ {produto.custo:.2f}\n" if produto else ""
        return (
            f" *ORÇAMENTO PONTO* \n\n Desenho: {self.descricao}\n"
            f" Tamanho: {self.largura_mm}mm x {self.altura_mm}mm\n"
            f" Bastidor: {self.bastidor_recomendado}\n Cores: {self.sequencia_cores}\n"
            f" Tempo: {self.tempo_estimado}\n{linha_produto}"
            f"\n *VALOR TOTAL: R$ {custo_bordado + custo_produto:.2f}*"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE — DENTRO DA CLASSE (indentação correta)
    # ─────────────────────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        Ao salvar, sempre copia largura/altura desejada para os campos de cálculo
        e tenta rodar a análise avançada para calcular pontos.
        """
        import os
        import sys

        # ── Garante que largura_mm e altura_mm sempre têm as dimensões ──────
        lw = float(self.largura_desejada_mm or 0)
        lh = float(self.altura_desejada_mm  or 0)
        self.largura_mm = lw
        self.altura_mm  = lh

        # ── Análise de pontos ────────────────────────────────────────────────
        if lw > 0 and lh > 0 and self.imagem_original:
            try:
                from django.conf import settings as dj_settings
                gestao_dir = os.path.join(dj_settings.BASE_DIR, 'gestao')
                if gestao_dir not in sys.path:
                    sys.path.insert(0, gestao_dir)

                from analise_avancada import analisar_imagem
                from PIL import Image as PILImage

                # Abre a imagem — funciona tanto com path (objeto salvo) quanto com arquivo em memória
                if hasattr(self.imagem_original, 'path'):
                    try:
                        img = PILImage.open(self.imagem_original.path)
                    except (FileNotFoundError, ValueError):
                        # Arquivo ainda não foi salvo em disco (primeiro save)
                        self.imagem_original.seek(0)
                        img = PILImage.open(self.imagem_original)
                else:
                    img = PILImage.open(self.imagem_original)

                analise = analisar_imagem(
                    img_pil=img,
                    largura_mm=lw,
                    altura_mm=lh,
                    densidade=float(self.densidade_escolhida or 5.5),
                    pontos_por_min=int(self.pontos_por_minuto or 850),
                )

                if analise:
                    self.quantidade_pontos    = analise['total_pontos']
                    self.mudancas_cores       = analise['trocas_linha']
                    self.sequencia_cores      = analise['sequencia_nomes']
                    self.bastidor_recomendado = analise['bastidor']
                else:
                    self._calcular_estimativa_basica(lw, lh)

            except Exception as e:
                print(f"[MatrizBordado.save] análise avançada falhou: {e}")
                self._calcular_estimativa_basica(lw, lh)

        elif lw > 0 and lh > 0:
            self._calcular_estimativa_basica(lw, lh)

        super().save(*args, **kwargs)

    def _calcular_estimativa_basica(self, lw, lh):
        """Fallback quando não há imagem ou a análise falha."""
        area = lw * lh
        self.quantidade_pontos    = int(area * 0.5 * 2.6)
        self.mudancas_cores       = 2
        self.sequencia_cores      = '—'
        self.bastidor_recomendado = (
            '6x6'   if lw <= 60  and lh <= 60  else
            '10x10' if lw <= 100 and lh <= 100 else
            '13x18' if lw <= 130 and lh <= 180 else
            '20x26' if lw <= 200 and lh <= 260 else '30x40'
        )


# =============================================================================
# CONTAS A PAGAR
# =============================================================================

class ContaPagar(models.Model):
    CATEGORIAS = [
        ('aluguel',    'Aluguel'),    ('energia',    'Energia'),
        ('agua',       'Água'),       ('internet',   'Internet'),
        ('insumos',    'Insumos / Materiais'),
        ('fornecedor', 'Fornecedor'), ('imposto',    'Imposto / Taxa'),
        ('salario',    'Salário / Funcionário'), ('outro', 'Outro'),
    ]
    STATUS = [('pendente', 'Pendente'), ('pago', 'Pago')]

    descricao           = models.CharField(max_length=200)
    fornecedor          = models.CharField(max_length=200, blank=True)
    valor               = models.DecimalField(max_digits=10, decimal_places=2)
    vencimento          = models.DateField()
    categoria           = models.CharField(max_length=20, choices=CATEGORIAS, default='outro')
    status              = models.CharField(max_length=10, choices=STATUS, default='pendente')
    nota_fiscal         = models.FileField(upload_to='notas_fiscais/', null=True, blank=True)
    observacoes         = models.TextField(blank=True)
    notificacao_enviada = models.BooleanField(default=False)
    criado_em           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['vencimento']

    def __str__(self):
        return f"{self.descricao} — R$ {self.valor} ({self.vencimento})"

    @property
    def dias_para_vencer(self):
        return (self.vencimento - timezone.localdate()).days

    @property
    def situacao(self):
        if self.status == 'pago':
            return 'secondary', 'Pago'
        d = self.dias_para_vencer
        if d < 0:   return 'danger',  'Vencida'
        if d == 0:  return 'warning', 'Vence hoje'
        if d <= 3:  return 'warning', f'Vence em {d}d'
        return 'success', f'{d} dias'


# =============================================================================
# CONTAS A RECEBER
# =============================================================================

class ContaReceber(models.Model):
    STATUS = [('pendente', 'Pendente'), ('recebido', 'Recebido')]
    CATEGORIAS = [
        ('pedido',       'Pedido / Venda'),
        ('servico',      'Serviço Avulso'),
        ('adiantamento', 'Adiantamento'),
        ('parcela',      'Parcela'),
        ('outro',        'Outro'),
    ]

    descricao   = models.CharField(max_length=200)
    cliente     = models.ForeignKey('Cliente', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='contas_receber')
    valor       = models.DecimalField(max_digits=10, decimal_places=2)
    vencimento  = models.DateField()
    categoria   = models.CharField(max_length=20, choices=CATEGORIAS, default='outro')
    status      = models.CharField(max_length=10, choices=STATUS, default='pendente')
    observacoes = models.TextField(blank=True)
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['vencimento']

    @property
    def dias_para_vencer(self):
        return (self.vencimento - timezone.localdate()).days

    @property
    def situacao(self):
        if self.status == 'recebido': return 'success', 'Recebido'
        d = self.dias_para_vencer
        if d < 0:  return 'danger',   'Vencida'
        if d == 0: return 'warning',  'Vence hoje'
        if d <= 3: return 'warning',  f'Vence em {d}d'
        return 'secondary', f'{d} dias'


# =============================================================================
# PEDIDO
# =============================================================================

class Pedido(models.Model):
    STATUS_PRODUCAO = [
        ('aguardando', 'Aguardando'),
        ('producao',   'Em Produção'),
        ('pronto',     'Pronto'),
        ('entregue',   'Entregue'),
    ]

    cliente             = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    valor_total         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pago                = models.BooleanField(default=False)
    data_pedido         = models.DateTimeField(auto_now_add=True)
    status_producao     = models.CharField(max_length=20, choices=STATUS_PRODUCAO, default='aguardando')
    data_prevista       = models.DateField(null=True, blank=True)
    observacao_producao = models.TextField(blank=True)
    notificado          = models.BooleanField(default=False)

    def atualizar_valor_total(self):
        self.valor_total = sum(i.subtotal() for i in self.itens.all())
        super().save(update_fields=['valor_total'])

    def __str__(self):
        return f"Pedido #{self.id} — {self.cliente.nome}"


# =============================================================================
# ITEM DE PEDIDO
# =============================================================================

class ItemPedido(models.Model):
    pedido         = models.ForeignKey(Pedido, related_name='itens', on_delete=models.CASCADE)
    produto        = models.ForeignKey(Produto, on_delete=models.PROTECT, null=True, blank=True)
    matriz_bordado = models.ForeignKey(MatrizBordado, on_delete=models.SET_NULL, null=True, blank=True)
    quantidade     = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def save(self, *args, **kwargs):
        config        = ConfiguracaoBordado.objects.first()
        custo_base    = float(self.produto.custo) if self.produto else 0.0
        custo_bordado = (self.matriz_bordado.quantidade_pontos / 1000) * float(config.valor_mil_pontos) \
                        if config and self.matriz_bordado else 0.0
        self.preco_unitario = Decimal(custo_base + custo_bordado)
        super().save(*args, **kwargs)
        self.pedido.atualizar_valor_total()


# =============================================================================
# CAIXA
# =============================================================================

class LancamentoCaixa(models.Model):
    METODOS = [
        ('dinheiro', 'Dinheiro'), ('pix', 'PIX'),
        ('credito',  'Cartão Crédito'), ('debito', 'Cartão Débito'),
        ('mix',      'Mix (Múltiplos)'), ('outro', 'Outro'),
    ]
    TIPOS = [('entrada', 'Entrada'), ('saida', 'Saída')]

    descricao  = models.CharField(max_length=200)
    valor      = models.DecimalField(max_digits=10, decimal_places=2)
    metodo     = models.CharField(max_length=20, choices=METODOS, default='dinheiro')
    tipo       = models.CharField(max_length=10, choices=TIPOS, default='entrada')
    pedido     = models.ForeignKey('Pedido', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='lancamentos')
    data       = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.get_tipo_display()} {self.get_metodo_display()} R$ {self.valor}"

    @property
    def valor_liquido(self):
        config = ConfiguracaoBordado.objects.first()
        if not config or self.tipo == 'saida':
            return self.valor
        taxa = {
            'credito': float(getattr(config, 'taxa_credito', 0)),
            'debito':  float(getattr(config, 'taxa_debito',  0)),
        }.get(self.metodo, 0)
        return float(self.valor) * (1 - taxa / 100)


class FechamentoCaixa(models.Model):
    data          = models.DateField(unique=True)
    total_entrada = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_saida   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observacao    = models.TextField(blank=True)
    criado_em     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"Fechamento {self.data} — Saldo R$ {self.saldo}"

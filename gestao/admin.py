from django.contrib import admin
from .models import Cliente, Produto, ConfiguracaoBordado, MatrizBordado, Pedido, ItemPedido

# --- INLINES (Listas dentro de outras telas) ---

# Lista de Matrizes dentro da tela do Cliente
class MatrizBordadoInline(admin.TabularInline):
    model = MatrizBordado
    extra = 1

# Lista de Itens dentro da tela do Pedido
class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1
    readonly_fields = ('preco_unitario',)

# --- ADMINS (Telas principais customizadas) ---

class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone')
    inlines = [MatrizBordadoInline] # <-- MÁGICA AQUI

class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'data_pedido', 'valor_total')
    readonly_fields = ('valor_total',)
    inlines = [ItemPedidoInline]

# --- Configuração da tela de Matrizes ---
class MatrizBordadoAdmin(admin.ModelAdmin):
    # O que aparece na lista principal
    list_display = ('descricao', 'cliente', 'quantidade_pontos', 'tempo_estimado', 'bastidor_recomendado')
    
    # Organizando os campos dentro da tela em grupos (Fieldsets)
    fieldsets = (
        ('Arquivos da Matriz', {
            'fields': ('cliente', 'descricao', 'imagem_original', 'cor_tecido_fundo', 'largura_desejada_mm', 'arquivo_dst')
        }),
        ('Relatório de Produção (Análise IA)', {
            'fields': (
                ('quantidade_pontos', 'pontos_por_minuto'),
                ('largura_mm', 'altura_mm'),
                'sequencia_cores',
                'mudancas_cores',
                'bastidor_recomendado',
                'tempo_estimado'
            )
        }),
        ('Área de Vendas (Orçamento)', { # NOVA SEÇÃO 🔥
            'fields': ('texto_whatsapp',),
        }),
    )
    
    readonly_fields = ('tempo_estimado', 'texto_whatsapp')

    def texto_whatsapp(self, obj):
        return obj.gerar_orcamento_texto()
    
    texto_whatsapp.short_description = "Texto para copiar (WhatsApp)"

# --- REGISTROS GERAIS ---
admin.site.register(Cliente, ClienteAdmin) # <-- Atualizado aqui
admin.site.register(Pedido, PedidoAdmin)
admin.site.register(Produto)
admin.site.register(MatrizBordado, MatrizBordadoAdmin) # <-- Registrando a tela customizada de Matrizes
admin.site.register(ConfiguracaoBordado)
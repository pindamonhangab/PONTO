import 'dart:io';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

class ResultadoScreen extends StatelessWidget {
  final Map<String, dynamic> resultado;
  final File imagemFile;

  const ResultadoScreen({
    super.key,
    required this.resultado,
    required this.imagemFile,
  });

  String get _textoOrcamento {
    final pts   = resultado['total_pontos'] ?? 0;
    final custo = (resultado['custo_bordado'] ?? 0).toStringAsFixed(2);
    final larg  = resultado['largura_mm']  ?? 0;
    final alt   = resultado['altura_mm']   ?? 0;
    final bast  = resultado['bastidor']    ?? '—';
    final tempo = resultado['tempo_min']   ?? 0;
    final desc  = resultado['descricao']   ?? 'Bordado';
    final cores = resultado['sequencia_cores'] ?? '—';

    return '''🧵 *ORÇAMENTO PONTO*

📋 *$desc*
📐 Tamanho: ${larg}mm × ${alt}mm
🔲 Bastidor: $bast
🎨 Cores: $cores
⏱️ Tempo estimado: $tempo min
🔢 Total de pontos: $pts

💰 *VALOR DO BORDADO: R\$ $custo*

_Orçamento gerado pelo sistema PONTO_''';
  }

  void _compartilharWhatsApp(BuildContext context) async {
    final texto = Uri.encodeComponent(_textoOrcamento);
    final url   = 'https://wa.me/?text=$texto';
    final uri   = Uri.parse(url);

    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      // Fallback: compartilha pelo sistema
      await Share.share(_textoOrcamento);
    }
  }

  void _compartilharGeral() async {
    await Share.shareXFiles(
      [XFile(imagemFile.path)],
      text: _textoOrcamento,
    );
  }

  @override
  Widget build(BuildContext context) {
    final pontos = resultado['total_pontos'] ?? 0;
    final custo  = (resultado['custo_bordado'] ?? 0.0).toDouble();
    final cores  = List<Map<String, dynamic>>.from(resultado['cores'] ?? []);

    return Scaffold(
      backgroundColor: const Color(0xFFF4F7F6),
      appBar: AppBar(
        title: const Text('Resultado',
            style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: _compartilharGeral,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [

            // Card principal — custo
            _cardCusto(custo, pontos),
            const SizedBox(height: 16),

            // Imagem + resumo
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Imagem
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.file(
                    imagemFile,
                    width: 130,
                    height: 130,
                    fit: BoxFit.contain,
                  ),
                ),
                const SizedBox(width: 12),

                // Resumo
                Expanded(
                  child: _cardResumo(),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Cores
            if (cores.isNotEmpty) ...[
              const Text('Sequência de Cores',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 8),
              ...cores.asMap().entries.map((e) => _itemCor(e.key + 1, e.value, pontos)),
              const SizedBox(height: 16),
            ],

            // Botões de compartilhamento
            _secaoCompartilhar(context),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _cardCusto(double custo, int pontos) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFDC3545), Color(0xFFB02030)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFDC3545).withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('CUSTO DO BORDADO',
              style: TextStyle(
                  color: Colors.white70,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1)),
          const SizedBox(height: 8),
          Text(
            'R\$ ${custo.toStringAsFixed(2)}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 36,
              fontWeight: FontWeight.bold,
            ),
          ),
          Text(
            '$pontos pontos',
            style: const TextStyle(color: Colors.white60, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _cardResumo() {
    final itens = [
      ('Tamanho', '${resultado['largura_mm']}×${resultado['altura_mm']}mm'),
      ('Bastidor', resultado['bastidor'] ?? '—'),
      ('Tempo', '${resultado['tempo_min']} min'),
      ('Cores', '${resultado['n_cores']}'),
      ('Trocas', '${resultado['trocas_linha']}'),
      ('Tipo', (resultado['tipo_elemento'] ?? 'logo').toString().toUpperCase()),
    ];

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
          ),
        ],
      ),
      child: Column(
        children: itens.map((item) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(item.$1,
                  style: const TextStyle(
                      color: Colors.grey, fontSize: 12)),
              Text(item.$2,
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 12)),
            ],
          ),
        )).toList(),
      ),
    );
  }

  Widget _itemCor(int ordem, Map<String, dynamic> cor, int totalPontos) {
    final hex   = cor['hex'] as String? ?? '#888888';
    final rgb   = _hexToColor(hex);
    final pts   = cor['pontos'] as int? ?? 0;
    final pct   = cor['pct'] as double? ?? 0.0;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 6,
          ),
        ],
      ),
      child: Row(
        children: [
          // Número
          Container(
            width: 24, height: 24,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0xFFF4F7F6),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text('$ordem',
                style: const TextStyle(
                    fontSize: 11, fontWeight: FontWeight.bold,
                    color: Colors.grey)),
          ),
          const SizedBox(width: 10),

          // Swatch de cor
          Container(
            width: 28, height: 28,
            decoration: BoxDecoration(
              color: rgb,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: Colors.black12),
            ),
          ),
          const SizedBox(width: 10),

          // Nome e tipo
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(cor['nome'] ?? '—',
                    style: const TextStyle(fontWeight: FontWeight.bold,
                        fontSize: 13)),
                Text(cor['tipo'] ?? '—',
                    style: const TextStyle(color: Colors.grey, fontSize: 11)),
              ],
            ),
          ),

          // Barra + %
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('$pts pts',
                  style: const TextStyle(
                      fontSize: 11, color: Colors.grey)),
              const SizedBox(height: 2),
              Container(
                width: 60, height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[200],
                  borderRadius: BorderRadius.circular(2),
                ),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: pct / 100,
                  child: Container(
                    decoration: BoxDecoration(
                      color: rgb,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
              ),
              Text('${pct.toStringAsFixed(1)}%',
                  style: TextStyle(
                      fontSize: 10,
                      color: rgb,
                      fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _secaoCompartilhar(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Compartilhar Orçamento',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF25D366),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                icon: const Icon(Icons.chat, size: 20),
                label: const Text('WhatsApp',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                onPressed: () => _compartilharWhatsApp(context),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFDC3545),
                  side: const BorderSide(color: Color(0xFFDC3545)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                icon: const Icon(Icons.share, size: 20),
                label: const Text('Compartilhar',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                onPressed: _compartilharGeral,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Color _hexToColor(String hex) {
    try {
      return Color(int.parse(hex.replaceFirst('#', 'FF'), radix: 16));
    } catch (_) {
      return Colors.grey;
    }
  }
}

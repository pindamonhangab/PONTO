import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../services/api_service.dart';

class HistoricoScreen extends StatefulWidget {
  const HistoricoScreen({super.key});

  @override
  State<HistoricoScreen> createState() => _HistoricoScreenState();
}

class _HistoricoScreenState extends State<HistoricoScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  List<Map<String, dynamic>> _servidor = [];
  List<Map<String, dynamic>> _local    = [];
  bool _loadingServidor = true;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _loadingServidor = true);

    // Histórico local (sempre disponível, até offline)
    final local = await ApiService.historicoLocal();

    // Histórico do servidor
    List<Map<String, dynamic>> servidor = [];
    try {
      servidor = await ApiService.historico(limit: 50);
    } catch (_) {}

    if (mounted) {
      setState(() {
        _local           = local;
        _servidor        = servidor;
        _loadingServidor = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7F6),
      appBar: AppBar(
        title: const Text('Histórico',
            style: TextStyle(fontWeight: FontWeight.bold)),
        bottom: TabBar(
          controller: _tabCtrl,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          tabs: [
            Tab(text: 'Neste celular (${_local.length})'),
            Tab(text: 'Servidor (${_servidor.length})'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabCtrl,
        children: [
          _listaHistorico(_local,    local: true),
          _listaHistorico(_servidor, local: false),
        ],
      ),
    );
  }

  Widget _listaHistorico(List<Map<String, dynamic>> lista, {required bool local}) {
    if (!local && _loadingServidor) {
      return const Center(child: CircularProgressIndicator());
    }
    if (lista.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text(
              local
                  ? 'Nenhuma análise feita ainda.'
                  : 'Sem histórico no servidor.',
              style: const TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _carregar,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: lista.length,
        itemBuilder: (ctx, i) => _itemHistorico(lista[i], local: local),
      ),
    );
  }

  Widget _itemHistorico(Map<String, dynamic> item, {required bool local}) {
    final descricao = item['descricao'] as String? ?? 'Sem nome';
    final pontos    = item['pontos'] ?? item['total_pontos'] ?? 0;
    final custo     = (item['custo'] ?? item['custo_bordado'] ?? 0.0).toDouble();
    final bastidor  = item['bastidor'] ?? '—';
    final data      = item['criado_em'] ?? item['data_local'] ?? '';
    final imgUrl    = item['imagem_url'] as String?;
    final imgLocal  = item['imagem_local'] as String?;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
          ),
        ],
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(12),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: SizedBox(
            width: 56, height: 56,
            child: _buildThumb(imgLocal, imgUrl),
          ),
        ),
        title: Text(descricao,
            style: const TextStyle(fontWeight: FontWeight.bold),
            overflow: TextOverflow.ellipsis),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$pontos pts · Bastidor $bastidor',
                style: const TextStyle(fontSize: 12, color: Colors.grey)),
            if (data.isNotEmpty)
              Text(data.toString().length > 16
                      ? data.toString().substring(0, 16)
                      : data.toString(),
                  style: const TextStyle(fontSize: 11, color: Colors.grey)),
          ],
        ),
        trailing: Text(
          'R\$ ${custo.toStringAsFixed(2)}',
          style: const TextStyle(
            color: Color(0xFFDC3545),
            fontWeight: FontWeight.bold,
            fontSize: 15,
          ),
        ),
      ),
    );
  }

  Widget _buildThumb(String? localPath, String? serverUrl) {
    if (localPath != null) {
      try {
        return Image.file(
          Uri.parse(localPath).isAbsolute
              ? File(localPath)
              : File(localPath),
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => _placeholderThumb(),
        );
      } catch (_) {}
    }
    if (serverUrl != null) {
      final fullUrl = serverUrl.startsWith('http')
          ? serverUrl
          : '${ApiService.baseUrl}$serverUrl';
      return CachedNetworkImage(
        imageUrl: fullUrl,
        fit: BoxFit.cover,
        placeholder: (_, __) =>
            const Center(child: CircularProgressIndicator(strokeWidth: 2)),
        errorWidget: (_, __, ___) => _placeholderThumb(),
      );
    }
    return _placeholderThumb();
  }

  Widget _placeholderThumb() => Container(
    color: const Color(0xFFF4F7F6),
    child: const Icon(Icons.image_outlined, color: Colors.grey),
  );
}

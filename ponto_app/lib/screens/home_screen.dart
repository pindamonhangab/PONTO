import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';

import '../services/api_service.dart';
import 'resultado_screen.dart';
import 'historico_screen.dart';
import 'login_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _largCtrl = TextEditingController(text: '80');
  final _altCtrl  = TextEditingController(text: '60');
  final _descCtrl = TextEditingController();
  final _picker   = ImagePicker();

  File?  _imagem;
  bool   _loading = false;
  String _nome    = '';

  @override
  void initState() {
    super.initState();
    _carregarNome();
  }

  Future<void> _carregarNome() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() => _nome = prefs.getString('nome') ?? '');
  }

  Future<void> _selecionarImagem(ImageSource source) async {
    final picked = await _picker.pickImage(
      source: source,
      maxWidth: 1200,
      maxHeight: 1200,
      imageQuality: 90,
    );
    if (picked == null) return;

    // Comprime para não estourar o upload
    final compressed = await FlutterImageCompress.compressAndGetFile(
      picked.path,
      '${picked.path}_compressed.jpg',
      quality: 80,
      minWidth: 800,
      minHeight: 800,
    );

    setState(() => _imagem = File(compressed?.path ?? picked.path));
  }

  Future<void> _analisar() async {
    if (_imagem == null) {
      _showSnack('Selecione uma imagem primeiro.');
      return;
    }
    final larg = double.tryParse(_largCtrl.text.replaceAll(',', '.'));
    final alt  = double.tryParse(_altCtrl.text.replaceAll(',', '.'));
    if (larg == null || larg <= 0 || alt == null || alt <= 0) {
      _showSnack('Informe largura e altura válidas.');
      return;
    }

    setState(() => _loading = true);
    try {
      final resultado = await ApiService.analisar(
        imagem:    _imagem!,
        larguraMm: larg,
        alturaMm:  alt,
        descricao: _descCtrl.text.trim().isEmpty
            ? 'Análise ${DateTime.now().day}/${DateTime.now().month}'
            : _descCtrl.text.trim(),
      );

      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ResultadoScreen(
            resultado:  resultado,
            imagemFile: _imagem!,
          ),
        ),
      );
    } catch (e) {
      _showSnack('Erro: ${e.toString().replaceAll('Exception: ', '')}');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showSnack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _logout() async {
    await ApiService.logout();
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7F6),
      appBar: AppBar(
        title: const Text('PONTO', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'Histórico',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const HistoricoScreen()),
            ),
          ),
          PopupMenuButton<String>(
            onSelected: (v) { if (v == 'logout') _logout(); },
            itemBuilder: (_) => [
              PopupMenuItem(
                value: 'logout',
                child: Row(children: [
                  const Icon(Icons.logout, size: 18, color: Colors.red),
                  const SizedBox(width: 8),
                  const Text('Sair'),
                ]),
              ),
            ],
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Saudação
            Text('Olá, $_nome 👋',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const Text('Fotografe a logo para orçar o bordado.',
                style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 24),

            // Área de imagem
            GestureDetector(
              onTap: () => _mostrarOpcoesFoto(),
              child: Container(
                width: double.infinity,
                height: 220,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: _imagem != null
                        ? const Color(0xFFDC3545)
                        : const Color(0xFFDEE2E6),
                    width: _imagem != null ? 2 : 1,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.05),
                      blurRadius: 10,
                    ),
                  ],
                ),
                child: _imagem != null
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: Image.file(_imagem!, fit: BoxFit.contain),
                      )
                    : Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFFF5F5),
                              borderRadius: BorderRadius.circular(50),
                            ),
                            child: const Icon(Icons.add_a_photo,
                                size: 40, color: Color(0xFFDC3545)),
                          ),
                          const SizedBox(height: 12),
                          const Text('Toque para fotografar ou importar',
                              style: TextStyle(color: Colors.grey, fontSize: 14)),
                        ],
                      ),
              ),
            ),

            if (_imagem != null)
              TextButton.icon(
                onPressed: _mostrarOpcoesFoto,
                icon: const Icon(Icons.edit, size: 16),
                label: const Text('Trocar imagem'),
              ),

            const SizedBox(height: 20),

            // Dimensões
            const Text('Dimensões do Bordado',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _campo(
                    _largCtrl, 'Largura (mm)',
                    Icons.swap_horiz_rounded,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _campo(
                    _altCtrl, 'Altura (mm)',
                    Icons.swap_vert_rounded,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _campo(_descCtrl, 'Descrição (opcional)', Icons.label_outline),

            const SizedBox(height: 24),

            // Botão analisar
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _loading ? null : _analisar,
                icon: _loading
                    ? const SizedBox(
                        height: 18, width: 18,
                        child: CircularProgressIndicator(
                            color: Colors.white, strokeWidth: 2))
                    : const Icon(Icons.auto_awesome),
                label: Text(
                  _loading ? 'Analisando...' : 'Calcular Orçamento',
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),

            const SizedBox(height: 32),

            // Acesso rápido ao histórico
            _cardHistoricoRapido(),
          ],
        ),
      ),
    );
  }

  void _mostrarOpcoesFoto() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF5F5),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.camera_alt,
                      color: Color(0xFFDC3545)),
                ),
                title: const Text('Tirar foto agora',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Usar câmera do celular'),
                onTap: () {
                  Navigator.pop(context);
                  _selecionarImagem(ImageSource.camera);
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF0F7FF),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.photo_library,
                      color: Color(0xFF0D6EFD)),
                ),
                title: const Text('Escolher da galeria',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                subtitle: const Text('Importar imagem existente'),
                onTap: () {
                  Navigator.pop(context);
                  _selecionarImagem(ImageSource.gallery);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _campo(TextEditingController ctrl, String label, IconData icon) {
    return TextField(
      controller: ctrl,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 18, color: Colors.grey),
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFDC3545)),
        ),
        contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
      ),
    );
  }

  Widget _cardHistoricoRapido() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: ApiService.historicoLocal(),
      builder: (ctx, snap) {
        if (!snap.hasData || snap.data!.isEmpty) return const SizedBox.shrink();
        final ultimo = snap.data!.first;
        return InkWell(
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const HistoricoScreen()),
          ),
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 8,
                ),
              ],
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF5F5),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.history,
                      color: Color(0xFFDC3545)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Última análise',
                          style: TextStyle(
                              fontSize: 12, color: Colors.grey)),
                      Text(
                        ultimo['descricao'] ?? '—',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        'R\$ ${ultimo['custo_bordado']?.toStringAsFixed(2) ?? '0.00'}  ·  ${ultimo['total_pontos']} pts',
                        style: const TextStyle(
                            fontSize: 12, color: Color(0xFFDC3545)),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: Colors.grey),
              ],
            ),
          ),
        );
      },
    );
  }
}

import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // =========================================================================
  // CONFIGURAÇÃO — altere para o IP/domínio do seu servidor
  // =========================================================================
  static const String baseUrl = 'http://192.168.100.33:8000'; // ex: http://192.168.1.100:8000
  // Quando tiver domínio real: 'https://ponto.seudominio.com.br'

  // =========================================================================
  // HELPERS
  // =========================================================================

  static Future<String?> _getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('token');
  }

  static Future<Map<String, String>> _headers({bool json = false}) async {
    final token = await _getToken();
    return {
      'Authorization': 'Token $token',
      if (json) 'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
  }

  // =========================================================================
  // LOGIN
  // =========================================================================

  static Future<Map<String, dynamic>> login(String username, String password) async {
    final resp = await http.post(
      Uri.parse('$baseUrl/api/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    ).timeout(const Duration(seconds: 15));

    final data = jsonDecode(resp.body) as Map<String, dynamic>;

    if (resp.statusCode == 200) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('token',    data['token']);
      await prefs.setString('nome',     data['nome']     ?? username);
      await prefs.setString('username', data['username'] ?? username);
      await prefs.setBool('is_admin',   data['is_admin'] ?? false);
    }

    return {'status': resp.statusCode, ...data};
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('token');
    await prefs.remove('nome');
    await prefs.remove('username');
  }

  // =========================================================================
  // ANALISAR LOGO
  // =========================================================================

  static Future<Map<String, dynamic>> analisar({
    required File imagem,
    required double larguraMm,
    required double alturaMm,
    String descricao = 'Análise App',
    int ppm = 850,
  }) async {
    final token = await _getToken();
    if (token == null) throw Exception('Não autenticado');

    final uri = Uri.parse('$baseUrl/api/analisar/');
    final req = http.MultipartRequest('POST', uri)
      ..headers['Authorization'] = 'Token $token'
      ..fields['largura_mm'] = larguraMm.toString()
      ..fields['altura_mm']  = alturaMm.toString()
      ..fields['descricao']  = descricao
      ..fields['ppm']        = ppm.toString()
      ..files.add(await http.MultipartFile.fromPath('imagem', imagem.path));

    final streamed = await req.send().timeout(const Duration(seconds: 60));
    final resp     = await http.Response.fromStream(streamed);
    final data     = jsonDecode(resp.body) as Map<String, dynamic>;

    if (resp.statusCode != 200) {
      throw Exception(data['error'] ?? 'Erro ao analisar imagem');
    }

    // Salva no histórico local
    await _salvarHistoricoLocal(data, imagem.path);

    return data;
  }

  // =========================================================================
  // HISTÓRICO DO SERVIDOR
  // =========================================================================

  static Future<List<Map<String, dynamic>>> historico({int limit = 30}) async {
    final headers = await _headers();
    final resp = await http.get(
      Uri.parse('$baseUrl/api/historico/?limit=$limit'),
      headers: headers,
    ).timeout(const Duration(seconds: 10));

    if (resp.statusCode != 200) return [];
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    return List<Map<String, dynamic>>.from(data['historico'] ?? []);
  }

  // =========================================================================
  // CONFIG DO SERVIDOR
  // =========================================================================

  static Future<Map<String, dynamic>> config() async {
    final headers = await _headers();
    final resp = await http.get(
      Uri.parse('$baseUrl/api/config/'),
      headers: headers,
    ).timeout(const Duration(seconds: 10));

    if (resp.statusCode != 200) return {'valor_por_mil': 5.0};
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  // =========================================================================
  // HISTÓRICO LOCAL (SQLite) — funciona offline
  // =========================================================================

  static Future<void> _salvarHistoricoLocal(
      Map<String, dynamic> analise, String imagemPath) async {
    final prefs = await SharedPreferences.getInstance();
    final raw   = prefs.getStringList('historico_local') ?? [];

    final item = jsonEncode({
      ...analise,
      'imagem_local': imagemPath,
      'data_local':   DateTime.now().toIso8601String(),
    });

    raw.insert(0, item);
    // Mantém apenas os últimos 50
    await prefs.setStringList('historico_local', raw.take(50).toList());
  }

  static Future<List<Map<String, dynamic>>> historicoLocal() async {
    final prefs = await SharedPreferences.getInstance();
    final raw   = prefs.getStringList('historico_local') ?? [];
    return raw.map((s) => jsonDecode(s) as Map<String, dynamic>).toList();
  }
}

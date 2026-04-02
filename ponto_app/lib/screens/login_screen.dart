import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl  = TextEditingController();
  final _passCtrl  = TextEditingController();
  bool  _loading   = false;
  bool  _showPass  = false;
  String? _erro;

  Future<void> _login() async {
    if (_userCtrl.text.trim().isEmpty || _passCtrl.text.isEmpty) {
      setState(() => _erro = 'Preencha usuário e senha.');
      return;
    }
    setState(() { _loading = true; _erro = null; });

    try {
      final result = await ApiService.login(
        _userCtrl.text.trim(),
        _passCtrl.text,
      );
      if (!mounted) return;

      if (result['status'] == 200) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const HomeScreen()),
        );
      } else {
        setState(() => _erro = result['error'] ?? 'Credenciais inválidas.');
      }
    } catch (e) {
      setState(() => _erro = 'Não foi possível conectar ao servidor.\nVerifique sua conexão.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1a0a0a),
      body: Stack(
        children: [
          // Fundo decorativo
          Positioned.fill(
            child: CustomPaint(painter: _BordadoBgPainter()),
          ),

          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 400),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 30,
                      offset: const Offset(0, 10),
                    ),
                  ],
                ),
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Logo
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFFDC3545),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(Icons.content_cut,
                          color: Colors.white, size: 40),
                    ),
                    const SizedBox(height: 16),
                    const Text('PONTO',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFFDC3545),
                          letterSpacing: 4,
                        )),
                    const Text('Sistema de Bordados',
                        style: TextStyle(color: Colors.grey, fontSize: 13)),
                    const SizedBox(height: 32),

                    // Erro
                    if (_erro != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF5F5),
                          border: Border.all(color: const Color(0xFFF5C6CB)),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.error_outline,
                                color: Color(0xFFDC3545), size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(_erro!,
                                  style: const TextStyle(
                                    color: Color(0xFF842029), fontSize: 13)),
                            ),
                          ],
                        ),
                      ),

                    // Campo usuário
                    TextField(
                      controller: _userCtrl,
                      decoration: _inputDecoration('Usuário', Icons.person_outline),
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 12),

                    // Campo senha
                    TextField(
                      controller: _passCtrl,
                      obscureText: !_showPass,
                      decoration: _inputDecoration('Senha', Icons.lock_outline).copyWith(
                        suffixIcon: IconButton(
                          icon: Icon(_showPass
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined),
                          onPressed: () => setState(() => _showPass = !_showPass),
                        ),
                      ),
                      onSubmitted: (_) => _login(),
                    ),
                    const SizedBox(height: 24),

                    // Botão entrar
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _loading ? null : _login,
                        child: _loading
                            ? const SizedBox(
                                height: 20, width: 20,
                                child: CircularProgressIndicator(
                                    color: Colors.white, strokeWidth: 2))
                            : const Text('Entrar',
                                style: TextStyle(
                                    fontSize: 16, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  InputDecoration _inputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, color: Colors.grey),
      filled: true,
      fillColor: const Color(0xFFF8F9FA),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: Color(0xFFDC3545), width: 1.5),
      ),
    );
  }
}

// Fundo decorativo com padrão de bordado
class _BordadoBgPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFDC3545).withOpacity(0.06)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;

    const spacing = 24.0;
    for (double x = 0; x < size.width + size.height; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(0, x), paint);
      canvas.drawLine(
          Offset(size.width, x - size.width),
          Offset(x - size.height, size.height), paint);
    }
  }

  @override
  bool shouldRepaint(_) => false;
}

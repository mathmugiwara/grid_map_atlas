# Como subir o projeto no GitHub e PythonAnywhere

Siga estes passos simples para colocar seu projeto no GitHub e depois puxar diretamente no PythonAnywhere.

---

## Parte 1: Subir o projeto no GitHub

### Passo 1: Criar um repositório no GitHub
1. Acesse [github.com](https://github.com/) e faça login.
2. Clique no botão **New** (Novo) para criar um repositório.
3. Dê um nome ao repositório (ex: `gridmap-postes`).
4. Deixe como **Privado** (ou Público, se preferir) e **NÃO** marque a opção de adicionar README, .gitignore ou licença (pois já temos estes arquivos localmente).
5. Clique em **Create repository**.

### Passo 2: Enviar o código local pelo terminal (PowerShell)
Abra o terminal na pasta `PostesApp` e execute os comandos abaixo:

```powershell
# 1. Inicializar o Git na pasta PostesApp
git init

# 2. Adicionar todos os arquivos (o .gitignore evitará subir o banco de dados e as fotos de teste)
git add .

# 3. Criar o primeiro commit
git commit -m "Commit inicial: Grid Map Atlas simples"

# 4. Renomear a branch principal para main
git branch -M main

# 5. Vincular ao seu repositório do GitHub (Substitua SEU-USUARIO e SEU-REPOSITORIO)
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git

# 6. Enviar os arquivos para o GitHub
git push -u origin main
```

---

## Parte 2: Subir direto no PythonAnywhere

Como seu repositório no GitHub é privado, a forma mais segura e fácil de cloná-lo no PythonAnywhere sem precisar digitar senha toda hora é usando uma **chave SSH**.

### Passo 1: Gerar uma Chave SSH no PythonAnywhere
1. Acesse seu painel do **PythonAnywhere** e abra um console **Bash**.
2. Cole o comando abaixo para gerar a chave (pode apertar `Enter` em todas as perguntas para deixar sem senha):
   ```bash
   ssh-keygen -t ed25519 -C "gridmapgovernance"
   ```
3. Veja e copie a chave gerada com o comando:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   *(Copie todo o texto que começa com `ssh-ed25519...`)*

### Passo 2: Adicionar a chave no seu GitHub
1. No seu GitHub, vá nas configurações da sua conta (**Settings** no canto superior direito).
2. No menu esquerdo, clique em **SSH and GPG keys**.
3. Clique em **New SSH key**.
4. Cole um título (ex: `PythonAnywhere`) e cole a chave que você copiou no campo **Key**.
5. Clique em **Add SSH key**.

### Passo 3: Clonar o projeto no PythonAnywhere pelo terminal Bash
Volte no console **Bash** do PythonAnywhere e execute:

```bash
# 1. Ir para a sua pasta principal do usuário
cd ~

# 2. Clonar o projeto usando o endereço SSH do GitHub (pegue no botão verde "Code" no GitHub e mude para a aba "SSH")
git clone git@github.com:SEU-USUARIO/SEU-REPOSITORIO.git PostesApp

# 3. Criar o ambiente virtual e instalar as dependências
cd ~/PostesApp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Parte 4: Atualizar o site quando fizer mudanças futuras

Sempre que você fizer uma alteração no computador local e quiser atualizar o site que já está rodando no PythonAnywhere, siga este fluxo simples:

### No seu computador local:
```powershell
git add .
git commit -m "Descrição da sua alteração"
git push origin main
```

### No console Bash do PythonAnywhere:
```bash
cd ~/PostesApp
git pull
```
Depois, vá na aba **Web** do painel do PythonAnywhere e clique no botão verde **Reload** para aplicar as atualizações!

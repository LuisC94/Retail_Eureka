import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

doc = docx.Document()

# Set Margins
for sec in doc.sections:
    sec.top_margin = Inches(0.9)
    sec.bottom_margin = Inches(0.9)
    sec.left_margin = Inches(0.9)
    sec.right_margin = Inches(0.9)

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def add_code_block(doc, code_text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.2)
    run = p.add_run(code_text)
    run.font.name = 'Consolas'
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(30, 30, 30)
    # Add a light background
    pPr = p._p.get_or_add_pPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F4F8"/>')
    pPr.append(shd)

# Title
title_p = doc.add_paragraph()
title_p.paragraph_format.space_before = Pt(0)
title_p.paragraph_format.space_after = Pt(4)
title_run = title_p.add_run('Retail Eureka — Hyperledger Fabric Blockchain')
title_run.font.name = 'Calibri'
title_run.font.size = Pt(22)
title_run.font.bold = True
title_run.font.color.rgb = RGBColor(16, 44, 87)

# Subtitle
sub_p = doc.add_paragraph()
sub_p.paragraph_format.space_after = Pt(16)
sub_run = sub_p.add_run('Manual Completo de Instalação, Criação da Rede Local e Deploy do Web Service (Porta 3000)')
sub_run.font.name = 'Calibri'
sub_run.font.size = Pt(13)
sub_run.font.italic = True
sub_run.font.color.rgb = RGBColor(80, 80, 80)

# Section 1 - Overview
h1 = doc.add_heading('1. Visão Geral e Arquitetura', level=1)
h1.paragraph_format.space_before = Pt(12)
h1.paragraph_format.space_after = Pt(6)

doc.add_paragraph(
    'O serviço de Blockchain da plataforma Retail Eureka é baseado em Hyperledger Fabric (v2.5.x LTS), '
    'uma infraestrutura de Distributed Ledger Technology (DLT) empresarial, permissionada e de alto desempenho. '
    'A arquitetura é composta por 3 camadas completamente desacopladas:'
)

doc.add_paragraph(
    '1. Rede Blockchain (Fabric): Contentores Docker com os nós validadores (Peers), nó de consenso (Orderer) e Autoridade Certificadora (CA).\n'
    '2. Smart Contract (Chaincode "saip"): Código em Node.js (JavaScript) instalado e executado dentro dos nós para validar e persistir o estado do lote.\n'
    '3. Web Service REST (Golang - Porta 3000): API Middleware que se autentica com certificados digitais e expõe os endpoints HTTP /invoke e /query para qualquer cliente externo (como o Django).'
)

# Section 2 - Table of Components
h2 = doc.add_heading('2. Componentes e Estrutura de Pastas', level=1)
h2.paragraph_format.space_before = Pt(12)
h2.paragraph_format.space_after = Pt(6)

table = doc.add_table(rows=1, cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr_cells = table.rows[0].cells
headers = ['Diretoria / Ficheiro', 'Tecnologia', 'Função no Ecossistema']
for idx, text in enumerate(headers):
    hdr_cells[idx].text = text
    set_cell_background(hdr_cells[idx], '102C57')
    p = hdr_cells[idx].paragraphs[0]
    p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
    p.runs[0].font.bold = True

components_data = [
    ('chaincode/', 'Node.js (JavaScript)', 'Contrato Inteligente com funções CreateOrder, ReadOrder, UpdateOrder'),
    ('rest_api/', 'Golang (Porta 3000)', 'API REST Middleware com rotas /invoke e /query e certificados MSP'),
    ('setup_scripts/', 'Bash / Shell Scripts', 'Scripts de automação (bootstrap, arranque da rede e deploy do chaincode)'),
    ('test_client.py', 'Python', 'Script de teste autónomo para validar gravação e leitura local'),
    ('README.md', 'Markdown', 'Guia rápido e comandos de referência no repositório')
]

for d, tech, desc in components_data:
    row_cells = table.add_row().cells
    row_cells[0].text = d
    row_cells[1].text = tech
    row_cells[2].text = desc
    set_cell_background(row_cells[0], 'F5F5F5')
    set_cell_background(row_cells[1], 'FFFFFF')
    set_cell_background(row_cells[2], 'FFFFFF')

# Section 3 - Step by step tutorial
h3 = doc.add_heading('3. Guia Passo a Passo de Instalação (Máquina Limpa / Nova)', level=1)
h3.paragraph_format.space_before = Pt(14)
h3.paragraph_format.space_after = Pt(6)

# Step 1
doc.add_heading('Passo 1: Instalação de Pré-Requisitos', level=2)
doc.add_paragraph(
    'Numa nova máquina (Windows com WSL2 Ubuntu 22.04 ou Linux nativo), execute os seguintes comandos no terminal:'
)
add_code_block(doc, 
"""# 1. Atualizar pacotes do sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Git, cURL, Docker e Docker Compose
sudo apt install -y git curl docker.io docker-compose
sudo usermod -aG docker $USER

# 3. Instalar Golang (v1.20+)
sudo apt install -y golang-go

# 4. Instalar Node.js (v18+) e npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs"""
)

# Step 2
doc.add_heading('Passo 2: Descarregar o Hyperledger Fabric (Bootstrap)', level=2)
doc.add_paragraph(
    'Navegue para a pasta do Web Service e execute o script de bootstrap para descarregar os binários oficiais e imagens Docker:'
)
add_code_block(doc,
"""cd "Web Services/blockchain_service"
chmod +x setup_scripts/*.sh
./setup_scripts/bootstrap_fabric.sh"""
)

# Step 3
doc.add_heading('Passo 3: Levantar a Rede Local e Fazer Deploy do Smart Contract', level=2)
doc.add_paragraph(
    'Execute o script de automação para subir os contentores da rede (Peers, Orderer, CA) e instalar o Chaincode "saip":'
)
add_code_block(doc,
"""./setup_scripts/start_network_and_deploy.sh"""
)
doc.add_paragraph(
    'Este comando cria o canal "mychannel", sobe os contentores Docker da organização e instala o smart contract '
    'JavaScript localizado na pasta "chaincode/".'
)

# Step 4
doc.add_heading('Passo 4: Iniciar o Web Service REST em Go (Porta 3000)', level=2)
doc.add_paragraph(
    'Abra um novo terminal (ou execute em background) para iniciar o servidor REST:'
)
add_code_block(doc,
"""cd "Web Services/blockchain_service/rest_api"
go run main.go"""
)
doc.add_paragraph(
    'O servidor iniciará na porta 3000 e exibirá a mensagem de sucesso com os caminhos dos certificados carregados.'
)

# Step 5
doc.add_heading('Passo 5: Testar o Web Service Localmente', level=2)
doc.add_paragraph(
    'Para validar a gravação e leitura na rede Blockchain, execute o script de teste em Python:'
)
add_code_block(doc,
"""python test_client.py"""
)

# Section 4 - Protocol Specification
h4 = doc.add_heading('4. Especificação dos Endpoints REST', level=1)
h4.paragraph_format.space_before = Pt(14)
h4.paragraph_format.space_after = Pt(6)

doc.add_heading('4.1. Gravar / Modificar Transação (POST /invoke)', level=2)
doc.add_paragraph(
    '• URL: http://localhost:3000/invoke\n'
    '• Content-Type: application/x-www-form-urlencoded\n'
    '• Parâmetros:\n'
    '   - channelid: "mychannel"\n'
    '   - chaincodeid: "saip"\n'
    '   - function: "CreateOrder" ou "UpdateOrder"\n'
    '   - args: [JSON_COM_DADOS_DO_LOTE]'
)

doc.add_heading('4.2. Consultar Transação (POST /query)', level=2)
doc.add_paragraph(
    '• URL: http://localhost:3000/query\n'
    '• Content-Type: application/x-www-form-urlencoded\n'
    '• Parâmetros:\n'
    '   - channelid: "mychannel"\n'
    '   - chaincodeid: "saip"\n'
    '   - function: "ReadOrder" ou "GetAllOrders"\n'
    '   - args: ["ID_DO_LOTE"]'
)

# Section 5 - Django Integration
h5 = doc.add_heading('5. Integração com a Plataforma Django', level=1)
h5.paragraph_format.space_before = Pt(14)
h5.paragraph_format.space_after = Pt(6)

doc.add_paragraph(
    'Para que a plataforma Django comunique com a rede local, basta configurar no ficheiro .env ou core/settings.py:'
)
add_code_block(doc,
"""FABRIC_API_URL = "http://localhost:3000" """
)
doc.add_paragraph(
    'O serviço dashboard/services/fabric_service.py (classe FabricService) encarrega-se de enviar os dados '
    'de cada colheita, transporte e receção de forma 100% transparente e imutável.'
)

out_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(out_dir, "Manual_Instalacao_Deploy_Blockchain.docx")
doc.save(out_path)
print(f"Manual criado com sucesso em: {out_path}")

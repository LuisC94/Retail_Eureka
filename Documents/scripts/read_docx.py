import zipfile
import xml.etree.ElementTree as ET

def extract(path):
    d = zipfile.ZipFile(path)
    xml = d.read('word/document.xml')
    root = ET.fromstring(xml)
    text = ''.join(node.text for node in root.iter() if node.tag.endswith('}t') and node.text)
    with open('docx_content.txt', 'w', encoding='utf-8') as f:
        f.write(text)

extract('D2.2._Report_Solution_Architecture_Protocol_Final_refs_JB.docx')

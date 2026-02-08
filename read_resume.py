from docx import Document
import os

def read_docx(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

if __name__ == '__main__':
    resume_path = "/Users/xuming/.agentica/workspace/徐明_简历.docx"
    if os.path.exists(resume_path):
        resume_content = read_docx(resume_path)
        print(resume_content)
    else:
        print("简历文件不存在")
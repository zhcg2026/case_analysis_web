# -*- coding: utf-8 -*-
"""Word 模板解析器 - 提取模板结构、图片位置等信息"""
import os
import json
import shutil
from docx import Document
from docx.oxml.ns import qn


def parse_docx_template(file_path):
    """
    解析 Word 模板，返回结构化信息
    
    Returns:
        dict: {
            "sections": [...],        # 章节列表
            "images": [...],          # 图片信息
            "tables": [...],          # 表格信息
            "summary_section": {...}  # 总结章节信息
        }
    """
    doc = Document(file_path)
    
    result = {
        "sections": [],
        "images": [],
        "tables": [],
        "summary_section": None
    }
    
    # 收集所有段落信息
    paragraphs_info = []
    for i, p in enumerate(doc.paragraphs):
        para_info = {
            "index": i,
            "style": p.style.name,
            "text": p.text,
            "has_image": _has_image(p),
            "image_info": _get_image_info(p) if _has_image(p) else None,
        }
        paragraphs_info.append(para_info)
    
    # 识别章节（从 Heading 1 样式）
    sections = []
    for i, para in enumerate(paragraphs_info):
        if para["style"] == "Heading 1":
            section = {
                "index": len(sections),
                "title": para["text"],
                "heading_paragraph_index": para["index"],
                "image_paragraph_index": None,
                "caption_paragraph_index": None,
                "table_index": None,
                "query": "",  # 用户需要填写
                "chart_type": "bar",  # 默认柱状图
            }
            
            # 向后查找图片和图注
            for j in range(i + 1, min(i + 10, len(paragraphs_info))):
                next_para = paragraphs_info[j]
                
                # 遇到下一个标题就停止
                if next_para["style"] in ["Heading 1", "Heading 2"] and j > i + 1:
                    break
                
                # 找到图片
                if next_para["has_image"] and section["image_paragraph_index"] is None:
                    section["image_paragraph_index"] = next_para["index"]
                    result["images"].append({
                        "paragraph_index": next_para["index"],
                        "section_index": len(sections),
                        "image_info": next_para["image_info"]
                    })
                
                # 找到图注
                if next_para["style"] == "Caption" and section["caption_paragraph_index"] is None:
                    section["caption_paragraph_index"] = next_para["index"]
            
            sections.append(section)
    
    result["sections"] = sections
    
    # 识别表格位置
    for i, table in enumerate(doc.tables):
        table_pos = _get_table_paragraph_index(doc, i)
        # 找到表格前面最近的标题
        table_section_index = None
        for j, section in enumerate(sections):
            if section["heading_paragraph_index"] < len(doc.paragraphs):
                # 检查表格是否在这个章节范围内
                if j < len(sections) - 1:
                    next_section = sections[j + 1]
                    # 表格在当前章节标题之后、下一章节标题之前
                    if section["heading_paragraph_index"] <= table_pos < next_section["heading_paragraph_index"]:
                        table_section_index = j
                        break
                else:
                    # 最后一个章节：表格在其标题之后
                    if table_pos >= section["heading_paragraph_index"]:
                        table_section_index = j
                        break
        
        # 如果表格在第一个章节标题之前，关联到第一个章节
        if table_section_index is None and sections and table_pos < sections[0]["heading_paragraph_index"]:
            table_section_index = 0
        
        result["tables"].append({
            "table_index": i,
            "rows": len(table.rows),
            "cols": len(table.columns) if table.rows else 0,
            "section_index": table_section_index,
            "header": [cell.text[:30] for cell in table.rows[0].cells] if table.rows else []
        })
        
        # 关联表格到章节
        if table_section_index is not None and sections[table_section_index]["table_index"] is None:
            sections[table_section_index]["table_index"] = i
    
    # 识别总结章节
    for i, para in enumerate(paragraphs_info):
        if para["style"] == "Heading 1" and "总结" in para["text"]:
            summary = {
                "heading_paragraph_index": para["index"],
                "title": para["text"],
                "subsections": []
            }
            
            # 查找子章节
            for j in range(i + 1, len(paragraphs_info)):
                next_para = paragraphs_info[j]
                if next_para["style"] == "Heading 2":
                    summary["subsections"].append({
                        "title": next_para["text"],
                        "paragraph_index": next_para["index"]
                    })
                elif next_para["style"] == "Heading 1":
                    break
            
            result["summary_section"] = summary
            break
    
    return result


def extract_template_images(file_path, output_dir):
    """
    提取模板中的所有图片
    
    Args:
        file_path: Word 文件路径
        output_dir: 图片输出目录
    
    Returns:
        list: 图片信息列表
    """
    doc = Document(file_path)
    images = []
    
    os.makedirs(output_dir, exist_ok=True)
    
    for i, rel in enumerate(doc.part.rels.values()):
        if "image" in rel.reltype:
            blob = rel.target_part.blob
            ext = rel.target_ref.split(".")[-1]
            filename = f"image_{i}.{ext}"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(blob)
            
            images.append({
                "rId": rel.rId,
                "filename": filename,
                "filepath": filepath,
                "size": len(blob),
                "extension": ext
            })
    
    return images


def copy_template_file(source_path, dest_dir):
    """
    复制模板文件到目标目录
    
    Args:
        source_path: 源文件路径
        dest_dir: 目标目录
    
    Returns:
        str: 复制后的文件路径
    """
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, "template.docx")
    shutil.copy2(source_path, dest_path)
    return dest_path


def replace_image_in_doc(doc, paragraph_index, new_image_bytes, image_ext="png"):
    """
    替换文档中指定段落的图片
    
    Args:
        doc: python-docx Document 对象
        paragraph_index: 段落索引
        new_image_bytes: 新图片的字节数据
        image_ext: 图片扩展名
    
    Returns:
        bool: 是否成功替换
    """
    if paragraph_index >= len(doc.paragraphs):
        return False
    
    paragraph = doc.paragraphs[paragraph_index]
    
    # 查找段落中的图片元素
    drawings = paragraph._element.findall(f".//{qn('w:drawing')}")
    if not drawings:
        return False
    
    for drawing in drawings:
        # 查找图片引用
        blips = drawing.findall(f".//{qn('a:blip')}")
        for blip in blips:
            r_embed = blip.get(qn("r:embed"))
            if r_embed and r_embed in doc.part.rels:
                # 替换图片内容
                rel = doc.part.rels[r_embed]
                rel.target_part._blob = new_image_bytes
                return True
    
    return False


def replace_table_in_doc(doc, table_index, new_data, max_rows=20):
    """
    替换文档中指定索引的表格数据
    
    Args:
        doc: python-docx Document 对象
        table_index: 表格索引
        new_data: 新数据（列表字典）
        max_rows: 最大行数
    
    Returns:
        bool: 是否成功替换
    """
    if table_index >= len(doc.tables):
        return False
    
    table = doc.tables[table_index]
    if not new_data:
        return False
    
    # 获取列名
    cols = list(new_data[0].keys())
    
    # 清空现有表格（保留表头行）
    while len(table.rows) > 1:
        row = table.rows[-1]
        row._element.getparent().remove(row._element)
    
    # 更新表头
    header_row = table.rows[0]
    for j, col in enumerate(cols):
        if j < len(header_row.cells):
            cell = header_row.cells[j]
            cell.text = str(col)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
    
    # 添加数据行
    for row_data in new_data[:max_rows]:
        row = table.add_row()
        for j, col in enumerate(cols):
            if j < len(row.cells):
                val = row_data.get(col, "")
                if isinstance(val, float):
                    row.cells[j].text = f"{val:,.2f}"
                else:
                    row.cells[j].text = str(val) if val else ""
    
    return True


def _has_image(paragraph):
    """检查段落是否包含图片"""
    drawings = paragraph._element.findall(f".//{qn('w:drawing')}")
    return len(drawings) > 0


def _get_image_info(paragraph):
    """获取段落中图片的信息"""
    drawings = paragraph._element.findall(f".//{qn('w:drawing')}")
    images = []
    
    for drawing in drawings:
        blips = drawing.findall(f".//{qn('a:blip')}")
        for blip in blips:
            r_embed = blip.get(qn("r:embed"))
            if r_embed:
                images.append({"rId": r_embed})
    
    return images[0] if images else None


def _get_table_paragraph_index(doc, table_index):
    """获取表格在文档中的精确段落位置（通过分析XML结构）"""
    from docx.oxml.ns import qn
    
    if table_index >= len(doc.tables):
        return len(doc.paragraphs)
    
    # 获取文档body的所有子元素
    body = doc.element.body
    
    # 计算每个段落的全局索引
    para_index = 0
    table_count = 0
    
    for child in body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag == 'p':  # 段落
            para_index += 1
        elif tag == 'tbl':  # 表格
            if table_count == table_index:
                # 表格在其前面的段落之后
                return para_index
            table_count += 1
    
    return para_index

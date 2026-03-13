#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接从Excel文件中提取图片
"""
import zipfile
import xml.etree.ElementTree as ET
import os
import shutil

def extract_images_from_excel(excel_path, output_dir):
    """
    从Excel文件中提取图片
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 打开Excel文件（实际上是一个ZIP文件）
    with zipfile.ZipFile(excel_path, 'r') as zip_ref:
        # 读取工作表XML
        with zip_ref.open('xl/worksheets/sheet1.xml') as f:
            sheet_xml = f.read()
        
        # 解析工作表XML
        sheet_root = ET.fromstring(sheet_xml)
        
        # 读取drawing关系文件
        try:
            with zip_ref.open('xl/drawings/_rels/drawing1.xml.rels') as f:
                drawing_rels_xml = f.read()
        except KeyError:
            print("没有找到drawing关系文件")
            return
        
        # 解析drawing关系文件
        drawing_rels_root = ET.fromstring(drawing_rels_xml)
        
        # 创建关系ID到图片文件的映射
        rels_map = {}
        for rel in drawing_rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
            rel_id = rel.get('Id')
            target = rel.get('Target')
            if target.startswith('../media/'):
                image_file = 'xl/media/' + target[9:]
                rels_map[rel_id] = image_file
        
        print(f"找到 {len(rels_map)} 个图片关系")
        
        # 读取drawing XML
        try:
            with zip_ref.open('xl/drawings/drawing1.xml') as f:
                drawing_xml = f.read()
        except KeyError:
            print("没有找到drawing文件")
            return
        
        # 解析drawing XML
        drawing_root = ET.fromstring(drawing_xml)
        
        # 提取图片位置信息
        image_map = {}
        for anchor in drawing_root.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}twoCellAnchor'):
            # 获取图片位置
            from_elem = anchor.find('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}from')
            if from_elem is not None:
                row_elem = from_elem.find('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row')
                col_elem = from_elem.find('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}col')
                if row_elem is not None and col_elem is not None:
                    row = int(row_elem.text) + 1  # 转换为1-based索引
                    col = int(col_elem.text)
                    
                    # 获取图片关系ID
                    blip = anchor.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                    if blip is not None:
                        embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if embed and embed in rels_map:
                            image_file = rels_map[embed]
                            if row not in image_map:
                                image_map[row] = []
                            image_map[row].append(image_file)
        
        print(f"找到 {len(image_map)} 行包含图片")
        
        # 提取图片文件
        for row, image_files in image_map.items():
            print(f"行 {row}: {len(image_files)} 张图片")
            for i, image_file in enumerate(image_files):
                try:
                    # 提取图片文件
                    with zip_ref.open(image_file) as source:
                        image_data = source.read()
                        
                        # 保存图片文件
                        output_file = os.path.join(output_dir, f'row_{row}_image_{i}.jpeg')
                        with open(output_file, 'wb') as target:
                            target.write(image_data)
                        
                        print(f"  提取图片: {output_file} ({len(image_data)} bytes)")
                except Exception as e:
                    print(f"  提取图片失败: {str(e)}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("用法: python extract_images.py <excel文件路径> <输出目录>")
        sys.exit(1)
    
    extract_images_from_excel(sys.argv[1], sys.argv[2])

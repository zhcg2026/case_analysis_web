#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查Excel文件中的图片信息
"""
import sys
import openpyxl
from openpyxl.drawing.image import Image
import zipfile
import os

def check_excel_images(file_path):
    print(f"检查文件: {file_path}")
    print(f"文件大小: {os.path.getsize(file_path)} bytes")
    
    # 方法1: 使用openpyxl检查
    print("\n=== 方法1: 使用openpyxl检查 ===")
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    
    print(f"工作表名称: {ws.title}")
    print(f"工作表中的图片数量: {len(ws._images)}")
    
    for i, img in enumerate(ws._images):
        print(f"\n图片 {i+1}:")
        print(f"  类型: {type(img)}")
        print(f"  锚点: {img.anchor}")
        if hasattr(img, 'anchor'):
            print(f"  锚点类型: {type(img.anchor)}")
            if hasattr(img.anchor, '_from'):
                print(f"  位置: 行={img.anchor._from.row}, 列={img.anchor._from.col}")
        if hasattr(img, '_data'):
            print(f"  数据大小: {len(img._data) if img._data else 0} bytes")
        if hasattr(img, 'ref'):
            print(f"  ref类型: {type(img.ref)}")
    
    # 方法2: 检查Excel文件内部结构
    print("\n=== 方法2: 检查Excel文件内部结构 ===")
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        
        # 检查媒体文件
        media_files = [f for f in file_list if 'media' in f.lower()]
        print(f"媒体文件数量: {len(media_files)}")
        for media_file in media_files:
            print(f"  媒体文件: {media_file}")
        
        # 检查图片文件
        image_files = [f for f in file_list if f.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
        print(f"图片文件数量: {len(image_files)}")
        for image_file in image_files:
            print(f"  图片文件: {image_file}")
        
        # 检查drawing文件
        drawing_files = [f for f in file_list if 'drawing' in f.lower()]
        print(f"绘图文件数量: {len(drawing_files)}")
        for drawing_file in drawing_files:
            print(f"  绘图文件: {drawing_file}")
        
        # 检查OLE对象
        ole_files = [f for f in file_list if 'oleObject' in f.lower() or 'embeddings' in f.lower()]
        print(f"OLE对象数量: {len(ole_files)}")
        for ole_file in ole_files:
            print(f"  OLE对象: {ole_file}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python check_excel_images.py <excel文件路径>")
        sys.exit(1)
    
    check_excel_images(sys.argv[1])

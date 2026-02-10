import pandas as pd
import re

def clean_problem_description(text):
    """清理问题描述字段，删除所有任务编号、姓名、电话号码和详细地址"""
    if pd.isna(text) or text.strip() == "":
        return text
    
    text_str = str(text)
    
    # 1. 删除电话号码
    # 匹配手机、座机和短号码
    text_str = re.sub(r'1[3-9]\d{9}|0\d{2,3}-?\d{7,8}|\b\d{2,4}\b', '', text_str)
    
    # 2. 删除任务编号
    # 1. 纯数字串（长度4或更长）
    text_str = re.sub(r'\d{4,}', '', text_str)
    # 2. 字母+数字组合
    text_str = re.sub(r'[A-Za-z]+\d+|\d+[A-Za-z]+', '', text_str)
    # 3. 中文+数字组合（如"嘉靖012245"）
    text_str = re.sub(r'[\u4e00-\u9fa5]+\d+', '', text_str)
    # 4. 中文+字母+数字组合
    text_str = re.sub(r'[\u4e00-\u9fa5]+[A-Za-z]+\d+', '', text_str)
    
    # 3. 删除姓名（简单处理，假设姓名为2-4个中文字符）
    text_str = re.sub(r'[\u4e00-\u9fa5]{2,4}', '', text_str)
    
    # 4. 删除详细地址（简单处理，假设地址包含路、街、巷、号等关键词）
    text_str = re.sub(r'[\u4e00-\u9fa5]+[路街巷道号区市县镇村]+[\u4e00-\u9fa50-9]+', '', text_str)
    
    # 5. 删除特殊符号
    text_str = re.sub(r'[!@#$%^&*()_+\-=\[\]{};\'"\\|<>\/?]', '', text_str)
    
    # 6. 清理多余的空格
    text_str = re.sub(r'\s+', ' ', text_str).strip()
    
    return text_str

# 测试用例
test_cases = [
    "河东路：滏水东街橄榄城12345热线：38 至嘉靖012245市盐湖区：1月28日 012260盐湖区学苑路西012282市民投诉：2025年011988 盐湖区：1、20 011557市民投诉：盐湖区011241清运垃圾车机",
    "电话号码：13812345678，编号：AB1234，特殊符号：!@#$%",
    "座机：010-12345678，编号：123456，地址：北京市朝阳区"
]

print("测试结果：")
for i, test_case in enumerate(test_cases, 1):
    result = clean_problem_description(test_case)
    print(f"测试用例 {i}: {test_case}")
    print(f"处理结果: {result}")
    print()
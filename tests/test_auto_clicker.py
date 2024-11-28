import re
from rapidfuzz import fuzz


def preprocess_title(title):
    """
    预处理标题，去除所有非中文字符和数字字符。

    参数:
    - title: 原始标题字符串。

    返回:
    - 处理后的标题字符串。
    """
    return re.sub(r'[^\u4e00-\u9fa5\d]', '', title)


def extract_key_fields(title):
    """
    提取标题中的关键字段，如学校名称和考试类型。

    参数:
    - title: 预处理后的标题字符串。

    返回:
    - Tuple of (学校名称, 考试类型)
    """
    # 假设标题格式为：精品解析：<学校名称><学年><年级><考试类型>语文试题
    # 例如：精品解析：辽宁省抚顺市实验中学20242025学年八年级上学期期初考试语文试题
    match = re.match(r'精品解析：(.+?)(\d{4}-\d{4}学年八年级.+?语文试题)', title)
    if match:
        school_name = match.group(1)
        exam_type = match.group(2)
        return school_name, exam_type
    return "", ""


def calculate_similarity(title1, title2):
    """
    计算两个标题之间的各种相似度分数。

    参数:
    - title1: 第一个标题字符串。
    - title2: 第二个标题字符串。

    返回:
    - Dictionary containing different similarity scores.
    """
    return {
        'fuzz_ratio': fuzz.ratio(title1, title2),
        'fuzz_partial_ratio': fuzz.partial_ratio(title1, title2),
        'fuzz_token_sort_ratio': fuzz.token_sort_ratio(title1, title2),
        'fuzz_token_set_ratio': fuzz.token_set_ratio(title1, title2)
    }


def main():
    # 原始标题
    original_title = "精品解析：辽宁省抚顺市实验中学2024-2025学年八年级上学期期初考试语文试题"

    # 下载目录中的两个文件名
    title_a = "精品解析：辽宁省抚顺市实验中学2024-2025学年八年级上学期期初考试语文试题.docx"
    title_b = "精品解析：辽宁省大连市甘井子区2024-2025学年八年级10月月考语文试题.docx"

    # 预处理标题
    processed_original = preprocess_title(original_title)
    processed_a = preprocess_title(title_a)
    processed_b = preprocess_title(title_b)

    # 提取关键字段
    school_a, exam_a = extract_key_fields(processed_a)
    school_b, exam_b = extract_key_fields(processed_b)
    school_original, exam_original = extract_key_fields(processed_original)

    print("=== 标题预处理 ===")
    print(f"原始标题预处理后: {processed_original}")
    print(f"文件A预处理后: {processed_a}")
    print(f"文件B预处理后: {processed_b}\n")

    print("=== 提取关键字段 ===")
    print(f"原始标题 - 学校名称: {school_original}, 考试类型: {exam_original}")
    print(f"文件A - 学校名称: {school_a}, 考试类型: {exam_a}")
    print(f"文件B - 学校名称: {school_b}, 考试类型: {exam_b}\n")

    # 计算相似度
    similarity_a = calculate_similarity(processed_original, processed_a)
    similarity_b = calculate_similarity(processed_original, processed_b)

    print("=== 相似度分数 ===")
    print("文件A与原始标题的相似度:")
    for key, value in similarity_a.items():
        print(f"  {key}: {value}")
    print("\n文件B与原始标题的相似度:")
    for key, value in similarity_b.items():
        print(f"  {key}: {value}")

    # 定义相似度阈值
    threshold_ratio = 90
    threshold_token_set_ratio = 90

    # 判断匹配
    print("\n=== 匹配判断 ===")

    def is_match(similarity, school_match, exam_match):
        return (similarity['fuzz_ratio'] >= threshold_ratio and
                similarity['fuzz_token_set_ratio'] >= threshold_token_set_ratio and
                school_match and
                exam_match)

    # 判断文件A
    school_match_a = school_original in school_a
    exam_match_a = exam_original in exam_a
    match_a = is_match(similarity_a, school_match_a, exam_match_a)
    print(f"文件A匹配: {'成功' if match_a else '失败'}")

    # 判断文件B
    school_match_b = school_original in school_b
    exam_match_b = exam_original in exam_b
    match_b = is_match(similarity_b, school_match_b, exam_match_b)
    print(f"文件B匹配: {'成功' if match_b else '失败'}")

    # 结果总结
    print("\n=== 结果总结 ===")
    if match_a and not match_b:
        print("只有文件A成功匹配，文件B被正确忽略。")
    elif match_a and match_b:
        print("文件A和文件B都匹配，可能需要进一步优化阈值或匹配条件。")
    else:
        print("未能成功匹配到文件A，可能需要降低阈值或检查匹配逻辑。")


if __name__ == "__main__":
    main()

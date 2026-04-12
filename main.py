import os
import re
import zipfile
import tarfile
from collections import Counter

def is_archive_file(filename):
    """检查是否为压缩包文件"""
    archive_extensions = ['.zip', '.rar', '.tar', '.gz', '.tgz', '.tar.gz']
    return any(filename.lower().endswith(ext) for ext in archive_extensions)

def extract_archive(archive_path, extract_to):
    """解压压缩包"""
    try:
        if archive_path.lower().endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif archive_path.lower().endswith(('.tar', '.gz', '.tgz', '.tar.gz')):
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
        else:
            # 对于.rar文件，需要安装rarfile库
            try:
                import rarfile
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    rar_ref.extractall(extract_to)
            except ImportError:
                print("  ❌ 不支持的压缩格式或缺少rarfile库")
                return False
        return True
    except Exception as e:
        print(f"  ❌ 解压失败: {e}")
        return False

def check_txt_files(directory):
    """检查目录下是否全是txt文件"""
    files = os.listdir(directory)
    txt_files = [f for f in files if f.lower().endswith('.txt')]
    non_txt_files = [f for f in files if not f.lower().endswith('.txt')]
    
    print(f"  📁 解压目录包含 {len(files)} 个文件")
    print(f"  📝 TXT文件: {len(txt_files)} 个")
    if non_txt_files:
        print(f"  ⚠️  非TXT文件: {len(non_txt_files)} 个 - {non_txt_files[:5]}")  # 只显示前5个
    
    return len(non_txt_files) == 0 and len(txt_files) > 0

def get_archive_files():
    """获取当前目录下的压缩包文件"""
    files = os.listdir('.')
    archives = [f for f in files if is_archive_file(f)]
    return archives

def extract_and_check():
    """解压压缩包并检查"""
    archives = get_archive_files()
    
    if not archives:
        return None
    
    print(f"🔍 发现 {len(archives)} 个压缩包:")
    for i, archive in enumerate(archives, 1):
        size = os.path.getsize(archive)
        print(f"  {i}. {archive} ({size:,} 字节)")
    
    # 选择第一个压缩包进行解压
    selected_archive = archives[0]
    print(f"\n📦 准备解压: {selected_archive}")
    
    extract_dir = "extracted_docs"
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
    
    if extract_archive(selected_archive, extract_dir):
        print("  ✅ 解压成功")
        
        if check_txt_files(extract_dir):
            print("  ✅ 解压目录全是TXT文件，开始分析...")
            return extract_dir
        else:
            print("  ⚠️  解压目录包含非TXT文件，建议重新转换")
            return None
    else:
        return None

def extract_words_from_text(text):
    """从文本中提取英文单词"""
    # 清理文本
    text = text.lower()
    
    # 移除常见干扰项
    text = re.sub(r'http[s]?://[^\s]+', '', text)  # URL
    text = re.sub(r'\S+@\S+', '', text)           # 邮箱
    text = re.sub(r'\d+\.?\d*', '', text)         # 数字
    text = re.sub(r'[^\w\s]', ' ', text)          # 特殊字符替换为空格
    
    # 提取单词（2-20个字母）
    words = re.findall(r'\b[a-z]{2,20}\b', text)
    
    # 常见英语停用词
    stop_words = {
        'the', 'and', 'to', 'of', 'a', 'in', 'that', 'is', 'it', 'for', 'on', 'with', 'as', 'by',
        'at', 'an', 'be', 'this', 'which', 'or', 'from', 'but', 'not', 'are', 'was', 'were',
        'have', 'has', 'had', 'will', 'would', 'can', 'could', 'should', 'may', 'might', 'must',
        'about', 'after', 'all', 'also', 'any', 'because', 'been', 'before', 'between', 'both',
        'does', 'each', 'during', 'even', 'first', 'found', 'further', 'gave', 'gets', 'give',
        'given', 'giving', 'good', 'have', 'having', 'here', 'himself', 'herself', 'however',
        'into', 'its', 'itself', 'just', 'know', 'like', 'made', 'make', 'many', 'more', 'most',
        'myself', 'never', 'none', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over',
        'own', 'same', 'see', 'since', 'some', 'such', 'than', 'that', 'their', 'theirs', 'them',
        'themselves', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'too', 'under',
        'until', 'very', 'was', 'way', 'well', 'were', 'what', 'when', 'where', 'which', 'while',
        'who', 'whom', 'why', 'will', 'with', 'would', 'your', 'yours', 'yourself', 'yourselves'
    }
    
    # 过滤停用词和短词
    filtered_words = [word for word in words if word not in stop_words and len(word) >= 2]
    
    return filtered_words

def analyze_txt_files_from_dir(directory):
    """分析指定目录下的TXT文件"""
    txt_files = [f for f in os.listdir(directory) if f.lower().endswith('.txt')]
    
    if not txt_files:
        print("  ❌ 目录中没有找到TXT文件")
        return None, {}
    
    print(f"  📝 找到 {len(txt_files)} 个TXT文件")
    
    word_counter = Counter()
    processed_info = {}
    
    for txt_file in txt_files:
        file_path = os.path.join(directory, txt_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            if len(text) < 100:
                continue
            
            words = extract_words_from_text(text)
            
            if words:
                word_count = len(words)
                unique_words = len(set(words))
                
                word_counter.update(words)
                
                processed_info[txt_file] = {
                    'total_words': word_count,
                    'unique_words': unique_words
                }
                
                print(f"    ✓ {txt_file}: {word_count} 单词")
                
        except Exception as e:
            print(f"    ❌ 处理 {txt_file} 失败: {e}")
    
    return word_counter, processed_info

def print_detailed_report(word_counter, processed_info):
    """打印详细报告"""
    if not word_counter:
        print("\n❌ 没有分析到任何单词")
        return
    
    total_words = sum(word_counter.values())
    unique_words = len(word_counter)
    
    print("\n" + "=" * 80)
    print("📊 英语试卷单词频率分析报告")
    print("=" * 80)
    
    print(f"📈 总体统计:")
    print(f"   • 总单词数: {total_words:,}")
    print(f"   • 不同单词数: {unique_words:,}")
    print(f"   • 平均词频: {total_words/unique_words:.1f}")
    print(f"   • 处理文件数: {len(processed_info)}")
    
    print(f"\n🔥 TOP 50 高频单词:")
    print("-" * 80)
    print(f"{'排名':<4} {'单词':<15} {'频次':<8} {'占比(%)':<8}")
    print("-" * 80)
    
    for i, (word, count) in enumerate(word_counter.most_common(50), 1):
        percentage = (count / total_words * 100) if total_words > 0 else 0
        print(f"{i:<4} {word:<15} {count:<8} {percentage:.2f}%")

def save_results(word_counter, processed_info):
    """保存结果到文件"""
    try:
        # 保存完整的单词频率
        with open('word_frequency_full.csv', 'w', encoding='utf-8-sig') as f:
            f.write('单词,出现次数,排名,占比(%)\n')
            total = sum(word_counter.values())
            for i, (word, count) in enumerate(word_counter.most_common(), 1):
                percentage = (count / total) * 100 if total > 0 else 0
                f.write(f'"{word}",{count},{i},{percentage:.2f}\n')
        
        # 保存TOP 100单词
        with open('top_100_words.txt', 'w', encoding='utf-8') as f:
            f.write("英语试卷高频单词TOP 100\n")
            f.write("=" * 50 + "\n")
            f.write(f"总单词数: {sum(word_counter.values()):,}\n")
            f.write(f"不同单词数: {len(word_counter):,}\n\n")
            
            for i, (word, count) in enumerate(word_counter.most_common(100), 1):
                percentage = (count / sum(word_counter.values()) * 100) if sum(word_counter.values()) > 0 else 0
                f.write(f"{i:3d}. {word:<20} - {count:6d}次 ({percentage:.2f}%)\n")
        
        print(f"\n💾 结果已保存到:")
        print(f"   - word_frequency_full.csv (完整CSV数据)")
        print(f"   - top_100_words.txt (前100高频词)")
        
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")

def main():
    """主函数"""
    print("🎓 英语试卷单词频率分析工具")
    print("（智能检测压缩包模式）")
    print("=" * 80)
    
    print("🔍 检查当前目录...")
    
    # 检查是否有压缩包
    archives = get_archive_files()
    
    if archives:
        print(f"📦 发现压缩包，准备解压分析...")
        extract_dir = extract_and_check()
        
        if extract_dir:
            # 分析解压后的TXT文件
            word_counter, processed_info = analyze_txt_files_from_dir(extract_dir)
            
            if word_counter:
                print_detailed_report(word_counter, processed_info)
                save_results(word_counter, processed_info)
                print(f"\n🎉 分析完成！共处理了 {len(processed_info)} 个文件")
            else:
                print("❌ 解压后未找到有效的TXT内容")
        else:
            print("\n❌ 解压失败或文件格式不符合要求")
            print("💡 建议：")
            print("   1. 前往 https://www.freeconvert.com/zh/doc-to-txt/")
            print("   2. 上传您的文档")
            print("   3. 选择'下载全部'获取TXT格式")
            print("   4. 将下载的压缩包放在此目录重新运行脚本")
    else:
        print("❌ 当前目录没有发现压缩包文件")
        print("\n💡 请按以下步骤操作：")
        print("   1. 前往 https://www.freeconvert.com/zh/doc-to-txt/")
        print("   2. 上传您的英语试卷文档（.doc/.docx）")
        print("   3. 选择转换为TXT格式")
        print("   4. 点击'下载全部'按钮获取包含所有TXT文件的压缩包")
        print("   5. 将下载的压缩包（如 archive.zip）放到此目录")
        print("   6. 重新运行此脚本")

if __name__ == "__main__":
    main()
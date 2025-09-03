# analysis_summarizer_enhanced.py
import os
import re
import shutil
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

class EnhancedAnalysisSummarizer:
    def __init__(self, source_directory: str, output_directory: str = "Analysis_Summary"):
        self.source_dir = Path(source_directory)
        self.output_dir = Path(output_directory)
        self.summary_data = {}
        
        # 设置日志
        self.setup_logging()
        
        # 定义要跳过的文件类型和目录
        self.skip_extensions = ['.bin', '.raw']  # 跳过原始二进制文件
        self.skip_directories = ['Raw_ADC_Data', 'raw_data']  # 跳过原始数据目录
        
        # 可配置的目录匹配模式
        self.calibration_patterns = [
            r'Calibration_.*_\d{8}_\d{6}_.*',  # 原始模式
            r'.*Calibration.*',                # 更宽松的模式
            r'.*[Cc]al.*',                     # 包含"cal"的模式
        ]
        
        # 定义统一的分类标准 - 更新Time_Domain子分类
        self.categories = {
            'Time_Domain': {
                'keywords': ['time_domain', '_time_', 'waveform'],
                'subcategories': ['Raw_Time', 'ROI_Time', 'Diff_Time', 'Diff_ROI_Time']
            },
            'Frequency_Domain': {
                'keywords': ['frequency_domain', '_freq_', 'spectrum'],
                'subcategories': ['Magnitude', 'Phase', 'Complex']
            },
            'Differential_Analysis': {
                'keywords': ['diff_time', 'diff_freq', 'derivative'],
                'subcategories': ['Time_Diff', 'Freq_Diff']
            },
            'Edge_Analysis': {
                'keywords': ['edge', 'rise', 'fall', 'transition'],
                'subcategories': ['Rise_Time', 'Fall_Time', 'Transition']
            },
            'Statistical_Results': {
                'keywords': ['stat', 'summary', 'report', 'average'],
                'subcategories': ['Basic_Stats', 'Advanced_Stats']
            },
            'Visualizations': {
                'keywords': ['.png', '.jpg', '.jpeg', '.bmp', 'plot', 'graph'],
                'subcategories': ['Time_Plots', 'Freq_Plots', 'Comparison_Plots']
            },
            'Calibration_Data': {
                'keywords': ['calibration', 'error', 'coefficient'],
                'subcategories': ['SOL_Data', 'Thru_Data', 'Error_Matrix']
            }
        }
    
    def setup_logging(self):
        """设置日志记录"""
        log_dir = self.output_dir / 'Logs'
        log_dir.mkdir(exist_ok=True, parents=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'summary_log.txt'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def should_skip_file(self, file_path: Path) -> bool:
        """检查是否应该跳过这个文件"""
        # 跳过隐藏文件
        if file_path.name.startswith('.'):
            return True
        
        # 跳过原始二进制文件
        if file_path.suffix.lower() in self.skip_extensions:
            return True
        
        # 检查文件路径中是否包含要跳过的目录
        for skip_dir in self.skip_directories:
            if skip_dir.lower() in str(file_path).lower():
                return True
        
        return False
    
    def should_skip_directory(self, dir_path: Path) -> bool:
        """检查是否应该跳过这个目录"""
        dir_name = dir_path.name.lower()
        
        # 跳过原始数据目录
        skip_dirs = ['raw_adc_data', 'raw_data', 'binaries', 'binary_data']
        if any(skip_dir in dir_name for skip_dir in skip_dirs):
            return True
        
        return False
    
    def create_summary_structure(self):
        """创建汇总文件夹结构"""
        self.logger.info("创建汇总文件夹结构...")
        
        # 创建主输出目录
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建主分类目录
        for category in self.categories.keys():
            category_dir = self.output_dir / category
            category_dir.mkdir(exist_ok=True)
            
            # 创建子分类目录
            for subcategory in self.categories[category]['subcategories']:
                subcategory_dir = category_dir / subcategory
                subcategory_dir.mkdir(exist_ok=True)
        
        # 创建其他辅助目录
        (self.output_dir / 'Metadata').mkdir(exist_ok=True)
        (self.output_dir / 'Cross_Analysis').mkdir(exist_ok=True)
        (self.output_dir / 'Comparison_Results').mkdir(exist_ok=True)
        (self.output_dir / 'Logs').mkdir(exist_ok=True)
        
        self.logger.info("文件夹结构创建完成")
    
    def find_all_calibration_data(self) -> List[Path]:
        """查找所有校准数据目录，使用多种模式"""
        calibration_dirs = []
        
        for pattern in self.calibration_patterns:
            regex = re.compile(pattern)
            for item in self.source_dir.iterdir():
                if item.is_dir() and regex.match(item.name) and item not in calibration_dirs:
                    calibration_dirs.append(item)
                    self.logger.debug(f"找到校准目录(模式: {pattern}): {item.name}")
        
        # 如果没有找到任何目录，尝试列出所有目录
        if not calibration_dirs:
            self.logger.warning("未找到匹配的校准目录，将列出所有目录供参考:")
            for item in self.source_dir.iterdir():
                if item.is_dir():
                    self.logger.warning(f"  目录: {item.name}")
                    calibration_dirs.append(item)  # 临时添加以便后续处理
        
        self.logger.info(f"找到 {len(calibration_dirs)} 个校准目录")
        return calibration_dirs
    
    def categorize_file(self, file_path: Path) -> Tuple[str, str]:
        """对文件进行分类"""
        filename = file_path.name.lower()
        file_stem = file_path.stem.lower()
        
        # 首先检查文件类型
        if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
            return 'Visualizations', self._get_visualization_subcategory(filename)
        
        # 然后检查关键词
        for category, info in self.categories.items():
            for keyword in info['keywords']:
                if keyword in filename or keyword in file_stem:
                    subcategory = self._get_subcategory(category, filename)
                    return category, subcategory
        
        # 最后根据内容判断
        return self._categorize_by_content(file_path)
    
    def _get_subcategory(self, category: str, filename: str) -> str:
        """获取子分类"""
        if category == 'Time_Domain':
            # 首先检查是否同时包含diff和roi
            if ('diff' in filename or 'derivative' in filename) and ('roi' in filename or '0.0_100.0' in filename):
                return 'Diff_ROI_Time'
            elif 'diff' in filename or 'derivative' in filename:
                return 'Diff_Time'
            elif 'roi' in filename or '0.0_100.0' in filename:
                return 'ROI_Time'
            else:
                return 'Raw_Time'
        
        elif category == 'Frequency_Domain':
            if 'magnitude' in filename or 'mag' in filename:
                return 'Magnitude'
            elif 'phase' in filename:
                return 'Phase'
            elif 'complex' in filename or 'real' in filename or 'imag' in filename:
                return 'Complex'
            else:
                return 'Magnitude'  # 默认
        
        elif category == 'Differential_Analysis':
            if 'time' in filename:
                return 'Time_Diff'
            else:
                return 'Freq_Diff'
        
        elif category == 'Edge_Analysis':
            if 'rise' in filename:
                return 'Rise_Time'
            elif 'fall' in filename:
                return 'Fall_Time'
            else:
                return 'Transition'
        
        elif category == 'Visualizations':
            return self._get_visualization_subcategory(filename)
        
        else:
            return self.categories[category]['subcategories'][0]  # 返回第一个子分类
    
    def _get_visualization_subcategory(self, filename: str) -> str:
        """获取可视化子分类"""
        if 'time' in filename:
            return 'Time_Plots'
        elif 'freq' in filename or 'spectrum' in filename:
            return 'Freq_Plots'
        elif 'comparison' in filename or 'compare' in filename:
            return 'Comparison_Plots'
        else:
            return 'Time_Plots'  # 默认
    
    def _categorize_by_content(self, file_path: Path) -> Tuple[str, str]:
        """根据文件内容分类"""
        if file_path.suffix.lower() == '.csv':
            try:
                df = pd.read_csv(file_path, nrows=3)
                columns = [col.lower() for col in df.columns]
                
                if any(col in ['time', 'timestamp', 'ns', 'us'] for col in columns):
                    # 检查是否同时包含diff和roi相关的列
                    has_diff = any(col in ['diff', 'difference', 'derivative'] for col in columns)
                    has_roi = any(col in ['roi', 'region_of_interest'] for col in columns)
                    
                    if has_diff and has_roi:
                        return 'Time_Domain', 'Diff_ROI_Time'
                    elif has_diff:
                        return 'Time_Domain', 'Diff_Time'
                    elif has_roi:
                        return 'Time_Domain', 'ROI_Time'
                    else:
                        return 'Time_Domain', 'Raw_Time'
                
                elif any(col in ['frequency', 'freq', 'ghz', 'mhz'] for col in columns):
                    if any(col in ['diff', 'difference'] for col in columns):
                        return 'Differential_Analysis', 'Freq_Diff'
                    else:
                        return 'Frequency_Domain', 'Magnitude'
                
                elif any(col in ['real', 'imag', 'magnitude', 'phase'] for col in columns):
                    return 'Frequency_Domain', 'Complex'
                
            except Exception as e:
                self.logger.error(f"读取文件内容失败 {file_path.name}: {e}")
        
        return 'Statistical_Results', 'Basic_Stats'
    
    def copy_file_to_summary(self, source_file: Path, calibration_dir: Path) -> bool:
        """复制文件到汇总目录"""
        # 首先检查是否应该跳过这个文件
        if self.should_skip_file(source_file):
            return False
        
        category, subcategory = self.categorize_file(source_file)
        
        if category and subcategory:
            target_dir = self.output_dir / category / subcategory
            
            # 创建带有来源信息的文件名
            cal_name = calibration_dir.name
            new_filename = f"{cal_name}_{source_file.name}"
            
            target_file = target_dir / new_filename
            
            # 处理重名文件
            counter = 1
            while target_file.exists():
                stem = target_file.stem
                suffix = target_file.suffix
                target_file = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            try:
                shutil.copy2(source_file, target_file)
                self.logger.info(f"复制: {source_file.name} -> {category}/{subcategory}/")
                return True
            except Exception as e:
                self.logger.error(f"复制文件失败 {source_file}: {e}")
                return False
        
        return False
    
    def process_calibration_directory(self, cal_dir: Path) -> int:
        """处理单个校准目录"""
        self.logger.info(f"处理目录: {cal_dir.name}")
        
        files_processed = 0
        files_skipped = 0
        
        # 处理所有文件，跳过原始数据目录
        for file_path in cal_dir.rglob('*'):
            if file_path.is_file():
                # 检查是否应该跳过这个文件
                if self.should_skip_file(file_path):
                    files_skipped += 1
                    continue
                
                # 检查文件所在目录是否应该跳过
                if self.should_skip_directory(file_path.parent):
                    files_skipped += 1
                    continue
                
                if self.copy_file_to_summary(file_path, cal_dir):
                    files_processed += 1
        
        self.logger.info(f"已处理 {files_processed} 个文件，跳过 {files_skipped} 个原始文件")
        return files_processed
    
    def create_metadata_files(self):
        """创建元数据文件"""
        self.logger.info("创建元数据文件...")
        
        metadata_dir = self.output_dir / 'Metadata'
        
        # 创建目录结构说明
        with open(metadata_dir / 'directory_structure.txt', 'w', encoding='utf-8') as f:
            f.write("分析汇总目录结构说明\n")
            f.write("=" * 50 + "\n\n")
            f.write("注意：已跳过所有原始bin文件和Raw_ADC_Data目录\n\n")
            
            for category, info in self.categories.items():
                f.write(f"{category}/\n")
                for subcategory in info['subcategories']:
                    f.write(f"  ├── {subcategory}/\n")
                f.write("\n")
        
        # 创建文件统计
        self._create_file_statistics()
        
        # 创建跳过的文件列表
        self._create_skipped_files_list()
        
        self.logger.info("元数据文件创建完成")
    
    def _create_file_statistics(self):
        """创建文件统计信息"""
        stats = {}
        total_files = 0
        
        for category in self.categories.keys():
            category_dir = self.output_dir / category
            if category_dir.exists():
                stats[category] = {}
                for subcategory in self.categories[category]['subcategories']:
                    subcategory_dir = category_dir / subcategory
                    if subcategory_dir.exists():
                        file_count = len(list(subcategory_dir.iterdir()))
                        stats[category][subcategory] = file_count
                        total_files += file_count
        
        # 写入统计文件
        with open(self.output_dir / 'Metadata' / 'file_statistics.csv', 'w', encoding='utf-8') as f:
            f.write("Category,Subcategory,FileCount\n")
            for category, subcats in stats.items():
                for subcat, count in subcats.items():
                    f.write(f"{category},{subcat},{count}\n")
                f.write(f"{category},Total,{sum(subcats.values())}\n")
            f.write(f"Overall,Total,{total_files}\n")
    
    def _create_skipped_files_list(self):
        """创建跳过的文件列表"""
        skipped_files = []
        
        for cal_dir in self.find_all_calibration_data():
            for file_path in cal_dir.rglob('*'):
                if file_path.is_file() and self.should_skip_file(file_path):
                    skipped_files.append(str(file_path.relative_to(self.source_dir)))
        
        if skipped_files:
            with open(self.output_dir / 'Metadata' / 'skipped_files.txt', 'w', encoding='utf-8') as f:
                f.write("跳过的原始文件列表\n")
                f.write("=" * 50 + "\n\n")
                for file_path in sorted(skipped_files):
                    f.write(f"{file_path}\n")
        else:
            with open(self.output_dir / 'Metadata' / 'skipped_files.txt', 'w', encoding='utf-8') as f:
                f.write("没有跳过任何文件\n")
    
    def create_cross_analysis(self):
        """创建交叉分析结果"""
        self.logger.info("创建交叉分析...")
        
        cross_analysis_dir = self.output_dir / 'Cross_Analysis'
        
        # 创建示例交叉分析报告
        with open(cross_analysis_dir / 'summary_report.md', 'w', encoding='utf-8') as f:
            f.write("# 分析结果汇总报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## 汇总概述\n")
            f.write("- 汇总了所有校准目录的分析结果\n")
            f.write("- 跳过了原始bin文件和Raw_ADC_Data目录\n")
            f.write("- 按照统一标准进行分类整理\n")
            f.write("- 便于后续的比较和分析\n\n")
            f.write("## 包含的数据类型\n")
            f.write("- CSV分析结果文件\n")
            f.write("- 图像文件（PNG, JPG等）\n")
            f.write("- 统计报告\n")
            f.write("- 校准数据\n\n")
            f.write("## 跳过的数据类型\n")
            f.write("- 原始二进制文件 (.bin, .raw)\n")
            f.write("- Raw_ADC_Data目录中的文件\n")
        
        self.logger.info("交叉分析创建完成")
    
    def run_full_summarization(self):
        """运行完整的汇总流程"""
        self.logger.info("开始分析结果汇总...")
        self.logger.info("=" * 50)
        self.logger.info("注意：将跳过所有原始bin文件和Raw_ADC_Data目录")
        self.logger.info("=" * 50)
        
        # 检查源目录是否存在
        if not self.source_dir.exists():
            self.logger.error(f"源目录不存在: {self.source_dir}")
            return
        
        # 创建文件夹结构
        self.create_summary_structure()
        
        # 查找所有校准目录
        calibration_dirs = self.find_all_calibration_data()
        
        # 处理每个目录
        total_files = 0
        for cal_dir in calibration_dirs:
            files_processed = self.process_calibration_directory(cal_dir)
            total_files += files_processed
        
        # 创建元数据
        self.create_metadata_files()
        
        # 创建交叉分析
        self.create_cross_analysis()
        
        self.logger.info("=" * 50)
        self.logger.info(f"汇总完成！总共处理了 {total_files} 个分析结果文件")
        self.logger.info(f"跳过了所有原始bin文件和Raw_ADC_Data目录")
        self.logger.info(f"汇总结果保存在: {self.output_dir.absolute()}")

# 使用示例
def main():
    # 设置源目录和输出目录
    source_directory = "data\\calibration\\Calibration_SOLT_DUT_Test_20250903_202613_P3P2"
    output_directory = "data\\calibration\\Calibration_SOLT_DUT_Test_20250903_202613_P3P2\\Analysis_Summary_Processed_Only"
    
    # 创建汇总器实例
    summarizer = EnhancedAnalysisSummarizer(source_directory, output_directory)
    
    # 运行汇总
    summarizer.run_full_summarization()
    
    print("\n分析汇总完成！已跳过所有原始bin文件，只处理分析结果文件。")

if __name__ == "__main__":
    main()

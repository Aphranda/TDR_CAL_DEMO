import os
import sys
from pathlib import Path
from typing import List, Dict
import time

class ProjectGenerator:
    """
    自动化生成网分校准系统项目结构
    示例用法：
    generator = ProjectGenerator(root_path="NetCalibration_System")
    generator.generate()
    """
    
    def __init__(self, root_path: str = "NetCalibration_System"):
        self.root = Path(root_path).absolute()
        self.folder_structure = self._define_structure()
        self.created_paths = []
        
    def _define_structure(self) -> Dict[str, List[str]]:
        """定义完整的项目结构"""
        return {
            "": [  # 根目录文件
                "README.md",
                "requirements.txt",
                ".gitignore",
                ".env"
            ],
            "src/app": [
                "__init__.py",
                "main.py"
            ],
            "src/app/core": [
                "__init__.py",
                "calibration_engine.py",
                "message_bus.py",
                "exceptions/__init__.py"
            ],
            "src/app/widgets/CalibrationPanel": [
                "__init__.py",
                "Controller.py",
                "Model.py",
                "View.py",
                "widget.ui"
            ],
            "src/app/dialogs/CalibrationWizard": [
                "__init__.py",
                "Controller.py",
                "Model.py",
                "View.py",
                "wizard.ui"
            ],
            "src/resources/ui": [
                "__init__.py"
            ],
            "config": [
                "app_settings.ini",
                "instrument_config.json"
            ],
            "docs": [
                "calibration_protocol.md"
            ],
            "tests/widget_tests": [
                "__init__.py",
                "test_calibration_panel.py"
            ]
        }
    
    def _create_item(self, path: Path, is_file: bool = False):
        """创建单个文件或目录"""
        try:
            if is_file:
                path.touch(exist_ok=True)
                print(f"📄 创建文件: {path}")
            else:
                path.mkdir(parents=True, exist_ok=True)
                print(f"📂 创建目录: {path}")
            self.created_paths.append(str(path))
        except PermissionError:
            print(f"❌ 权限不足: {path}")
        except OSError as e:
            print(f"❌ 创建失败: {path} - {str(e)}")
    
    def _validate_path(self):
        """验证目标路径是否安全"""
        if self.root.exists() and any(self.root.iterdir()):
            print(f"⚠️ 目标目录已存在且不为空: {self.root}")
            response = input("是否继续？(y/n): ").lower()
            if response != 'y':
                sys.exit(1)
    
    def generate(self):
        """执行项目生成"""
        print(f"🚀 开始生成项目结构 @ {self.root}")
        start_time = time.time()
        
        self._validate_path()
        
        # 先创建所有目录
        for dir_path in self.folder_structure.keys():
            full_path = self.root / dir_path
            self._create_item(full_path)
        
        # 然后创建文件
        for dir_path, files in self.folder_structure.items():
            for file in files:
                full_path = self.root / dir_path / file
                self._create_item(full_path, is_file=True)
        
        # 创建空__init__.py文件确保Python包识别
        py_dirs = [p for p in self.root.rglob("*/") if "__pycache__" not in str(p)]
        for d in py_dirs:
            init_file = d / "__init__.py"
            if not init_file.exists():
                init_file.touch()
        
        elapsed = time.time() - start_time
        print(f"\n✅ 项目生成完成！共创建 {len(self.created_paths)} 个项目")
        print(f"⏱️ 耗时: {elapsed:.2f}秒")
        
        # 生成报告
        report_path = self.root / "generation_report.txt"
        with open(report_path, 'w') as f:
            f.write("生成项目结构报告\n")
            f.write(f"生成时间: {time.ctime()}\n")
            f.write("\n创建的路径:\n")
            f.write("\n".join(sorted(self.created_paths)))
        
        print(f"\n📝 详细报告已保存至: {report_path}")

    def cleanup(self):
        """清理生成的项目结构（用于测试）"""
        import shutil
        shutil.rmtree(self.root)
        print(f"🧹 已清理项目目录: {self.root}")


if __name__ == "__main__":
    # 示例使用
    try:
        project_name = input("请输入项目名称 [默认: NetCalibration_System]: ") or "NetCalibration_System"
        generator = ProjectGenerator(project_name)
        
        print("\n将要创建的项目结构:")
        for dir_path, files in generator.folder_structure.items():
            print(f"├── {dir_path or '.'}")
            for file in files:
                print(f"│   ├── {file}")
        
        confirm = input("\n确认生成项目结构？(y/n): ").lower()
        if confirm == 'y':
            generator.generate()
        else:
            print("操作已取消")
    except KeyboardInterrupt:
        print("\n用户中断操作")

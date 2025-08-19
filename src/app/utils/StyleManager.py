from PyQt5.QtWidgets import QApplication
from pathlib import Path

class StyleManager:
    @staticmethod
    def load_style(style_name="style_bule"):
        """加载QSS样式表"""
        try:
            style_path = Path(__file__).parent.parent.parent / "resources" / "styles" / f"{style_name}.qss"
            with open(style_path, "r", encoding="utf-8") as f:
                style = f.read()
                QApplication.instance().setStyleSheet(style)
            return True
        except Exception as e:
            print(f"加载样式表失败: {str(e)}")
            return False

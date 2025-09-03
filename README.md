
```
TDR_CAL_DEMO
├─ 📁.vscode
├─ 📁config
│  ├─ 📄app_settings.ini
│  ├─ 📄instrument_config.json
│  └─ 📄__init__.py
├─ 📁data
├─ 📁docs
│  ├─ 📄calibration_protocol.md
│  ├─ 📄ODC网分设计.pptx
│  ├─ 📄TDR链路测试.pdf
│  ├─ 📄TDR链路测试项.md
│  └─ 📄__init__.py
├─ 📁logs
├─ 📁scripts
│  ├─ 📄ADC_DataAnalyze.py
│  ├─ 📄Calibration_File_Execution.py
│  ├─ 📄Doicon.py
│  ├─ 📄project.py
│  ├─ 📄S_paramCalibration.py
│  ├─ 📄test.py
│  ├─ 📄Testing.py
│  ├─ 📄VNA_S_CAL.md
│  └─ 📄VNA_S_CALIBRATION.m
├─ 📁src
│  ├─ 📁app
│  │  ├─ 📁core
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄ADCSample.py
│  │  │  ├─ 📄ClockController.py
│  │  │  ├─ 📄ConfigManager.py
│  │  │  ├─ 📄DataAnalyze.py
│  │  │  ├─ 📄DataPlotter.py
│  │  │  ├─ 📄DataProcessor.py
│  │  │  ├─ 📄EdgeDetector.py
│  │  │  ├─ 📄FileManager.py
│  │  │  ├─ 📄ResultProcessor.py
│  │  │  ├─ 📄TcpClient.py
│  │  │  ├─ 📄VNACalibration.py
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁dialogs
│  │  │  ├─ 📁CalibrationWizard
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  ├─ 📄wizard.ui
│  │  │  │  └─ 📄__init__.py
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁instruments
│  │  ├─ 📁models
│  │  ├─ 📁threads
│  │  ├─ 📁utils
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄ProcessManager.py
│  │  │  └─ 📄StyleManager.py
│  │  ├─ 📁widgets
│  │  │  ├─ 📁ADCSamplingPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁CalibrationPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁DataAnalysisPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁InstrumentPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁LogWidget
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁PlotWidget
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁ProgressPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁VNAControlPanel
│  │  │  │  ├─ 📁__pycache__
│  │  │  │  ├─ 📄Controller.py
│  │  │  │  ├─ 📄Model.py
│  │  │  │  ├─ 📄View.py
│  │  │  │  └─ 📄__init__.py
│  │  │  ├─ 📁__pycache__
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁windows
│  │  │  ├─ 📁ChildWinow
│  │  │  └─ 📁MainWindow
│  │  │     ├─ 📁__pycache__
│  │  │     ├─ 📄Controller.py
│  │  │     ├─ 📄Model.py
│  │  │     ├─ 📄View.py
│  │  │     └─ 📄__init__.py
│  │  ├─ 📁__pycache__
│  │  └─ 📄__init__.py
│  ├─ 📁config
│  ├─ 📁docs
│  ├─ 📁resources
│  │  ├─ 📁icon
│  │  │  └─ 📄icon_TDR_01.ico
│  │  ├─ 📁styles
│  │  │  ├─ 📄style_bule.css
│  │  │  └─ 📄style_bule.qss
│  │  ├─ 📁ui
│  │  │  └─ 📄__init__.py
│  │  └─ 📄__init__.py
│  ├─ 📄main.py
│  └─ 📄__init__.py
├─ 📁tests
│  ├─ 📁widget_tests
│  │  ├─ 📄test_calibration_panel.py
│  │  └─ 📄__init__.py
│  └─ 📄__init__.py
├─ 📄.gitignore
├─ 📄generation_report.txt
├─ 📄README.md
└─ 📄requirements.txt
```
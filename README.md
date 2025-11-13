
```
TDR_CAL_DEMO
├─ 📁.vscode
├─ 📁config
│  ├─ 📄app_settings.ini
│  ├─ 📄instrument_config.json
│  └─ 📄__init__.py
├─ 📁data
├─ 📁docs
│  ├─ 📁TDR产品设计框架V0.1
│  ├─ 📄ad4080.pdf
│  ├─ 📄ADA4899-1.pdf
│  ├─ 📄ADA4927-1_4927-2.pdf
│  ├─ 📄ADA4938-1_4938-2.pdf
│  ├─ 📄ada4945-1.pdf
│  ├─ 📄AVA-17303+.pdf
│  ├─ 📄calibration_protocol.md
│  ├─ 📄DHO4000编程手册-目录.pdf
│  ├─ 📄DHO4000编程手册.pdf
│  ├─ 📄lmk01010.pdf
│  ├─ 📄LT6236.pdf
│  ├─ 📄MAX40025A-MAX40026.pdf
│  ├─ 📄ODC网分设计.pptx
│  ├─ 📄TDR链路测试.pdf
│  ├─ 📄TDR链路测试项.md
│  └─ 📄__init__.py
├─ 📁logs
├─ 📁scripts
│  ├─ 📁temp
│  │  └─ 📁test_raw
│  ├─ 📄ADCRawSample.py
│  ├─ 📄ADC_DataAnalyze.py
│  ├─ 📄average.py
│  ├─ 📄Calibration_File_Execution.py
│  ├─ 📄CSVSignalAnalyzer.py
│  ├─ 📄CurveComparator.py
│  ├─ 📄Doicon.py
│  ├─ 📄FreqStitcher.py
│  ├─ 📄project.py
│  ├─ 📄S_paramCalibration.py
│  ├─ 📄test.py
│  ├─ 📄TimeDomainRegionCopier.py
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
│  │  │  ├─ 📄DataCacheManager.py
│  │  │  ├─ 📄DataPlotter.py
│  │  │  ├─ 📄DataProcessor.py
│  │  │  ├─ 📄DebugPlotter.py
│  │  │  ├─ 📄EdgeDetector.py
│  │  │  ├─ 📄FileManager.py
│  │  │  ├─ 📄PerformanceMonitor.py
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
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄ADCProcessWorker.py
│  │  │  ├─ 📄ADCSampleWorker.py
│  │  │  ├─ 📄DataSaverWorker.py
│  │  │  ├─ 📄ThreadManager.py
│  │  │  └─ 📄__init__.py
│  │  ├─ 📁utils
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄MathUtils.py
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
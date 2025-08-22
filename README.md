
```
TDR_CAL_DEMO
├─ 📁.vscode
├─ 📁config
│  ├─ 📄app_settings.ini
│  ├─ 📄instrument_config.json
│  └─ 📄__init__.py
├─ 📁CSV_Data0818_testonly
├─ 📁data
│  ├─ 📁calibration
│  │  ├─ 📁coefficients
│  │  └─ 📁s2p_files
│  ├─ 📁processed
│  │  ├─ 📁adc_analysis
│  │  ├─ 📁s_parameters
│  │  └─ 📁tdr
│  ├─ 📁raw
│  │  ├─ 📁adc_samples
│  │  └─ 📁calibration
│  │     ├─ 📄Sdd21.csv
│  │     ├─ 📄Sdd21_diff_frequency_domain.csv
│  │     ├─ 📄Sdd21_diff_time_domain.csv
│  │     ├─ 📄Sdd21_frequency_domain.csv
│  │     └─ 📄Sdd21_time_domain.csv
│  └─ 📁results
│     ├─ 📁exports
│     ├─ 📁plots
│     │  ├─ 📄Sdd21.csv
│     │  ├─ 📄Sdd21_diff_frequency_domain.csv
│     │  ├─ 📄Sdd21_diff_frequency_domain.png
│     │  ├─ 📄Sdd21_diff_time_domain.csv
│     │  ├─ 📄Sdd21_diff_time_domain.png
│     │  ├─ 📄Sdd21_frequency_domain.csv
│     │  ├─ 📄Sdd21_frequency_domain.png
│     │  ├─ 📄Sdd21_time_domain.csv
│     │  └─ 📄Sdd21_time_domain.png
│     ├─ 📁reports
│     └─ 📁test
│        ├─ 📄adc_data_0001.csv
│        ├─ 📄adc_data_0002.csv
│        ├─ 📄adc_data_0003.csv
│        ├─ 📄adc_data_0004.csv
│        ├─ 📄adc_data_0005.csv
│        ├─ 📄adc_data_0006.csv
│        ├─ 📄adc_data_0007.csv
│        ├─ 📄adc_data_0008.csv
│        ├─ 📄adc_data_0009.csv
│        └─ 📄adc_data_0010.csv
├─ 📁docs
│  ├─ 📄calibration_protocol.md
│  ├─ 📄ODC网分设计.pptx
│  ├─ 📄TDR链路测试.pdf
│  ├─ 📄TDR链路测试项.md
│  └─ 📄__init__.py
├─ 📁logs
├─ 📁scripts
│  ├─ 📄ADC_DataAnalyze.py
│  ├─ 📄project.py
│  ├─ 📄S_paramCalibration.py
│  ├─ 📄Testing.py
│  └─ 📄VNA_S_CALIBRATION.m
├─ 📁src
│  ├─ 📁app
│  │  ├─ 📁core
│  │  │  ├─ 📁__pycache__
│  │  │  ├─ 📄ADCSample.py
│  │  │  ├─ 📄DataAnalyze.py
│  │  │  ├─ 📄FileManager.py
│  │  │  ├─ 📄S_paramCalibration.py
│  │  │  ├─ 📄TcpClient.py
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
│  │  │  ├─ 📄ADC_Tester.py
│  │  │  ├─ 📄ProcessManager.py
│  │  │  └─ 📄StyleManager.py
│  │  ├─ 📁widgets
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
├─ 📄Cable_S23.csv
├─ 📄generation_report.txt
├─ 📄README.md
└─ 📄requirements.txt
```
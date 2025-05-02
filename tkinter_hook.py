from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# This will collect all tkinter related modules
hiddenimports = collect_submodules('tkinter')
hiddenimports.append('sv_ttk')

# Collect data files
datas = collect_data_files('tkinter')
datas += collect_data_files('sv_ttk')

# -*- mode: python -*-
block_cipher = None

a = Analysis(['csv_processor_gui.py'],
             pathex=['/Users/nerveband/wavedepth Dropbox/Ashraf Ali/Mac (2)/Desktop'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Apple Music Play History Converter',  # Change this to your desired app name
          debug=False,
          strip=False,
          upx=True,
          console=False,
          icon='aphc.icns')  # Change this to the filename of your .icns icon

app = BUNDLE(exe,
             name='Apple Music Play History Converter.app',  # Change this to your desired app name
             icon='aphc.icns',  # Change this to the filename of your .icns icon
             bundle_identifier=None)